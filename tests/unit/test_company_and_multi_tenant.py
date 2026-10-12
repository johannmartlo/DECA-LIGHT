from __future__ import annotations

import io
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from src.application.dtos.deca_dto import EmitDeCAInputDTO
from src.application.dtos.email_dto import SendDeCAEmailInputDTO
from src.application.dtos.vehicle_assignment_dto import AssignVehicleInputDTO
from src.application.use_cases.assign_vehicle import AssignVehicleToExpeditionUseCase
from src.application.use_cases.emit_deca import EmitDeCAUseCase
from src.application.use_cases.import_documents_batch import (
    ImportDocumentsBatchUseCase,
    UploadedFileInput,
)
from src.application.use_cases.send_deca_email import SendDeCAEmailUseCase
from src.config.companies import CULTIVOS_ARABA_ID, TOMATES_DE_AUTOR_ID, build_companies
from src.config.settings import Settings
from src.domain.entities.company import Company
from src.domain.entities.deca import DeCA, DeCAEstructurado, DeCAVersion
from src.domain.entities.email_delivery import EmailDelivery
from src.domain.entities.expedition import Expedition
from src.domain.enums import (
    AuditAction,
    EmailDeliveryStatus,
    ExpeditionStatus,
    VehicleType,
)
from src.domain.exceptions import (
    InvalidStateTransitionException,
    ValidationException,
)
from src.domain.services.company_detector import (
    CompanyDetectionSource,
    CompanyDetectionStatus,
    CompanyDetector,
)
from src.domain.services.deca_engine import DeCAEngine
from src.domain.services.deca_validator import DeCAValidator
from src.domain.value_objects import NIF, Matricula, Weight
from src.infrastructure.document.reportlab_pdf_renderer import ReportLabPdfRenderer
from src.infrastructure.email.fake_microsoft_graph_email_sender import (
    FakeMicrosoftGraphEmailSender,
)
from src.infrastructure.importers.pdf_document_importer import PdfDocumentImporter
from src.infrastructure.logging.in_memory_audit_service import InMemoryAuditService
from src.infrastructure.parsers.composite_parser import CompositeDocumentParser
from src.infrastructure.repositories.in_memory_company_repository import (
    InMemoryCompanyRepository,
)
from src.infrastructure.repositories.in_memory_deca_repository import (
    InMemoryDeCARepository,
)
from src.infrastructure.repositories.in_memory_email_delivery_repository import (
    InMemoryEmailDeliveryRepository,
)
from src.infrastructure.repositories.in_memory_expedition_repository import (
    InMemoryExpeditionRepository,
)
from src.infrastructure.storage.filesystem_storage import FilesystemStorageAdapter


