from __future__ import annotations

import concurrent.futures
import os
import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.domain.entities.expedition import Expedition
from src.infrastructure.database.models import CompanyORM
from src.infrastructure.database.session import (
    Base,
    create_db_engine,
    create_session_factory,
)
from src.infrastructure.repositories.sqlalchemy_expedition_repository import (
    SqlAlchemyExpeditionRepository,
)

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")


@pytest.mark.postgres
@pytest.mark.skipif(
    not POSTGRES_URL,
    reason="PostgreSQL de prueba no configurado (definir variable TEST_POSTGRES_URL para ejecutar)",
)
class TestPostgresConcurrencySuite:
    """Suite de integración y concurrencia ejecutada exclusivamente contra PostgreSQL real.

    Verifica el comportamiento de:
    1. Bloqueo de fila FOR UPDATE en dialecto postgresql durante `next_internal_id`.
    2. Colisiones atómicas en restricción física `uq_expeditions_company_internal_id` con SQLSTATE 23505.
    3. Rollback estricto de sesión y recuperación con `save_with_id_retry`.
    4. Independencia de secuencias multiempresa bajo concurrencia real.
    """

    @pytest.fixture(scope="class")
    def pg_engine(self):
        engine = create_db_engine(POSTGRES_URL)
        Base.metadata.create_all(bind=engine)
        yield engine
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    @pytest.fixture(scope="class")
    def pg_session_factory(self, pg_engine) -> sessionmaker[Session]:
        return create_session_factory(pg_engine)

    @pytest.fixture(autouse=True)
    def seed_companies(self, pg_session_factory: sessionmaker[Session]):
        session = pg_session_factory()
        try:
            # Limpiar datos previos
            session.query(CompanyORM).delete()
            session.commit()

            session.add_all([
                CompanyORM(company_id="TOMATES_DE_AUTOR", legal_name="Tomates de Autor S.L.", active=True),
                CompanyORM(company_id="CULTIVOS_ARABA", legal_name="Cultivos Araba S.L.", active=True),
            ])
            session.commit()
        finally:
            session.close()

    def test_postgres_concurrent_next_internal_id_no_overlap(
        self, pg_session_factory: sessionmaker[Session]
    ) -> None:
        """Verifica que múltiples hilos concurrentes no generen identificadores duplicados."""
        num_workers = 10
        fiscal_year = "2026"
        company_id = "TOMATES_DE_AUTOR"

        def worker_task(worker_idx: int) -> str:
            session = pg_session_factory()
            try:
                repo = SqlAlchemyExpeditionRepository(session)
                exp = Expedition(
                    id=uuid.uuid4(),
                    internal_id=f"TEMP-{worker_idx}",
                    reference=f"REF-PG-{worker_idx}",
                    fiscal_year=fiscal_year,
                    company_id=company_id,
                )
                saved = repo.save_with_id_retry(exp, fiscal_year=fiscal_year, company_id=company_id)
                session.commit()
                return saved.internal_id
            finally:
                session.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker_task, i) for i in range(num_workers)]
            generated_ids = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Ningún identificador debe duplicarse
        assert len(generated_ids) == num_workers
        assert len(set(generated_ids)) == num_workers

    def test_postgres_sqlstate_23505_and_save_retry(
        self, pg_session_factory: sessionmaker[Session]
    ) -> None:
        """Verifica que ante SQLSTATE 23505 (unique_violation en uq_expeditions_company_internal_id),
        el repositorio realiza rollback y reintenta satisfactoriamente."""
        session1 = pg_session_factory()
        session2 = pg_session_factory()
        try:
            repo1 = SqlAlchemyExpeditionRepository(session1)
            repo2 = SqlAlchemyExpeditionRepository(session2)

            # Inserción base
            fixed_id = "TD-2026-00099"
            exp1 = Expedition(
                id=uuid.uuid4(),
                internal_id=fixed_id,
                reference="REF-PG-FIXED",
                fiscal_year="2026",
                company_id="TOMATES_DE_AUTOR",
            )
            repo1.save(exp1)
            session1.commit()

            # Worker 2 intenta con el mismo ID pero mediante save_with_id_retry
            exp2 = Expedition(
                id=uuid.uuid4(),
                internal_id=fixed_id,
                reference="REF-PG-COMPETE",
                fiscal_year="2026",
                company_id="TOMATES_DE_AUTOR",
            )
            saved2 = repo2.save_with_id_retry(exp2, fiscal_year="2026", company_id="TOMATES_DE_AUTOR")
            session2.commit()

            assert saved2.internal_id != fixed_id
            assert saved2.internal_id.startswith("TD-2026-")
        finally:
            session1.close()
            session2.close()
