from __future__ import annotations

import hashlib
import logging
import threading
import uuid

from src.application.dtos.email_dto import (
    EmailAttachmentDTO,
    EmailMessageDTO,
    EmailSendResultDTO,
    SendDeCAEmailInputDTO,
    SendDeCAEmailResultDTO,
)
from src.application.ports.audit_service import AuditServicePort
from src.application.ports.deca_repository import DeCARepositoryPort
from src.application.ports.email_delivery_repository import (
    EmailDeliveryRepositoryPort,
)
from src.application.ports.email_sender import EmailSenderPort
from src.application.ports.expedition_repository import ExpeditionRepositoryPort
from src.application.ports.storage_service import StorageServicePort
from src.domain.entities.audit_event import AuditEvent
from src.domain.entities.email_delivery import EmailDelivery
from src.domain.enums import AuditAction, EmailDeliveryStatus, ExpeditionStatus
from src.domain.exceptions import EntityNotFoundException
from src.domain.services.clock import Clock
from src.domain.value_objects import CompanyContext, EmailAddress

logger = logging.getLogger("deca_light.use_cases.send_deca_email")


class SendDeCAEmailUseCase:
    """Caso de uso para el envío transaccional, idempotente y auditable de DeCA por correo.

    Garantiza:
    1. Verificación obligatoria de integridad binaria SHA-256 del PDF custodial.
    2. Idempotencia matemática para evitar dobles envíos accidentales.
    3. Soporte de reenvío explícito con auditoría dedicada (EMAIL_RESEND_REQUESTED).
    4. Transición de la expedición a ENVIADA únicamente si el envío tiene éxito.
    5. Inmutabilidad estricta del DeCA en caso de fallos de red o del proveedor de correo.
    6. Ofuscación de direcciones de correo en trazas y auditorías para privacidad.
    """

    def __init__(
        self,
        expedition_repo: ExpeditionRepositoryPort,
        deca_repo: DeCARepositoryPort,
        storage_service: StorageServicePort,
        email_sender: EmailSenderPort,
        email_delivery_repo: EmailDeliveryRepositoryPort,
        audit_service: AuditServicePort | None = None,
        sender_email: str = "pedidos@tomatesdeautor.com",
    ) -> None:
        self.expedition_repo = expedition_repo
        self.deca_repo = deca_repo
        self.storage_service = storage_service
        self.email_sender = email_sender
        self.email_delivery_repo = email_delivery_repo
        self.audit_service = audit_service
        self.sender_email = sender_email
        self._lock = threading.Lock()

    def execute(self, input_dto: SendDeCAEmailInputDTO) -> SendDeCAEmailResultDTO:
        """Ejecuta el flujo de envío de correo protegiendo concurrencia e invariantes."""
        if input_dto.company_id:
            CompanyContext.create(input_dto.company_id, actor=input_dto.actor)

        try:
            exp_uuid = (
                uuid.UUID(str(input_dto.expedition_id))
                if not isinstance(input_dto.expedition_id, uuid.UUID)
                else input_dto.expedition_id
            )
        except ValueError as exc:
            raise EntityNotFoundException(
                f"Identificador de expedición UUID inválido: '{input_dto.expedition_id}'"
            ) from exc

        with self._lock:
            # 1. Recuperar expedición
            expedition = self.expedition_repo.get_by_id(
                exp_uuid, company_id=input_dto.company_id
            )
            if not expedition:
                raise EntityNotFoundException(
                    f"Expedición con ID '{input_dto.expedition_id}' no encontrada."
                )

            # 2. Recuperar documento DeCA asociado
            deca = self.deca_repo.find_by_expedition_id(exp_uuid)
            if not deca or not deca.versions:
                raise EntityNotFoundException(
                    f"No existe DeCA emitido para la expedición '{input_dto.expedition_id}'."
                )

            version = deca.latest_version
            if not version:
                raise EntityNotFoundException("El DeCA no cuenta con versiones generadas.")

            # 3. Comprobar email del transportista
            raw_email = expedition.carrier_email
            if not raw_email or not str(raw_email).strip():
                logger.info(
                    "Expedición %s sin email de transportista. Estado EMAIL_PENDING.",
                    expedition.internal_id,
                )
                return SendDeCAEmailResultDTO(
                    deca_code=deca.deca_code,
                    expedition_id=str(expedition.id),
                    email_status=EmailDeliveryStatus.EMAIL_PENDING.value,
                    recipient="",
                    recipient_masked="",
                    idempotency_key="",
                    message_id=None,
                    sent_at=None,
                    is_idempotent=False,
                    message="Email del transportista no configurado. Pendiente de envío.",
                )

            try:
                email_vo = EmailAddress.create(raw_email)
            except ValueError as val_err:
                logger.warning(
                    "Email de transportista inválido '%s' en expedición %s",
                    EmailAddress.mask_str(str(raw_email)),
                    expedition.internal_id,
                )
                idempotency_key = hashlib.sha256(
                    f"INVALID:{deca.id}:{version.version_number}:{raw_email}".encode()
                ).hexdigest()

                subject_text = (
                    f"DECA – Expedición {expedition.internal_id} – [{expedition.destination}]"
                )
                delivery = EmailDelivery(
                    expedition_id=expedition.id,
                    deca_id=deca.id,
                    company_id=expedition.company_id or "TOMATES_DE_AUTOR",
                    deca_code=deca.deca_code,
                    deca_version=version.version_number,
                    recipient_email=str(raw_email),
                    subject=subject_text,
                    idempotency_key=idempotency_key,
                    is_resend=input_dto.force_resend,
                )
                delivery.mark_failed(f"Dirección de email inválida: {val_err}")
                self.email_delivery_repo.save(delivery)

                if self.audit_service:
                    self.audit_service.record(
                        AuditEvent(
                            action=AuditAction.EMAIL_SEND_FAILED,
                            user_identifier=input_dto.actor,
                            entity_name="EMAIL_DELIVERY",
                            entity_id=delivery.id,
                            company_id=expedition.company_id or None,
                            new_state={
                                "error": "INVALID_EMAIL_FORMAT",
                                "detail": str(val_err),
                                "recipient_masked": EmailAddress.mask_str(str(raw_email)),
                            },
                        )
                    )

                return SendDeCAEmailResultDTO(
                    deca_code=deca.deca_code,
                    expedition_id=str(expedition.id),
                    email_status=EmailDeliveryStatus.EMAIL_FAILED.value,
                    recipient=str(raw_email),
                    recipient_masked=EmailAddress.mask_str(str(raw_email)),
                    idempotency_key=idempotency_key,
                    message_id=None,
                    sent_at=None,
                    is_idempotent=False,
                    message=f"Email del transportista inválido: {val_err}",
                )

            normalized_email = email_vo.value
            masked_recipient = email_vo.masked

            # 4. Recuperación del PDF y comprobación estricta de integridad SHA-256
            try:
                pdf_bytes = self.storage_service.read(version.pdf_storage_path)
            except Exception as exc:
                logger.error(
                    "No se pudo recuperar el PDF de custodia para DeCA %s en %s: %s",
                    deca.deca_code,
                    version.pdf_storage_path,
                    exc,
                )
                idempotency_key = hashlib.sha256(
                    f"STORAGE_ERR:{deca.id}:{version.version_number}:{normalized_email}".encode()
                ).hexdigest()

                subject_text = (
                    f"DECA – Expedición {expedition.internal_id} – [{expedition.destination}]"
                )
                delivery = EmailDelivery(
                    expedition_id=expedition.id,
                    deca_id=deca.id,
                    company_id=expedition.company_id or "TOMATES_DE_AUTOR",
                    deca_code=deca.deca_code,
                    deca_version=version.version_number,
                    recipient_email=normalized_email,
                    subject=subject_text,
                    idempotency_key=idempotency_key,
                    is_resend=input_dto.force_resend,
                )
                delivery.mark_failed(f"PDF no disponible en almacenamiento: {exc}")
                self.email_delivery_repo.save(delivery)

                if self.audit_service:
                    self.audit_service.record(
                        AuditEvent(
                            action=AuditAction.EMAIL_SEND_FAILED,
                            user_identifier=input_dto.actor,
                            entity_name="EMAIL_DELIVERY",
                            entity_id=delivery.id,
                            company_id=expedition.company_id or None,
                            new_state={
                                "error": "PDF_NOT_FOUND",
                                "storage_path": version.pdf_storage_path,
                                "recipient_masked": masked_recipient,
                            },
                        )
                    )

                return SendDeCAEmailResultDTO(
                    deca_code=deca.deca_code,
                    expedition_id=str(expedition.id),
                    email_status=EmailDeliveryStatus.EMAIL_FAILED.value,
                    recipient=normalized_email,
                    recipient_masked=masked_recipient,
                    idempotency_key=idempotency_key,
                    message_id=None,
                    sent_at=None,
                    is_idempotent=False,
                    message=f"Archivo PDF no disponible en almacenamiento: {exc}",
                )

            computed_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
            if computed_sha256 != version.pdf_sha256:
                # VIOLACIÓN DE INTEGRIDAD BINARIA: abortar inmediatamente con cero transmisión
                logger.critical(
                    "PDF_INTEGRITY_ERROR para DeCA %s: esperado=%s, obtenido=%s",
                    deca.deca_code,
                    version.pdf_sha256,
                    computed_sha256,
                )
                idempotency_key = hashlib.sha256(
                    f"INTEGRITY_ERR:{deca.id}:{version.version_number}:{computed_sha256}".encode()
                ).hexdigest()

                subject_text = (
                    f"DECA – Expedición {expedition.internal_id} – [{expedition.destination}]"
                )
                delivery = EmailDelivery(
                    expedition_id=expedition.id,
                    deca_id=deca.id,
                    company_id=expedition.company_id or "TOMATES_DE_AUTOR",
                    deca_code=deca.deca_code,
                    deca_version=version.version_number,
                    recipient_email=normalized_email,
                    subject=subject_text,
                    idempotency_key=idempotency_key,
                    is_resend=input_dto.force_resend,
                )
                delivery.mark_failed(
                    f"PDF_INTEGRITY_ERROR: Hash en almacenamiento ({computed_sha256}) "
                    f"no coincide con versión inmutable ({version.pdf_sha256})"
                )
                self.email_delivery_repo.save(delivery)

                if self.audit_service:
                    self.audit_service.record(
                        AuditEvent(
                            action=AuditAction.EMAIL_SEND_FAILED,
                            user_identifier=input_dto.actor,
                            entity_name="EMAIL_DELIVERY",
                            entity_id=delivery.id,
                            new_state={
                                "error": "PDF_INTEGRITY_ERROR",
                                "expected_sha256": version.pdf_sha256,
                                "computed_sha256": computed_sha256,
                                "recipient_masked": masked_recipient,
                            },
                        )
                    )

                return SendDeCAEmailResultDTO(
                    deca_code=deca.deca_code,
                    expedition_id=str(expedition.id),
                    email_status=EmailDeliveryStatus.EMAIL_FAILED.value,
                    recipient=normalized_email,
                    recipient_masked=masked_recipient,
                    idempotency_key=idempotency_key,
                    message_id=None,
                    sent_at=None,
                    is_idempotent=False,
                    message="Error de integridad: el hash SHA-256 no coincide.",
                )

            # 5. Cálculo determinista de la clave de idempotencia
            v_hash = version.pdf_sha256
            if not input_dto.force_resend:
                raw_key = f"AUTO:{deca.id}:{version.version_number}:{normalized_email}:{v_hash}"
                idempotency_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
            else:
                t_str = Clock.now().isoformat()
                raw_key = (
                    f"MANUAL_RESEND:{deca.id}:{version.version_number}:"
                    f"{normalized_email}:{v_hash}:{t_str}"
                )
                idempotency_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

            # 6. Comprobación de idempotencia: evitar doble envío accidental
            if not input_dto.force_resend:
                existing_delivery = self.email_delivery_repo.find_by_idempotency_key(
                    idempotency_key
                )
                if existing_delivery and existing_delivery.status == EmailDeliveryStatus.EMAIL_SENT:
                    logger.info(
                        "Envío DeCA omitido por idempotencia: %s ya fue enviado a %s",
                        deca.deca_code,
                        masked_recipient,
                    )
                    return SendDeCAEmailResultDTO(
                        deca_code=deca.deca_code,
                        expedition_id=str(expedition.id),
                        email_status=EmailDeliveryStatus.EMAIL_SENT.value,
                        recipient=normalized_email,
                        recipient_masked=masked_recipient,
                        idempotency_key=idempotency_key,
                        message_id=existing_delivery.message_id,
                        sent_at=existing_delivery.sent_at.isoformat()
                        if existing_delivery.sent_at
                        else None,
                        is_idempotent=True,
                        message="Operación idempotente: el DeCA ya fue enviado previamente.",
                    )

            # 7. Crear registro de entrega en estado EMAIL_SENDING
            subject_text = (
                f"DECA – Expedición {expedition.internal_id} – [{expedition.destination}]"
            )
            delivery = EmailDelivery(
                expedition_id=expedition.id,
                deca_id=deca.id,
                company_id=expedition.company_id or "TOMATES_DE_AUTOR",
                deca_code=deca.deca_code,
                deca_version=version.version_number,
                recipient_email=normalized_email,
                subject=subject_text,
                idempotency_key=idempotency_key,
                is_resend=input_dto.force_resend,
                provider="graph",
            )
            delivery.mark_sending()
            self.email_delivery_repo.save(delivery)

            # 8. Auditoría de solicitud de envío
            if self.audit_service:
                req_action = (
                    AuditAction.EMAIL_RESEND_REQUESTED
                    if input_dto.force_resend
                    else AuditAction.EMAIL_SEND_REQUESTED
                )
                self.audit_service.record(
                    AuditEvent(
                        action=req_action,
                        user_identifier=input_dto.actor,
                        entity_name="EMAIL_DELIVERY",
                        entity_id=delivery.id,
                        company_id=expedition.company_id or None,
                        new_state={
                            "deca_code": deca.deca_code,
                            "version": version.version_number,
                            "company_id": delivery.company_id,
                            "recipient_masked": masked_recipient,
                            "idempotency_key": idempotency_key,
                            "is_resend": input_dto.force_resend,
                        },
                    )
                )

            # 9. Construcción del mensaje para el puerto de envío
            formatted_date = (
                expedition.transport_date.strftime("%d/%m/%Y")
                if hasattr(expedition.transport_date, "strftime")
                else str(expedition.transport_date)
            )
            tractor_desc = str(expedition.tractor_plate) if expedition.tractor_plate else "N/A"
            trailer_desc = str(expedition.trailer_plate) if expedition.trailer_plate else "N/A"

            body_text = (
                f"Estimado transportista,\n\n"
                f"Adjunto remitimos el Documento de Control Administrativo (DeCA) "
                f"correspondiente a la expedición {expedition.internal_id}.\n\n"
                f"Código DeCA: {deca.deca_code}\n"
                f"Destino: {expedition.destination}\n"
                f"Fecha de expedición: {formatted_date}\n"
                f"Vehículo tractor: {tractor_desc}\n"
                f"Semirremolque: {trailer_desc}\n\n"
                f"Por favor, conserve este documento durante el transporte "
                f"ante cualquier inspección.\n\n"
                f"Atentamente,\n"
                f"{expedition.shipper_name or 'Tomates de Autor S.L.'}\n"
            )

            attachment = EmailAttachmentDTO(
                filename=f"{deca.deca_code}.pdf",
                content_bytes=pdf_bytes,
                content_type="application/pdf",
                sha256=version.pdf_sha256,
            )

            message = EmailMessageDTO(
                sender=self.sender_email,
                recipient=normalized_email,
                subject=delivery.subject,
                body_text=body_text,
                attachments=[attachment],
                expedition_reference=expedition.internal_id,
                deca_reference=deca.deca_code,
                idempotency_key=idempotency_key,
                is_resend=input_dto.force_resend,
            )

            # 10. Transmisión transaccional a través del puerto
            result: EmailSendResultDTO = self.email_sender.send(message)

            # 11. Procesamiento del resultado y aplicación de invariantes
            if result.success:
                delivery.mark_sent(message_id=result.message_id)
                self.email_delivery_repo.save(delivery)

                # Transición a ENVIADA únicamente si el envío tiene éxito
                if expedition.status != ExpeditionStatus.ENVIADA:
                    expedition.transition_to(ExpeditionStatus.ENVIADA)
                    self.expedition_repo.save(expedition, company_id=input_dto.company_id)

                if self.audit_service:
                    self.audit_service.record(
                        AuditEvent(
                            action=AuditAction.EMAIL_SENT,
                            user_identifier=input_dto.actor,
                            entity_name="EMAIL_DELIVERY",
                            entity_id=delivery.id,
                            company_id=expedition.company_id or None,
                            new_state={
                                "deca_code": deca.deca_code,
                                "version": version.version_number,
                                "company_id": delivery.company_id,
                                "recipient_masked": masked_recipient,
                                "message_id": result.message_id,
                                "idempotency_key": idempotency_key,
                            },
                        )
                    )

                return SendDeCAEmailResultDTO(
                    deca_code=deca.deca_code,
                    expedition_id=str(expedition.id),
                    email_status=EmailDeliveryStatus.EMAIL_SENT.value,
                    recipient=normalized_email,
                    recipient_masked=masked_recipient,
                    idempotency_key=idempotency_key,
                    message_id=result.message_id,
                    sent_at=delivery.sent_at.isoformat() if delivery.sent_at else None,
                    is_idempotent=False,
                    message="DeCA enviado correctamente por correo electrónico.",
                )
            else:
                if result.is_transient:
                    delivery.mark_retry(result.error_message or "Error transitorio")
                else:
                    delivery.mark_failed(result.error_message or "Fallo permanente")

                self.email_delivery_repo.save(delivery)

                # INVARIANTE CRÍTICO: La expedición NO pasa a ENVIADA y el DeCA NO se invalida
                if self.audit_service:
                    self.audit_service.record(
                        AuditEvent(
                            action=AuditAction.EMAIL_SEND_FAILED,
                            user_identifier=input_dto.actor,
                            entity_name="EMAIL_DELIVERY",
                            entity_id=delivery.id,
                            company_id=expedition.company_id or None,
                            new_state={
                                "deca_code": deca.deca_code,
                                "company_id": delivery.company_id,
                                "recipient_masked": masked_recipient,
                                "error": result.error_message,
                                "is_transient": result.is_transient,
                                "status_code": result.status_code,
                            },
                        )
                    )

                return SendDeCAEmailResultDTO(
                    deca_code=deca.deca_code,
                    expedition_id=str(expedition.id),
                    email_status=delivery.status.value,
                    recipient=normalized_email,
                    recipient_masked=masked_recipient,
                    idempotency_key=idempotency_key,
                    message_id=None,
                    sent_at=None,
                    is_idempotent=False,
                    message=f"Fallo en el envío: {result.error_message}",
                )
