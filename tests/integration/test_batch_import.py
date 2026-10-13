from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from src.config.companies import TEST_API_KEY_TOMATES
from src.application.ports.expedition_repository import ExpeditionRepositoryPort
from src.application.use_cases.import_documents_batch import (
    ImportDocumentsBatchUseCase,
    UploadedFileInput,
)
from src.domain.entities.expedition import Expedition
from src.domain.enums import DocumentFormatType, ExpeditionStatus
from src.infrastructure.importers.pdf_document_importer import PdfDocumentImporter
from src.infrastructure.parsers.composite_parser import CompositeDocumentParser
from src.infrastructure.storage.filesystem_storage import FilesystemStorageAdapter


def create_sample_pdf(text_lines: list[str]) -> bytes:
    """Genera un PDF binario real con capas de texto legibles para pruebas."""
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


class InMemoryExpeditionRepo(ExpeditionRepositoryPort):
    """Repositorio en memoria para pruebas de deduplicación de expediciones."""

    def __init__(self) -> None:
        self.expeditions: dict[str, Expedition] = {}

    def save(self, expedition: Expedition, company_id: str | None = None) -> Expedition:
        if company_id and not expedition.company_id:
            expedition.company_id = company_id
        self.expeditions[str(expedition.id)] = expedition
        return expedition

    def get_by_id(self, expedition_id) -> Expedition | None:
        return self.expeditions.get(str(expedition_id))

    def find_by_reference(
        self, reference: str, fiscal_year: str, company_id: str | None = None
    ) -> Expedition | None:
        for exp in self.expeditions.values():
            if company_id and exp.company_id and exp.company_id != company_id:
                continue
            if exp.reference == reference and exp.fiscal_year == fiscal_year:
                return exp
        return None

    def list_pending_vehicle(self) -> list[Expedition]:
        return [
            e for e in self.expeditions.values() if e.status == ExpeditionStatus.PENDIENTE_MATRICULA
        ]

    def next_internal_id(
        self, fiscal_year: str, company_id: str | None = None, prefix: str = "TD"
    ) -> str:
        count = (
            sum(
                1
                for e in self.expeditions.values()
                if e.fiscal_year == fiscal_year and (not company_id or e.company_id == company_id)
            )
            + 1
        )
        return f"{prefix}-{fiscal_year}-{count:05d}"

    def find_duplicate_cargo(
        self,
        fiscal_year: str,
        transport_date,
        destination: str | None,
        weight_kg: float | None,
        company_id: str | None = None,
    ) -> Expedition | None:
        for exp in self.expeditions.values():
            if company_id and exp.company_id and exp.company_id != company_id:
                continue
            if exp.fiscal_year != fiscal_year:
                continue
            if transport_date and exp.transport_date != transport_date:
                continue
            if destination and exp.destination != destination:
                continue
            if weight_kg and exp.weight_kg and abs(exp.weight_kg - weight_kg) > 0.01:
                continue
            return exp
        return None