def create_sample_pdf(text_lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    y = 800
    for line in text_lines:
        c.drawString(50, y, line)
        y -= 25
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# ==============================================================================
# 1. Creación de empresas con datos válidos y validación
# ==============================================================================
def test_company_creation_and_validation() -> None:
    company = Company(
        company_id="TOMATES_DE_AUTOR",
        legal_name="Tomates de Autor S.L.",
        tax_id=NIF("B04123456"),
        fiscal_address="Calle Mayor 1, Almería",
    )
    assert company.company_id == "TOMATES_DE_AUTOR"
    assert company.legal_name == "Tomates de Autor S.L."
    assert str(company.tax_id) == "B04123456"
    assert company.is_fully_configured is True
    assert company.pending_fields == ()

    # Validation errors
    with pytest.raises(ValidationException, match="company_id inválido"):
        Company(company_id="inv@lid!", legal_name="Empresa")

    with pytest.raises(ValidationException, match="razón social"):
        Company(company_id="TEST_CO", legal_name="  ")


# ==============================================================================
# 2. Empresa pendiente de configuración fiscal (REQUIERE_CONFIGURACION)
# ==============================================================================
def test_company_fiscal_pending_fields() -> None:
    settings = Settings(
        COMPANY_ARABA_LEGAL_NAME="Cultivos Araba S.L.",
        COMPANY_ARABA_TAX_ID="",
        COMPANY_ARABA_ADDRESS="",
    )
    companies = build_companies(settings)
    araba = next(c for c in companies if c.company_id == CULTIVOS_ARABA_ID)

    assert araba.company_id == "CULTIVOS_ARABA"
    assert araba.tax_id is None
    assert araba.fiscal_address == ""
    assert araba.is_fully_configured is False
    assert "tax_id" in araba.pending_fields
    assert "fiscal_address" in araba.pending_fields


# ==============================================================================
# 3. Detección automática por NIF/CIF (Prioridad 1)
# ==============================================================================
def test_company_detector_priority_1_tax_id() -> None:
    c1 = Company(
        company_id="TOMATES_DE_AUTOR",
        legal_name="Tomates de Autor S.L.",
        tax_id=NIF("B04123456"),
    )
    c2 = Company(
        company_id="CULTIVOS_ARABA",
        legal_name="Cultivos Araba S.L.",
        tax_id=NIF("B01584988"),
    )
    result = CompanyDetector.detect(
        companies=[c1, c2],
        shipper_tax_id="B-04.123.456",
        shipper_name="Nombre Comercial Desconocido",
    )
    assert result.detected is True
    assert result.company_id == "TOMATES_DE_AUTOR"
    assert result.source == CompanyDetectionSource.TAX_ID
    assert result.confidence == 1.0


# ==============================================================================
# 4. Detección automática por Razón Social exacta (Prioridad 2)
# ==============================================================================
def test_company_detector_priority_2_legal_name() -> None:
    c1 = Company(
        company_id="TOMATES_DE_AUTOR",
        legal_name="Tomates de Autor S.L.",
        tax_id=NIF("B04123456"),
    )
    c2 = Company(
        company_id="CULTIVOS_ARABA",
        legal_name="Cultivos Araba S.L.",
        tax_id=None,
    )
    result = CompanyDetector.detect(
        companies=[c1, c2],
        shipper_tax_id=None,
        shipper_name="CULTIVOS ARABA, S.L.",
    )
    assert result.detected is True
    assert result.company_id == "CULTIVOS_ARABA"
    assert result.source == CompanyDetectionSource.LEGAL_NAME
    assert result.confidence == 0.95


# ==============================================================================
# 5. Detección automática por Alias Documental (Prioridad 3)
# ==============================================================================
def test_company_detector_priority_3_alias() -> None:
    c1 = Company(
        company_id="TOMATES_DE_AUTOR",
        legal_name="Tomates de Autor S.L.",
        tax_id=NIF("B04123456"),
        document_aliases=("TDA EXPORT", "TOMATES AUTOR"),
    )
    result = CompanyDetector.detect(
        companies=[c1],
        shipper_tax_id=None,
        shipper_name="TDA EXPORT",
    )
    assert result.detected is True
    assert result.company_id == "TOMATES_DE_AUTOR"
    assert result.source == CompanyDetectionSource.DOCUMENT_ALIAS
    assert result.confidence == 0.85


# ==============================================================================
# 6. Empresa desconocida y conflicto ambigüedad -> PENDIENTE_REVISION
# ==============================================================================
def test_company_detector_unknown_and_ambiguous() -> None:
    c1 = Company(
        company_id="TOMATES_DE_AUTOR",
        legal_name="Tomates de Autor S.L.",
        tax_id=NIF("B04123456"),
    )
    c2 = Company(
        company_id="CULTIVOS_ARABA",
        legal_name="Cultivos Araba S.L.",
        tax_id=NIF("B01584988"),
    )
    # Desconocida
    res_unknown = CompanyDetector.detect(
        companies=[c1, c2],
        shipper_tax_id=None,
        shipper_name="AGRICOLA DEL SUR S.A.",
    )
    assert res_unknown.status == CompanyDetectionStatus.UNKNOWN
    assert res_unknown.detected is False

    # Conflicto: NIF de Tomates pero nombre de Araba
    res_conflict = CompanyDetector.detect(
        companies=[c1, c2],
        shipper_tax_id="B04123456",
        shipper_name="Cultivos Araba S.L.",
    )
    assert res_conflict.status == CompanyDetectionStatus.AMBIGUOUS
    assert res_conflict.detected is False


# ==============================================================================
# 7. Aislamiento e invariantes en la entidad Expedition
# ==============================================================================
def test_expedition_company_invariants() -> None:
    exp = Expedition(
        internal_id="TD-2026-00001",
        shipper_name="Tomates de Autor S.L.",
        company_id="TOMATES_DE_AUTOR",
    )
    assert exp.belongs_to("TOMATES_DE_AUTOR") is True
    assert exp.belongs_to("CULTIVOS_ARABA") is False

    # No se puede reasignar a otra empresa
    with pytest.raises(InvalidStateTransitionException, match="no puede cambiarse"):
        exp.assign_company("CULTIVOS_ARABA")

    # Invariante: no se puede transicionar a LISTA_PARA_DECA sin company_id
    exp_unassigned = Expedition(internal_id="TD-2026-00002", company_id="")
    with pytest.raises(InvalidStateTransitionException, match="sin una empresa emisora asignada"):
        exp_unassigned.transition_to(ExpeditionStatus.LISTA_PARA_DECA)


# ==============================================================================
# 8. DeCAValidator valida company_id y coherencia
# ==============================================================================
def test_deca_validator_company_checks() -> None:
    exp = Expedition(
        company_id="",
        shipper_name="Empresa Desconocida S.L.",
        vehicle_type=VehicleType.RIGIDO,
        tractor_plate=Matricula("1234BBB"),
        carrier_name_raw="Transportes Test",
        carrier_tax_id=NIF("B12345678"),
        origin="Almería",
        destination="Madrid",
        goods="Tomates",
        weight=Weight(1000.0),
    )
    object.__setattr__(exp, "company_id", "")
    val = DeCAValidator.validate(exp)
    assert not val.valid
    assert any(e.code == "COMPANY_MISSING" for e in val.errors)

    # Coherencia: company_id TOMATES pero cargador CULTIVOS ARABA
    exp.company_id = "TOMATES_DE_AUTOR"
    exp.shipper_name = "Cultivos Araba S.L."
    val_mismatch = DeCAValidator.validate(exp)
    assert not val_mismatch.valid
    assert any(e.code == "COMPANY_MISMATCH" for e in val_mismatch.errors)

    # Válido cuando coinciden
    exp.company_id = "CULTIVOS_ARABA"
    val_ok = DeCAValidator.validate(exp)
    assert val_ok.valid


# ==============================================================================
# 9. DeCAEngine genera snapshot inmutable con datos de la empresa emisora
# ==============================================================================
def test_deca_engine_immutable_snapshot_contains_company() -> None:
    exp = Expedition(
        company_id="CULTIVOS_ARABA",
        shipper_name="Cultivos Araba S.L.",
        shipper_tax_id=NIF("B01584988"),
        shipper_address="Vitoria-Gasteiz",
        vehicle_type=VehicleType.RIGIDO,
        tractor_plate=Matricula("1234BBB"),
        carrier_name_raw="Transportes Norte",
        carrier_tax_id=NIF("B99887766"),
        origin="Vitoria",
        destination="Bilbao",
        goods="Patatas",
        weight=Weight(2000.0),
        status=ExpeditionStatus.LISTA_PARA_DECA,
    )
    deca_estructurado, snapshot, snap_hash = DeCAEngine.create_deca_estructurado(
        expedition=exp,
        deca_code="DECA-2026-000001",
    )
    assert deca_estructurado.company_id == "CULTIVOS_ARABA"
    assert snapshot["company_id"] == "CULTIVOS_ARABA"
    assert snapshot["shipper"]["name"] == "Cultivos Araba S.L."

    # Roundtrip snapshot
    restored = DeCAEstructurado.from_snapshot(snapshot, snap_hash)
    assert restored.company_id == "CULTIVOS_ARABA"
    assert restored.shipper_name == "Cultivos Araba S.L."


# ==============================================================================
# 10. Inmutabilidad histórica: cambios de config no alteran DeCA ya emitido
# ==============================================================================
def test_historical_snapshot_immutability_on_company_config_change() -> None:
    company = Company(
        company_id="TOMATES_DE_AUTOR",
        legal_name="Tomates de Autor S.L.",
        tax_id=NIF("B04123456"),
        fiscal_address="Calle Original 123",
    )
    exp = Expedition(
        company_id=company.company_id,
        shipper_name=company.legal_name,
        shipper_tax_id=company.tax_id,
        shipper_address=company.fiscal_address,
        vehicle_type=VehicleType.RIGIDO,
        tractor_plate=Matricula("1234BBB"),
        carrier_name_raw="Transportes Test",
        carrier_tax_id=NIF("B12345678"),
        origin="Almería",
        destination="Madrid",
        goods="Tomates",
        weight=Weight(1000.0),
        status=ExpeditionStatus.LISTA_PARA_DECA,
    )
    deca_est, snapshot, snap_hash = DeCAEngine.create_deca_estructurado(
        expedition=exp, deca_code="DECA-2026-000010"
    )

    # Supongamos que la empresa cambia de razón social o domicilio fiscal en el futuro
    company_updated = Company(
        company_id="TOMATES_DE_AUTOR",
        legal_name="Tomates de Autor Internacional S.L.",
        tax_id=NIF("B04123456"),
        fiscal_address="Avenida Nueva 456",
    )
    assert company_updated.legal_name != snapshot["shipper"]["name"]

    # El snapshot previo permanece inalterado
    assert snapshot["shipper"]["name"] == "Tomates de Autor S.L."
    assert snapshot["shipper"]["address"] == "Calle Original 123"
    assert deca_est.shipper_name == "Tomates de Autor S.L."


# ==============================================================================
# 11. Renderizado PDF: membrete y metadatos dinámicos por empresa
# ==============================================================================
def test_pdf_rendering_company_branding() -> None:
    renderer = ReportLabPdfRenderer()

    # Tomates de Autor
    deca_tda = DeCAEstructurado(
        deca_code="DECA-2026-000001",
        version_number=1,
        company_id="TOMATES_DE_AUTOR",
        issue_datetime=datetime.now(UTC),
        transport_date=date.today(),
        shipper_name="Tomates de Autor S.L.",
        shipper_tax_id="B04123456",
        shipper_address="Almería",
        carrier_name="Trans Almería",
        carrier_tax_id="B11223344",
        vehicle_type="RIGIDO",
        tractor_plate="1234BBB",
        trailer_plate=None,
        origin="Almería",
        destination="Madrid",
        goods="Tomates",
        weight_kg=1500.0,
    )
    pdf_tda = renderer.render(deca_tda)
    assert b"Tomates de Autor S.L." in pdf_tda or b"TOMATES DE AUTOR S.L." in pdf_tda

    # Cultivos Araba
    deca_araba = DeCAEstructurado(
        deca_code="DECA-2026-000002",
        version_number=1,
        company_id="CULTIVOS_ARABA",
        issue_datetime=datetime.now(UTC),
        transport_date=date.today(),
        shipper_name="Cultivos Araba S.L.",
        shipper_tax_id="B01584988",
        shipper_address="Vitoria",
        carrier_name="Trans Vitoria",
        carrier_tax_id="B55667788",
        vehicle_type="RIGIDO",
        tractor_plate="5678CCC",
        trailer_plate=None,
        origin="Vitoria",
        destination="Bilbao",
        goods="Patatas",
        weight_kg=3000.0,
    )
    pdf_araba = renderer.render(deca_araba)
    assert b"Cultivos Araba S.L." in pdf_araba or b"CULTIVOS ARABA S.L." in pdf_araba


# ==============================================================================
# 12. Importación masiva de lote mixto (15 Tomates + 15 Cultivos Araba = 30 total)
# ==============================================================================
def test_batch_import_mixed_companies_30_documents(tmp_path: Path) -> None:
    importer = PdfDocumentImporter(CompositeDocumentParser())
    storage = FilesystemStorageAdapter(tmp_path)
    expedition_repo = InMemoryExpeditionRepository()

    company_repo = InMemoryCompanyRepository(
        [
            Company(
                company_id=TOMATES_DE_AUTOR_ID,
                legal_name="Tomates de Autor S.L.",
                tax_id=NIF("B04123456"),
            ),
            Company(
                company_id=CULTIVOS_ARABA_ID,
                legal_name="Cultivos Araba S.L.",
                tax_id=NIF("B01584988"),
            ),
        ]
    )

    use_case = ImportDocumentsBatchUseCase(
        importer=importer,
        storage=storage,
        expedition_repo=expedition_repo,
        company_repo=company_repo,
    )

    files: list[UploadedFileInput] = []

    # 15 Cartas de Porte de Tomates de Autor
    for i in range(1, 16):
        pdf_bytes = create_sample_pdf(
            [
                "ALBARÁN DE CARGA / CARTA DE PORTE NACIONAL HISPATEC",
                f"Albarán Nº: CP-TDA-2026-{i:04d}",
                "Fecha Transporte: 03/10/2026",
                "Cargador: Tomates de Autor S.L.",
                "NIF Cargador: B04123456",
                f"Transportista: Transportes Almería {i} S.L.",
                "Origen: El Ejido (Almería)",
                "Destino: Mercamadrid",
                "Mercancía: Tomate Rama",
                f"Peso Total: {10000 + i * 100} kg",
            ]
        )
        files.append(
            UploadedFileInput(
                filename=f"cp_tda_{i}.pdf",
                stream=io.BytesIO(pdf_bytes),
                content_bytes=pdf_bytes,
            )
        )

    # 15 CMRs de Cultivos Araba
    for i in range(1, 16):
        pdf_bytes = create_sample_pdf(
            [
                "CMR - INTERNATIONAL CONSIGNMENT NOTE",
                f"CMR Nº: CMR-ARA-2026-{i:04d}",
                "Date: 03/10/2026",
                "1 Expéditeur / Sender: Cultivos Araba S.L.",
                "VAT Sender: B01584988",
                f"16 Transporteur: Araba Express {i}",
                "4 Place of taking over: Vitoria-Gasteiz, Spain",
                "2 Destinataire: Paris Rungis, France",
                "6 Nature of the goods: Bio Vegetables",
                f"11 Gross weight: {12000 + i * 50} kg",
            ]
        )
        files.append(
            UploadedFileInput(
                filename=f"cmr_ara_{i}.pdf",
                stream=io.BytesIO(pdf_bytes),
                content_bytes=pdf_bytes,
            )
        )

    assert len(files) == 30
    batch_res = use_case.execute(files)

    assert batch_res.total_files == 30
    assert batch_res.imported_count == 30
    assert batch_res.duplicates_count == 0
    assert batch_res.review_needed_count == 0

    tda_items = [it for it in batch_res.items if it.company_id == TOMATES_DE_AUTOR_ID]
    ara_items = [it for it in batch_res.items if it.company_id == CULTIVOS_ARABA_ID]
    assert len(tda_items) == 15
    assert len(ara_items) == 15


# ==============================================================================
# 13. Documento de empresa desconocida -> PENDIENTE_REVISION
# ==============================================================================
def test_batch_import_unknown_company_goes_to_needs_review(tmp_path: Path) -> None:
    importer = PdfDocumentImporter(CompositeDocumentParser())
    storage = FilesystemStorageAdapter(tmp_path)
    expedition_repo = InMemoryExpeditionRepository()
    company_repo = InMemoryCompanyRepository(
        [
            Company(
                company_id=TOMATES_DE_AUTOR_ID,
                legal_name="Tomates de Autor S.L.",
                tax_id=NIF("B04123456"),
            ),
        ]
    )
    use_case = ImportDocumentsBatchUseCase(
        importer=importer,
        storage=storage,
        expedition_repo=expedition_repo,
        company_repo=company_repo,
    )

    pdf_bytes = create_sample_pdf(
        [
            "ALBARÁN DE CARGA / CARTA DE PORTE NACIONAL",
            "Albarán Nº: CP-UNK-001",
            "Fecha Transporte: 03/10/2026",
            "Cargador: Transportes Desconocidos Hermanos García S.A.",
            "NIF Cargador: A99887766",
            "Origen: Murcia",
            "Destino: Valencia",
            "Mercancía: Naranjas",
            "Peso Total: 5000 kg",
        ]
    )
    res = use_case.execute(
        [
            UploadedFileInput(
                filename="unknown.pdf", stream=io.BytesIO(pdf_bytes), content_bytes=pdf_bytes
            )
        ]
    )
    assert res.total_files == 1
    assert res.review_needed_count == 1
    item = res.items[0]
    assert item.status == "NEEDS_REVIEW"
    assert "empresa_emisora" in item.fields_needing_review


# ==============================================================================
# 14. Email: remitente compartido pedidos@tomatesdeautor.com y firma dinámica
# ==============================================================================
def test_send_deca_email_shared_sender_and_dynamic_signature(tmp_path: Path) -> None:
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    deliv_repo = InMemoryEmailDeliveryRepository()
    storage = FilesystemStorageAdapter(tmp_path)
    fake_sender = FakeMicrosoftGraphEmailSender(sender_email="pedidos@tomatesdeautor.com")

    # Expedición de Cultivos Araba
    exp = Expedition(
        internal_id="TD-2026-ARA01",
        company_id="CULTIVOS_ARABA",
        shipper_name="Cultivos Araba S.L.",
        carrier_name_raw="Trans Araba",
        carrier_email="trafico@transaraba.com",
        destination="Bilbao",
        status=ExpeditionStatus.LISTA_PARA_DECA,
    )
    exp_repo.save(exp)

    # DeCA emitido
    deca = DeCA(
        expedition_id=exp.id,
        company_id="CULTIVOS_ARABA",
        deca_code="DECA-2026-000099",
    )
    pdf_content = b"%PDF-1.4 dummy content"
    saved_path = storage.save(pdf_content, "deca/2026/DECA-2026-000099.pdf")
    import hashlib

    pdf_sha = hashlib.sha256(pdf_content).hexdigest()
    deca.add_version(
        DeCAVersion(
            version_number=1,
            pdf_sha256=pdf_sha,
            pdf_storage_path=saved_path,
            pdf_size_bytes=len(pdf_content),
        )
    )
    deca_repo.save(deca)

    use_case = SendDeCAEmailUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        storage_service=storage,
        email_sender=fake_sender,
        email_delivery_repo=deliv_repo,
        sender_email="pedidos@tomatesdeautor.com",
    )

    res = use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))
    assert res.email_status == EmailDeliveryStatus.EMAIL_SENT.value

    # Verificación del mensaje enviado
    sent_msgs = fake_sender.sent_messages
    assert len(sent_msgs) == 1
    msg = sent_msgs[0]

    # Remitente debe ser siempre la cuenta unificada corporativa
    assert msg.sender == "pedidos@tomatesdeautor.com"
    # La firma del cuerpo debe referenciar a la sociedad emisora
    assert "Cultivos Araba S.L." in msg.body_text


