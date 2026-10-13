from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from src.domain.enums import DocumentFormatType
from src.domain.value_objects import ExtractedField


@dataclass(frozen=True)
class RawDocumentDTO:
    """Representación del contenido textual y metadatos extraídos del PDF original."""

    content_bytes: bytes
    filename: str
    sha256_hash: str
    extracted_text: str = ""
    pages_count: int = 1


@dataclass(frozen=True)
class NormalizedDocumentDTO:
    """Documento normalizado común, independiente del formato de origen."""

    format_type: DocumentFormatType
    format_confidence: float

    # Campos con trazabilidad de certeza y calidad
    reference: ExtractedField[str]
    fiscal_year: ExtractedField[str]
    transport_date: ExtractedField[date]
    shipper_name: ExtractedField[str]
    shipper_tax_id: ExtractedField[str]
    shipper_address: ExtractedField[str]
    carrier_name: ExtractedField[str]
    carrier_tax_id: ExtractedField[str]
    origin: ExtractedField[str]
    destination: ExtractedField[str]
    goods: ExtractedField[str]
    weight_kg: ExtractedField[float]
    tractor_plate: ExtractedField[str]
    trailer_plate: ExtractedField[str]
    observations: ExtractedField[str]

    # Campos de auditoría detallada (Prompt 03.5)
    document_number: ExtractedField[str] = field(default_factory=ExtractedField.not_present)
    external_reference: ExtractedField[str] = field(default_factory=ExtractedField.not_present)
    consignee: ExtractedField[str] = field(default_factory=ExtractedField.not_present)
    total_packages: ExtractedField[int] = field(default_factory=ExtractedField.not_present)
    total_gross_weight_kg: ExtractedField[float] = field(default_factory=ExtractedField.not_present)
    total_net_weight_kg: ExtractedField[float] = field(default_factory=ExtractedField.not_present)

    raw_carrier_text: str = ""
    metadata: dict = field(default_factory=dict)

    # Detección de empresa emisora
    issuer_company_id: str | None = None
    issuer_detection_confidence: float = 0.0
    issuer_detection_source: str = "NONE"

    def __post_init__(self) -> None:
        if not self.reference.is_valid:
            if self.external_reference.is_valid:
                object.__setattr__(self, "reference", self.external_reference)
            elif self.document_number.is_valid:
                object.__setattr__(self, "reference", self.document_number)

        if not self.consignee.is_valid and self.destination.is_valid:
            object.__setattr__(self, "consignee", self.destination)

        if not self.total_gross_weight_kg.is_valid and self.weight_kg.is_valid:
            object.__setattr__(self, "total_gross_weight_kg", self.weight_kg)
        elif not self.weight_kg.is_valid and self.total_gross_weight_kg.is_valid:
            object.__setattr__(self, "weight_kg", self.total_gross_weight_kg)

    @property
    def document_type(self) -> DocumentFormatType:
        return self.format_type

    @property
    def loading_date(self) -> ExtractedField[date]:
        return self.transport_date

    @property
    def shipper(self) -> ExtractedField[str]:
        return self.shipper_name

    @property
    def carrier(self) -> ExtractedField[str]:
        return self.carrier_name

    def is_valid_for_import(self, min_confidence: float = 0.5) -> bool:
        """Determina si el documento cumple los REQUISITOS DE IMPORTACIÓN.

        Permite registrar la expedición en estado PENDIENTE_MATRICULA.
        REGLA DE NEGOCIO (Prompt 03.5):
        - Transportista y matrícula NO deben ser requisitos para importar una Carta de Porte
          o CMR que los deja vacíos en muelle.
        - La referencia externa (albarán) NO es fiable en Cartas de Porte
          y puede ser null/NO_PRESENTE.
        - Requisitos mínimos:
          1. Formato reconocido con confianza >= min_confidence.
          2. Fecha de transporte válida.
          3. Cargador válido (Tomates de Autor S.L.).
          4. Origen y Destino/Consignatario válidos.
          5. Mercancía válida.
          6. Peso válido (bruto, neto o total).
        """
        if self.format_type == DocumentFormatType.DESCONOCIDO:
            return False
        if self.format_confidence < min_confidence:
            return False

        critical_fields = [
            self.transport_date,
            self.shipper_name,
            self.origin,
            self.destination,
            self.goods,
        ]
        if not all(f.is_valid for f in critical_fields):
            return False

        has_weight = (
            self.total_gross_weight_kg.is_valid
            or self.total_net_weight_kg.is_valid
            or self.weight_kg.is_valid
        )
        return has_weight

    def is_ready_for_deca(self) -> bool:
        """Determina si la expedición cumple los REQUISITOS PARA READY_FOR_DECA.

        Para emitir el DeCA es OBLIGATORIO:
        - Cumplir los requisitos de importación.
        - Transportista identificado y con NIF.
        - Al menos matrícula tractora asignada.
        """
        if not self.is_valid_for_import():
            return False
        if not (self.carrier_name.is_valid and self.carrier_tax_id.is_valid):
            return False
        return self.tractor_plate.is_valid

    def is_complete_and_confident(self, min_confidence: float = 0.5) -> bool:
        """Delega en los requisitos de importación para admisión en el flujo operativo."""
        return self.is_valid_for_import(min_confidence=min_confidence)


@dataclass(frozen=True)
class ImportResultItemDTO:
    """Resultado individual de procesar un archivo en un lote."""

    filename: str
    sha256_hash: str
    format_type: DocumentFormatType
    reference: str | None
    status: str
    company_id: str | None = None
    expedition_id: str | None = None
    internal_id: str | None = None
    message: str = ""
    fields_needing_review: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BatchImportResultDTO:
    """Resumen consolidado de una operación de importación masiva de documentos."""

    total_files: int
    imported_count: int
    duplicates_count: int
    review_needed_count: int
    items: list[ImportResultItemDTO]
    rejected_count: int = 0