def test_batch_import_30_documents_mix(tmp_path: Path) -> None:
    """Simula la importación masiva de 30 documentos (Cartas de Porte y CMRs) simultáneos."""
    importer = PdfDocumentImporter(CompositeDocumentParser())
    storage = FilesystemStorageAdapter(tmp_path)
    repo = InMemoryExpeditionRepo()
    use_case = ImportDocumentsBatchUseCase(importer=importer, storage=storage, expedition_repo=repo)

    files: list[UploadedFileInput] = []

    # 15 Cartas de Porte
    for i in range(1, 16):
        pdf_bytes = create_sample_pdf(
            [
                "ALBARÁN DE CARGA / CARTA DE PORTE NACIONAL HISPATEC",
                f"Albarán Nº: CP-2026-{i:04d}",
                "Fecha Transporte: 03/10/2026",
                "Cargador: Tomates de Autor S.L.",
                "NIF Cargador: B04123456",
                f"Transportista: Transportes Almería {i} S.L.",
                "Origen: El Ejido (Almería)",
                "Destino: Madrid Central",
                "Mercancía: Tomate Pera Export",
                f"Peso Total: {15000 + i * 100} kg",
            ]
        )
        files.append(
            UploadedFileInput(
                filename=f"carta_porte_{i}.pdf",
                stream=io.BytesIO(pdf_bytes),
                content_bytes=pdf_bytes,
            )
        )

    # 15 CMRs internacionales
    for i in range(1, 16):
        pdf_bytes = create_sample_pdf(
            [
                "CMR - INTERNATIONAL CONSIGNMENT NOTE",
                "CONTRAT DE TRANSPORT INTERNATIONAL",
                f"CMR Nº: CMR-INT-2026-{i:04d}",
                "Date: 03/10/2026",
                "1 Expéditeur / Sender: Tomates de Autor S.L.",
                f"16 Transporteur / Carrier: EuroTransport Cargo {i}",
                "4 Place of taking over: El Ejido, Spain",
                "2 Destinataire / Consignee: Munich Supermarket, Germany",
                "6 Nature of the goods: Vine Tomatoes Extra",
                f"11 Gross weight: {20000 + i * 50} kg",
            ]
        )
        files.append(
            UploadedFileInput(
                filename=f"cmr_{i}.pdf",
                stream=io.BytesIO(pdf_bytes),
                content_bytes=pdf_bytes,
            )
        )

    assert len(files) == 30

    result = use_case.execute(files)

    assert result.total_files == 30
    assert result.imported_count == 30
    assert result.duplicates_count == 0
    assert result.review_needed_count == 0
    assert len(repo.expeditions) == 30

    # Todos deben estar en PENDIENTE_MATRICULA
    for exp in repo.expeditions.values():
        assert exp.status == ExpeditionStatus.PENDIENTE_MATRICULA


def test_batch_import_deduplication(tmp_path: Path) -> None:
    importer = PdfDocumentImporter(CompositeDocumentParser())
    storage = FilesystemStorageAdapter(tmp_path)
    repo = InMemoryExpeditionRepo()
    use_case = ImportDocumentsBatchUseCase(importer=importer, storage=storage, expedition_repo=repo)

    pdf_bytes = create_sample_pdf(
        [
            "CARTA DE PORTE NACIONAL",
            "Albarán Nº: CP-DUPLICADA-001",
            "Fecha: 03/10/2026",
            "Cargador: Tomates de Autor S.L.",
            "Transportista: Transportes ABC",
            "Origen: Almería",
            "Destino: Valencia",
            "Mercancía: Tomate",
            "Peso: 5000 kg",
        ]
    )

    files = [
        UploadedFileInput("doc_original.pdf", io.BytesIO(pdf_bytes), pdf_bytes),
        UploadedFileInput("doc_copia.pdf", io.BytesIO(pdf_bytes), pdf_bytes),  # Mismo SHA-256
    ]

    result = use_case.execute(files)

    assert result.total_files == 2
    assert result.imported_count == 1
    assert result.duplicates_count == 1
    assert result.items[0].status == "PENDING_VEHICLE"
    assert result.items[1].status == "DUPLICATE"


def test_batch_import_unknown_format_fallback_to_review(tmp_path: Path) -> None:
    importer = PdfDocumentImporter(CompositeDocumentParser())
    storage = FilesystemStorageAdapter(tmp_path)
    repo = InMemoryExpeditionRepo()
    use_case = ImportDocumentsBatchUseCase(importer=importer, storage=storage, expedition_repo=repo)

    unknown_pdf = create_sample_pdf(
        [
            "CERTIFICADO DE CALIDAD DE AGUAS",
            "Informe Analítico Nº: LAB-992",
            "Laboratorio Central de Análisis",
        ]
    )

    files = [
        UploadedFileInput("analitica.pdf", io.BytesIO(unknown_pdf), unknown_pdf),
    ]

    result = use_case.execute(files)
    assert result.total_files == 1
    assert result.review_needed_count == 1
    assert result.items[0].status == "NEEDS_REVIEW"
    assert result.items[0].format_type == DocumentFormatType.DESCONOCIDO

    saved_exp = list(repo.expeditions.values())[0]
    assert saved_exp.status == ExpeditionStatus.PENDIENTE_REVISION


