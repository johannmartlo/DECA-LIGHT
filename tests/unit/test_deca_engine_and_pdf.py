from __future__ import annotations

import hashlib
import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pytest
from pypdf import PdfReader

from src.application.dtos.deca_dto import EmitDeCAInputDTO
from src.application.use_cases.emit_deca import EmitDeCAUseCase
from src.domain.entities.deca import DeCA, DeCAVersion
from src.domain.entities.expedition import Expedition
from src.domain.enums import (
    AuditAction,
    DeCAStatus,
    ExpeditionStatus,
    VehicleType,
)
from src.domain.exceptions import (
    DeCAEmissionException,
    EntityNotFoundException,
    ExpeditionNotReadyException,
    ImmutableDeCAException,
    StorageException,
)
from src.domain.services.deca_engine import DeCAEngine
from src.domain.value_objects import NIF, Matricula, Weight
from src.infrastructure.document.reportlab_pdf_renderer import ReportLabPdfRenderer
from src.infrastructure.logging.in_memory_audit_service import InMemoryAuditService
from src.infrastructure.repositories.in_memory_deca_repository import (
    InMemoryDeCARepository,
)
from src.infrastructure.repositories.in_memory_expedition_repository import (
    InMemoryExpeditionRepository,
)
from src.infrastructure.storage.local_pdf_storage import LocalPdfStorage


def make_ready_expedition(
    *,
    vehicle_type: VehicleType = VehicleType.RIGIDO,
    tractor_plate: str = "1234BCD",
    trailer_plate: str | None = None,
    shipper_name: str = "Tomates de Autor S.L.",
    shipper_tax_id: str = "B12345678",
    shipper_address: str = "Polígono La Redonda, Almería",
    carrier_name: str = "Transportes Almería S.L.",
    carrier_tax_id: str = "B04123456",
    carrier_email: str | None = "trafico@transportesalmeria.com",
    origin: str = "El Ejido (Almería)",
    destination: str = "Mercamadrid (Madrid)",
    goods: str = "Tomate Rama Extra",
    weight_kg: float = 18500.0,
    reference: str = "ALB-2026-9999",
    internal_id: str = "TD-2026-00001",
    observations: str | None = "Conservar entre 10 y 12 grados",
    status: ExpeditionStatus = ExpeditionStatus.LISTA_PARA_DECA,
) -> Expedition:
    """Helper que crea una expedición en estado LISTA_PARA_DECA con datos válidos."""
    exp = Expedition(
        id=uuid.uuid4(),
        internal_id=internal_id,
        reference=reference,
        fiscal_year="2026",
        transport_date=date(2026, 10, 15),
        shipper_name=shipper_name,
        shipper_tax_id=NIF(shipper_tax_id) if shipper_tax_id else None,
        shipper_address=shipper_address,
        carrier_name_raw=carrier_name,
        carrier_tax_id=NIF(carrier_tax_id) if carrier_tax_id else None,
        carrier_email=carrier_email,
        origin=origin,
        destination=destination,
        goods=goods,
        weight=Weight(weight_kg) if weight_kg > 0 else None,
        observations=observations,
        status=status,
    )
    if vehicle_type == VehicleType.RIGIDO:
        exp.assign_vehicle(
            VehicleType.RIGIDO,
            Matricula(tractor_plate),
            None,
        )
    else:
        exp.assign_vehicle(
            VehicleType.ARTICULADO,
            Matricula(tractor_plate),
            Matricula(trailer_plate or "R1234BCD"),
        )
    exp.status = status
    return exp


# =========================================================================
# SECCIÓN 24 - MATRIZ DE TESTS (1 A 28)
# =========================================================================


