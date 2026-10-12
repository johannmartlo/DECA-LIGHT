from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.enums import VehicleType
from src.domain.exceptions import InvalidVehicleConfigurationException
from src.domain.value_objects import Matricula


@dataclass
class Vehicle:
    """Entidad de vehículo con tipificación estricta: Rígido vs. Conjunto Articulado."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    carrier_id: uuid.UUID | None = None
    vehicle_type: VehicleType = VehicleType.ARTICULADO
    tractor_plate: Matricula | None = None
    trailer_plate: Matricula | None = None
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def validate_configuration(self) -> None:
        """Verifica que las matrículas correspondan exactamente al tipo de transporte."""
        if self.vehicle_type == VehicleType.RIGIDO:
            if not self.tractor_plate:
                raise InvalidVehicleConfigurationException(
                    "Un vehículo rígido exige obligatoriamente la matrícula del vehículo."
                )
            if self.trailer_plate is not None:
                raise InvalidVehicleConfigurationException(
                    "Un vehículo rígido no puede tener asignada una matrícula de remolque."
                )
        elif self.vehicle_type == VehicleType.ARTICULADO:
            if not self.tractor_plate:
                raise InvalidVehicleConfigurationException(
                    "Un conjunto articulado exige matrícula de la cabeza tractora."
                )
            if not self.trailer_plate:
                raise InvalidVehicleConfigurationException(
                    "Un conjunto articulado exige matrícula del semirremolque/remolque."
                )
