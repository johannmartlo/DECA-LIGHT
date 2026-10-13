from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.domain.entities.expedition import Expedition
from src.domain.enums import ExpeditionStatus, VehicleType
from src.domain.exceptions import CompanyMismatchException
from src.domain.value_objects import NIF, Matricula, Weight
from src.infrastructure.database.models import CompanyORM
from src.infrastructure.database.session import (
    Base,
    create_db_engine,
    create_session_factory,
)
from src.infrastructure.repositories.sqlalchemy_expedition_repository import (
    SqlAlchemyExpeditionRepository,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_expedition_repo.db"


@pytest.fixture
def db_engine(temp_db_path: Path):
    db_url = f"sqlite:///{temp_db_path.as_posix()}"
    engine = create_db_engine(db_url)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=10000;")
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
def seed_companies(db_session: Session) -> None:
    """Inserta empresas padre válidas para satisfacer las claves foráneas RESTRICT."""
    companies = [
        CompanyORM(
            company_id="TOMATES_DE_AUTOR",
            legal_name="Tomates de Autor S.L.",
            tax_id="B12345678",
            fiscal_address="Polígono La Redonda, Almería",
            active=True,
            document_aliases=["TOMATES AUTOR"],
        ),
        CompanyORM(
            company_id="CULTIVOS_ARABA",
            legal_name="Cultivos Araba S.L.",
            tax_id="B01999888",
            fiscal_address="Vitoria-Gasteiz",
            active=True,
            document_aliases=["CULTIVOS ARABA"],
        ),
    ]
    db_session.add_all(companies)
    db_session.flush()


@pytest.fixture
def expedition_repo(db_session: Session) -> SqlAlchemyExpeditionRepository:
    return SqlAlchemyExpeditionRepository(db_session)


# ---------------------------------------------------------------------------
# (1) Guardar y recuperar expedición completa con todos sus Value Objects
# ---------------------------------------------------------------------------
def test_save_and_get_by_id_complete(
    seed_companies: None, expedition_repo: SqlAlchemyExpeditionRepository
) -> None:
    expedition_id = uuid.uuid4()
    exp = Expedition(
        id=expedition_id,
        internal_id="TD-2026-00001",
        reference="ALB/2026/00100",
        fiscal_year="2026",
        transport_date=date(2026, 10, 15),
        company_id="TOMATES_DE_AUTOR",
        issuer_detection_confidence=0.98,
        issuer_detection_source="RULE",
        shipper_name="Tomates de Autor S.L.",
        shipper_tax_id=NIF("B12345678"),
        shipper_address="Polígono La Redonda, Almería",
        carrier_name_raw="Transportes Rápidos S.A.",
        carrier_tax_id=NIF("A99887766"),
        carrier_email="trafico@rapidos.es",
        vehicle_type=VehicleType.ARTICULADO,
        tractor_plate=Matricula("1234BBB"),
        trailer_plate=Matricula("R5678CCC"),
        origin="Almería",
        destination="Mercamadrid",
        goods="Tomates en rama",
        weight=Weight(18500.50),
        observations="Mantener refrigerado a 12°C",
        status=ExpeditionStatus.LISTA_PARA_DECA,
        extraction_metadata={"scanner": "v1.2", "page_count": 2},
    )

    saved = expedition_repo.save(exp)
    assert saved.id == expedition_id
    assert saved.internal_id == "TD-2026-00001"

    retrieved = expedition_repo.get_by_id(expedition_id)
    assert retrieved is not None
    assert retrieved.id == expedition_id
    assert retrieved.internal_id == "TD-2026-00001"
    assert retrieved.reference == "ALB/2026/00100"
    assert retrieved.fiscal_year == "2026"
    assert retrieved.transport_date == date(2026, 10, 15)
    assert retrieved.company_id == "TOMATES_DE_AUTOR"
    assert retrieved.issuer_detection_confidence == 0.98
    assert retrieved.issuer_detection_source == "RULE"
    assert retrieved.shipper_name == "Tomates de Autor S.L."

    # Validación de Value Objects reconstituidos
    assert isinstance(retrieved.shipper_tax_id, NIF)
    assert retrieved.shipper_tax_id.valor == "B12345678"
    assert isinstance(retrieved.carrier_tax_id, NIF)
    assert retrieved.carrier_tax_id.valor == "A99887766"
    assert isinstance(retrieved.tractor_plate, Matricula)
    assert retrieved.tractor_plate.valor == "1234BBB"
    assert isinstance(retrieved.trailer_plate, Matricula)
    assert retrieved.trailer_plate.valor == "R5678CCC"
    assert isinstance(retrieved.weight, Weight)
    assert retrieved.weight.kg == 18500.50
    assert retrieved.vehicle_type == VehicleType.ARTICULADO
    assert retrieved.status == ExpeditionStatus.LISTA_PARA_DECA
    assert retrieved.origin == "Almería"
    assert retrieved.destination == "Mercamadrid"
    assert retrieved.goods == "Tomates en rama"
    assert retrieved.observations == "Mantener refrigerado a 12°C"
    assert retrieved.carrier_email == "trafico@rapidos.es"
    assert retrieved.extraction_metadata == {"scanner": "v1.2", "page_count": 2}


# ---------------------------------------------------------------------------
# (2) Recuperar expedición inexistente devuelve None
# ---------------------------------------------------------------------------
def test_get_by_id_non_existent(expedition_repo: SqlAlchemyExpeditionRepository) -> None:
    assert expedition_repo.get_by_id(uuid.uuid4()) is None


# ---------------------------------------------------------------------------
# (3) Actualización de datos de una expedición existente
# ---------------------------------------------------------------------------
def test_update_existing_expedition(
    seed_companies: None, expedition_repo: SqlAlchemyExpeditionRepository
) -> None:
    exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00002",
        reference="ALB-UPD-001",
        fiscal_year="2026",
        transport_date=date(2026, 10, 16),
        company_id="TOMATES_DE_AUTOR",
        status=ExpeditionStatus.IMPORTADA,
    )
    expedition_repo.save(exp)

    # Actualizamos estado, transportista y vehículo
    exp.status = ExpeditionStatus.PENDIENTE_MATRICULA
    exp.assign_vehicle(VehicleType.RIGIDO, "9999XYZ")
    exp.update_carrier(
        carrier_name="Logística Exprés",
        carrier_tax_id="B88776655",
        carrier_email="info@expres.com",
    )
    expedition_repo.save(exp)

    retrieved = expedition_repo.get_by_id(exp.id)
    assert retrieved is not None
    assert retrieved.status == ExpeditionStatus.PENDIENTE_MATRICULA
    assert retrieved.vehicle_type == VehicleType.RIGIDO
    assert retrieved.tractor_plate is not None
    assert retrieved.tractor_plate.valor == "9999XYZ"
    assert retrieved.trailer_plate is None
    assert retrieved.carrier_name_raw == "Logística Exprés"
    assert retrieved.carrier_tax_id is not None
    assert retrieved.carrier_tax_id.valor == "B88776655"
    assert retrieved.carrier_email == "info@expres.com"