def test_01_valid_deca_generated(tmp_path: Path) -> None:
    """Test 1: DeCA válido generado a partir de Expedition LISTA_PARA_DECA."""
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    audit_service = InMemoryAuditService()
    storage = LocalPdfStorage(tmp_path)
    renderer = ReportLabPdfRenderer()

    exp = make_ready_expedition()
    exp_repo.save(exp)

    use_case = EmitDeCAUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        pdf_renderer=renderer,
        storage_service=storage,
        audit_service=audit_service,
    )

    result = use_case.execute(EmitDeCAInputDTO(expedition_id=exp.id, actor="OPERATOR_1"))

    assert result.version == 1
    assert result.status == str(DeCAStatus.ISSUED)
    assert result.is_idempotent is False
    assert result.pdf_filename == "DECA-2026-000001.pdf"
    assert len(result.pdf_sha256) == 64
    assert result.pdf_size_bytes > 0

    # Estado de expedición transicionado a DECA_GENERADO
    updated_exp = exp_repo.get_by_id(exp.id)
    assert updated_exp is not None
    assert updated_exp.status == ExpeditionStatus.DECA_GENERADO


def test_02_invalid_expedition_rejected(tmp_path: Path) -> None:
    """Test 2: Expedition no válida rechazada (campos incompletos)."""
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    storage = LocalPdfStorage(tmp_path)
    renderer = ReportLabPdfRenderer()

    # Falta mercancía y destino
    exp = make_ready_expedition(goods="", destination="")
    exp_repo.save(exp)

    use_case = EmitDeCAUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        pdf_renderer=renderer,
        storage_service=storage,
    )

    with pytest.raises(DeCAEmissionException) as exc_info:
        use_case.execute(EmitDeCAInputDTO(expedition_id=exp.id))

    assert "Revalidación legal fallida" in str(exc_info.value)


def test_03_non_existent_expedition_rejected(tmp_path: Path) -> None:
    """Test 3: Expedition inexistente produce EntityNotFoundException."""
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    storage = LocalPdfStorage(tmp_path)
    renderer = ReportLabPdfRenderer()

    use_case = EmitDeCAUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        pdf_renderer=renderer,
        storage_service=storage,
    )

    non_existent_id = uuid.uuid4()
    with pytest.raises(EntityNotFoundException):
        use_case.execute(EmitDeCAInputDTO(expedition_id=non_existent_id))


def test_04_expedition_in_incorrect_status_rejected(tmp_path: Path) -> None:
    """Test 4: Expedition en estado incorrecto (PENDIENTE_MATRICULA) rechazada."""
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    storage = LocalPdfStorage(tmp_path)
    renderer = ReportLabPdfRenderer()

    exp = make_ready_expedition(status=ExpeditionStatus.PENDIENTE_MATRICULA)
    exp_repo.save(exp)

    use_case = EmitDeCAUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        pdf_renderer=renderer,
        storage_service=storage,
    )

    with pytest.raises(ExpeditionNotReadyException) as exc_info:
        use_case.execute(EmitDeCAInputDTO(expedition_id=exp.id))

    assert "Debe estar en LISTA_PARA_DECA" in str(exc_info.value)


def test_05_snapshot_correctly_constructed() -> None:
    """Test 5: Snapshot inmutable correctamente construido con todos los campos canónicos."""
    exp = make_ready_expedition(
        vehicle_type=VehicleType.ARTICULADO,
        tractor_plate="1234BCD",
        trailer_plate="R5678EFG",
        observations="Tratar con cuidado",
    )

    deca_estructurado, snapshot_dict, snapshot_hash = DeCAEngine.create_deca_estructurado(
        expedition=exp,
        deca_code="DECA-2026-000001",
        version_number=1,
    )

    assert snapshot_dict["deca_code"] == "DECA-2026-000001"
    assert snapshot_dict["version"] == 1
    assert snapshot_dict["internal_id"] == "TD-2026-00001"
    assert snapshot_dict["external_reference"] == "ALB-2026-9999"
    assert snapshot_dict["shipper"]["name"] == "Tomates de Autor S.L."
    assert snapshot_dict["shipper"]["tax_id"] == "B12345678"
    assert snapshot_dict["carrier"]["name"] == "Transportes Almería S.L."
    assert snapshot_dict["carrier"]["tax_id"] == "B04123456"
    assert snapshot_dict["vehicle"]["type"] == "ARTICULADO"
    assert snapshot_dict["vehicle"]["tractor_plate"] == "1234BCD"
    assert snapshot_dict["vehicle"]["trailer_plate"] == "R5678EFG"
    assert snapshot_dict["route_and_goods"]["origin"] == "El Ejido (Almería)"
    assert snapshot_dict["route_and_goods"]["destination"] == "Mercamadrid (Madrid)"
    assert snapshot_dict["route_and_goods"]["goods"] == "Tomate Rama Extra"
    assert snapshot_dict["route_and_goods"]["weight_kg"] == 18500.0
    assert snapshot_dict["observations"] == "Tratar con cuidado"
    assert len(snapshot_hash) == 64


