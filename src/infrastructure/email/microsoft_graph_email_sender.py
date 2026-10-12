from __future__ import annotations

import base64
import logging
import time
import uuid
from typing import Any

import httpx

from src.application.dtos.email_dto import EmailMessageDTO, EmailSendResultDTO
from src.application.ports.email_sender import EmailSenderPort
from src.domain.enums import EmailDeliveryStatus
from src.domain.value_objects import EmailAddress

logger = logging.getLogger("deca_light.email.graph")


class MicrosoftGraphEmailSender(EmailSenderPort):
    """Adaptador de infraestructura para el envío de correos mediante Microsoft Graph API v1.0.

    Utiliza el flujo OAuth 2.0 Client Credentials de Azure Entra ID con el permiso Mail.Send
    para transmitir mensajes en nombre del buzón oficial autorizado.
    """

    TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
    PERMANENT_STATUS_CODES = {400, 401, 403, 404}

    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        sender_email: str = "pedidos@tomatesdeautor.com",
        http_client: httpx.Client | None = None,
        max_retries: int = 3,
        base_retry_delay: float = 0.5,
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self._client_secret = client_secret
        self.sender_email = sender_email
        self._http_client = http_client
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay

        # Caché interna del token de aplicación para minimizar llamadas a login
        self._cached_access_token: str | None = None
        self._token_expires_at: float = 0.0

    def _get_client(self) -> httpx.Client:
        """Obtiene o crea un cliente HTTP tipado."""
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(timeout=15.0)

    def _acquire_access_token(
        self, client: httpx.Client
    ) -> tuple[str | None, str | None, int | None]:
        """Adquiere o reutiliza el token OAuth 2.0 de Microsoft Graph API.

        Retorna:
            (access_token, error_message, status_code)
        """
        now = time.time()
        if self._cached_access_token and now < self._token_expires_at - 60:
            return self._cached_access_token, None, None

        if not self.tenant_id or not self.client_id or not self._client_secret:
            return (
                None,
                "Credenciales de Graph incompletas (requiere tenant_id, client_id, secret).",
                401,
            )

        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self._client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }

        try:
            resp = client.post(token_url, data=payload)
            if resp.status_code != 200:
                logger.error(
                    "Error al obtener token de Azure Entra ID: HTTP %d",
                    resp.status_code,
                )
                return (
                    None,
                    f"Fallo de autenticación Azure Entra ID: {resp.status_code}",
                    resp.status_code,
                )

            data = resp.json()
            access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)

            if not access_token:
                return None, "Respuesta de token inválida desde Azure Entra ID.", 500

            self._cached_access_token = access_token
            self._token_expires_at = now + float(expires_in)
            return access_token, None, 200

        except httpx.TimeoutException:
            return None, "Timeout al conectar con el servidor de autenticación de Microsoft.", 408
        except httpx.RequestError as exc:
            return None, f"Error de red al autenticar con Microsoft: {type(exc).__name__}", 503

    def _build_graph_payload(self, message: EmailMessageDTO) -> dict[str, Any]:
        """Construye el payload canónico para sendMail de Microsoft Graph API v1.0."""
        attachments_payload = []
        for att in message.attachments:
            encoded_bytes = base64.b64encode(att.content_bytes).decode("ascii")
            attachments_payload.append(
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": att.filename,
                    "contentType": att.content_type or "application/pdf",
                    "contentBytes": encoded_bytes,
                }
            )

        return {
            "message": {
                "subject": message.subject,
                "body": {
                    "contentType": "Text",
                    "content": message.body_text,
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": message.recipient,
                        }
                    }
                ],
                "attachments": attachments_payload,
            },
            "saveToSentItems": "true",
        }

    def send(self, message: EmailMessageDTO) -> EmailSendResultDTO:
        """Transmite el mensaje transaccional con política de reintentos exponenciales."""
        client = self._get_client()
        recipient_masked = EmailAddress.mask_str(message.recipient)
        send_url = f"https://graph.microsoft.com/v1.0/users/{self.sender_email}/sendMail"

        payload = self._build_graph_payload(message)

        last_error_message = ""
        last_status_code: int | None = None
        is_transient = False

        for attempt in range(1, self.max_retries + 1):
            token, token_err, token_status = self._acquire_access_token(client)
            if not token:
                is_transient_auth = (
                    token_status in self.TRANSIENT_STATUS_CODES or token_status == 408
                )
                logger.error(
                    "Intento %d/%d: No se pudo obtener token de Graph API para enviar a %s: %s",
                    attempt,
                    self.max_retries,
                    recipient_masked,
                    token_err,
                )
                if not is_transient_auth or attempt == self.max_retries:
                    return EmailSendResultDTO(
                        success=False,
                        status=(
                            EmailDeliveryStatus.EMAIL_RETRY_PENDING
                            if is_transient_auth
                            else EmailDeliveryStatus.EMAIL_FAILED
                        ),
                        message_id=None,
                        error_message=token_err,
                        is_transient=is_transient_auth,
                        status_code=token_status,
                    )
                time.sleep(self.base_retry_delay * attempt)
                continue

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            try:
                logger.info(
                    "Enviando correo vía Microsoft Graph a %s (Intento %d/%d)",
                    recipient_masked,
                    attempt,
                    self.max_retries,
                )
                resp = client.post(send_url, json=payload, headers=headers)

                # Microsoft Graph retorna 202 Accepted en caso de envío aceptado
                if resp.status_code in (200, 202):
                    # El client-request-id o un identificador generado sirve de message_id
                    client_req_id = resp.headers.get("client-request-id")
                    generated_id = (
                        client_req_id
                        or f"<graph-{uuid.uuid4()}@{self.sender_email.split('@')[-1]}>"
                    )
                    logger.info(
                        "Correo enviado con éxito a %s vía Microsoft Graph (ID: %s)",
                        recipient_masked,
                        generated_id,
                    )
                    return EmailSendResultDTO(
                        success=True,
                        status=EmailDeliveryStatus.EMAIL_SENT,
                        message_id=generated_id,
                        error_message=None,
                        is_transient=False,
                        status_code=resp.status_code,
                    )

                last_status_code = resp.status_code
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("error", {}).get("message", resp.text)
                except Exception:
                    err_detail = resp.text

                last_error_message = f"HTTP {resp.status_code}: {err_detail}"

                if resp.status_code in self.TRANSIENT_STATUS_CODES:
                    is_transient = True
                    retry_after_hdr = resp.headers.get("Retry-After")
                    delay = (
                        float(retry_after_hdr)
                        if retry_after_hdr and retry_after_hdr.isdigit()
                        else self.base_retry_delay * (2**attempt)
                    )
                    logger.warning(
                        "Fallo transitorio Graph (%d) enviando a %s. Reintentando en %.1fs... (%s)",
                        resp.status_code,
                        recipient_masked,
                        delay,
                        err_detail,
                    )
                    if attempt < self.max_retries:
                        time.sleep(delay)
                        continue
                else:
                    # Error permanente de cliente (400, 401, 403, 404, etc.)
                    is_transient = False
                    logger.error(
                        "Fallo permanente Graph API (%d) enviando a %s: %s",
                        resp.status_code,
                        recipient_masked,
                        err_detail,
                    )
                    return EmailSendResultDTO(
                        success=False,
                        status=EmailDeliveryStatus.EMAIL_FAILED,
                        message_id=None,
                        error_message=last_error_message,
                        is_transient=False,
                        status_code=resp.status_code,
                    )

            except httpx.TimeoutException:
                is_transient = True
                last_status_code = 408
                last_error_message = "Timeout de conexión con Microsoft Graph API."
                logger.warning(
                    "Timeout enviando a %s en intento %d/%d.",
                    recipient_masked,
                    attempt,
                    self.max_retries,
                )
                if attempt < self.max_retries:
                    time.sleep(self.base_retry_delay * attempt)
                    continue

            except httpx.RequestError as exc:
                is_transient = True
                last_status_code = 503
                last_error_message = f"Error de red con Microsoft Graph: {type(exc).__name__}"
                logger.warning(
                    "Error de red enviando a %s en intento %d/%d: %s",
                    recipient_masked,
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.base_retry_delay * attempt)
                    continue

        # Agotados los reintentos
        return EmailSendResultDTO(
            success=False,
            status=EmailDeliveryStatus.EMAIL_RETRY_PENDING
            if is_transient
            else EmailDeliveryStatus.EMAIL_FAILED,
            message_id=None,
            error_message=last_error_message
            or "Agotados todos los reintentos hacia Microsoft Graph API.",
            is_transient=is_transient,
            status_code=last_status_code,
        )
