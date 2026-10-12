from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from src.domain.enums import EmailDeliveryStatus
from src.domain.services.clock import Clock
from src.domain.value_objects import EmailAddress


@dataclass
class EmailDelivery:
    """Entidad de dominio que modela el ciclo de vida y auditoría del envío de un DeCA."""

    expedition_id: uuid.UUID
    deca_id: uuid.UUID
    deca_code: str
    deca_version: int
    recipient_email: str
    subject: str
    idempotency_key: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    company_id: str = "TOMATES_DE_AUTOR"
    status: EmailDeliveryStatus = EmailDeliveryStatus.EMAIL_PENDING
    attempts: int = 0
    provider: str = "graph"
    message_id: str | None = None
    last_error: str | None = None
    is_resend: bool = False
    created_at: datetime = field(default_factory=Clock.now)
    sent_at: datetime | None = None

    def belongs_to(self, company_id: str | None) -> bool:
        """Indica si el registro de envío pertenece a la empresa indicada."""
        return bool(company_id) and self.company_id == company_id

    def mark_sending(self) -> None:
        """Marca el inicio del intento de transmisión transaccional."""
        self.status = EmailDeliveryStatus.EMAIL_SENDING
        self.attempts += 1

    def mark_sent(self, message_id: str | None = None) -> None:
        """Registra la entrega confirmada por el proveedor de correo."""
        self.status = EmailDeliveryStatus.EMAIL_SENT
        self.sent_at = Clock.now()
        self.message_id = message_id
        self.last_error = None

    def mark_failed(self, error: str) -> None:
        """Registra un fallo permanente en la entrega."""
        self.status = EmailDeliveryStatus.EMAIL_FAILED
        self.last_error = error

    def mark_retry(self, error: str) -> None:
        """Registra un fallo transitorio pendiente de reintento."""
        self.status = EmailDeliveryStatus.EMAIL_RETRY_PENDING
        self.last_error = error

    @property
    def recipient_masked(self) -> str:
        """Retorna la dirección del destinatario ofuscada para preservar la privacidad."""
        return EmailAddress.mask_str(self.recipient_email)