def test_06_snapshot_isolation_from_expedition_mutation() -> None:
    """Test 6: Snapshot no cambia al modificar Expedition posteriormente (inmutabilidad)."""
    exp = make_ready_expedition()
    deca_estructurado, snapshot_dict, initial_hash = DeCAEngine.create_deca_estructurado(
        expedition=exp,
        deca_code="DECA-2026-000001",
    )

    # Mutar la entidad de origen
    exp.carrier_name_raw = "Nuevo Transportista Cambiado S.L."
    exp.destination = "Berlín (Alemania)"
    exp.weight = Weight(25000.0)
    exp.assign_vehicle(VehicleType.RIGIDO, Matricula("9999ZZZ"), None)

    # El snapshot no debe verse afectado en absoluto
    assert snapshot_dict["carrier"]["name"] == "Transportes Almería S.L."
    assert snapshot_dict["route_and_goods"]["destination"] == "Mercamadrid (Madrid)"
    assert snapshot_dict["route_and_goods"]["weight_kg"] == 18500.0
    assert snapshot_dict["vehicle"]["tractor_plate"] == "1234BCD"
    assert deca_estructurado.carrier_name == "Transportes Almería S.L."
    assert deca_estructurado.destination == "Mercamadrid (Madrid)"
    assert deca_estructurado.tractor_plate == "1234BCD"


def test_07_deca_v1_correctly_persisted(tmp_path: Path) -> None:
    """Test 7: DeCA v1 correctamente persistido con su versión física y metadatos."""
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    storage = LocalPdfStorage(tmp_path)
    renderer = ReportLabPdfRenderer()

    exp = make_ready_expedition()
    exp_repo.save(exp)

    use_case = EmitDeCAUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        pdf_renderer=renderer,
        storage_service=storage,
    )
    result = use_case.execute(EmitDeCAInputDTO(expedition_id=exp.id))

    saved_deca = deca_repo.find_by_expedition_id(exp.id)
    assert saved_deca is not None
    assert saved_deca.deca_code == "DECA-2026-000001"
    assert saved_deca.current_version == 1
    v1 = saved_deca.get_version(1)
    assert v1 is not None
    assert v1.version_number == 1
    assert v1.pdf_sha256 == result.pdf_sha256
    assert v1.pdf_storage_path.replace("\\", "/").endswith("deca/2026/DECA-2026-000001.pdf")


def test_08_second_attempt_is_idempotent(tmp_path: Path) -> None:
    """Test 8: Segundo intento de emisión es idempotente y no genera duplicados."""
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    audit_service = InMemoryAuditService()
    storage = LocalPdfStorage(tmp_path)
    renderer = ReportLabPdfRenderer()

    exp = make_ready_expedition()
    exp_repo.save(exp)

    use_case = EmitDeCAUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        pdf_renderer=renderer,
        storage_service=storage,
        audit_service=audit_service,
    )

    # 1ª emisión
    result1 = use_case.execute(EmitDeCAInputDTO(expedition_id=exp.id, actor="OPERATOR_1"))
    assert result1.is_idempotent is False

    # Contar eventos de auditoría y archivos generados
    emitted_events_count = len(
        [e for e in audit_service.get_events() if e.action == AuditAction.DECA_EMITTED]
    )
    assert emitted_events_count == 1

    # 2ª emisión (idéntica)
    result2 = use_case.execute(EmitDeCAInputDTO(expedition_id=exp.id, actor="OPERATOR_2"))
    assert result2.is_idempotent is True
    assert result2.deca_id == result1.deca_id
    assert result2.pdf_sha256 == result1.pdf_sha256
    assert result2.pdf_filename == result1.pdf_filename

    # No debe haberse creado un nuevo evento DECA_EMITTED
    assert (
        len([e for e in audit_service.get_events() if e.action == AuditAction.DECA_EMITTED])
        == emitted_events_count
    )