# ==============================================================================
# 15. Idempotencia de envíos cruzada
# ==============================================================================
def test_email_idempotency_cross_company(tmp_path: Path) -> None:
    deliv_repo = InMemoryEmailDeliveryRepository()
    id_1 = str(uuid.uuid4())
    id_2 = str(uuid.uuid4())

    d1 = EmailDelivery(
        expedition_id=uuid.uuid4(),
        deca_id=uuid.uuid4(),
        company_id="TOMATES_DE_AUTOR",
        deca_code="DECA-2026-000001",
        deca_version=1,
        recipient_email="trafico@test.com",
        subject="DeCA 1",
        idempotency_key=f"KEY:{id_1}",
    )
    d2 = EmailDelivery(
        expedition_id=uuid.uuid4(),
        deca_id=uuid.uuid4(),
        company_id="CULTIVOS_ARABA",
        deca_code="DECA-2026-000002",
        deca_version=1,
        recipient_email="trafico@test.com",
        subject="DeCA 2",
        idempotency_key=f"KEY:{id_2}",
    )
    deliv_repo.save(d1)
    deliv_repo.save(d2)

    assert deliv_repo.find_by_idempotency_key(f"KEY:{id_1}").company_id == "TOMATES_DE_AUTOR"
    assert deliv_repo.find_by_idempotency_key(f"KEY:{id_2}").company_id == "CULTIVOS_ARABA"


