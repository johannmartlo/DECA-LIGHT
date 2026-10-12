from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import date

from src.domain.entities.expedition import Expedition


class ExpeditionRepositoryPort(ABC):
    """Puerto de persistencia para expediciones de transporte."""

    @abstractmethod
    def save(self, expedition: Expedition) -> Expedition:
        """Persiste o actualiza una expedición."""
        pass

    @abstractmethod
    def get_by_id(self, expedition_id: uuid.UUID) -> Expedition | None:
        """Recupera una expedición por su UUID interno."""
        pass

    @abstractmethod
    def find_by_reference(
        self, reference: str, fiscal_year: str, company_id: str | None = None
    ) -> Expedition | None:
        """Busca si ya existe una expedición registrada para ese albarán, ejercicio y empresa."""
        pass

    @abstractmethod
    def list_pending_vehicle(self, company_id: str | None = None) -> list[Expedition]:
        """Lista las expediciones que están a la espera de matrícula."""
        pass

    def next_internal_id(self, fiscal_year: str) -> str:
        """Genera el siguiente identificador legible TD-YYYY-NNNNN de forma atómica."""
        raise NotImplementedError

    def find_by_internal_id(self, internal_id: str) -> Expedition | None:
        """Busca una expedición por su identificador visible TD-YYYY-NNNNN."""
        return None

    def find_duplicate_cargo(
        self,
        fiscal_year: str,
        transport_date: date | None,
        destination: str | None,
        weight_kg: float | None,
        company_id: str | None = None,
    ) -> Expedition | None:
        """Busca duplicados de carga cuando no existe número de albarán fiable
        (ej. Carta de Porte sin albarán explícito)."""
        return None
