from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.domain.entities.expedition import Expedition
from src.domain.exceptions import DuplicateEntityException
from src.domain.services.expedition_id_generator import (
    InMemoryExpeditionSequenceGenerator,
)
from src.infrastructure.database.models import CompanyORM
from src.infrastructure.database.session import (
    Base,
    create_db_engine,
    create_session_factory,
)
from src.infrastructure.repositories.in_memory_expedition_repository import (
    InMemoryExpeditionRepository,
)
from src.infrastructure.repositories.sqlalchemy_expedition_repository import (
    SqlAlchemyExpeditionRepository,
)


def test_independent_sequence_generator_per_company_and_year() -> None:
    gen = InMemoryExpeditionSequenceGenerator()

    # Empresa 1, año 2026
    t1 = gen.next_identifier("2026", company_id="TOMATES_DE_AUTOR")
    t2 = gen.next_identifier("2026", company_id="TOMATES_DE_AUTOR")
    assert t1 == "TD-2026-00001"
    assert t2 == "TD-2026-00002"

    # Empresa 2, año 2026: secuencia independiente iniciada en 00001
    a1 = gen.next_identifier("2026", company_id="CULTIVOS_ARABA")
    a2 = gen.next_identifier("2026", company_id="CULTIVOS_ARABA")
    assert a1 == "TD-2026-00001"
    assert a2 == "TD-2026-00002"

    # Ejercicio fiscal 2027: reinicio independiente de secuencia
    t_2027 = gen.next_identifier("2027", company_id="TOMATES_DE_AUTOR")
    assert t_2027 == "TD-2027-00001"

    # Prefijo configurable
    custom_pfx = gen.next_identifier("2026", company_id="TOMATES_DE_AUTOR", prefix="EXP")
    assert custom_pfx == "EXP-2026-00001"


def test_in_memory_repository_compound_uniqueness() -> None:
    repo = InMemoryExpeditionRepository()

    # Expedición para Tomates con TD-2026-00001
    exp1 = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00001",
        reference="REF-01",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    repo.save(exp1)

    # Expedición para Araba con el MISMO internal_id TD-2026-00001: PERMITIDO
    exp2 = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00001",
        reference="REF-02",
        fiscal_year="2026",
        company_id="CULTIVOS_ARABA",
    )
    repo.save(exp2)

    assert repo.find_by_internal_id("TD-2026-00001", company_id="TOMATES_DE_AUTOR") == exp1
    assert repo.find_by_internal_id("TD-2026-00001", company_id="CULTIVOS_ARABA") == exp2

    # Intentar guardar OTRA expedición de Tomates con TD-2026-00001: RECHAZADO
    exp3 = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00001",
        reference="REF-03",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    with pytest.raises(DuplicateEntityException) as exc_info:
        repo.save(exp3)
    assert "ya existe una expedición" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Pruebas de persistencia relacional con SQLite y restricción física compuesta
# ---------------------------------------------------------------------------

@pytest.fixture
def repo_session(tmp_path: Path):
    db_file = tmp_path / "test_tenant_num.db"
    engine = create_db_engine(f"sqlite:///{db_file.as_posix()}")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    factory = create_session_factory(engine)
    session = factory()

    # Empresas sembradas
    session.add_all([
        CompanyORM(company_id="TOMATES_DE_AUTOR", legal_name="Tomates", active=True),
        CompanyORM(company_id="CULTIVOS_ARABA", legal_name="Araba", active=True),
    ])
    session.commit()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_sqlalchemy_independent_next_internal_id(repo_session: Session) -> None:
    repo = SqlAlchemyExpeditionRepository(repo_session)

    # Inicialmente ambos deben generar 00001
    next_tom = repo.next_internal_id("2026", company_id="TOMATES_DE_AUTOR")
    next_ara = repo.next_internal_id("2026", company_id="CULTIVOS_ARABA")
    assert next_tom == "TD-2026-00001"
    assert next_ara == "TD-2026-00001"

    # Guardar uno para Tomates
    exp_tom = Expedition(
        id=uuid.uuid4(),
        internal_id=next_tom,
        reference="REF-TOM-1",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    repo.save(exp_tom)
    repo_session.commit()

    # Tomates ahora da 00002, Araba sigue dando 00001
    assert repo.next_internal_id("2026", company_id="TOMATES_DE_AUTOR") == "TD-2026-00002"
    assert repo.next_internal_id("2026", company_id="CULTIVOS_ARABA") == "TD-2026-00001"


def test_sqlalchemy_compound_uniqueness_db_enforcement(repo_session: Session) -> None:
    repo = SqlAlchemyExpeditionRepository(repo_session)

    # Ambos persisten con TD-2026-00001 en empresas distintas sin colisión
    e1 = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00001",
        reference="REF-T1",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    e2 = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00001",
        reference="REF-A1",
        fiscal_year="2026",
        company_id="CULTIVOS_ARABA",
    )
    repo.save(e1)
    repo.save(e2)
    repo_session.commit()

    # Tercero compitiendo con TD-2026-00001 dentro de Tomates eleva IntegrityError
    e3 = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00001",
        reference="REF-T2",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    with pytest.raises(IntegrityError):
        repo.save(e3)
    repo_session.rollback()

    # save_with_id_retry recupera automáticamente generando TD-2026-00002 para Tomates
    saved3 = repo.save_with_id_retry(e3, fiscal_year="2026", company_id="TOMATES_DE_AUTOR")
    repo_session.commit()
    assert saved3.internal_id == "TD-2026-00002"
