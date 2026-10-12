from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from src.domain.enums import ExpeditionStatus, VehicleType
from src.domain.exceptions import (
    InvalidStateTransitionException,
    InvalidVehicleConfigurationException,
)
from src.domain.value_objects import NIF, Matricula, Weight


@dataclass
class Expedition:
    """Entidad central que modela el servicio de transporte derivado de la carta de porte o CMR."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    internal_id: str = ""  # Identificador visible para operador: TD-YYYY-NNNNN
    document_id: uuid.UUID | None = None
    reference: str = ""  # Referencia externa (albarán o identificador fuente)
    fiscal_year: str = "2026"
    transport_date: date = field(default_factory=date.today)

    # Cargador contractual y empresa emisora (Multiempresa / Tenant context)
    company_id: str = ""
    issuer_detection_confidence: float | None = None
    issuer_detection_source: str | None = None
    shipper_name: str = ""
    shipper_tax_id: NIF | None = None
    shipper_address: str = ""

    # Transportista efectivo
    carrier_id: uuid.UUID | None = None
    carrier_name_raw: str = ""
    carrier_tax_id: NIF | None = None
    carrier_email: str | None = None

    # Vehículo asignado
    vehicle_type: VehicleType | None = None
    tractor_plate: Matricula | None = None
    trailer_plate: Matricula | None = None

    # Datos de la carga
    origin: str = ""
    destination: str = ""
    goods: str = ""
    weight: Weight | None = None
    observations: str | None = None

    # Estado del flujo
    status: ExpeditionStatus = ExpeditionStatus.IMPORTADA
    extraction_metadata: dict = field(default_factory=dict)

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.company_id and self.shipper_name:
            s_upper = self.shipper_name.upper()
            if "CULTIVOS ARABA" in s_upper:
                self.company_id = "CULTIVOS_ARABA"
            elif "TOMATES DE AUTOR" in s_upper:
                self.company_id = "TOMATES_DE_AUTOR"

    def belongs_to(self, company_id: str | None) -> bool:
        """Indica si la expedición pertenece a la empresa indicada (aislamiento multiempresa)."""
        return bool(company_id) and self.company_id == company_id

    def assign_company(
        self, company_id: str, confidence: float | None = None, source: str | None = None
    ) -> None:
        """Asigna la empresa emisora una única vez; no se permite reasignar a otra empresa."""
        if not company_id:
            raise InvalidStateTransitionException("company_id no puede ser vacío.")
        if self.company_id and self.company_id != company_id:
            raise InvalidStateTransitionException(
                "La empresa emisora de una expedición no puede cambiarse una vez asignada."
            )
        self.company_id = company_id
        self.issuer_detection_confidence = confidence
        self.issuer_detection_source = source
        self.updated_at = datetime.now(UTC)

    def transition_to(self, new_status: ExpeditionStatus) -> None:
        """Aplica una transición de estado validada en el ciclo de vida de la expedición."""
        if self.status == new_status:
            return

        if (
            new_status
            in (
                ExpeditionStatus.LISTA_PARA_DECA,
                ExpeditionStatus.DECA_GENERADO,
                ExpeditionStatus.ENVIADA,
            )
            and not self.company_id
        ):
            raise InvalidStateTransitionException(
                f"No se puede transicionar a {new_status.value} sin una empresa emisora asignada."
            )

        if (
            self.status == ExpeditionStatus.PENDIENTE_REVISION
            and new_status == ExpeditionStatus.LISTA_PARA_DECA
        ):
            raise InvalidStateTransitionException(
                "Una expedición en PENDIENTE_REVISION no puede saltar directamente a "
                "LISTA_PARA_DECA sin resolver la revisión previa."
            )

        if (
            self.status in (ExpeditionStatus.CANCELADA, ExpeditionStatus.ENVIADA)
            and new_status != self.status
        ):
            raise InvalidStateTransitionException(
                f"No se permite cambiar el estado de una expedición terminal ({self.status})."
            )

        self.status = new_status
        self.updated_at = datetime.now(UTC)

    def assign_vehicle(
        self,
        vehicle_type: VehicleType | str,
        tractor_plate: str | Matricula,
        trailer_plate: str | Matricula | None = None,
    ) -> None:
        """Asigna y valida el vehículo para la expedición."""
        if self.status == ExpeditionStatus.PENDIENTE_REVISION:
            raise InvalidStateTransitionException(
                "Una expedición en PENDIENTE_REVISION no puede recibir asignación de vehículo "
                "ni pasar a LISTA_PARA_DECA sin resolver la revisión documental previa."
            )
        if self.status in (ExpeditionStatus.CANCELADA, ExpeditionStatus.ENVIADA):
            raise InvalidStateTransitionException(
                f"No se puede modificar el vehículo de una expedición en estado {self.status}."
            )

        norm_tractor = (
            tractor_plate if isinstance(tractor_plate, Matricula) else Matricula(tractor_plate)
        )
        norm_trailer = (
            trailer_plate
            if (trailer_plate is None or isinstance(trailer_plate, Matricula))
            else Matricula(trailer_plate)
        )

        v_type = VehicleType.from_str(vehicle_type)

        if v_type == VehicleType.RIGIDO:
            if not norm_tractor or not norm_tractor.valor:
                raise InvalidVehicleConfigurationException(
                    "Un vehículo rígido exige obligatoriamente la matrícula del vehículo."
                )
            if norm_trailer is not None and norm_trailer.valor:
                raise InvalidVehicleConfigurationException(
                    "Un vehículo rígido no puede tener asignada una matrícula de "
                    "remolque/semirremolque."
                )
        elif v_type == VehicleType.ARTICULADO:
            if not norm_tractor or not norm_tractor.valor:
                raise InvalidVehicleConfigurationException(
                    "Un conjunto articulado exige matrícula de la cabeza tractora."
                )
            if not norm_trailer or not norm_trailer.valor:
                raise InvalidVehicleConfigurationException(
                    "Un conjunto articulado exige matrícula del semirremolque/remolque."
                )

        self.vehicle_type = v_type
        self.tractor_plate = norm_tractor
        self.trailer_plate = norm_trailer
        self.updated_at = datetime.now(UTC)

    def update_carrier(
        self,
        carrier_name: str | None = None,
        carrier_tax_id: NIF | str | None = None,
        carrier_email: str | None = None,
    ) -> None:
        """Actualiza la información del transportista efectivo."""
        if carrier_name is not None and carrier_name.strip():
            self.carrier_name_raw = carrier_name.strip()
        if carrier_tax_id is not None:
            tax_str = str(carrier_tax_id).strip()
            if tax_str:
                self.carrier_tax_id = (
                    carrier_tax_id if isinstance(carrier_tax_id, NIF) else NIF(tax_str)
                )
        if carrier_email is not None:
            self.carrier_email = carrier_email.strip() if carrier_email.strip() else None
        self.updated_at = datetime.now(UTC)
