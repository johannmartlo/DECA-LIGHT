from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.value_objects import NIF


@dataclass
class CarrierAlias:
    """Variación comercial o denominación textual del transportista."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    carrier_id: uuid.UUID | None = None
    normalized_alias: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Carrier:
    """Ficha oficial del transportista efectivo homologado."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    business_name: str = ""
    tax_id: NIF | None = None
    email: str | None = None
    phone: str | None = None
    active: bool = True
    aliases: list[CarrierAlias] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
