from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from src.domain.entities.email_delivery import EmailDelivery


class EmailDeliveryRepositoryPort(ABC):
    """Puerto de persistencia para el registro auditable e idempotente de envíos de correo."""

    @abstractmethod
    def save(self, delivery: EmailDelivery) -> None:
        """Persiste o actualiza el registro de entrega."""
        pass

    @abstractmethod
    def find_by_id(self, delivery_id: uuid.UUID) -> EmailDelivery | None:
        """Recupera un envío por su identificador primario."""
        pass

    @abstractmethod
    def find_by_idempotency_key(self, idempotency_key: str) -> EmailDelivery | None:
        """Busca deterministamente por la clave de idempotencia única."""
        pass

    @abstractmethod
    def find_by_deca_id(self, deca_id: uuid.UUID) -> list[EmailDelivery]:
        """Obtiene el historial de envíos de un documento DeCA específico."""
        pass

    @abstractmethod
    def find_latest_by_expedition_id(self, expedition_id: uuid.UUID) -> EmailDelivery | None:
        """Obtiene el envío más reciente registrado para una expedición."""
        pass
