from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.audit_event import AuditEvent


class AuditServicePort(ABC):
    """Puerto para el registro inmutable de eventos de auditoría (append-only)."""

    @abstractmethod
    def record(self, event: AuditEvent) -> None:
        """Registra un evento de auditoría de forma inmutable."""
        pass
