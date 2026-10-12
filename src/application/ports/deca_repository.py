from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from src.domain.entities.deca import DeCA, DeCAVersion


class DeCARepositoryPort(ABC):
    """Puerto de persistencia para documentos DeCA y versiones físicas."""

    @abstractmethod
    def save(self, deca: DeCA) -> DeCA:
        """Guarda o actualiza la entidad DeCA."""
        pass

    @abstractmethod
    def get_by_id(self, deca_id: uuid.UUID, company_id: str | None = None) -> DeCA | None:
        """Recupera un DeCA por su ID interno, opcionalmente filtrando por empresa."""
        pass

    @abstractmethod
    def find_by_expedition_id(
        self, expedition_id: uuid.UUID, company_id: str | None = None
    ) -> DeCA | None:
        """Recupera el DeCA asociado a una expedición si existe."""
        pass

    @abstractmethod
    def find_by_code(self, deca_code: str, company_id: str | None = None) -> DeCA | None:
        """Recupera un DeCA por su código oficial (ej. DECA-2026-000001)."""
        pass

    @abstractmethod
    def get_by_public_token(self, token: str) -> DeCA | None:
        """Recupera un DeCA por su token criptográfico de acceso público."""
        pass

    @abstractmethod
    def save_version(self, version: DeCAVersion) -> DeCAVersion:
        """Registra una versión física inmutable."""
        pass

    @abstractmethod
    def next_deca_code(self, fiscal_year: str) -> str:
        """Genera el siguiente código oficial correlativo y atómico en formato DECA-YYYY-NNNNNN."""
        pass