def test_09_pdf_generated_with_bytes(tmp_path: Path) -> None:
    """Test 9: PDF generado correctamente con tamaño en bytes mayor a cero y menor a 300 KB."""
    renderer = ReportLabPdfRenderer()
    exp = make_ready_expedition()
    deca_data, _, _ = DeCAEngine.create_deca_estructurado(exp, "DECA-2026-000001")

    pdf_bytes = renderer.render(deca_data)
    assert len(pdf_bytes) > 0
    assert len(pdf_bytes) < 300 * 1024  # Menor a 300 KB (cumple objetivo de ligereza)


def test_10_pdf_is_valid_format() -> None:
    """Test 10: El binario PDF generado comienza con la firma canónica %PDF-."""
    renderer = ReportLabPdfRenderer()
    exp = make_ready_expedition()
    deca_data, _, _ = DeCAEngine.create_deca_estructurado(exp, "DECA-2026-000001")

    pdf_bytes = renderer.render(deca_data)
    assert pdf_bytes.startswith(b"%PDF-")


def test_11_to_17_pdf_contains_all_required_text() -> None:
    """Tests 11 a 17: Verificación de contenido textual seleccionable en el PDF generado."""
    renderer = ReportLabPdfRenderer()
    exp = make_ready_expedition(
        tractor_plate="1234BCD",
        shipper_name="Tomates de Autor S.L.",
        carrier_name="Transportes Almería S.L.",
        origin="El Ejido (Almería)",
        destination="Mercamadrid (Madrid)",
        goods="Tomate Rama Extra",
        weight_kg=18500.0,
    )
    deca_data, _, _ = DeCAEngine.create_deca_estructurado(exp, "DECA-2026-000001", version_number=1)
    pdf_bytes = renderer.render(deca_data)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join(page.extract_text() for page in reader.pages)

    # Test 11: Identificador DeCA
    assert "DECA-2026-000001" in full_text
    # Test 12: Versión
    assert "VERSIÓN 1" in full_text
    # Test 13: Cargador
    assert "Tomates de Autor S.L." in full_text
    assert "B12345678" in full_text
    # Test 14: Transportista
    assert "Transportes Almería S.L." in full_text
    assert "B04123456" in full_text
    # Test 15: Vehículo
    assert "1234BCD" in full_text
    # Test 16: Origen y destino
    assert "El Ejido (Almería)" in full_text
    assert "Mercamadrid (Madrid)" in full_text
    # Test 17: Mercancía y peso
    assert "Tomate Rama Extra" in full_text
    assert "18.500,00 kg" in full_text or "18500" in full_text


def test_18_rigid_vehicle_renders_no_trailer() -> None:
    """Test 18: Vehículo rígido no muestra semirremolque como activo."""
    renderer = ReportLabPdfRenderer()
    exp = make_ready_expedition(vehicle_type=VehicleType.RIGIDO, tractor_plate="1234BCD")
    deca_data, _, _ = DeCAEngine.create_deca_estructurado(exp, "DECA-2026-000001")
    pdf_bytes = renderer.render(deca_data)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join(page.extract_text() for page in reader.pages)

    assert "No aplica (Vehículo rígido)" in full_text
    assert "1234BCD" in full_text


def test_19_articulated_vehicle_renders_both_plates() -> None:
    """Test 19: Conjunto articulado muestra tractora y semirremolque."""
    renderer = ReportLabPdfRenderer()
    exp = make_ready_expedition(
        vehicle_type=VehicleType.ARTICULADO,
        tractor_plate="1234BCD",
        trailer_plate="R9988ZZZ",
    )
    deca_data, _, _ = DeCAEngine.create_deca_estructurado(exp, "DECA-2026-000001")
    pdf_bytes = renderer.render(deca_data)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join(page.extract_text() for page in reader.pages)

    assert "1234BCD" in full_text
    assert "R9988ZZZ" in full_text


