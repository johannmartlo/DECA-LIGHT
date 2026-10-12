from __future__ import annotations

from abc import ABC, abstractmethod


class EmailServicePort(ABC):
    """Puerto para el servicio de entrega de correos con documentos DeCA adjuntos."""

    @abstractmethod
    def send_deca(
        self,
        recipient_email: str,
        subject: str,
        body_text: str,
        attachment_bytes: bytes,
        attachment_filename: str,
        idempotency_key: str,
    ) -> tuple[bool, str | None]:
        """Envía el correo con el DeCA adjunto.

        Retorna:
            (éxito: bool, message_id_o_error: str | None)
        """
        pass