# ---------------------------------------------------------------------------
# (4) Búsqueda por referencia aislando por empresa (multiempresa)
# ---------------------------------------------------------------------------
def test_find_by_reference_tenant_isolation(
    seed_companies: None, expedition_repo: SqlAlchemyExpeditionRepository
) -> None:
    # Dos empresas distintas pueden registrar la misma referencia documental externa
    exp_tda = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00010",
        reference="ALB-DUP-777",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    exp_ara = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00011",
        reference="ALB-DUP-777",
        fiscal_year="2026",
        company_id="CULTIVOS_ARABA",
    )
    expedition_repo.save(exp_tda)
    expedition_repo.save(exp_ara)

    found_tda = expedition_repo.find_by_reference(
        reference="ALB-DUP-777", fiscal_year="2026", company_id="TOMATES_DE_AUTOR"
    )
    assert found_tda is not None
    assert found_tda.id == exp_tda.id
    assert found_tda.company_id == "TOMATES_DE_AUTOR"

    found_ara = expedition_repo.find_by_reference(
        reference="ALB-DUP-777", fiscal_year="2026", company_id="CULTIVOS_ARABA"
    )
    assert found_ara is not None
    assert found_ara.id == exp_ara.id
    assert found_ara.company_id == "CULTIVOS_ARABA"

    assert (
        expedition_repo.find_by_reference(
            reference="ALB-DUP-777", fiscal_year="2026", company_id="OTRA_EMPRESA"
        )
        is None
    )
    assert expedition_repo.find_by_reference("NO_EXISTE", "2026") is None


