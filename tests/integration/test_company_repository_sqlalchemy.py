from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.domain.entities.company import Company
from src.domain.value_objects import NIF
from src.infrastructure.database.models import CompanyORM
from src.infrastructure.database.session import (
    Base,
    create_db_engine,
    create_session_factory,
)
from src.infrastructure.repositories.sqlalchemy_company_repository import (
    SqlAlchemyCompanyRepository,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_company_repo.db"


@pytest.fixture
def db_engine(temp_db_path: Path):
    db_url = f"sqlite:///{temp_db_path.as_posix()}"
    engine = create_db_engine(db_url)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(db_engine) -> sessionmaker[Session]:
    return create_session_factory(db_engine)


@pytest.fixture
def db_session(session_factory: sessionmaker[Session]):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def company_repo(db_session: Session) -> SqlAlchemyCompanyRepository:
    return SqlAlchemyCompanyRepository(db_session)


def test_save_and_get_by_id(company_repo: SqlAlchemyCompanyRepository) -> None:
    company = Company(
        company_id="TOMATES_DE_AUTOR",
        legal_name="Tomates de Autor S.L.",
        tax_id=NIF("B12345678"),
        fiscal_address="Polígono La Redonda, Almería",
        active=True,
        document_aliases=("TOMATES AUTOR", "TDA"),
    )

    saved = company_repo.save(company)
    assert saved.company_id == "TOMATES_DE_AUTOR"
    assert saved.legal_name == "Tomates de Autor S.L."

    retrieved = company_repo.get_by_id("TOMATES_DE_AUTOR")
    assert retrieved is not None
    assert retrieved.company_id == "TOMATES_DE_AUTOR"
    assert retrieved.legal_name == "Tomates de Autor S.L."
    assert retrieved.tax_id is not None
    assert isinstance(retrieved.tax_id, NIF)
    assert retrieved.tax_id.valor == "B12345678"
    assert str(retrieved.tax_id) == "B12345678"
    assert retrieved.fiscal_address == "Polígono La Redonda, Almería"
    assert retrieved.active is True
    assert retrieved.document_aliases == ("TOMATES AUTOR", "TDA")


def test_get_by_id_non_existent(company_repo: SqlAlchemyCompanyRepository) -> None:
    assert company_repo.get_by_id("EMPRESA_INEXISTENTE") is None


def test_update_existing_company(company_repo: SqlAlchemyCompanyRepository) -> None:
    initial = Company(
        company_id="CULTIVOS_ARABA",
        legal_name="Cultivos Araba S.L.",
        tax_id=NIF("B01999888"),
        fiscal_address="Vitoria-Gasteiz",
        active=True,
        document_aliases=("ARABA",),
    )
    company_repo.save(initial)

    updated = Company(
        company_id="CULTIVOS_ARABA",
        legal_name="Cultivos Araba Sociedad Limitada",
        tax_id=NIF("B01999888"),
        fiscal_address="Polígono Jundiz, Vitoria-Gasteiz",
        active=False,
        document_aliases=("ARABA", "CULTIVOS ARABA SL"),
    )
    result = company_repo.save(updated)

    assert result.legal_name == "Cultivos Araba Sociedad Limitada"
    assert result.active is False
    assert result.document_aliases == ("ARABA", "CULTIVOS ARABA SL")

    fetched = company_repo.get_by_id("CULTIVOS_ARABA")
    assert fetched is not None
    assert fetched.legal_name == "Cultivos Araba Sociedad Limitada"
    assert fetched.fiscal_address == "Polígono Jundiz, Vitoria-Gasteiz"
    assert fetched.active is False
    assert fetched.document_aliases == ("ARABA", "CULTIVOS ARABA SL")


def test_list_all_and_list_active(company_repo: SqlAlchemyCompanyRepository) -> None:
    c1 = Company(
        company_id="COMP_ALPHA",
        legal_name="Alpha S.L.",
        active=True,
    )
    c2 = Company(
        company_id="COMP_BETA",
        legal_name="Beta S.L.",
        active=False,
    )
    c3 = Company(
        company_id="COMP_GAMMA",
        legal_name="Gamma S.L.",
        active=True,
    )

    company_repo.save(c1)
    company_repo.save(c2)
    company_repo.save(c3)

    all_companies = company_repo.list_all()
    assert len(all_companies) == 3
    assert [c.company_id for c in all_companies] == ["COMP_ALPHA", "COMP_BETA", "COMP_GAMMA"]

    active_companies = company_repo.list_active()
    assert len(active_companies) == 2
    assert [c.company_id for c in active_companies] == ["COMP_ALPHA", "COMP_GAMMA"]


def test_mapping_optional_fields_and_none_tax_id(
    company_repo: SqlAlchemyCompanyRepository,
) -> None:
    company = Company(
        company_id="COMP_MINIMAL",
        legal_name="Empresa Sin NIF",
        tax_id=None,
        fiscal_address="",
        active=True,
        document_aliases=(),
    )

    saved = company_repo.save(company)
    assert saved.tax_id is None
    assert saved.fiscal_address == ""
    assert saved.document_aliases == ()

    retrieved = company_repo.get_by_id("COMP_MINIMAL")
    assert retrieved is not None
    assert retrieved.tax_id is None
    assert retrieved.fiscal_address == ""
    assert retrieved.document_aliases == ()


def test_persistence_across_independent_sessions(
    session_factory: sessionmaker[Session],
) -> None:
    company_id = "PERSISTENT_CORP"

    # Sesión 1: Guardar y commitear
    session_1 = session_factory()
    try:
        repo_1 = SqlAlchemyCompanyRepository(session_1)
        repo_1.save(
            Company(
                company_id=company_id,
                legal_name="Persistencia Real S.L.",
                tax_id=NIF("B99887766"),
                fiscal_address="Calle Mayor 1, Madrid",
                active=True,
                document_aliases=("PERSIST",),
            )
        )
        session_1.commit()
    finally:
        session_1.close()

    # Sesión 2: Leer desde conexión totalmente independiente
    session_2 = session_factory()
    try:
        repo_2 = SqlAlchemyCompanyRepository(session_2)
        retrieved = repo_2.get_by_id(company_id)
        assert retrieved is not None
        assert retrieved.company_id == company_id
        assert retrieved.legal_name == "Persistencia Real S.L."
        assert retrieved.tax_id is not None
        assert retrieved.tax_id.valor == "B99887766"
        assert retrieved.fiscal_address == "Calle Mayor 1, Madrid"
        assert retrieved.document_aliases == ("PERSIST",)
    finally:
        session_2.close()


def test_duplicate_primary_key_direct_orm_integrity_error(
    session_factory: sessionmaker[Session],
) -> None:
    # Comprobar que la restricción primary key de la BD rechaza duplicados directos
    from sqlalchemy import insert

    session = session_factory()
    try:
        session.execute(
            insert(CompanyORM).values(
                company_id="DUPLICATE_ID",
                legal_name="Primera Empresa",
                document_aliases=[],
            )
        )
        session.flush()

        with pytest.raises(IntegrityError):
            session.execute(
                insert(CompanyORM).values(
                    company_id="DUPLICATE_ID",
                    legal_name="Segunda Empresa Colisión",
                    document_aliases=[],
                )
            )
            session.flush()
    finally:
        session.rollback()
        session.close()



def test_transactional_rollback_clears_uncommitted_state(
    session_factory: sessionmaker[Session],
) -> None:
    session = session_factory()
    try:
        repo = SqlAlchemyCompanyRepository(session)
        repo.save(
            Company(
                company_id="ROLLBACK_CO",
                legal_name="Empresa Descartada",
            )
        )
        # Hacemos rollback antes de commit
        session.rollback()

        # En la misma sesión tras rollback no debe estar
        assert repo.get_by_id("ROLLBACK_CO") is None
    finally:
        session.close()

    # En una nueva sesión tampoco debe existir
    new_session = session_factory()
    try:
        new_repo = SqlAlchemyCompanyRepository(new_session)
        assert new_repo.get_by_id("ROLLBACK_CO") is None
    finally:
        new_session.close()
