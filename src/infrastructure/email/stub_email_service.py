from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.ports.email_service import EmailServicePort

logger = logging.getLogger("deca_light.email")


@dataclass
class SentEmailRecord:
    id: uuid.UUID
    recipient: str
    subject: str
    filename: str
    idempotency_key: str
    timestamp: datetime


class StubEmailService(EmailServicePort):
    """Implementación de prueba/desarrollo del servicio de correo."""

    def __init__(self) -> None:
        self.sent_emails: list[SentEmailRecord] = []
        self._sent_keys: set[str] = set()

    def send_deca(
        self,
        recipient_email: str,
        subject: str,
        body_text: str,
        attachment_bytes: bytes,
        attachment_filename: str,
        idempotency_key: str,
    ) -> tuple[bool, str | None]:
        # Idempotencia: si ya fue enviado con esta clave, confirmar sin duplicar
        if idempotency_key in self._sent_keys:
            logger.info("Email omitido por clave de idempotencia ya existente: %s", idempotency_key)
            return True, f"idempotent-replay-{idempotency_key}"

        record_id = uuid.uuid4()
        message_id = f"<stub-{record_id}@deca.local>"

        self.sent_emails.append(
            SentEmailRecord(
                id=record_id,
                recipient=recipient_email,
                subject=subject,
                filename=attachment_filename,
                idempotency_key=idempotency_key,
                timestamp=datetime.now(UTC),
            )
        )
        self._sent_keys.add(idempotency_key)

        logger.info(
            "Simulación de envío DeCA exitoso a %s (Adjunto: %s, %d bytes)",
            recipient_email,
            attachment_filename,
            len(attachment_bytes),
        )
        return True, message_id