# ---------------------------------------------------------------------------
# (5) Búsqueda por ID interno legible TD-YYYY-NNNNN
# ---------------------------------------------------------------------------
def test_find_by_internal_id(
    seed_companies: None, expedition_repo: SqlAlchemyExpeditionRepository
) -> None:
    exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00042",
        reference="REF-INT-001",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    expedition_repo.save(exp)

    found = expedition_repo.find_by_internal_id("TD-2026-00042")
    assert found is not None
    assert found.id == exp.id
    assert found.internal_id == "TD-2026-00042"

    assert expedition_repo.find_by_internal_id("TD-2026-99999") is None


# ---------------------------------------------------------------------------
# (6) Listado de pendientes de matrícula y filtrado por empresa
# ---------------------------------------------------------------------------
def test_list_pending_vehicle_filtering(
    seed_companies: None, expedition_repo: SqlAlchemyExpeditionRepository
) -> None:
    exp_pend_tda = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00020",
        reference="P-01",
        fiscal_year="2026",
        transport_date=date(2026, 10, 10),
        company_id="TOMATES_DE_AUTOR",
        status=ExpeditionStatus.PENDIENTE_MATRICULA,
    )
    exp_pend_ara = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00021",
        reference="P-02",
        fiscal_year="2026",
        transport_date=date(2026, 10, 11),
        company_id="CULTIVOS_ARABA",
        status=ExpeditionStatus.PENDIENTE_MATRICULA,
    )
    exp_ready = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00022",
        reference="P-03",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
        status=ExpeditionStatus.LISTA_PARA_DECA,
    )
    exp_importada = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00023",
        reference="P-04",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
        status=ExpeditionStatus.IMPORTADA,
    )

    for e in (exp_pend_tda, exp_pend_ara, exp_ready, exp_importada):
        expedition_repo.save(e)

    # Global
    all_pending = expedition_repo.list_pending_vehicle()
    assert len(all_pending) == 2
    pending_ids = {p.id for p in all_pending}
    assert pending_ids == {exp_pend_tda.id, exp_pend_ara.id}

    # Filtrado por empresa
    tda_pending = expedition_repo.list_pending_vehicle(company_id="TOMATES_DE_AUTOR")
    assert len(tda_pending) == 1
    assert tda_pending[0].id == exp_pend_tda.id

    ara_pending = expedition_repo.list_pending_vehicle(company_id="CULTIVOS_ARABA")
    assert len(ara_pending) == 1
    assert ara_pending[0].id == exp_pend_ara.id

    assert expedition_repo.list_pending_vehicle(company_id="INEXISTENTE") == []