# ==============================================================================
# 16. Endpoint público GET /d/{token} sirve ambas empresas sin requerir cabecera
# ==============================================================================
def test_public_qr_cross_company_access(client: TestClient, test_settings: Settings) -> None:
    import hashlib

    from src.presentation.api.dependencies import get_deca_repository, get_storage_service

    deca_repo = get_deca_repository()
    storage = get_storage_service(test_settings)

    # Emitir un DeCA de Tomates y otro de Araba con tokens conocidos y versiones físicas
    pdf_bytes = b"%PDF-1.4 dummy deca content"
    pdf_sha = hashlib.sha256(pdf_bytes).hexdigest()

    path_tda = storage.save(pdf_bytes, "deca/2026/DECA-2026-000088.pdf")
    d_tda = DeCA(
        company_id="TOMATES_DE_AUTOR",
        deca_code="DECA-2026-000088",
    )
    d_tda.add_version(
        DeCAVersion(
            version_number=1,
            pdf_sha256=pdf_sha,
            pdf_storage_path=path_tda,
            pdf_size_bytes=len(pdf_bytes),
        )
    )
    tda_token = str(d_tda.public_access_token)
    deca_repo.save(d_tda)

    path_ara = storage.save(pdf_bytes, "deca/2026/DECA-2026-000089.pdf")
    d_ara = DeCA(
        company_id="CULTIVOS_ARABA",
        deca_code="DECA-2026-000089",
    )
    d_ara.add_version(
        DeCAVersion(
            version_number=1,
            pdf_sha256=pdf_sha,
            pdf_storage_path=path_ara,
            pdf_size_bytes=len(pdf_bytes),
        )
    )
    ara_token = str(d_ara.public_access_token)
    deca_repo.save(d_ara)

    # Consulta pública sin cabecera X-Company-Id
    res_tda = client.get(f"/d/{tda_token}")
    assert res_tda.status_code == 200

    res_ara = client.get(f"/d/{ara_token}")
    assert res_ara.status_code == 200