def test_api_import_batch_endpoint(client: TestClient) -> None:
    pdf1 = create_sample_pdf(
        [
            "CARTA DE PORTE NACIONAL HISPATEC",
            "Albarán Nº: CP-API-001",
            "Fecha: 03/10/2026",
            "Cargador: Tomates de Autor S.L.",
            "Transportista: Transportes Sur",
            "Origen: El Ejido",
            "Destino: Sevilla",
            "Mercancía: Tomates",
            "Peso: 4000 kg",
        ]
    )

    pdf2 = create_sample_pdf(
        [
            "CMR INTERNATIONAL CONSIGNMENT NOTE",
            "CMR Nº: CMR-API-002",
            "Date: 03/10/2026",
            "1 Expéditeur / Sender: Tomates de Autor S.L.",
            "16 Transporteur: EuroTransit",
            "4 Place of loading: El Ejido",
            "2 Consignee: Perpignan Fruits",
            "6 Goods: Fresh Tomatoes",
            "11 Gross weight: 12000 kg",
        ]
    )

    response = client.post(
        "/api/v1/documents/import-batch",
        headers={"Authorization": f"Bearer {TEST_API_KEY_TOMATES}"},
        files=[
            ("files", ("cp1.pdf", pdf1, "application/pdf")),
            ("files", ("cmr2.pdf", pdf2, "application/pdf")),
        ],
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] == 2
    assert data["imported_count"] == 2
    assert data["duplicates_count"] == 0
    assert len(data["items"]) == 2


def test_batch_import_real_carta_de_porte_without_albaran_and_carrier(tmp_path: Path) -> None:
    """Verifica que la Carta de Porte habitual de Tomates de Autor (sin albarán y
    sin transportista/matrículas) se acepte directamente en PENDIENTE_MATRICULA
    sin enviarse a PENDIENTE_REVISION."""
    importer = PdfDocumentImporter(CompositeDocumentParser())
    storage = FilesystemStorageAdapter(tmp_path)
    repo = InMemoryExpeditionRepo()
    use_case = ImportDocumentsBatchUseCase(importer=importer, storage=storage, expedition_repo=repo)

    real_cp_pdf = create_sample_pdf(
        [
            "TOMATES DE AUTOR S.L.",
            "CARTA DE PORTE NACIONAL",
            "Documento Nº: CP-2026/00450",
            "Fecha Transporte: 03/10/2026",
            "Cargador: Tomates de Autor S.L.",
            "CIF Cargador: B04123456",
            "Lugar de Carga: El Ejido (Almería)",
            "Lugar de Descarga: Mercamadrid, Nave 4 (Madrid)",
            "Consignatario: Frutas Hermanos Sánchez S.A.",
            "Mercancía: Tomate Rama Extra Calibre M",
            "Total Bultos: 1200 cajas",
            "Peso Bruto: 18.450,50 kg",
            "Peso Neto: 17.200,00 kg",
        ]
    )

    files = [
        UploadedFileInput("cp_real_00450.pdf", io.BytesIO(real_cp_pdf), real_cp_pdf),
    ]

    result = use_case.execute(files)

    assert result.total_files == 1
    assert result.imported_count == 1
    assert result.review_needed_count == 0
    assert result.items[0].status == "PENDING_VEHICLE"

    saved_exp = list(repo.expeditions.values())[0]
    assert saved_exp.status == ExpeditionStatus.PENDIENTE_MATRICULA
    assert saved_exp.destination == "Mercamadrid, Nave 4 (Madrid)"
    assert saved_exp.weight.kg == 18450.50
    assert saved_exp.document_id is not None