# ---------------------------------------------------------------------------
# (7) Generación consecutiva y segura de identificadores TD-YYYY-NNNNN
# ---------------------------------------------------------------------------
def test_next_internal_id_sequential_and_safe(
    seed_companies: None, expedition_repo: SqlAlchemyExpeditionRepository
) -> None:
    # 1. Base vacía para 2026
    first_id = expedition_repo.next_internal_id("2026")
    assert first_id == "TD-2026-00001"

    exp1 = Expedition(
        id=uuid.uuid4(),
        internal_id=first_id,
        reference="SEC-01",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    expedition_repo.save(exp1)

    # 2. Tras persistir el primero, el siguiente debe ser 00002
    second_id = expedition_repo.next_internal_id("2026")
    assert second_id == "TD-2026-00002"

    exp2 = Expedition(
        id=uuid.uuid4(),
        internal_id=second_id,
        reference="SEC-02",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    expedition_repo.save(exp2)

    third_id = expedition_repo.next_internal_id("2026")
    assert third_id == "TD-2026-00003"

    # 3. Ejercicio fiscal diferente tiene su propio contador
    id_2027 = expedition_repo.next_internal_id("2027")
    assert id_2027 == "TD-2027-00001"


# ---------------------------------------------------------------------------
# (8) Detección de duplicados de carga con tolerancia de peso (±0.01 kg)
# ---------------------------------------------------------------------------
def test_find_duplicate_cargo_weight_tolerance(
    seed_companies: None, expedition_repo: SqlAlchemyExpeditionRepository
) -> None:
    target_date = date(2026, 10, 20)
    exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00030",
        reference="CARGO-ORIG",
        fiscal_year="2026",
        transport_date=target_date,
        destination="Mercamadrid",
        weight=Weight(12000.50),
        company_id="TOMATES_DE_AUTOR",
    )
    expedition_repo.save(exp)

    # Coincidencia exacta
    match_exact = expedition_repo.find_duplicate_cargo(
        fiscal_year="2026",
        transport_date=target_date,
        destination="Mercamadrid",
        weight_kg=12000.50,
        company_id="TOMATES_DE_AUTOR",
    )
    assert match_exact is not None
    assert match_exact.id == exp.id

    # Coincidencia dentro de la tolerancia de ±0.01 kg
    match_plus = expedition_repo.find_duplicate_cargo(
        fiscal_year="2026",
        transport_date=target_date,
        destination="Mercamadrid",
        weight_kg=12000.508,
        company_id="TOMATES_DE_AUTOR",
    )
    assert match_plus is not None

    match_minus = expedition_repo.find_duplicate_cargo(
        fiscal_year="2026",
        transport_date=target_date,
        destination="Mercamadrid",
        weight_kg=12000.492,
        company_id="TOMATES_DE_AUTOR",
    )
    assert match_minus is not None

    # Fuera de la tolerancia (+0.05 kg)
    no_match_weight = expedition_repo.find_duplicate_cargo(
        fiscal_year="2026",
        transport_date=target_date,
        destination="Mercamadrid",
        weight_kg=12000.55,
        company_id="TOMATES_DE_AUTOR",
    )
    assert no_match_weight is None

    # Destino diferente
    no_match_dest = expedition_repo.find_duplicate_cargo(
        fiscal_year="2026",
        transport_date=target_date,
        destination="Mercabarna",
        weight_kg=12000.50,
        company_id="TOMATES_DE_AUTOR",
    )
    assert no_match_dest is None

    # Empresa diferente
    no_match_company = expedition_repo.find_duplicate_cargo(
        fiscal_year="2026",
        transport_date=target_date,
        destination="Mercamadrid",
        weight_kg=12000.50,
        company_id="CULTIVOS_ARABA",
    )
    assert no_match_company is None


# ---------------------------------------------------------------------------
# (9) Rechazo por FK inválida (empresa inexistente con PRAGMA foreign_keys=ON)
# ---------------------------------------------------------------------------
def test_foreign_key_violation_company_id(
    expedition_repo: SqlAlchemyExpeditionRepository,
) -> None:
    exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00090",
        reference="FK-FAIL",
        fiscal_year="2026",
        company_id="EMPRESA_FANTASMA",  # No existe en tabla companies
    )
    with pytest.raises(IntegrityError):
        expedition_repo.save(exp)


