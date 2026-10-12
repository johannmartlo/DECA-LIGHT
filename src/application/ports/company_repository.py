from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.company import Company


class CompanyRepositoryPort(ABC):
    """Puerto de consulta de sociedades emisoras configuradas."""

    @abstractmethod
    def get_by_id(self, company_id: str) -> Company | None:
        """Recupera una empresa por su identificador estable."""

    @abstractmethod
    def list_all(self) -> list[Company]:
        """Lista todas las empresas configuradas (activas o no)."""

    def list_active(self) -> list[Company]:
        return [c for c in self.list_all() if c.active]
