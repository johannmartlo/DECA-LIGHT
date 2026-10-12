from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.enums import EmailDeliveryStatus


@dataclass(frozen=True)
class EmailAttachmentDTO:
    """Representa un adjunto binario para su transmisión por correo electrónico."""

    filename: str
    content_bytes: bytes
    content_type: str = "application/pdf"
    sha256: str = ""


@dataclass(frozen=True)
class EmailMessageDTO:
    """DTO desacoplado que define el mensaje a transmitir a través de EmailSenderPort."""

    sender: str
    recipient: str
    subject: str
    body_text: str
    attachments: list[EmailAttachmentDTO] = field(default_factory=list)
    expedition_reference: str = ""
    deca_reference: str = ""
    idempotency_key: str = ""
    is_resend: bool = False


@dataclass(frozen=True)
class EmailSendResultDTO:
    """Resultado devuelto por el adaptador de infraestructura tras la llamada al proveedor."""

    success: bool
    status: EmailDeliveryStatus
    message_id: str | None = None
    error_message: str | None = None
    is_transient: bool = False
    status_code: int | None = None


@dataclass(frozen=True)
class SendDeCAEmailInputDTO:
    """Parámetros de entrada para el caso de uso de envío transaccional de DeCA."""

    expedition_id: str
    actor: str = "OPERATOR"
    force_resend: bool = False


@dataclass(frozen=True)
class SendDeCAEmailResultDTO:
    """Resultado formal del caso de uso de envío de DeCA."""

    deca_code: str
    expedition_id: str
    email_status: str
    recipient: str
    recipient_masked: str
    idempotency_key: str
    message_id: str | None = None
    sent_at: str | None = None
    is_idempotent: bool = False
    message: str = ""