# ---------------------------------------------------------------------------
# (10) Rechazo por duplicidad de internal_id (restricción UNIQUE)
# ---------------------------------------------------------------------------
def test_unique_constraint_internal_id(
    seed_companies: None, expedition_repo: SqlAlchemyExpeditionRepository
) -> None:
    exp1 = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00099",
        reference="REF-U1",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    expedition_repo.save(exp1)

    exp2 = Expedition(
        id=uuid.uuid4(),  # ID distinto
        internal_id="TD-2026-00099",  # Mismo internal_id
        reference="REF-U2",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    with pytest.raises(IntegrityError):
        expedition_repo.save(exp2)


# ---------------------------------------------------------------------------
# (11) Comprobación de rollback gestionado por el invocador
# ---------------------------------------------------------------------------
def test_invoker_managed_transactional_rollback(
    seed_companies: None,
    db_session: Session,
    expedition_repo: SqlAlchemyExpeditionRepository,
) -> None:
    exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00077",
        reference="ROLLBACK-TEST",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    expedition_repo.save(exp)

    # El repositorio solo hizo flush(); el invocador controla la transacción
    db_session.rollback()

    assert expedition_repo.get_by_id(exp.id) is None
    assert expedition_repo.find_by_internal_id("TD-2026-00077") is None


# ---------------------------------------------------------------------------
# (12) Mapeo correcto de campos opcionales y vacíos
# ---------------------------------------------------------------------------
def test_save_and_get_by_id_optional_fields(
    expedition_repo: SqlAlchemyExpeditionRepository,
) -> None:
    exp_id = uuid.uuid4()
    exp = Expedition(
        id=exp_id,
        internal_id="TD-2026-00088",
        reference="MINIMAL-01",
        fiscal_year="2026",
        transport_date=date(2026, 10, 10),
        company_id="",  # Sin empresa asignada (se mapea a NULL en ORM)
        document_id=None,
        shipper_tax_id=None,
        carrier_id=None,
        carrier_tax_id=None,
        carrier_email=None,
        vehicle_type=None,
        tractor_plate=None,
        trailer_plate=None,
        weight=None,
        observations=None,
        status=ExpeditionStatus.IMPORTADA,
        extraction_metadata={},
    )

    saved = expedition_repo.save(exp)
    assert saved.id == exp_id

    retrieved = expedition_repo.get_by_id(exp_id)
    assert retrieved is not None
    assert retrieved.id == exp_id
    assert retrieved.company_id == ""
    assert retrieved.document_id is None
    assert retrieved.shipper_tax_id is None
    assert retrieved.carrier_id is None
    assert retrieved.carrier_tax_id is None
    assert retrieved.carrier_email is None
    assert retrieved.vehicle_type is None
    assert retrieved.tractor_plate is None
    assert retrieved.trailer_plate is None
    assert retrieved.weight is None
    assert retrieved.observations is None
    assert retrieved.extraction_metadata == {}


# ---------------------------------------------------------------------------
# (13) Aislamiento multiempresa: get_by_id con contexto de tenant previene IDOR
# ---------------------------------------------------------------------------
def test_cross_tenant_get_by_id_isolation(
    seed_companies: None, expedition_repo: SqlAlchemyExpeditionRepository
) -> None:
    exp_tda = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00101",
        reference="ALB-TDA-01",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    expedition_repo.save(exp_tda)

    # 1. Recuperación legítima con la empresa propietaria
    found = expedition_repo.get_by_id(exp_tda.id, company_id="TOMATES_DE_AUTOR")
    assert found is not None
    assert found.id == exp_tda.id

    # 2. Intento de acceso cruzado desde otra empresa (previene IDOR)
    cross_found = expedition_repo.get_by_id(exp_tda.id, company_id="CULTIVOS_ARABA")
    assert cross_found is None

    # 3. Intento de acceso desde tenant inexistente
    non_tenant_found = expedition_repo.get_by_id(exp_tda.id, company_id="OTRA_EMPRESA")
    assert non_tenant_found is None


# ---------------------------------------------------------------------------
# (14) Aislamiento multiempresa: find_by_internal_id con contexto de tenant
# ---------------------------------------------------------------------------
def test_cross_tenant_find_by_internal_id_isolation(
    seed_companies: None, expedition_repo: SqlAlchemyExpeditionRepository
) -> None:
    exp_tda = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00102",
        reference="ALB-TDA-02",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    expedition_repo.save(exp_tda)

    # Recuperación legítima
    assert (
        expedition_repo.find_by_internal_id("TD-2026-00102", company_id="TOMATES_DE_AUTOR")
        is not None
    )

    # Intento de acceso cruzado: otra empresa no puede ver el registro
    assert (
        expedition_repo.find_by_internal_id("TD-2026-00102", company_id="CULTIVOS_ARABA")
        is None
    )


# ---------------------------------------------------------------------------
# (15) Aislamiento multiempresa: rechazo de mutaciones cruzadas en save()
# ---------------------------------------------------------------------------
def test_cross_tenant_save_update_rejection(
    seed_companies: None, expedition_repo: SqlAlchemyExpeditionRepository
) -> None:
    exp_tda = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00103",
        reference="ALB-TDA-03",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    expedition_repo.save(exp_tda)

    # Caso a: Invocador desde el contexto de CULTIVOS_ARABA intenta modificar la expedición de TOMATES_DE_AUTOR
    with pytest.raises(CompanyMismatchException) as exc_info:
        expedition_repo.save(exp_tda, company_id="CULTIVOS_ARABA")
    assert "Aislamiento multiempresa" in str(exc_info.value)

    # Caso b: Intento de reasignar o cambiar la empresa del registro existente
    exp_tda.company_id = "CULTIVOS_ARABA"
    with pytest.raises(CompanyMismatchException) as exc_info:
        expedition_repo.save(exp_tda)
    assert "no está permitido alterar la empresa" in str(exc_info.value)

    # Caso c: Intento de eliminar la empresa (dejarla vacía) en una expedición existente
    exp_tda.company_id = ""
    with pytest.raises(CompanyMismatchException) as exc_info:
        expedition_repo.save(exp_tda)
    assert "no está permitido alterar la empresa" in str(exc_info.value)


# ---------------------------------------------------------------------------
# (16) Aislamiento multiempresa: rechazo en inserción si contexto difiere de la entidad
# ---------------------------------------------------------------------------
def test_cross_tenant_save_insert_mismatch(
    seed_companies: None, expedition_repo: SqlAlchemyExpeditionRepository
) -> None:
    new_exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00104",
        reference="ALB-TDA-04",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    with pytest.raises(CompanyMismatchException) as exc_info:
        expedition_repo.save(new_exp, company_id="CULTIVOS_ARABA")
    assert "la expedición indica empresa 'TOMATES_DE_AUTOR' pero el contexto exige 'CULTIVOS_ARABA'" in str(exc_info.value)


# ---------------------------------------------------------------------------
# (17) Concurrencia: simulación de colisión simultánea de internal_id e IntegrityError
# ---------------------------------------------------------------------------
def test_concurrent_internal_id_collision_raises_integrity_error(
    session_factory: sessionmaker[Session],
) -> None:
    # Simulamos dos workers concurrentes independientes con sesiones distintas
    session1 = session_factory()
    session2 = session_factory()
    try:
        session1.add_all([
            CompanyORM(company_id="TOMATES_DE_AUTOR", legal_name="Tomates", tax_id="B12345678", active=True),
            CompanyORM(company_id="CULTIVOS_ARABA", legal_name="Araba", tax_id="B01999888", active=True),
        ])
        session1.commit()

        repo1 = SqlAlchemyExpeditionRepository(session1)
        repo2 = SqlAlchemyExpeditionRepository(session2)

        id_worker1 = "TD-2026-00200"
        id_worker2 = "TD-2026-00200"  # Colisión simulada

        exp1 = Expedition(
            id=uuid.uuid4(),
            internal_id=id_worker1,
            reference="RACE-01",
            fiscal_year="2026",
            company_id="TOMATES_DE_AUTOR",
        )
        exp2 = Expedition(
            id=uuid.uuid4(),
            internal_id=id_worker2,
            reference="RACE-02",
            fiscal_year="2026",
            company_id="TOMATES_DE_AUTOR",
        )

        # Worker 1 guarda y confirma
        repo1.save(exp1)
        session1.commit()

        # Worker 2 intenta guardar con el mismo internal_id dentro de la misma empresa
        # La restricción física uq_expeditions_company_internal_id eleva IntegrityError
        with pytest.raises(IntegrityError):
            repo2.save(exp2)
    finally:
        session1.close()
        session2.close()


# ---------------------------------------------------------------------------
# (18) Concurrencia: recuperación ante colisión mediante rollback y reintento
# ---------------------------------------------------------------------------
def test_concurrent_internal_id_collision_retry_recovery(
    session_factory: sessionmaker[Session],
) -> None:
    session1 = session_factory()
    session2 = session_factory()
    try:
        session1.add(
            CompanyORM(company_id="TOMATES_DE_AUTOR", legal_name="Tomates", tax_id="B12345678", active=True)
        )
        session1.commit()

        repo1 = SqlAlchemyExpeditionRepository(session1)
        repo2 = SqlAlchemyExpeditionRepository(session2)

        # Worker 1 toma TD-2026-00300 y persiste
        exp1 = Expedition(
            id=uuid.uuid4(),
            internal_id="TD-2026-00300",
            reference="RETRY-01",
            fiscal_year="2026",
            company_id="TOMATES_DE_AUTOR",
        )
        repo1.save(exp1)
        session1.commit()

        # Worker 2 tenía preparado TD-2026-00300 por concurrencia dentro de la misma empresa
        exp2 = Expedition(
            id=uuid.uuid4(),
            internal_id="TD-2026-00300",
            reference="RETRY-02",
            fiscal_year="2026",
            company_id="TOMATES_DE_AUTOR",
        )

        # Intento 1: colisión
        with pytest.raises(IntegrityError):
            repo2.save(exp2)

        # Recuperación en la capa superior (Unit of Work / Use Case pattern):
        # 1. Rollback de la transacción fallida
        session2.rollback()

        # 2. Re-consulta del siguiente identificador atómico disponible para la empresa
        new_internal_id = repo2.next_internal_id("2026", company_id="TOMATES_DE_AUTOR")
        assert new_internal_id == "TD-2026-00301"

        # 3. Asignación del nuevo identificador y reintento
        exp2.internal_id = new_internal_id
        saved2 = repo2.save(exp2)
        session2.commit()

        # Verificación: ambos registros persisten sin corrupción ni pérdida de datos
        assert saved2.internal_id == "TD-2026-00301"
        assert repo1.find_by_internal_id("TD-2026-00300", company_id="TOMATES_DE_AUTOR") is not None
        assert repo2.find_by_internal_id("TD-2026-00301", company_id="TOMATES_DE_AUTOR") is not None
    finally:
        session1.close()
        session2.close()


# ---------------------------------------------------------------------------
# (19) save_with_id_retry: reintento automático exitoso ante colisión de internal_id
# ---------------------------------------------------------------------------
def test_save_with_id_retry_success_after_collision(
    session_factory: sessionmaker[Session],
) -> None:
    session1 = session_factory()
    session2 = session_factory()
    try:
        session1.add(
            CompanyORM(company_id="TOMATES_DE_AUTOR", legal_name="Tomates", tax_id="B12345678", active=True)
        )
        session1.commit()

        repo1 = SqlAlchemyExpeditionRepository(session1)
        repo2 = SqlAlchemyExpeditionRepository(session2)

        # Worker 1 guarda con internal_id TD-2026-00400
        exp1 = Expedition(
            id=uuid.uuid4(),
            internal_id="TD-2026-00400",
            reference="COLLIDE-01",
            fiscal_year="2026",
            company_id="TOMATES_DE_AUTOR",
        )
        repo1.save(exp1)
        session1.commit()

        # Worker 2 intenta guardar inicialmente con el mismo TD-2026-00400 usando save_with_id_retry
        exp2 = Expedition(
            id=uuid.uuid4(),
            internal_id="TD-2026-00400",
            reference="COLLIDE-02",
            fiscal_year="2026",
            company_id="TOMATES_DE_AUTOR",
        )
        saved2 = repo2.save_with_id_retry(exp2, fiscal_year="2026", company_id="TOMATES_DE_AUTOR")
        session2.commit()

        # El reintento debió detectar la colisión de internal_id, generar TD-2026-00401 y persistir
        assert saved2.internal_id == "TD-2026-00401"
        assert repo2.find_by_internal_id("TD-2026-00401", company_id="TOMATES_DE_AUTOR") is not None
    finally:
        session1.close()
        session2.close()


# ---------------------------------------------------------------------------
# (20) save_with_id_retry: error de clave foránea NO es reintentado
# ---------------------------------------------------------------------------
def test_save_with_id_retry_rejects_foreign_key_violation_without_retry(
    expedition_repo: SqlAlchemyExpeditionRepository,
) -> None:
    # Expedición con empresa no existente en la base de datos (viola FK company_id)
    exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00500",
        reference="NO-FK-01",
        fiscal_year="2026",
        company_id="EMPRESA_FANTASMA",
    )
    with pytest.raises(IntegrityError) as exc_info:
        expedition_repo.save_with_id_retry(exp, fiscal_year="2026")

    # Verifica que el error se propagó y no fue tratado como colisión de internal_id
    assert "foreign key" in str(exc_info.value).lower() or "foreignkey" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# (21) save_with_id_retry: propagación al superar max_retries
