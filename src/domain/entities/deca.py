from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from src.domain.enums import DeCAStatus
from src.domain.exceptions import ImmutableDeCAException
from src.domain.services.clock import Clock
from src.domain.value_objects import DeCAToken


@dataclass(frozen=True)
class DeCAEstructurado:
    """Modelo estructurado e inmutable de los datos requeridos para un DeCA emitido.

    Representa la información legal y operativa completa antes del renderizado PDF,
    totalmente desacoplada de la entidad Expedition y del framework web.
    """

    deca_code: str
    version_number: int
    issue_datetime: datetime
    transport_date: date

    # Cargador contractual
    shipper_name: str
    shipper_tax_id: str
    shipper_address: str

    # Transportista efectivo
    carrier_name: str
    carrier_tax_id: str

    # Vehículo
    vehicle_type: str
    tractor_plate: str
    trailer_plate: str | None

    # Mercancía y ruta
    origin: str
    destination: str
    goods: str
    weight_kg: float

    # Empresa emisora y trazabilidad
    company_id: str = "TOMATES_DE_AUTOR"
    internal_id: str | None = None
    external_reference: str | None = None
    observations: str | None = None
    snapshot_hash: str | None = None

    # Campos opcionales para interoperabilidad
    public_url: str = ""
    qr_payload: str = ""

    def to_snapshot(self) -> dict:
        """Serializa a diccionario canónico inmutable para persistencia y auditoría."""
        return {
            "deca_code": self.deca_code,
            "version": self.version_number,
            "company_id": self.company_id,
            "internal_id": self.internal_id,
            "external_reference": self.external_reference,
            "issue_datetime": self.issue_datetime.isoformat(),
            "transport_date": self.transport_date.isoformat(),
            "public_url": self.public_url,
            "shipper": {
                "name": self.shipper_name,
                "tax_id": self.shipper_tax_id,
                "address": self.shipper_address,
            },
            "carrier": {
                "name": self.carrier_name,
                "tax_id": self.carrier_tax_id,
            },
            "vehicle": {
                "type": self.vehicle_type,
                "tractor_plate": self.tractor_plate,
                "trailer_plate": self.trailer_plate,
            },
            "route_and_goods": {
                "origin": self.origin,
                "destination": self.destination,
                "goods": self.goods,
                "weight_kg": self.weight_kg,
            },
            "observations": self.observations,
        }

    @classmethod
    def from_snapshot(
        cls, snapshot_data: dict, snapshot_hash: str | None = None
    ) -> DeCAEstructurado:
        """Reconstruye el objeto DeCAEstructurado a partir del snapshot inmutable."""
        shipper = snapshot_data.get("shipper", {})
        carrier = snapshot_data.get("carrier", {})
        vehicle = snapshot_data.get("vehicle", {})
        route = snapshot_data.get("route_and_goods", {})

        raw_issue = snapshot_data.get("issue_datetime", "")
        issue_dt = datetime.fromisoformat(raw_issue) if raw_issue else datetime.now(UTC)
        raw_transport = snapshot_data.get("transport_date", "")
        transport_d = date.fromisoformat(raw_transport) if raw_transport else date.today()

        return cls(
            deca_code=snapshot_data.get("deca_code", ""),
            version_number=snapshot_data.get("version", 1),
            company_id=snapshot_data.get("company_id", "TOMATES_DE_AUTOR"),
            issue_datetime=issue_dt,
            transport_date=transport_d,
            shipper_name=shipper.get("name", ""),
            shipper_tax_id=shipper.get("tax_id", ""),
            shipper_address=shipper.get("address", ""),
            carrier_name=carrier.get("name", ""),
            carrier_tax_id=carrier.get("tax_id", ""),
            vehicle_type=vehicle.get("type", ""),
            tractor_plate=vehicle.get("tractor_plate", ""),
            trailer_plate=vehicle.get("trailer_plate"),
            origin=route.get("origin", ""),
            destination=route.get("destination", ""),
            goods=route.get("goods", ""),
            weight_kg=float(route.get("weight_kg", 0.0)),
            internal_id=snapshot_data.get("internal_id"),
            external_reference=snapshot_data.get("external_reference"),
            observations=snapshot_data.get("observations"),
            snapshot_hash=snapshot_hash,
            public_url=snapshot_data.get("public_url", ""),
            qr_payload=snapshot_data.get("public_url", ""),
        )