def test_batch_deduplication_cargo_for_carta_de_porte_without_albaran(tmp_path: Path) -> None:
    """Verifica la deduplicación de Cartas de Porte sin albarán mediante clave de negocio de carga
    (ejercicio, fecha, destino y peso) incluso si los archivos tienen hash SHA-256 diferente."""
    importer = PdfDocumentImporter(CompositeDocumentParser())
    storage = FilesystemStorageAdapter(tmp_path)
    repo = InMemoryExpeditionRepo()
    use_case = ImportDocumentsBatchUseCase(importer=importer, storage=storage, expedition_repo=repo)

    # Archivo 1
    pdf1 = create_sample_pdf(
        [
            "TOMATES DE AUTOR S.L.",
            "CARTA DE PORTE NACIONAL",
            "Documento Nº: CP-ORIGINAL-01",
            "Fecha: 03/10/2026",
            "Cargador: Tomates de Autor S.L.",
            "Origen: El Ejido",
            "Destino: Mercabarna Nave 12",
            "Mercancía: Tomates Canarios",
            "Peso Bruto: 14200 kg",
        ]
    )
    # Archivo 2 con texto ligeramente distinto para variar SHA-256 pero misma carga
    pdf2 = create_sample_pdf(
        [
            "TOMATES DE AUTOR S.L.",
            "CARTA DE PORTE NACIONAL HISPATEC COPIA",
            "Documento Nº: CP-COPIA-02",
            "Fecha: 03/10/2026",
            "Cargador: Tomates de Autor S.L.",
            "Origen: El Ejido",
            "Destino: Mercabarna Nave 12",
            "Mercancía: Tomates Canarios",
            "Peso Bruto: 14200 kg",
            "Nota adicional de muelle",
        ]
    )

    # Ejecución secuencial o por lote
    res1 = use_case.execute([UploadedFileInput("file1.pdf", io.BytesIO(pdf1), pdf1)])
    assert res1.imported_count == 1

    res2 = use_case.execute([UploadedFileInput("file2.pdf", io.BytesIO(pdf2), pdf2)])
    assert res2.imported_count == 0
    assert res2.duplicates_count == 1
    assert res2.items[0].status == "DUPLICATE"


def test_batch_import_concurrency_config(tmp_path: Path) -> None:
    """Verifica que el límite de concurrencia max_concurrency se respeta y procesa correctamente."""
    importer = PdfDocumentImporter(CompositeDocumentParser())
    storage = FilesystemStorageAdapter(tmp_path)
    repo = InMemoryExpeditionRepo()
    use_case = ImportDocumentsBatchUseCase(
        importer=importer, storage=storage, expedition_repo=repo, max_concurrency=4
    )

    files = []
    for i in range(8):
        content = create_sample_pdf(
            [
                "CARTA DE PORTE NACIONAL HISPATEC",
                f"Documento Nº: CP-CONC-{i}",
                "Fecha: 03/10/2026",
                "Cargador: Tomates de Autor S.L.",
                "Origen: El Ejido",
                f"Destino: Plataforma Logística {i}",
                "Mercancía: Tomate Ensalada",
                f"Peso: {10000 + i * 500} kg",
            ]
        )
        files.append(UploadedFileInput(f"f_{i}.pdf", io.BytesIO(content), content))

    result = use_case.execute(files)
    assert result.total_files == 8
    assert result.imported_count == 8
    assert result.duplicates_count == 0
    assert len(repo.expeditions) == 8