# ---------------------------------------------------------------------------
def test_save_with_id_retry_exceeds_max_retries(
    seed_companies: None, expedition_repo: SqlAlchemyExpeditionRepository, monkeypatch
) -> None:
    exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00600",
        reference="MAX-RETRY-01",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    expedition_repo.save(exp)

    # Forzar que next_internal_id siga retornando el mismo id colisionado
    monkeypatch.setattr(expedition_repo, "next_internal_id", lambda fy, **kwargs: "TD-2026-00600")

    exp2 = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00600",
        reference="MAX-RETRY-02",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    with pytest.raises(IntegrityError):
        expedition_repo.save_with_id_retry(exp2, fiscal_year="2026", max_retries=2)


# ---------------------------------------------------------------------------
# (22) Multiempresa: empresas distintas pueden compartir el mismo internal_id
# ---------------------------------------------------------------------------
def test_different_companies_can_share_same_internal_id(
    session_factory: sessionmaker[Session],
) -> None:
    session = session_factory()
    try:
        session.add_all([
            CompanyORM(company_id="TOMATES_DE_AUTOR", legal_name="Tomates", tax_id="B12345678", active=True),
            CompanyORM(company_id="CULTIVOS_ARABA", legal_name="Araba", tax_id="B01999888", active=True),
        ])
        session.commit()
        repo = SqlAlchemyExpeditionRepository(session)

        exp1 = Expedition(
            id=uuid.uuid4(),
            internal_id="TD-2026-00001",
            reference="EXP-TOM-01",
            fiscal_year="2026",
            company_id="TOMATES_DE_AUTOR",
        )
        exp2 = Expedition(
            id=uuid.uuid4(),
            internal_id="TD-2026-00001",
            reference="EXP-ARA-01",
            fiscal_year="2026",
            company_id="CULTIVOS_ARABA",
        )
        repo.save(exp1)
        repo.save(exp2)
        session.commit()

        tom_res = repo.find_by_internal_id("TD-2026-00001", company_id="TOMATES_DE_AUTOR")
        ara_res = repo.find_by_internal_id("TD-2026-00001", company_id="CULTIVOS_ARABA")
        assert tom_res is not None and tom_res.reference == "EXP-TOM-01"
        assert ara_res is not None and ara_res.reference == "EXP-ARA-01"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# (23) save_with_id_retry: savepoint preserva objetos previos de la transacción externa tras colisión