@dataclass
class DeCAVersion:
    """Snapshot inmutable de una versión física de DeCA generada."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    deca_id: uuid.UUID | None = None
    version_number: int = 1
    pdf_sha256: str = ""
    pdf_storage_path: str = ""
    pdf_size_bytes: int = 0
    snapshot_hash: str = ""
    modification_reason: str | None = None
    snapshot_data: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=Clock.now)

    def __post_init__(self) -> None:
        # Almacenar copia desacoplada de snapshot_data para garantizar inmutabilidad
        if self.snapshot_data:
            # Deep copy mediante serialización canónica para aislar de referencias mutables
            self.snapshot_data = json.loads(json.dumps(self.snapshot_data))


@dataclass
class DeCA:
    """Documento formal DeCA emitido para una expedición."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    expedition_id: uuid.UUID | None = None
    company_id: str = "TOMATES_DE_AUTOR"
    deca_code: str = ""
    public_access_token: DeCAToken = field(
        default_factory=lambda: DeCAToken(secrets.token_urlsafe(32))
    )
    public_token_hash: str = ""
    service_start_at: datetime = field(default_factory=Clock.now)
    service_end_at: datetime | None = None
    public_download_expires_at: datetime | None = None
    legal_custody_until: datetime = field(default_factory=lambda: Clock.now() + timedelta(days=365))
    public_download_active: bool = True
    current_version: int = 1
    status: DeCAStatus = DeCAStatus.ISSUED
    versions: list[DeCAVersion] = field(default_factory=list)
    created_at: datetime = field(default_factory=Clock.now)
    updated_at: datetime = field(default_factory=Clock.now)

    def belongs_to(self, company_id: str | None) -> bool:
        """Indica si el DeCA pertenece a la empresa indicada."""
        return bool(company_id) and self.company_id == company_id

    def __post_init__(self) -> None:
        if self.public_access_token and not self.public_token_hash:
            self.public_token_hash = hashlib.sha256(
                str(self.public_access_token).encode("utf-8")
            ).hexdigest()

    def add_version(self, version: DeCAVersion) -> None:
        """Añade una versión inmutable al DeCA rechazando duplicados o alteraciones."""
        for existing in self.versions:
            if existing.version_number == version.version_number:
                raise ImmutableDeCAException(
                    f"El DeCA '{self.deca_code}' ya cuenta con la versión "
                    f"v{version.version_number} emitida. Las versiones son inmutables."
                )
        version.deca_id = self.id
        self.versions.append(version)
        self.current_version = max(self.current_version, version.version_number)
        self.updated_at = Clock.now()

    def get_version(self, version_number: int = 1) -> DeCAVersion | None:
        """Recupera una versión histórica específica del DeCA."""
        for v in self.versions:
            if v.version_number == version_number:
                return v
        return None

    @property
    def latest_version(self) -> DeCAVersion | None:
        """Devuelve la versión más reciente del documento."""
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.version_number)

    def record_service_end(self, end_at: datetime | None = None) -> None:
        """Registra el fin del servicio y calcula deterministamente la expiración."""
        actual_end = end_at if end_at is not None else Clock.now()
        self.service_end_at = actual_end
        self.public_download_expires_at = actual_end + timedelta(days=7)
        self.updated_at = Clock.now()

    def is_public_download_allowed(self, at_time: datetime | None = None) -> bool:
        """Comprueba si el documento puede ser descargado públicamente."""
        if not self.public_download_active:
            return False
        if self.status in (DeCAStatus.REVOKED, DeCAStatus.EXPIRED_PUBLIC):
            return False
        current = at_time if at_time is not None else Clock.now()
        if self.public_download_expires_at and current > self.public_download_expires_at:
            return False
        return True
