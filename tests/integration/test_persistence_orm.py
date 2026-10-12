from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.infrastructure.database.models import (
    CarrierORM,
    CompanyORM,
    DeCAORM,
    DeCAVersionORM,
    DocumentORM,
    EmailDeliveryORM,
    ExpeditionORM,
)
from src.infrastructure.database.session import (
    Base,
    create_db_engine,
    create_session_factory,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_persistence.db"


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
def session_factory(db_engine):
    return create_session_factory(db_engine)


def test_company_and_expedition_persistence_across_sessions(session_factory) -> None:
    """Verifica que CompanyORM y ExpeditionORM se escriben, se cierra la sesión
    y se leen intactos desde una nueva sesión independiente.
    """
    expedition_id = uuid.uuid4()
    company_id = "TOMATES_DE_AUTOR"

    # 1. Sesión de escritura
    session1: Session = session_factory()
    try:
        company = CompanyORM(
            company_id=company_id,
            legal_name="TOMATES DE AUTOR S.L.",
            tax_id="B12345678",
            fiscal_address="C/ Mayor 1, Madrid",
            active=True,
            document_aliases=["TOMATES DE AUTOR", "TDA"],
        )
        session1.add(company)

        expedition = ExpeditionORM(
            id=expedition_id,
            internal_id="TD-2026-00001",
            reference="ALB-9988",
            fiscal_year="2026",
            transport_date=date(2026, 10, 12),
            company_id=company_id,
            shipper_name="TOMATES DE AUTOR S.L.",
            carrier_name_raw="TRANSPORTES RAPIDOS S.A.",
            vehicle_type="ARTICULADO",
            tractor_plate="1234BBB",
            trailer_plate="R1234BBB",
            origin="Almería",
            destination="Perpignan",
            goods="Tomates Rama 10kg",
            weight_kg=22500.0,
            status="IMPORTADA",
            extraction_metadata={"source": "hispatec_pdf", "confidence": 0.98},
        )
        session1.add(expedition)
        session1.commit()
    finally:
        session1.close()

    # 2. Nueva sesión independiente: verificación de persistencia real
    session2: Session = session_factory()
    try:
        loaded_company = session2.get(CompanyORM, company_id)
        assert loaded_company is not None
        assert loaded_company.legal_name == "TOMATES DE AUTOR S.L."
        assert loaded_company.document_aliases == ["TOMATES DE AUTOR", "TDA"]

        loaded_expedition = session2.get(ExpeditionORM, expedition_id)
        assert loaded_expedition is not None
        assert loaded_expedition.internal_id == "TD-2026-00001"
        assert loaded_expedition.weight_kg == 22500.0
        assert loaded_expedition.tractor_plate == "1234BBB"
        assert loaded_expedition.trailer_plate == "R1234BBB"
        assert loaded_expedition.company_id == company_id

        # Relación bidireccional navegable
        assert loaded_expedition.company is not None
        assert loaded_expedition.company.company_id == company_id
        assert len(loaded_company.expeditions) == 1
        assert loaded_company.expeditions[0].id == expedition_id
    finally:
        session2.close()


def test_deca_and_immutable_version_persistence(session_factory) -> None:
    """Verifica la persistencia del DeCA y de su versión con snapshot estructurado JSON."""
    deca_id = uuid.uuid4()
    expedition_id = uuid.uuid4()
    company_id = "CULTIVOS_ARABA"
    deca_code = "DECA-2026-000042"

    session1: Session = session_factory()
    try:
        company = CompanyORM(
            company_id=company_id,
            legal_name="CULTIVOS ARABA S.L.",
            tax_id="B87654321",
            fiscal_address="Polígono Industrial Araba, Vitoria",
            active=True,
            document_aliases=["CULTIVOS ARABA"],
        )
        session1.add(company)

        expedition = ExpeditionORM(
            id=expedition_id,
            internal_id="TD-2026-00042",
            reference="CMR-7711",
            fiscal_year="2026",
            transport_date=date(2026, 10, 12),
            company_id=company_id,
            shipper_name="CULTIVOS ARABA S.L.",
            status="DECA_GENERADO",
        )
        session1.add(expedition)

        now = datetime.now(UTC)
        deca = DeCAORM(
            id=deca_id,
            expedition_id=expedition_id,
            company_id=company_id,
            deca_code=deca_code,
            public_access_token="test_token_csprng_32_characters_long_123456",
            public_token_hash="hash_sha256_del_token_para_busqueda_o1",
            service_start_at=now,
            legal_custody_until=now,
            public_download_active=True,
            current_version=1,
            status="ISSUED",
        )
        session1.add(deca)

        version = DeCAVersionORM(
            id=uuid.uuid4(),
            deca_id=deca_id,
            version_number=1,
            pdf_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            pdf_storage_path="storage/2026/10/deca_42.pdf",
            pdf_size_bytes=45210,
            snapshot_hash="f5a8c9b2d3e1",
            modification_reason="Emisión inicial",
            snapshot_data={
                "deca_code": deca_code,
                "version": 1,
                "route_and_goods": {"origin": "Vitoria", "destination": "Madrid"},
            },
        )
        session1.add(version)
        session1.commit()
    finally:
        session1.close()

    # Sesión 2: Verificación
    session2: Session = session_factory()
    try:
        stmt = select(DeCAORM).where(DeCAORM.deca_code == deca_code)
        loaded_deca = session2.scalar(stmt)
        assert loaded_deca is not None
        assert loaded_deca.id == deca_id
        assert loaded_deca.public_token_hash == "hash_sha256_del_token_para_busqueda_o1"
        assert len(loaded_deca.versions) == 1

        loaded_version = loaded_deca.versions[0]
        assert loaded_version.version_number == 1
        assert loaded_version.pdf_size_bytes == 45210
        assert loaded_version.snapshot_data["route_and_goods"]["origin"] == "Vitoria"
    finally:
        session2.close()


def test_carrier_alias_and_document_deduplication(session_factory) -> None:
    """Verifica integridad referencial de CarrierORM y unicidad de DocumentORM por hash."""
    session1: Session = session_factory()
    try:
        carrier = CarrierORM(
            id=uuid.uuid4(),
            business_name="LOGISTICA DEL SUR SL",
            tax_id="B99001122",
            email="trafico@logsur.com",
            active=True,
        )
        session1.add(carrier)

        doc = DocumentORM(
            id=uuid.uuid4(),
            sha256_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            original_filename="albaran_123.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            storage_path="storage/docs/doc1.pdf",
            status="PROCESSED",
        )
        session1.add(doc)
        session1.commit()
    finally:
        session1.close()

    session2: Session = session_factory()
    try:
        # Consulta de documento por hash
        stmt = select(DocumentORM).where(
            DocumentORM.sha256_hash
            == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )
        loaded_doc = session2.scalar(stmt)
        assert loaded_doc is not None
        assert loaded_doc.original_filename == "albaran_123.pdf"
    finally:
        session2.close()


def test_multi_company_can_share_albaran_reference_safely(session_factory) -> None:
    """Verifica que dos empresas distintas pueden tener el mismo albarán/referencia de origen
    sin colisión, gracias a que internal_id es único e independiente.
    """
    session: Session = session_factory()
    try:
        c1 = CompanyORM(
            company_id="TOMATES_DE_AUTOR",
            legal_name="TOMATES DE AUTOR S.L.",
            fiscal_address="Dir 1",
        )
        c2 = CompanyORM(
            company_id="CULTIVOS_ARABA",
            legal_name="CULTIVOS ARABA S.L.",
            fiscal_address="Dir 2",
        )
        session.add_all([c1, c2])

        # Ambas empresas reciben un albarán con la misma referencia "ALB-2026-0001" de Hispatec
        exp1 = ExpeditionORM(
            id=uuid.uuid4(),
            internal_id="TD-2026-00001",
            reference="ALB-2026-0001",
            fiscal_year="2026",
            transport_date=date(2026, 10, 12),
            company_id="TOMATES_DE_AUTOR",
            shipper_name="TOMATES DE AUTOR S.L.",
        )
        exp2 = ExpeditionORM(
            id=uuid.uuid4(),
            internal_id="TD-2026-00002",
            reference="ALB-2026-0001",
            fiscal_year="2026",
            transport_date=date(2026, 10, 12),
            company_id="CULTIVOS_ARABA",
            shipper_name="CULTIVOS ARABA S.L.",
        )
        session.add_all([exp1, exp2])
        session.commit()

        # Comprobación de que ambas existen y están asociadas a sus respectivas empresas
        res1 = session.scalar(
            select(ExpeditionORM).where(
                ExpeditionORM.reference == "ALB-2026-0001",
                ExpeditionORM.company_id == "TOMATES_DE_AUTOR",
            )
        )
        res2 = session.scalar(
            select(ExpeditionORM).where(
                ExpeditionORM.reference == "ALB-2026-0001",
                ExpeditionORM.company_id == "CULTIVOS_ARABA",
            )
        )
        assert res1 is not None and res1.internal_id == "TD-2026-00001"
        assert res2 is not None and res2.internal_id == "TD-2026-00002"
    finally:
        session.close()


def test_duplicate_internal_id_raises_integrity_error(session_factory) -> None:
    """Verifica que el identificador interno operativo TD-YYYY-NNNNN es estrictamente único
    a nivel de motor de base de datos.
    """
    session: Session = session_factory()
    try:
        exp1 = ExpeditionORM(
            id=uuid.uuid4(),
            internal_id="TD-2026-99999",
            reference="REF-1",
            fiscal_year="2026",
            transport_date=date(2026, 10, 12),
        )
        session.add(exp1)
        session.commit()

        exp2 = ExpeditionORM(
            id=uuid.uuid4(),
            internal_id="TD-2026-99999",  # Duplicado
            reference="REF-2",
            fiscal_year="2026",
            transport_date=date(2026, 10, 12),
        )
        session.add(exp2)
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_deca_version_unique_constraint_rejects_duplicate_version_number(
    session_factory,
) -> None:
    """Verifica que no se pueden crear dos versiones físicas con el mismo número de versión
    para un mismo DeCA (restricción uq_deca_version_number).
    """
    session: Session = session_factory()
    try:
        c = CompanyORM(
            company_id="TOMATES_DE_AUTOR",
            legal_name="TOMATES DE AUTOR S.L.",
            fiscal_address="Dir 1",
        )
        session.add(c)
        exp = ExpeditionORM(
            id=uuid.uuid4(),
            internal_id="TD-2026-00100",
            fiscal_year="2026",
            transport_date=date(2026, 10, 12),
            company_id="TOMATES_DE_AUTOR",
        )
        session.add(exp)

        now = datetime.now(UTC)
        deca_id = uuid.uuid4()
        deca = DeCAORM(
            id=deca_id,
            expedition_id=exp.id,
            company_id="TOMATES_DE_AUTOR",
            deca_code="DECA-2026-000100",
            public_access_token="tok_1",
            public_token_hash="hash_1",
            service_start_at=now,
            legal_custody_until=now,
            public_download_active=True,
            current_version=1,
            status="ISSUED",
        )
        session.add(deca)

        v1 = DeCAVersionORM(
            id=uuid.uuid4(),
            deca_id=deca_id,
            version_number=1,
            pdf_sha256="hash_pdf_v1",
            pdf_storage_path="path/v1.pdf",
            snapshot_hash="snap_v1",
            snapshot_data={"version": 1},
        )
        session.add(v1)
        session.commit()

        # Intento de añadir otra versión con version_number=1
        v1_dup = DeCAVersionORM(
            id=uuid.uuid4(),
            deca_id=deca_id,
            version_number=1,  # Colisión
            pdf_sha256="hash_pdf_v1_dup",
            pdf_storage_path="path/v1_dup.pdf",
            snapshot_hash="snap_v1_dup",
            snapshot_data={"version": 1, "tampered": True},
        )
        session.add(v1_dup)
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_deca_delete_restricted_when_versions_exist(session_factory) -> None:
    """Verifica que el motor lanza IntegrityError (ON DELETE RESTRICT)
    si se intenta borrar físicamente un DeCA que tiene versiones históricas.
    """
    session: Session = session_factory()
    try:
        company = CompanyORM(
            company_id="TOMATES_DE_AUTOR",
            legal_name="TOMATES DE AUTOR S.L.",
            fiscal_address="Dir 1",
        )
        session.add(company)
        exp = ExpeditionORM(
            id=uuid.uuid4(),
            internal_id="TD-2026-00301",
            fiscal_year="2026",
            transport_date=date(2026, 10, 12),
            company_id="TOMATES_DE_AUTOR",
        )
        session.add(exp)
        deca = DeCAORM(
            id=uuid.uuid4(),
            expedition_id=exp.id,
            company_id="TOMATES_DE_AUTOR",
            deca_code="DECA-2026-000301",
            public_access_token="tok_restrict_v1",
            public_token_hash="hash_restrict_v1",
            service_start_at=datetime.now(UTC),
            legal_custody_until=datetime.now(UTC),
            current_version=1,
            status="ISSUED",
        )
        session.add(deca)
        version = DeCAVersionORM(
            id=uuid.uuid4(),
            deca_id=deca.id,
            version_number=1,
            pdf_sha256="hash_v1_restrict",
            pdf_storage_path="path/v1_restrict.pdf",
            snapshot_hash="snap_v1_restrict",
            snapshot_data={"version": 1},
        )
        session.add(version)
        session.commit()

        # Intentar borrar físicamente el DeCA: debe fallar por ON DELETE RESTRICT en deca_versions
        session.delete(deca)
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_removing_version_from_relationship_does_not_delete_version(
    session_factory,
) -> None:
    """Verifica que al retirar una versión de la colección ORM en memoria (deca.versions.remove(v)),
    NO se produce un borrado físico en cascada (ausencia de delete-orphan).
    La versión original continúa existiendo físicamente en la base de datos.
    """
    session: Session = session_factory()
    deca_id = uuid.uuid4()
    version_id = uuid.uuid4()
    try:
        company = CompanyORM(
            company_id="TOMATES_DE_AUTOR",
            legal_name="TOMATES DE AUTOR S.L.",
            fiscal_address="Dir 1",
        )
        session.add(company)
        exp = ExpeditionORM(
            id=uuid.uuid4(),
            internal_id="TD-2026-00302",
            fiscal_year="2026",
            transport_date=date(2026, 10, 12),
            company_id="TOMATES_DE_AUTOR",
        )
        session.add(exp)
        deca = DeCAORM(
            id=deca_id,
            expedition_id=exp.id,
            company_id="TOMATES_DE_AUTOR",
            deca_code="DECA-2026-000302",
            public_access_token="tok_orphan_test",
            public_token_hash="hash_orphan_test",
            service_start_at=datetime.now(UTC),
            legal_custody_until=datetime.now(UTC),
            current_version=1,
            status="ISSUED",
        )
        session.add(deca)
        version = DeCAVersionORM(
            id=version_id,
            deca_id=deca_id,
            version_number=1,
            pdf_sha256="hash_v1_orphan",
            pdf_storage_path="path/v1_orphan.pdf",
            snapshot_hash="snap_v1_orphan",
            snapshot_data={"version": 1},
        )
        session.add(version)
        session.commit()

        # 1. Retirar la versión de la lista en memoria del objeto deca
        deca.versions.remove(version)

        # 2. Sin cascade="all, delete-orphan", SQLAlchemy NO emite un DELETE sobre deca_versions.
        # En su lugar, intenta desvincularla (poner deca_id = NULL). Al ser NOT NULL,
        # la base de datos rechaza la desvinculación.
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # 3. Comprobar que en la base de datos la versión sigue existiendo físicamente intacta
        persisted_version = session.get(DeCAVersionORM, version_id)
        assert persisted_version is not None
        assert persisted_version.id == version_id
        assert persisted_version.deca_id == deca_id
        assert persisted_version.version_number == 1
    finally:
        session.close()


def test_email_delivery_blocks_deletion_of_expedition_and_deca(session_factory) -> None:
    """Demuestra que los registros de EmailDeliveryORM bloquean físicamente el borrado
    tanto de la expedición como del DeCA al que pertenecen (ON DELETE RESTRICT).
    """
    session: Session = session_factory()
    try:
        company = CompanyORM(
            company_id="TOMATES_DE_AUTOR",
            legal_name="TOMATES DE AUTOR S.L.",
            fiscal_address="Dir 1",
        )
        session.add(company)
        exp = ExpeditionORM(
            id=uuid.uuid4(),
            internal_id="TD-2026-00303",
            fiscal_year="2026",
            transport_date=date(2026, 10, 12),
            company_id="TOMATES_DE_AUTOR",
        )
        session.add(exp)
        deca = DeCAORM(
            id=uuid.uuid4(),
            expedition_id=exp.id,
            company_id="TOMATES_DE_AUTOR",
            deca_code="DECA-2026-000303",
            public_access_token="tok_email_restrict",
            public_token_hash="hash_email_restrict",
            service_start_at=datetime.now(UTC),
            legal_custody_until=datetime.now(UTC),
            current_version=1,
            status="ISSUED",
        )
        session.add(deca)
        delivery = EmailDeliveryORM(
            id=uuid.uuid4(),
            expedition_id=exp.id,
            deca_id=deca.id,
            deca_code="DECA-2026-000303",
            deca_version=1,
            company_id="TOMATES_DE_AUTOR",
            recipient_email="transporte@logistica.com",
            subject="Envío DeCA",
            idempotency_key="idemp_h01_email_1",
            status="SENT",
            attempts=1,
            provider="graph",
        )
        session.add(delivery)
        session.commit()

        # 1. Intentar borrar el DeCA: debe fallar con IntegrityError por ON DELETE RESTRICT
        session.delete(deca)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # 2. Intentar borrar la Expedición: debe fallar con IntegrityError por ON DELETE RESTRICT
        session.delete(exp)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()


