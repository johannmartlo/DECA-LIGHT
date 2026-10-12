from __future__ import annotations

import copy
import threading
import uuid

from src.application.ports.email_delivery_repository import (
    EmailDeliveryRepositoryPort,
)
from src.domain.entities.email_delivery import EmailDelivery


class InMemoryEmailDeliveryRepository(EmailDeliveryRepositoryPort):
    """Adaptador de repositorio en memoria y thread-safe para envíos de correo."""

    def __init__(self) -> None:
        self._deliveries: dict[uuid.UUID, EmailDelivery] = {}
        self._by_idempotency: dict[str, uuid.UUID] = {}
        self._lock = threading.Lock()

    def save(self, delivery: EmailDelivery) -> None:
        """Persiste o actualiza el registro de entrega asegurando integridad."""
        with self._lock:
            # Guardamos copia defensiva para evitar mutaciones externas involuntarias
            self._deliveries[delivery.id] = copy.deepcopy(delivery)
            if delivery.idempotency_key:
                self._by_idempotency[delivery.idempotency_key] = delivery.id

    def find_by_id(self, delivery_id: uuid.UUID) -> EmailDelivery | None:
        with self._lock:
            item = self._deliveries.get(delivery_id)
            return copy.deepcopy(item) if item else None

    def find_by_idempotency_key(self, idempotency_key: str) -> EmailDelivery | None:
        with self._lock:
            delivery_id = self._by_idempotency.get(idempotency_key)
            if not delivery_id:
                return None
            item = self._deliveries.get(delivery_id)
            return copy.deepcopy(item) if item else None

    def find_by_deca_id(self, deca_id: uuid.UUID) -> list[EmailDelivery]:
        with self._lock:
            results = [copy.deepcopy(d) for d in self._deliveries.values() if d.deca_id == deca_id]
            results.sort(key=lambda d: d.created_at)
            return results

    def find_latest_by_expedition_id(self, expedition_id: uuid.UUID) -> EmailDelivery | None:
        with self._lock:
            matching = [d for d in self._deliveries.values() if d.expedition_id == expedition_id]
            if not matching:
                return None
            latest = max(matching, key=lambda d: d.created_at)
            return copy.deepcopy(latest)

    def clear(self) -> None:
        """Limpia todos los registros (útil para pruebas)."""
        with self._lock:
            self._deliveries.clear()
            self._by_idempotency.clear()
