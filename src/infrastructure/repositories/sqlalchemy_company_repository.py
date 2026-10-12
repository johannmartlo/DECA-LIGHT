from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.application.ports.company_repository import CompanyRepositoryPort
from src.domain.entities.company import Company
from src.domain.value_objects import NIF
from src.infrastructure.database.models import CompanyORM


class SqlAlchemyCompanyRepository(CompanyRepositoryPort):
    """Adaptador de persistencia SQLAlchemy para sociedades emisoras (Company)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, company: Company) -> Company:
        """Persiste o actualiza una sociedad emisora en la base de datos relacional.

        Aplica `session.flush()` para sincronizar los cambios con la transacción
        activa sin emitir un commit forzado, permitiendo que la frontera
        transaccional superior controle la unidad de trabajo.
        """
        orm = self._session.get(CompanyORM, company.company_id)
        if orm is not None:
            orm.legal_name = company.legal_name
            orm.tax_id = company.tax_id.valor if company.tax_id else None
            orm.fiscal_address = company.fiscal_address
            orm.active = company.active
            orm.document_aliases = list(company.document_aliases)
        else:
            orm = self._to_orm(company)
            self._session.add(orm)

        self._session.flush()
        return self._to_domain(orm)

    def get_by_id(self, company_id: str) -> Company | None:
        """Recupera una empresa por su identificador estable."""
        orm = self._session.get(CompanyORM, company_id)
        return self._to_domain(orm) if orm is not None else None

    def list_all(self) -> list[Company]:
        """Lista todas las empresas configuradas (activas o inactivas)."""
        stmt = select(CompanyORM).order_by(CompanyORM.company_id)
        orms = self._session.scalars(stmt).all()
        return [self._to_domain(orm) for orm in orms]

    def list_active(self) -> list[Company]:
        """Lista únicamente las empresas con marca de actividad positiva."""
        stmt = (
            select(CompanyORM)
            .where(CompanyORM.active.is_(True))
            .order_by(CompanyORM.company_id)
        )
        orms = self._session.scalars(stmt).all()
        return [self._to_domain(orm) for orm in orms]

    @staticmethod
    def _to_orm(company: Company) -> CompanyORM:
        """Mapea una entidad de dominio Company a su representación relacional CompanyORM."""
        return CompanyORM(
            company_id=company.company_id,
            legal_name=company.legal_name,
            tax_id=company.tax_id.valor if company.tax_id else None,
            fiscal_address=company.fiscal_address,
            active=company.active,
            document_aliases=list(company.document_aliases),
        )

    @staticmethod
    def _to_domain(orm: CompanyORM) -> Company:
        """Reconstruye una entidad de dominio Company a partir de CompanyORM preservando Value Objects."""
        tax_id_vo = NIF(orm.tax_id) if orm.tax_id else None
        aliases = tuple(orm.document_aliases or [])
        return Company(
            company_id=orm.company_id,
            legal_name=orm.legal_name,
            tax_id=tax_id_vo,
            fiscal_address=orm.fiscal_address or "",
            active=bool(orm.active),
            document_aliases=aliases,
        )