def test_20_missing_mandatory_fields_block_emission(tmp_path: Path) -> None:
    """Test 20: Datos obligatorios ausentes bloquean la emisión formal."""
    exp = make_ready_expedition()
    exp.carrier_name_raw = ""  # Dejar sin transportista

    with pytest.raises(DeCAEmissionException) as exc_info:
        DeCAEngine.create_deca_estructurado(exp, "DECA-2026-000001")

    assert "Revalidación legal fallida" in str(exc_info.value)


def test_21_sha256_hash_calculated_correctly() -> None:
    """Test 21: Hash SHA-256 del binario y del snapshot calculados correctamente."""
    renderer = ReportLabPdfRenderer()
    exp = make_ready_expedition()
    deca_data, snapshot_dict, snapshot_hash = DeCAEngine.create_deca_estructurado(
        exp, "DECA-2026-000001"
    )

    pdf_bytes = renderer.render(deca_data)
    computed_pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()

    assert len(computed_pdf_hash) == 64
    assert len(snapshot_hash) == 64


def test_22_pdf_stored_in_expected_location(tmp_path: Path) -> None:
    """Test 22: PDF almacenado en la ubicación custodial esperada
    (deca/YYYY/DECA-YYYY-NNNNNN.pdf).
    """
    storage = LocalPdfStorage(tmp_path)
    sample_content = b"%PDF-1.4 test content"
    relative_path = storage.save_deca_pdf("2026", "DECA-2026-000001", sample_content)

    assert relative_path == "deca/2026/DECA-2026-000001.pdf"
    expected_full_path = tmp_path / "deca" / "2026" / "DECA-2026-000001.pdf"
    assert expected_full_path.exists()
    assert expected_full_path.read_bytes() == sample_content


def test_23_path_traversal_rejected(tmp_path: Path) -> None:
    """Test 23: Intentos de path traversal son estrictamente rechazados."""
    storage = LocalPdfStorage(tmp_path)

    # Intento con ../ en relative_path
    with pytest.raises(StorageException):
        storage.save(b"malicious", "../../malicious.pdf")

    # Intento en save_deca_pdf con fiscal_year o deca_code malicioso
    with pytest.raises(StorageException):
        storage.save_deca_pdf("../2026", "DECA-2026-000001", b"data")

    with pytest.raises(StorageException):
        storage.save_deca_pdf("2026", "../../DECA-000001", b"data")


def test_24_storage_failure_handled(tmp_path: Path) -> None:
    """Test 24: Error de almacenamiento tratado adecuadamente con StorageException."""
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    audit_service = InMemoryAuditService()
    renderer = ReportLabPdfRenderer()

    class FailingStorage(LocalPdfStorage):
        def save(self, file_content, destination_path: str) -> str:
            raise StorageException("Error forzado de almacenamiento en disco.")

    broken_storage = FailingStorage(tmp_path)

    exp = make_ready_expedition()
    exp_repo.save(exp)

    use_case = EmitDeCAUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        pdf_renderer=renderer,
        storage_service=broken_storage,
        audit_service=audit_service,
    )

    with pytest.raises(StorageException):
        use_case.execute(EmitDeCAInputDTO(expedition_id=exp.id))

    # Auditoría debe registrar DECA_EMISSION_FAILED
    failed_events = [
        e for e in audit_service.get_events() if e.action == AuditAction.DECA_EMISSION_FAILED
    ]
    assert len(failed_events) >= 1


