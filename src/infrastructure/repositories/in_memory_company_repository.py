from __future__ import annotations

from collections.abc import Iterable

from src.application.ports.company_repository import CompanyRepositoryPort
from src.domain.entities.company import Company


class InMemoryCompanyRepository(CompanyRepositoryPort):
    """Registro de empresas en memoria, cargado desde configuración."""

    def __init__(self, companies: Iterable[Company] = ()) -> None:
        self._companies: dict[str, Company] = {}
        for company in companies:
            if company.company_id in self._companies:
                raise ValueError(f"company_id duplicado: {company.company_id}")
            self._companies[company.company_id] = company

    def save(self, company: Company) -> Company:
        self._companies[company.company_id] = company
        return company

    def get_by_id(self, company_id: str) -> Company | None:
        return self._companies.get(company_id)

    def list_all(self) -> list[Company]:
        return list(self._companies.values())

    def list_active(self) -> list[Company]:
        return [c for c in self._companies.values() if c.active]
