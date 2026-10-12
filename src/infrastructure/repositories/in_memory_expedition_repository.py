from __future__ import annotations

import threading
import uuid
from datetime import date

from src.application.ports.expedition_repository import ExpeditionRepositoryPort
from src.domain.entities.expedition import Expedition
from src.domain.enums import ExpeditionStatus
from src.domain.services.expedition_id_generator import (
    InMemoryExpeditionSequenceGenerator,
)


class InMemoryExpeditionRepository(ExpeditionRepositoryPort):
    """Implementación thread-safe en memoria del repositorio de expediciones."""

    def __init__(self) -> None:
        self.expeditions: dict[str, Expedition] = {}
        self._seq_gen = InMemoryExpeditionSequenceGenerator()
        self._lock = threading.Lock()

    def save(self, expedition: Expedition) -> Expedition:
        with self._lock:
            self.expeditions[str(expedition.id)] = expedition
            return expedition

    def get_by_id(self, expedition_id: uuid.UUID | str) -> Expedition | None:
        with self._lock:
            return self.expeditions.get(str(expedition_id))

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

    def find_by_internal_id(self, internal_id: str) -> Expedition | None:
        with self._lock:
            for exp in self.expeditions.values():
                if exp.internal_id == internal_id:
                    return exp
            return None

    def next_internal_id(self, fiscal_year: str) -> str:
        return self._seq_gen.next_identifier(fiscal_year)

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
