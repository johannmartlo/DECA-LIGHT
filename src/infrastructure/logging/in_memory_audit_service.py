from __future__ import annotations

import threading
import uuid

from src.application.ports.audit_service import AuditServicePort
from src.domain.entities.audit_event import AuditEvent


class InMemoryAuditService(AuditServicePort):
    """Adaptador en memoria y thread-safe para el registro inmutable de eventos de auditoría."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.Lock()

    def record(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)

    def get_events(self, entity_id: uuid.UUID | None = None) -> list[AuditEvent]:
        with self._lock:
            if entity_id is None:
                return list(self._events)
            return [e for e in self._events if e.entity_id == entity_id]

    @property
    def events(self) -> list[AuditEvent]:
        """Propiedad de conveniencia para consultar todos los eventos registrados."""
        return self.get_events()

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