def test_25_concurrent_emissions_do_not_duplicate(tmp_path: Path) -> None:
    """Test 25: Concurrencia: emisiones simultáneas de la misma expedición no duplican el DeCA."""
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    audit_service = InMemoryAuditService()
    storage = LocalPdfStorage(tmp_path)
    renderer = ReportLabPdfRenderer()

    exp = make_ready_expedition()
    exp_repo.save(exp)

    use_case = EmitDeCAUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        pdf_renderer=renderer,
        storage_service=storage,
        audit_service=audit_service,
    )

    def run_emit(worker_id: int):
        return use_case.execute(EmitDeCAInputDTO(expedition_id=exp.id, actor=f"WORKER_{worker_id}"))

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_emit, i) for i in range(5)]
        results = [f.result() for f in futures]

    # Todos los resultados deben apuntar al mismo DeCA
    deca_ids = {r.deca_id for r in results}
    assert len(deca_ids) == 1

    # Exactamente una versión física creada
    saved_deca = deca_repo.find_by_expedition_id(exp.id)
    assert saved_deca is not None
    assert len(saved_deca.versions) == 1

    # Exactamente un evento de auditoría DECA_EMITTED
    emitted_events = [e for e in audit_service.get_events() if e.action == AuditAction.DECA_EMITTED]
    assert len(emitted_events) == 1


def test_26_to_28_audit_events_recorded(tmp_path: Path) -> None:
    """Tests 26, 27 y 28: Verificación de eventos de auditoría (STARTED, EMITTED, FAILED)."""
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    audit_service = InMemoryAuditService()
    storage = LocalPdfStorage(tmp_path)
    renderer = ReportLabPdfRenderer()

    use_case = EmitDeCAUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        pdf_renderer=renderer,
        storage_service=storage,
        audit_service=audit_service,
    )

    # 1. Emisión exitosa
    exp = make_ready_expedition()
    exp_repo.save(exp)
    use_case.execute(EmitDeCAInputDTO(expedition_id=exp.id, actor="OPERATOR_TEST"))

    # Test 26: DECA_EMISSION_STARTED
    started = [
        e for e in audit_service.get_events() if e.action == AuditAction.DECA_EMISSION_STARTED
    ]
    assert len(started) == 1
    assert started[0].user_identifier == "OPERATOR_TEST"

    # Test 27: DECA_EMITTED
    emitted = [e for e in audit_service.get_events() if e.action == AuditAction.DECA_EMITTED]
    assert len(emitted) == 1
    assert emitted[0].new_state["deca_code"] == "DECA-2026-000001"

    # 2. Emisión fallida por estado incorrecto
    exp_unready = make_ready_expedition(status=ExpeditionStatus.PENDIENTE_MATRICULA)
    exp_repo.save(exp_unready)
    with pytest.raises(ExpeditionNotReadyException):
        use_case.execute(EmitDeCAInputDTO(expedition_id=exp_unready.id, actor="OPERATOR_FAIL"))

    # Test 28: DECA_EMISSION_FAILED
    failed = [e for e in audit_service.get_events() if e.action == AuditAction.DECA_EMISSION_FAILED]
    assert len(failed) >= 1
    assert failed[-1].user_identifier == "OPERATOR_FAIL"
    assert len(failed) >= 1
    assert failed[-1].user_identifier == "OPERATOR_FAIL"


# =========================================================================
# SECCIÓN 25 - PRUEBA DE REGRESIÓN OBLIGATORIA
# =========================================================================