# ---------------------------------------------------------------------------
def test_save_with_id_retry_preserves_outer_transaction_state(
    session_factory: sessionmaker[Session],
) -> None:
    """Verifica que el uso de savepoints (begin_nested) dentro de save_with_id_retry
    permita recuperarse de una colisión de internal_id SIN hacer rollback de la transacción
    externa ni destruir objetos previamente registrados/flusheados en la misma sesión."""
    session = session_factory()
    try:
        session.add(
            CompanyORM(company_id="TOMATES_DE_AUTOR", legal_name="Tomates", tax_id="B12345678", active=True)
        )
        session.commit()

        repo = SqlAlchemyExpeditionRepository(session)

        # 1. Crear expedición existente con internal_id TD-2026-00700
        exp_first = Expedition(
            id=uuid.uuid4(),
            internal_id="TD-2026-00700",
            reference="FIRST-01",
            fiscal_year="2026",
            company_id="TOMATES_DE_AUTOR",
        )
        repo.save(exp_first)
        session.commit()

        # 2. En una nueva transacción de sesión, guardar una entidad previa (flusheada, no committeada)
        exp_previa = Expedition(
            id=uuid.uuid4(),
            internal_id="TD-2026-00750",
            reference="PREV-IN-TX",
            fiscal_year="2026",
            company_id="TOMATES_DE_AUTOR",
        )
        repo.save(exp_previa)
        # exp_previa está pendiente en la sesión/transacción activa

        # 3. Guardar una tercera expedición que intente usar el internal_id colisionado TD-2026-00700
        exp_collide = Expedition(
            id=uuid.uuid4(),
            internal_id="TD-2026-00700",
            reference="COLLIDE-RETRY",
            fiscal_year="2026",
            company_id="TOMATES_DE_AUTOR",
        )
        saved = repo.save_with_id_retry(exp_collide, fiscal_year="2026", company_id="TOMATES_DE_AUTOR")

        # 4. El reintento debió generar el siguiente número disponible sin romper la sesión
        assert saved.internal_id == "TD-2026-00751"

        # 5. Commit de la transacción externa completa
        session.commit()

        # 6. VERIFICACIÓN CRÍTICA: exp_previa NO fue destruida por un rollback global
        assert repo.get_by_id(exp_previa.id, company_id="TOMATES_DE_AUTOR") is not None
        assert repo.get_by_id(exp_collide.id, company_id="TOMATES_DE_AUTOR") is not None
    finally:
        session.close()