def test_batch_import_cross_tenant_pdf_rejected(tmp_path: Path) -> None:
    """Verifica que un PDF de otra empresa registrada se RECHACE completamente
    sin persistir en base de datos ni escribir en disco cuando el tenant autenticado difiere."""
    importer = PdfDocumentImporter(CompositeDocumentParser())
    storage = FilesystemStorageAdapter(tmp_path)
    repo = InMemoryExpeditionRepo()
    use_case = ImportDocumentsBatchUseCase(importer=importer, storage=storage, expedition_repo=repo)

    araba_pdf = create_sample_pdf(
        [
            "CULTIVOS ARABA S.L.",
            "CARTA DE PORTE NACIONAL",
            "Documento Nº: CP-ARABA-0099",
            "Fecha Transporte: 03/10/2026",
            "Cargador: Cultivos Araba S.L.",
            "CIF Cargador: B01987654",
            "Lugar de Carga: Vitoria-Gasteiz",
            "Lugar de Descarga: Bilbao Muelle 3",
            "Mercancía: Patata de Álava",
            "Peso Bruto: 22.000 kg",
        ]
    )

    files = [UploadedFileInput("araba_doc.pdf", io.BytesIO(araba_pdf), araba_pdf)]

    # El cliente se autentica como TOMATES_DE_AUTOR pero sube un PDF de CULTIVOS_ARABA
    result = use_case.execute(files, company_id="TOMATES_DE_AUTOR")

    assert result.total_files == 1
    assert result.rejected_count == 1
    assert result.imported_count == 0
    assert result.review_needed_count == 0
    assert result.items[0].status == "REJECTED"
    assert "Conflicto de tenant" in result.items[0].message
    assert result.items[0].company_id == "CULTIVOS_ARABA"

    # Ninguna expedición persistida en el repositorio
    assert len(repo.expeditions) == 0

    # Ningún archivo guardado en el almacenamiento físico
    saved_files = list(tmp_path.rglob("*.pdf"))
    assert len(saved_files) == 0


def test_batch_import_unrecognized_shipper_assigned_to_authorized_tenant_needing_review(
    tmp_path: Path,
) -> None:
    """Verifica que un documento con cargador no registrado se asigne al tenant autenticado,
    pero se marque como PENDIENTE_REVISION requiriendo revisión manual de empresa emisora."""
    importer = PdfDocumentImporter(CompositeDocumentParser())
    storage = FilesystemStorageAdapter(tmp_path)
    repo = InMemoryExpeditionRepo()
    use_case = ImportDocumentsBatchUseCase(importer=importer, storage=storage, expedition_repo=repo)

    unknown_shipper_pdf = create_sample_pdf(
        [
            "AGRÍCOLA EL MEDITERRÁNEO S.L.",
            "CARTA DE PORTE NACIONAL",
            "Documento Nº: CP-MED-00123",
            "Fecha: 03/10/2026",
            "Cargador: Agrícola El Mediterráneo S.L.",
            "CIF Cargador: B99887766",
            "Lugar de Carga: El Ejido",
            "Lugar de Descarga: Zaragoza",
            "Mercancía: Pimientos Padrón",
            "Peso Bruto: 8500 kg",
        ]
    )

    files = [UploadedFileInput("unknown_doc.pdf", io.BytesIO(unknown_shipper_pdf), unknown_shipper_pdf)]

    result = use_case.execute(files, company_id="TOMATES_DE_AUTOR")

    assert result.total_files == 1
    assert result.rejected_count == 0
    assert result.review_needed_count == 1
    assert result.imported_count == 0
    assert result.items[0].status == "NEEDS_REVIEW"
    assert "empresa_emisora" in result.items[0].fields_needing_review

    # La expedición existe y pertenece al tenant autenticado, preservando los datos del cargador real
    assert len(repo.expeditions) == 1
    saved_exp = list(repo.expeditions.values())[0]
    assert saved_exp.company_id == "TOMATES_DE_AUTOR"
    assert saved_exp.shipper_name == "Agrícola El Mediterráneo S.L."
    assert saved_exp.status == ExpeditionStatus.PENDIENTE_REVISION


