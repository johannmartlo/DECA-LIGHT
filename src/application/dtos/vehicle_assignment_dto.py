from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from src.domain.enums import ExpeditionStatus, VehicleType
from src.domain.services.deca_validator import ValidationResult


@dataclass(frozen=True)
class AssignVehicleInputDTO:
    """Datos de entrada para asignar o actualizar el vehículo y transportista de una expedición."""

    expedition_id: uuid.UUID | str
    vehicle_type: str | VehicleType
    tractor_registration: str
    trailer_registration: str | None = None
    carrier_name: str | None = None
    carrier_tax_id: str | None = None
    carrier_email: str | None = None
    actor: str = "OPERATOR"
    company_id: str | None = None


@dataclass(frozen=True)
class AssignVehicleResultDTO:
    """Resultado estructurado de la asignación de vehículo y validación DeCA."""

    expedition_id: str
    internal_id: str
    status: ExpeditionStatus
    vehicle_type: VehicleType
    tractor_plate: str
    trailer_plate: str | None
    carrier_name: str
    carrier_tax_id: str | None
    carrier_email: str | None
    validation: ValidationResult
    is_ready_for_deca: bool
    message: str
    audit_events_recorded: list[str] = field(default_factory=list)
