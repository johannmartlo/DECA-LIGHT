from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.application.ports.expedition_repository import ExpeditionRepositoryPort
from src.domain.entities.expedition import Expedition
from src.domain.enums import ExpeditionStatus, VehicleType
from src.domain.exceptions import CompanyMismatchException
from src.domain.services.internal_id_collision_policy import is_internal_id_collision
from src.domain.value_objects import NIF, Matricula, Weight
from src.infrastructure.database.models import ExpeditionORM


class SqlAlchemyExpeditionRepository(ExpeditionRepositoryPort):
    """Adaptador de persistencia SQLAlchemy para expediciones de transporte (Expedition)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self, expedition: Expedition, company_id: str | None = None
    ) -> Expedition:
        """Persiste o actualiza una expedición en la base de datos relacional.

        Aplica `session.flush()` para sincronizar los cambios con la transacción
        activa y verificar restricciones físicas (UNIQUE, FK, NOT NULL) sin emitir
        un commit forzado. La frontera transaccional pertenece al caso de uso invocador.
        Nunca captura ni oculta IntegrityError.

        Aislamiento multiempresa (multi-tenant):
        - En actualización: si el registro pertenece a una empresa, rechaza cualquier
          modificación desde un contexto `company_id` diferente o cualquier intento
          de alterar la empresa del registro existente (`CompanyMismatchException`).
        - En inserción: si se proporciona `company_id` de contexto y difiere del
          indicado en la entidad, rechaza la operación (`CompanyMismatchException`).
        """
        orm = self._session.get(ExpeditionORM, expedition.id)
        if orm is not None:
            # 1. Blindaje contra acceso cruzado en actualización:
            if orm.company_id:
                if company_id is not None and orm.company_id != company_id:
                    raise CompanyMismatchException(
                        f"Aislamiento multiempresa: intento de modificar la expedición {expedition.id} "
                        f"perteneciente a '{orm.company_id}' desde el contexto no autorizado '{company_id}'."
                    )
                if not expedition.company_id or orm.company_id != expedition.company_id:
                    raise CompanyMismatchException(
                        f"Aislamiento multiempresa: no está permitido alterar la empresa de una expedición existente "
                        f"(actual: '{orm.company_id}', solicitada: '{expedition.company_id}')."
                    )
            else:
                if company_id is not None and expedition.company_id and expedition.company_id != company_id:
                    raise CompanyMismatchException(
                        f"Aislamiento multiempresa: la expedición indica '{expedition.company_id}' "
                        f"pero el contexto exige '{company_id}'."
                    )
                if company_id is not None and not expedition.company_id:
                    expedition.company_id = company_id

            orm.internal_id = expedition.internal_id
            orm.document_id = expedition.document_id
            orm.reference = expedition.reference
            orm.fiscal_year = expedition.fiscal_year
            orm.transport_date = expedition.transport_date
            orm.company_id = expedition.company_id if expedition.company_id else None
            orm.issuer_detection_confidence = expedition.issuer_detection_confidence
            orm.issuer_detection_source = expedition.issuer_detection_source
            orm.shipper_name = expedition.shipper_name
            orm.shipper_tax_id = (
                expedition.shipper_tax_id.valor if expedition.shipper_tax_id else None
            )
            orm.shipper_address = expedition.shipper_address
            orm.carrier_id = expedition.carrier_id
            orm.carrier_name_raw = expedition.carrier_name_raw
            orm.carrier_tax_id = (
                expedition.carrier_tax_id.valor if expedition.carrier_tax_id else None
            )
            orm.carrier_email = expedition.carrier_email
            orm.vehicle_type = expedition.vehicle_type.value if expedition.vehicle_type else None
            orm.tractor_plate = (
                expedition.tractor_plate.valor if expedition.tractor_plate else None
            )
            orm.trailer_plate = (
                expedition.trailer_plate.valor if expedition.trailer_plate else None
            )
            orm.origin = expedition.origin
            orm.destination = expedition.destination
            orm.goods = expedition.goods
            orm.weight_kg = expedition.weight.kg if expedition.weight else None
            orm.observations = expedition.observations
            orm.status = expedition.status.value
            orm.extraction_metadata = dict(expedition.extraction_metadata)
            orm.updated_at = expedition.updated_at
        else:
            # 2. Blindaje en inserción nueva:
            if company_id is not None and expedition.company_id and expedition.company_id != company_id:
                raise CompanyMismatchException(
                    f"Aislamiento multiempresa: la expedición indica empresa '{expedition.company_id}' "
                    f"pero el contexto exige '{company_id}'."
                )
            if company_id is not None and not expedition.company_id:
                expedition.company_id = company_id

            orm = self._to_orm(expedition)
            self._session.add(orm)

        self._session.flush()
        return self._to_domain(orm)

    def get_by_id(
        self, expedition_id: uuid.UUID, company_id: str | None = None
    ) -> Expedition | None:
        """Recupera una expedición por su UUID interno con filtrado opcional por empresa."""
        uid = (
            uuid.UUID(str(expedition_id))
            if not isinstance(expedition_id, uuid.UUID)
            else expedition_id
        )
        stmt = select(ExpeditionORM).where(ExpeditionORM.id == uid)
        if company_id is not None:
            stmt = stmt.where(ExpeditionORM.company_id == company_id)
        orm = self._session.scalars(stmt.limit(1)).first()
        return self._to_domain(orm) if orm is not None else None

    def find_by_reference(
        self, reference: str, fiscal_year: str, company_id: str | None = None
    ) -> Expedition | None:
        """Busca si ya existe una expedición registrada para ese albarán, ejercicio y empresa."""
        stmt = select(ExpeditionORM).where(
            ExpeditionORM.reference == reference,
            ExpeditionORM.fiscal_year == fiscal_year,
        )
        if company_id is not None:
            stmt = stmt.where(ExpeditionORM.company_id == company_id)

        orm = self._session.scalars(stmt.limit(1)).first()
        return self._to_domain(orm) if orm is not None else None

    def list_pending_vehicle(self, company_id: str | None = None) -> list[Expedition]:
        """Lista las expediciones que están a la espera de matrícula."""
        stmt = (
            select(ExpeditionORM)
            .where(ExpeditionORM.status == ExpeditionStatus.PENDIENTE_MATRICULA.value)
            .order_by(ExpeditionORM.transport_date.asc(), ExpeditionORM.internal_id.asc())
        )
        if company_id is not None:
            stmt = stmt.where(ExpeditionORM.company_id == company_id)

        orms = self._session.scalars(stmt).all()
        return [self._to_domain(orm) for orm in orms]

    def next_internal_id(
        self, fiscal_year: str, company_id: str | None = None, prefix: str = "TD"
    ) -> str:
        """Genera el siguiente identificador legible de forma atómica e independiente por empresa.

        En PostgreSQL aplica bloqueo de fila `with_for_update()`.
        La restricción física `uq_expeditions_company_internal_id`
        garantiza la imposibilidad de colisión, elevando IntegrityError ante carreras.
        """
        id_prefix = f"{prefix}-{fiscal_year}-"
        stmt = (
            select(ExpeditionORM.internal_id)
            .where(
                ExpeditionORM.fiscal_year == fiscal_year,
                ExpeditionORM.internal_id.like(f"{id_prefix}%"),
            )
        )
        if company_id is not None:
            stmt = stmt.where(ExpeditionORM.company_id == company_id)

        stmt = stmt.order_by(ExpeditionORM.internal_id.desc())

        # En PostgreSQL aplicamos bloqueo con FOR UPDATE si el dialecto lo soporta
        try:
            if self._session.bind and self._session.bind.dialect.name == "postgresql":
                stmt = stmt.with_for_update()
        except Exception:
            pass

        candidates = self._session.scalars(stmt.limit(20)).all()
        max_num = 0
        for cand in candidates:
            if cand.startswith(id_prefix):
                suffix = cand[len(id_prefix) :]
                if suffix.isdigit():
                    num = int(suffix)
                    if num > max_num:
                        max_num = num
                        break

        next_num = max_num + 1
        return f"{id_prefix}{next_num:05d}"

    def find_by_internal_id(
        self, internal_id: str, company_id: str | None = None
    ) -> Expedition | None:
        """Busca una expedición por su identificador visible TD-YYYY-NNNNN y opcionalmente su empresa."""
        stmt = select(ExpeditionORM).where(ExpeditionORM.internal_id == internal_id)
        if company_id is not None:
            stmt = stmt.where(ExpeditionORM.company_id == company_id)
        orm = self._session.scalars(stmt.limit(1)).first()
        return self._to_domain(orm) if orm is not None else None

    def find_duplicate_cargo(
        self,
        fiscal_year: str,
        transport_date: date | None,
        destination: str | None,
        weight_kg: float | None,
        company_id: str | None = None,
    ) -> Expedition | None:
        """Busca duplicados de carga cuando no existe número de albarán fiable
        (tolerancia de peso: ±0.01 kg)."""
        stmt = select(ExpeditionORM).where(ExpeditionORM.fiscal_year == fiscal_year)
        if company_id is not None:
            stmt = stmt.where(ExpeditionORM.company_id == company_id)
        if transport_date is not None:
            stmt = stmt.where(ExpeditionORM.transport_date == transport_date)
        if destination is not None:
            stmt = stmt.where(ExpeditionORM.destination == destination)
        if weight_kg is not None:
            stmt = stmt.where(
                ExpeditionORM.weight_kg.is_not(None),
                ExpeditionORM.weight_kg.between(weight_kg - 0.01, weight_kg + 0.01),
            )

        orm = self._session.scalars(stmt.limit(1)).first()
        return self._to_domain(orm) if orm is not None else None

    def save_with_id_retry(
        self,
        expedition: Expedition,
        fiscal_year: str,
        company_id: str | None = None,
        max_retries: int = 3,
    ) -> Expedition:
        """Persiste una expedición aplicando reintentos automáticos EXCLUSIVAMENTE
        ante colisiones verificadas en la restricción uq_expeditions_company_internal_id.

        Descarta y propaga inmediatamente errores de:
        - Claves foráneas (FK: company_id, carrier_id inexistentes).
        - Nulidad (NOT NULL).
        - Cualquier restricción distinta de internal_id.
        - Superación del umbral max_retries.
        """
        effective_company = company_id or expedition.company_id
        prefix = expedition.internal_id.split("-")[0] if "-" in expedition.internal_id else "TD"
        attempts = 0
        while True:
            try:
                with self._session.begin_nested():
                    return self.save(expedition, company_id=company_id)
            except IntegrityError as exc:
                if not is_internal_id_collision(exc) or attempts >= max_retries:
                    raise
                attempts += 1
                new_id = self.next_internal_id(
                    fiscal_year, company_id=effective_company, prefix=prefix
                )
                expedition.internal_id = new_id

    @staticmethod
    def _to_orm(expedition: Expedition) -> ExpeditionORM:
        """Mapea una entidad de dominio Expedition a ExpeditionORM."""
        return ExpeditionORM(
            id=expedition.id,
            internal_id=expedition.internal_id,
            document_id=expedition.document_id,
            reference=expedition.reference,
            fiscal_year=expedition.fiscal_year,
            transport_date=expedition.transport_date,
            company_id=expedition.company_id if expedition.company_id else None,
            issuer_detection_confidence=expedition.issuer_detection_confidence,
            issuer_detection_source=expedition.issuer_detection_source,
            shipper_name=expedition.shipper_name,
            shipper_tax_id=expedition.shipper_tax_id.valor if expedition.shipper_tax_id else None,
            shipper_address=expedition.shipper_address,
            carrier_id=expedition.carrier_id,
            carrier_name_raw=expedition.carrier_name_raw,
            carrier_tax_id=expedition.carrier_tax_id.valor if expedition.carrier_tax_id else None,
            carrier_email=expedition.carrier_email,
            vehicle_type=expedition.vehicle_type.value if expedition.vehicle_type else None,
            tractor_plate=expedition.tractor_plate.valor if expedition.tractor_plate else None,
            trailer_plate=expedition.trailer_plate.valor if expedition.trailer_plate else None,
            origin=expedition.origin,
            destination=expedition.destination,
            goods=expedition.goods,
            weight_kg=expedition.weight.kg if expedition.weight else None,
            observations=expedition.observations,
            status=expedition.status.value,
            extraction_metadata=dict(expedition.extraction_metadata),
            created_at=expedition.created_at,
            updated_at=expedition.updated_at,
        )

    @staticmethod
    def _to_domain(orm: ExpeditionORM) -> Expedition:
        """Reconstruye una entidad de dominio Expedition a partir de ExpeditionORM."""
        shipper_tax_id = NIF(orm.shipper_tax_id) if orm.shipper_tax_id else None
        carrier_tax_id = NIF(orm.carrier_tax_id) if orm.carrier_tax_id else None
        tractor_plate = Matricula(orm.tractor_plate) if orm.tractor_plate else None
        trailer_plate = Matricula(orm.trailer_plate) if orm.trailer_plate else None
        weight = Weight(orm.weight_kg) if orm.weight_kg is not None else None
        vehicle_type = VehicleType.from_str(orm.vehicle_type) if orm.vehicle_type else None
        status = ExpeditionStatus(orm.status)

        return Expedition(
            id=orm.id,
            internal_id=orm.internal_id,
            document_id=orm.document_id,
            reference=orm.reference,
            fiscal_year=orm.fiscal_year,
            transport_date=orm.transport_date,
            company_id=orm.company_id or "",
            issuer_detection_confidence=orm.issuer_detection_confidence,
            issuer_detection_source=orm.issuer_detection_source,
            shipper_name=orm.shipper_name,
            shipper_tax_id=shipper_tax_id,
            shipper_address=orm.shipper_address,
            carrier_id=orm.carrier_id,
            carrier_name_raw=orm.carrier_name_raw,
            carrier_tax_id=carrier_tax_id,
            carrier_email=orm.carrier_email,
            vehicle_type=vehicle_type,
            tractor_plate=tractor_plate,
            trailer_plate=trailer_plate,
            origin=orm.origin,
            destination=orm.destination,
            goods=orm.goods,
            weight=weight,
            observations=orm.observations,
            status=status,
            extraction_metadata=dict(orm.extraction_metadata or {}),
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )
