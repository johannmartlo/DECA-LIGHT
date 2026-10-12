from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.enums import AuditAction


@dataclass
class AuditEvent:
    """Evento inmutable de auditoría para trazabilidad de negocio y legal."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    user_id: uuid.UUID | None = None
    user_identifier: str = "SYSTEM"
    action: AuditAction = AuditAction.DOCUMENT_IMPORTED
    entity_name: str = ""
    entity_id: uuid.UUID | None = None
    ip_address: str | None = None
    old_state: dict | None = None
    new_state: dict | None = None
    company_id: str | None = None