def test_batch_import_mix_valid_cross_tenant_and_unrecognized(tmp_path: Path) -> None:
    """Verifica un lote heterogéneo: un documento propio, un documento de otra empresa registrada,
    y un documento de cargador desconocido."""
    importer = PdfDocumentImporter(CompositeDocumentParser())
    storage = FilesystemStorageAdapter(tmp_path)
    repo = InMemoryExpeditionRepo()
    use_case = ImportDocumentsBatchUseCase(importer=importer, storage=storage, expedition_repo=repo)

    # 1. Documento legítimo de TOMATES_DE_AUTOR
    pdf_legit = create_sample_pdf(
        [
            "TOMATES DE AUTOR S.L.",
            "CARTA DE PORTE NACIONAL",
            "Documento Nº: CP-LEGIT-01",
            "Fecha: 03/10/2026",
            "Cargador: Tomates de Autor S.L.",
            "CIF Cargador: B04123456",
            "Origen: El Ejido",
            "Destino: Mercamadrid",
            "Mercancía: Tomates",
            "Peso: 15000 kg",
        ]
    )
    # 2. Documento de CULTIVOS_ARABA (debe ser rechazado)
    pdf_cross = create_sample_pdf(
        [
            "CULTIVOS ARABA S.L.",
            "CARTA DE PORTE NACIONAL",
            "Documento Nº: CP-CROSS-02",
            "Fecha: 03/10/2026",
            "Cargador: Cultivos Araba S.L.",
            "CIF Cargador: B01987654",
            "Origen: Vitoria",
            "Destino: Bilbao",
            "Mercancía: Patatas",
            "Peso: 12000 kg",
        ]
    )
    # 3. Documento con cargador no registrado (debe quedar en revisión para el tenant)
    pdf_unknown = create_sample_pdf(
        [
            "FRUTAS DEL SUR S.L.",
            "CARTA DE PORTE NACIONAL",
            "Documento Nº: CP-UNK-03",
            "Fecha: 03/10/2026",
            "Cargador: Frutas del Sur S.L.",
            "CIF Cargador: B55443322",
            "Origen: Motril",
            "Destino: Granada",
            "Mercancía: Aguacates",
            "Peso: 6000 kg",
        ]
    )

    files = [
        UploadedFileInput("legit.pdf", io.BytesIO(pdf_legit), pdf_legit),
        UploadedFileInput("cross.pdf", io.BytesIO(pdf_cross), pdf_cross),
        UploadedFileInput("unknown.pdf", io.BytesIO(pdf_unknown), pdf_unknown),
    ]

    result = use_case.execute(files, company_id="TOMATES_DE_AUTOR")

    assert result.total_files == 3
    assert result.imported_count == 1
    assert result.rejected_count == 1
    assert result.review_needed_count == 1

    # Exactamente 2 expediciones persistidas, ambas asignadas al tenant autenticado
    assert len(repo.expeditions) == 2
    for exp in repo.expeditions.values():
        assert exp.company_id == "TOMATES_DE_AUTOR"


def test_api_import_batch_cross_tenant_rejection(client: TestClient) -> None:
    """Verifica que el endpoint API rechace con status REJECTED un PDF perteneciente
    a otra empresa que la autorizada por la API Key."""
    araba_pdf = create_sample_pdf(
        [
            "CULTIVOS ARABA S.L.",
            "CARTA DE PORTE NACIONAL",
            "Documento Nº: CP-API-CROSS-01",
            "Fecha: 03/10/2026",
            "Cargador: Cultivos Araba S.L.",
            "CIF Cargador: B01987654",
            "Origen: Vitoria",
            "Destino: San Sebastián",
            "Mercancía: Remolacha",
            "Peso: 18000 kg",
        ]
    )

    response = client.post(
        "/api/v1/documents/import-batch",
        headers={"Authorization": f"Bearer {TEST_API_KEY_TOMATES}"},
        files=[
            ("files", ("cross_araba.pdf", araba_pdf, "application/pdf")),
        ],
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] == 1
    assert data["rejected_count"] == 1
    assert data["imported_count"] == 0
    assert data["items"][0]["status"] == "REJECTED"
    assert "Conflicto de tenant" in data["items"][0]["message"]