# ==============================================================================
# 17. Rechazo IDOR cross-company con X-Company-Id
# ==============================================================================
def test_cross_company_idor_rejection(client: TestClient) -> None:
    from src.presentation.api.dependencies import get_expedition_repository

    exp_repo = get_expedition_repository()

    # Expedición registrada para CULTIVOS_ARABA
    exp_araba = Expedition(
        internal_id="TD-2026-ARA-IDOR",
        company_id="CULTIVOS_ARABA",
        shipper_name="Cultivos Araba S.L.",
        status=ExpeditionStatus.PENDIENTE_MATRICULA,
    )
    exp_repo.save(exp_araba)

    # Intento de acceso indicando X-Company-Id: TOMATES_DE_AUTOR
    res_get = client.get(
        f"/api/v1/expeditions/{exp_araba.id}",
        headers={"X-Company-Id": "TOMATES_DE_AUTOR"},
    )
    assert res_get.status_code == 403
    assert "otra empresa" in res_get.json()["detail"]

    # Intento de asignación de vehículo indicando X-Company-Id erróneo
    res_patch = client.patch(
        f"/api/v1/expeditions/{exp_araba.id}/vehicle",
        headers={"X-Company-Id": "TOMATES_DE_AUTOR"},
        json={
            "vehicle_type": "RIGIDO",
            "tractor_registration": "1234BBB",
        },
    )
    assert res_patch.status_code == 403

    # Con la cabecera correcta de CULTIVOS_ARABA sí se permite
    res_ok = client.get(
        f"/api/v1/expeditions/{exp_araba.id}",
        headers={"X-Company-Id": "CULTIVOS_ARABA"},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["company_id"] == "CULTIVOS_ARABA"


# ==============================================================================
# 18. Auditoría registra company_id y COMPANY_DETECTED
# ==============================================================================
def test_audit_records_company_events(tmp_path: Path) -> None:
    audit_service = InMemoryAuditService()
    importer = PdfDocumentImporter(CompositeDocumentParser())
    storage = FilesystemStorageAdapter(tmp_path)
    exp_repo = InMemoryExpeditionRepository()
    company_repo = InMemoryCompanyRepository(
        [
            Company(
                company_id="CULTIVOS_ARABA",
                legal_name="Cultivos Araba S.L.",
                tax_id=NIF("B01584988"),
            )
        ]
    )

    use_case = ImportDocumentsBatchUseCase(
        importer=importer,
        storage=storage,
        expedition_repo=exp_repo,
        company_repo=company_repo,
        audit_service=audit_service,
    )

    pdf_bytes = create_sample_pdf(
        [
            "ALBARÁN DE CARGA / CARTA DE PORTE NACIONAL",
            "Albarán Nº: CP-AUDIT-01",
            "Fecha Transporte: 03/10/2026",
            "Cargador: Cultivos Araba S.L.",
            "NIF Cargador: B01584988",
            "Origen: Vitoria",
            "Destino: Bilbao",
            "Mercancía: Verduras",
            "Peso Total: 1500 kg",
        ]
    )
    use_case.execute(
        [
            UploadedFileInput(
                filename="doc.pdf", stream=io.BytesIO(pdf_bytes), content_bytes=pdf_bytes
            )
        ]
    )

    events = audit_service.get_events()
    detected_events = [e for e in events if e.action == AuditAction.COMPANY_DETECTED]
    assert len(detected_events) == 1
    assert detected_events[0].company_id == "CULTIVOS_ARABA"


# ==============================================================================
# 19. Flujo operativo completo para Cultivos Araba
# ==============================================================================
def test_full_workflow_cultivos_araba(tmp_path: Path) -> None:
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    deliv_repo = InMemoryEmailDeliveryRepository()
    storage = FilesystemStorageAdapter(tmp_path)
    audit = InMemoryAuditService()
    renderer = ReportLabPdfRenderer()
    fake_sender = FakeMicrosoftGraphEmailSender()

    # 1. Crear expedición de Cultivos Araba (simulando importación)
    exp = Expedition(
        internal_id="TD-2026-ARA-FULL",
        company_id="CULTIVOS_ARABA",
        shipper_name="Cultivos Araba S.L.",
        shipper_tax_id=NIF("B01584988"),
        shipper_address="Polígono Industrial Júndiz, Vitoria-Gasteiz",
        origin="Vitoria",
        destination="Zaragoza",
        goods="Patata Alavesa",
        weight=Weight(4500.0),
        status=ExpeditionStatus.PENDIENTE_MATRICULA,
    )
    exp_repo.save(exp)

    # 2. Captura de vehículo en muelle
    assign_uc = AssignVehicleToExpeditionUseCase(expedition_repo=exp_repo, audit_service=audit)
    assign_res = assign_uc.execute(
        AssignVehicleInputDTO(
            expedition_id=exp.id,
            vehicle_type="RIGIDO",
            tractor_registration="9876XYZ",
            carrier_name="Transportes Álava S.L.",
            carrier_tax_id="B01999888",
            carrier_email="logistica@transalava.com",
        )
    )
    assert assign_res.status == ExpeditionStatus.LISTA_PARA_DECA.value

    # 3. Emisión del DeCA
    emit_uc = EmitDeCAUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        pdf_renderer=renderer,
        storage_service=storage,
        audit_service=audit,
    )
    emit_res = emit_uc.execute(EmitDeCAInputDTO(expedition_id=str(exp.id)))
    assert emit_res.company_id == "CULTIVOS_ARABA"
    assert emit_res.status == "ISSUED"

    # Verificar DeCA emitido y su snapshot
    deca = deca_repo.find_by_expedition_id(exp.id)
    assert deca is not None
    assert deca.company_id == "CULTIVOS_ARABA"
    v1 = deca.get_version(1)
    assert v1.snapshot_data["company_id"] == "CULTIVOS_ARABA"
    assert v1.snapshot_data["shipper"]["name"] == "Cultivos Araba S.L."

    # 4. Envío del DeCA por correo al transportista
    send_uc = SendDeCAEmailUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        storage_service=storage,
        email_sender=fake_sender,
        email_delivery_repo=deliv_repo,
        audit_service=audit,
        sender_email="pedidos@tomatesdeautor.com",
    )
    send_res = send_uc.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))
    assert send_res.email_status == EmailDeliveryStatus.EMAIL_SENT.value

    # Comprobar estado final de la expedición
    updated_exp = exp_repo.get_by_id(exp.id)
    assert updated_exp.status == ExpeditionStatus.ENVIADA
