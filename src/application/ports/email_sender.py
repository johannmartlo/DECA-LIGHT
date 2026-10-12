from __future__ import annotations

from abc import ABC, abstractmethod

from src.application.dtos.email_dto import EmailMessageDTO, EmailSendResultDTO


class EmailSenderPort(ABC):
    """Puerto de aplicación para el envío transaccional de correos electrónicos.

    Desacopla por completo la lógica de negocio y los casos de uso del proveedor
    tecnológico (Microsoft Graph API, SMTP, sendgrid, mocks locales).
    """

    @abstractmethod
    def send(self, message: EmailMessageDTO) -> EmailSendResultDTO:
        """Transmite el mensaje y sus adjuntos a través del canal configurado."""
        pass