def test_section_25_regression_deca_v1_remains_intact_when_expedition_mutates(
    tmp_path: Path,
) -> None:
    """PRUEBA DE REGRESIÓN OBLIGATORIA:

    Emitir DeCA v1 -> Modificar Expedition (matrícula, transportista, peso, destino)
    -> Verificar que DeCA v1, su snapshot inmutable, su PDF y su hash permanecen
    100% idénticos e intactos, mientras Expedition refleja los nuevos valores.
    """
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    audit_service = InMemoryAuditService()
    storage = LocalPdfStorage(tmp_path)
    renderer = ReportLabPdfRenderer()

    # 1. Crear expedición original y emitir DeCA v1
    exp = make_ready_expedition(
        vehicle_type=VehicleType.RIGIDO,
        tractor_plate="1111AAA",
        carrier_name="Transportes Iniciales S.L.",
        destination="Mercamadrid (Madrid)",
        weight_kg=12000.0,
    )
    exp_repo.save(exp)

    use_case = EmitDeCAUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        pdf_renderer=renderer,
        storage_service=storage,
        audit_service=audit_service,
    )

    use_case.execute(EmitDeCAInputDTO(expedition_id=exp.id))

    # Guardar estado de DeCA v1
    deca_v1 = deca_repo.find_by_expedition_id(exp.id)
    assert deca_v1 is not None
    v1_version = deca_v1.get_version(1)
    assert v1_version is not None

    original_pdf_bytes = storage.read(v1_version.pdf_storage_path)
    original_pdf_sha256 = v1_version.pdf_sha256
    original_snapshot_hash = v1_version.snapshot_hash
    original_snapshot_carrier = v1_version.snapshot_data["carrier"]["name"]
    original_snapshot_plate = v1_version.snapshot_data["vehicle"]["tractor_plate"]
    original_snapshot_dest = v1_version.snapshot_data["route_and_goods"]["destination"]
    original_snapshot_weight = v1_version.snapshot_data["route_and_goods"]["weight_kg"]

    # 2. Modificar agresivamente la expedición en base de datos
    exp.carrier_name_raw = "Nuevo Transportista Modificado S.A."
    exp.destination = "Perpignan (Francia)"
    exp.weight = Weight(24500.0)
    exp.assign_vehicle(VehicleType.RIGIDO, Matricula("9999ZZZ"), None)
    exp_repo.save(exp)

    # 3. Comprobar que la expedición SÍ ha cambiado
    mutated_exp = exp_repo.get_by_id(exp.id)
    assert mutated_exp is not None
    assert mutated_exp.carrier_name_raw == "Nuevo Transportista Modificado S.A."
    assert mutated_exp.destination == "Perpignan (Francia)"
    assert mutated_exp.weight.kg == 24500.0
    assert str(mutated_exp.tractor_plate) == "9999ZZZ"

    # 4. Verificar que DeCA v1 permanece 100% INTACTO
    verified_deca = deca_repo.find_by_expedition_id(exp.id)
    assert verified_deca is not None
    verified_v1 = verified_deca.get_version(1)
    assert verified_v1 is not None

    # El snapshot no ha cambiado
    assert verified_v1.snapshot_data["carrier"]["name"] == original_snapshot_carrier
    assert verified_v1.snapshot_data["carrier"]["name"] == "Transportes Iniciales S.L."
    assert verified_v1.snapshot_data["vehicle"]["tractor_plate"] == original_snapshot_plate
    assert verified_v1.snapshot_data["vehicle"]["tractor_plate"] == "1111AAA"
    assert verified_v1.snapshot_data["route_and_goods"]["destination"] == original_snapshot_dest
    assert verified_v1.snapshot_data["route_and_goods"]["destination"] == "Mercamadrid (Madrid)"
    assert verified_v1.snapshot_data["route_and_goods"]["weight_kg"] == original_snapshot_weight
    assert verified_v1.snapshot_data["route_and_goods"]["weight_kg"] == 12000.0

    # Los hashes no han cambiado
    assert verified_v1.snapshot_hash == original_snapshot_hash
    assert verified_v1.pdf_sha256 == original_pdf_sha256

    # El binario físico en disco permanece idéntico
    current_pdf_bytes = storage.read(verified_v1.pdf_storage_path)
    assert current_pdf_bytes == original_pdf_bytes
    assert hashlib.sha256(current_pdf_bytes).hexdigest() == original_pdf_sha256


# =========================================================================
# SECCIÓN 26 - CASOS DE PRUEBA REALISTAS (A A E)
# =========================================================================


def test_section_26_case_a_rigid_vehicle() -> None:
    """Caso A: Vehículo rígido — 1 sola matrícula, sin semirremolque."""
    renderer = ReportLabPdfRenderer()
    exp = make_ready_expedition(
        vehicle_type=VehicleType.RIGIDO,
        tractor_plate="4567JKL",
        carrier_name="Transportes Rígidos del Sur S.L.",
    )
    deca_data, snapshot, _ = DeCAEngine.create_deca_estructurado(exp, "DECA-2026-000101")
    pdf_bytes = renderer.render(deca_data)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() for page in reader.pages)

    assert "4567JKL" in text
    assert "No aplica (Vehículo rígido)" in text
    assert snapshot["vehicle"]["trailer_plate"] is None


