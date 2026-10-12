from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass

from src.application.dtos.email_dto import EmailMessageDTO, EmailSendResultDTO
from src.application.ports.email_sender import EmailSenderPort
from src.domain.enums import EmailDeliveryStatus
from src.domain.value_objects import EmailAddress

logger = logging.getLogger("deca_light.email.fake")


@dataclass
class FakeFailureConfig:
    """Configuración de simulación de fallo para pruebas."""

    status_code: int = 500
    error_message: str = "Simulated Microsoft Graph API error"
    is_transient: bool | None = None
    remaining_failures: int = 1
    simulate_timeout: bool = False


class FakeMicrosoftGraphEmailSender(EmailSenderPort):
    """Adaptador de pruebas offline para Microsoft Graph API.

    Permite simular respuestas 202 Accepted, errores transitorios (429, 500, timeouts)
    y errores permanentes (400, 401, 403, 404) de forma determinista y configurable.
    """

    def __init__(self, sender_email: str = "pedidos@tomatesdeautor.com") -> None:
        self.sender_email = sender_email
        self.sent_messages: list[EmailMessageDTO] = []
        self.send_count: int = 0
        self._lock = threading.Lock()
        self._failure_config: FakeFailureConfig | None = None

    def configure_success(self) -> None:
        """Configura el emisor para que las siguientes llamadas tengan éxito."""
        with self._lock:
            self._failure_config = None

    def configure_failure(
        self,
        status_code: int = 500,
        error_message: str = "Simulated Microsoft Graph API error",
        is_transient: bool | None = None,
        fail_times: int = 1,
    ) -> None:
        """Configura fallos simulados para las próximas N llamadas."""
        transient = is_transient
        if transient is None:
            # Determinación automática según código de estado HTTP
            transient = status_code in (429, 500, 502, 503, 504)

        with self._lock:
            self._failure_config = FakeFailureConfig(
                status_code=status_code,
                error_message=error_message,
                is_transient=transient,
                remaining_failures=fail_times,
                simulate_timeout=False,
            )

    def configure_timeout(self, fail_times: int = 1) -> None:
        """Configura un timeout transitorio para las próximas N llamadas."""
        with self._lock:
            self._failure_config = FakeFailureConfig(
                status_code=408,
                error_message="Simulated connection timeout to Microsoft Graph API",
                is_transient=True,
                remaining_failures=fail_times,
                simulate_timeout=True,
            )

    def reset(self) -> None:
        """Reinicia el historial y las configuraciones de simulación."""
        with self._lock:
            self.sent_messages.clear()
            self.send_count = 0
            self._failure_config = None

    def send(self, message: EmailMessageDTO) -> EmailSendResultDTO:
        """Ejecuta el envío simulado conforme a la configuración activa."""
        with self._lock:
            self.send_count += 1
            recipient_masked = EmailAddress.mask_str(message.recipient)

            # Comprobar si hay fallo programado activo
            if self._failure_config and self._failure_config.remaining_failures > 0:
                cfg = self._failure_config
                cfg.remaining_failures -= 1
                if cfg.remaining_failures <= 0:
                    self._failure_config = None

                logger.warning(
                    "Simulación de error Graph API (%d) enviando a %s: %s (transient=%s)",
                    cfg.status_code,
                    recipient_masked,
                    cfg.error_message,
                    cfg.is_transient,
                )

                status = (
                    EmailDeliveryStatus.EMAIL_RETRY_PENDING
                    if cfg.is_transient
                    else EmailDeliveryStatus.EMAIL_FAILED
                )

                return EmailSendResultDTO(
                    success=False,
                    status=status,
                    message_id=None,
                    error_message=cfg.error_message,
                    is_transient=bool(cfg.is_transient),
                    status_code=cfg.status_code,
                )

            # Envío exitoso
            self.sent_messages.append(message)
            generated_id = f"<fake-graph-{uuid.uuid4()}@tomatesdeautor.com>"

            logger.info(
                "Envío simulado exitoso a %s (ID: %s, Adjuntos: %d)",
                recipient_masked,
                generated_id,
                len(message.attachments),
            )

            return EmailSendResultDTO(
                success=True,
                status=EmailDeliveryStatus.EMAIL_SENT,
                message_id=generated_id,
                error_message=None,
                is_transient=False,
                status_code=202,
            )
