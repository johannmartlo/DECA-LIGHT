from __future__ import annotations

import copy
import threading
import uuid
from datetime import date

from src.application.ports.expedition_repository import ExpeditionRepositoryPort
from src.domain.entities.expedition import Expedition
from src.domain.enums import ExpeditionStatus
from src.domain.exceptions import CompanyMismatchException, DuplicateEntityException
from src.domain.services.expedition_id_generator import (
    InMemoryExpeditionSequenceGenerator,
)


class InMemoryExpeditionRepository(ExpeditionRepositoryPort):
    """Implementación thread-safe en memoria del repositorio de expediciones."""

    def __init__(self) -> None:
        self.expeditions: dict[str, Expedition] = {}
        self._seq_gen = InMemoryExpeditionSequenceGenerator()
        self._lock = threading.Lock()

    def save(
        self, expedition: Expedition, company_id: str | None = None
    ) -> Expedition:
        with self._lock:
            existing = self.expeditions.get(str(expedition.id))
            if existing is not None:
                if existing.company_id:
                    if company_id is not None and existing.company_id != company_id:
                        raise CompanyMismatchException(
                            f"Aislamiento multiempresa: intento de modificar la expedición {expedition.id} "
                            f"perteneciente a '{existing.company_id}' desde el contexto no autorizado '{company_id}'."
                        )
                    if not expedition.company_id or existing.company_id != expedition.company_id:
                        raise CompanyMismatchException(
                            f"Aislamiento multiempresa: no está permitido alterar la empresa de una expedición existente "
                            f"(actual: '{existing.company_id}', solicitada: '{expedition.company_id}')."
                        )
                else:
                    if company_id is not None and expedition.company_id and expedition.company_id != company_id:
                        raise CompanyMismatchException(
                            f"Aislamiento multiempresa: la expedición indica '{expedition.company_id}' "
                            f"pero el contexto exige '{company_id}'."
                        )
                    if company_id is not None and not expedition.company_id:
                        expedition.company_id = company_id
            else:
                if company_id is not None and expedition.company_id and expedition.company_id != company_id:
                    raise CompanyMismatchException(
                        f"Aislamiento multiempresa: la expedición indica empresa '{expedition.company_id}' "
                        f"pero el contexto exige '{company_id}'."
                    )
                if company_id is not None and not expedition.company_id:
                    expedition.company_id = company_id

            # Restricción de unicidad compuesta: (company_id, internal_id)
            effective_company = company_id or expedition.company_id
            if effective_company and expedition.internal_id:
                for other_id, other_exp in self.expeditions.items():
                    if other_id != str(expedition.id):
                        if (
                            other_exp.internal_id == expedition.internal_id
                            and other_exp.company_id == effective_company
                        ):
                            raise DuplicateEntityException(
                                f"Ya existe una expedición con identificador '{expedition.internal_id}' "
                                f"para la empresa '{effective_company}'."
                            )

            self.expeditions[str(expedition.id)] = copy.copy(expedition)
            return expedition

    def get_by_id(
        self, expedition_id: uuid.UUID | str, company_id: str | None = None
    ) -> Expedition | None:
        with self._lock:
            exp = self.expeditions.get(str(expedition_id))
            if exp is None:
                return None
            if company_id is not None and exp.company_id != company_id:
                return None
            return exp

    def find_by_reference(
        self, reference: str, fiscal_year: str, company_id: str | None = None
    ) -> Expedition | None:
        with self._lock:
            for exp in self.expeditions.values():
                if company_id and exp.company_id != company_id:
                    continue
                if exp.reference == reference and exp.fiscal_year == fiscal_year:
                    return exp
            return None

    def find_by_internal_id(
        self, internal_id: str, company_id: str | None = None
    ) -> Expedition | None:
        with self._lock:
            for exp in self.expeditions.values():
                if exp.internal_id == internal_id:
                    if company_id is not None and exp.company_id != company_id:
                        continue
                    return exp
            return None

    def next_internal_id(
        self, fiscal_year: str, company_id: str | None = None, prefix: str = "TD"
    ) -> str:
        return self._seq_gen.next_identifier(fiscal_year, company_id=company_id, prefix=prefix)

    def list_pending_vehicle(self, company_id: str | None = None) -> list[Expedition]:
        with self._lock:
            return [
                e
                for e in self.expeditions.values()
                if e.status == ExpeditionStatus.PENDIENTE_MATRICULA
                and (not company_id or e.company_id == company_id)
            ]

    def find_duplicate_cargo(
        self,
        fiscal_year: str,
        transport_date: date | None,
        destination: str | None,
        weight_kg: float | None,
        company_id: str | None = None,
    ) -> Expedition | None:
        with self._lock:
            for exp in self.expeditions.values():
                if company_id and exp.company_id != company_id:
                    continue
                if exp.fiscal_year != fiscal_year:
                    continue
                if transport_date and exp.transport_date != transport_date:
                    continue
                if destination and exp.destination != destination:
                    continue
                if weight_kg and exp.weight and abs(exp.weight.kg - weight_kg) > 0.01:
                    continue
                return exp
            return None

    def save_with_id_retry(
        self,
        expedition: Expedition,
        fiscal_year: str,
        company_id: str | None = None,
        max_retries: int = 3,
    ) -> Expedition:
        """Persiste una expedición en memoria (satisfaciendo el contrato de puerto)."""
        return self.save(expedition, company_id=company_id)