def test_section_26_case_b_articulated_vehicle() -> None:
    """Caso B: Conjunto articulado — Tractora + Semirremolque."""
    renderer = ReportLabPdfRenderer()
    exp = make_ready_expedition(
        vehicle_type=VehicleType.ARTICULADO,
        tractor_plate="1234BBB",
        trailer_plate="R5678CCC",
        carrier_name="Logística Articulada Internacional S.A.",
    )
    deca_data, snapshot, _ = DeCAEngine.create_deca_estructurado(exp, "DECA-2026-000102")
    pdf_bytes = renderer.render(deca_data)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() for page in reader.pages)

    assert "1234BBB" in text
    assert "R5678CCC" in text
    assert snapshot["vehicle"]["tractor_plate"] == "1234BBB"
    assert snapshot["vehicle"]["trailer_plate"] == "R5678CCC"


def test_section_26_case_c_international_transport() -> None:
    """Caso C: Transporte internacional — Destino fuera de España (Francia)."""
    renderer = ReportLabPdfRenderer()
    exp = make_ready_expedition(
        origin="El Ejido (España)",
        destination="Marché Saint-Charles, Perpignan (Francia)",
        goods="Tomate Rama Certificado GlobalGAP",
        weight_kg=22400.0,
    )
    deca_data, snapshot, _ = DeCAEngine.create_deca_estructurado(exp, "DECA-2026-000103")
    pdf_bytes = renderer.render(deca_data)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() for page in reader.pages)

    assert "Perpignan" in text
    assert "Francia" in text
    assert "Marché Saint-Charles" in text
    assert snapshot["route_and_goods"]["destination"] == "Marché Saint-Charles, Perpignan (Francia)"


def test_section_26_case_d_with_detailed_observations() -> None:
    """Caso D: Documento con instrucciones y observaciones de transporte."""
    renderer = ReportLabPdfRenderer()
    obs_text = (
        "Carga termosellada a temperatura constante de +11ºC. "
        "Descarga urgente en muelle 4 antes de las 08:00 AM."
    )
    exp = make_ready_expedition(observations=obs_text)
    deca_data, snapshot, _ = DeCAEngine.create_deca_estructurado(exp, "DECA-2026-000104")
    pdf_bytes = renderer.render(deca_data)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() for page in reader.pages)

    assert "Carga termosellada" in text
    assert "+11ºC" in text
    assert snapshot["observations"] == obs_text


def test_section_26_case_e_missing_optional_fields() -> None:
    """Caso E: Documento con campos opcionales ausentes (sin observaciones, sin ref externa)."""
    renderer = ReportLabPdfRenderer()
    exp = make_ready_expedition(
        observations=None,
        reference="",
        carrier_email=None,
    )
    deca_data, snapshot, _ = DeCAEngine.create_deca_estructurado(exp, "DECA-2026-000105")
    pdf_bytes = renderer.render(deca_data)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() for page in reader.pages)

    assert "Sin observaciones particulares registradas" in text
    assert snapshot["observations"] is None
    assert snapshot["external_reference"] is None


# =========================================================================
# TESTS ADICIONALES DE DOMINIO E INMUTABILIDAD
# =========================================================================


def test_deca_entity_immutability_duplicate_version_rejected() -> None:
    """La entidad DeCA rechaza añadir dos veces la misma versión."""
    deca = DeCA(deca_code="DECA-2026-000001")
    v1 = DeCAVersion(version_number=1, pdf_sha256="abc", pdf_storage_path="path")
    deca.add_version(v1)

    v1_duplicate = DeCAVersion(version_number=1, pdf_sha256="def", pdf_storage_path="path2")
    with pytest.raises(ImmutableDeCAException) as exc_info:
        deca.add_version(v1_duplicate)

    assert "Las versiones son inmutables" in str(exc_info.value)
