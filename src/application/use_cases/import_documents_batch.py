import concurrent.futures
from functools import partial
import hashlib
import io
import logging
import threading
from dataclasses import dataclass
from datetime import date
from typing import BinaryIO

from src.application.dtos.document_dto import (
    BatchImportResultDTO,
    ImportResultItemDTO,
    NormalizedDocumentDTO,
)
from src.application.ports.audit_service import AuditServicePort
from src.application.ports.company_repository import CompanyRepositoryPort
from src.application.ports.document_importer import DocumentImporterPort
from src.application.ports.expedition_repository import ExpeditionRepositoryPort
from src.application.ports.storage_service import StorageServicePort
from src.domain.entities.audit_event import AuditEvent
from src.domain.entities.document import Document
from src.domain.entities.expedition import Expedition
from src.domain.enums import (
    AuditAction,
    DocumentFormatType,
    DocumentProcessingStatus,
    ExpeditionStatus,
)
from src.domain.services.company_detector import (
    CompanyDetector,
)
from src.domain.value_objects import Weight

logger = logging.getLogger("deca_light.use_cases.batch_import")


@dataclass
class UploadedFileInput:
    """Entrada para un archivo individual a procesar en lote."""

    filename: str
    stream: BinaryIO
    content_bytes: bytes | None = None

    def get_bytes(self) -> bytes:
        if self.content_bytes is not None:
            return self.content_bytes
        self.stream.seek(0)
        content = self.stream.read()
        self.stream.seek(0)
        return content


class ImportDocumentsBatchUseCase:
    """Caso de uso para la importación masiva y concurrente de cartas de porte y CMRs."""

    def __init__(
        self,
        importer: DocumentImporterPort,
        storage: StorageServicePort,
        expedition_repo: ExpeditionRepositoryPort | None = None,
        audit_service: AuditServicePort | None = None,
        company_repo: CompanyRepositoryPort | None = None,
        max_concurrency: int = 10,
    ) -> None:
        self.importer = importer
        self.storage = storage
        self.expedition_repo = expedition_repo
        self.audit_service = audit_service
        self.company_repo = company_repo
        self.max_concurrency = max(1, max_concurrency)
        self._processed_hashes: set[str] = set()
        self._in_flight_business_keys: set[str] = set()
        self._lock = threading.Lock()

    def execute(
        self, files: list[UploadedFileInput], company_id: str | None = None
    ) -> BatchImportResultDTO:
        total_files = len(files)
        logger.info(
            "Iniciando importación por lote de %d archivos (concurrencia máx: %d, tenant: %s)",
            total_files,
            self.max_concurrency,
            company_id or "NO_ESPECIFICADO",
        )

        if total_files <= 1:
            items = [
                self._process_single_file(f, authorized_company_id=company_id)
                for f in files
            ]
        else:
            workers = min(total_files, self.max_concurrency)
            process_fn = partial(
                self._process_single_file, authorized_company_id=company_id
            )
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                items = list(executor.map(process_fn, files))

        imported_count = sum(1 for item in items if item.status in ("PENDING_VEHICLE", "IMPORTED"))
        duplicates_count = sum(1 for item in items if item.status == "DUPLICATE")
        review_needed_count = sum(1 for item in items if item.status == "NEEDS_REVIEW")
        rejected_count = sum(1 for item in items if item.status == "REJECTED")

        logger.info(
            "Fin de lote: Total=%d, Importados=%d, Duplicados=%d, PendientesRevisión=%d, Rechazados=%d",
            total_files,
            imported_count,
            duplicates_count,
            review_needed_count,
            rejected_count,
        )

        return BatchImportResultDTO(
            total_files=total_files,
            imported_count=imported_count,
            duplicates_count=duplicates_count,
            review_needed_count=review_needed_count,
            items=items,
            rejected_count=rejected_count,
        )

    def _process_single_file(
        self,
        file_input: UploadedFileInput,
        authorized_company_id: str | None = None,
    ) -> ImportResultItemDTO:
        filename = file_input.filename
        content = file_input.get_bytes()
        sha256_hash = hashlib.sha256(content).hexdigest()

        # 1. Deduplicación por hash SHA-256 a nivel binario
        with self._lock:
            if sha256_hash in self._processed_hashes:
                return ImportResultItemDTO(
                    filename=filename,
                    sha256_hash=sha256_hash,
                    format_type=DocumentFormatType.DESCONOCIDO,
                    reference=None,
                    status="DUPLICATE",
                    message="Archivo idéntico ya procesado en esta sesión o base de datos.",
                )
            self._processed_hashes.add(sha256_hash)

        # 2. Parseo determinista y normalización
        try:
            stream = io.BytesIO(content)
            normalized: NormalizedDocumentDTO = self.importer.parse(stream, filename)
        except Exception as exc:
            with self._lock:
                self._processed_hashes.discard(sha256_hash)
            logger.error("Error inesperado parseando '%s': %s", filename, str(exc))
            return ImportResultItemDTO(
                filename=filename,
                sha256_hash=sha256_hash,
                format_type=DocumentFormatType.DESCONOCIDO,
                reference=None,
                status="NEEDS_REVIEW",
                message=f"Fallo en la lectura del documento: {exc}",
            )

        ref_val = normalized.external_reference.value or normalized.reference.value
        year_val = normalized.fiscal_year.value or str(date.today().year)

        # Detección determinista de la empresa emisora
        detected_company_id: str | None = None
        det_confidence: float = 0.0
        det_source: str = "NONE"
        company_detection_failed: bool = False

        if self.company_repo:
            companies = self.company_repo.list_active()
            det_res = CompanyDetector.detect(
                companies=companies,
                shipper_tax_id=normalized.shipper_tax_id.value,
                shipper_name=normalized.shipper.value,
            )
            if det_res.detected:
                detected_company_id = det_res.company_id
                det_confidence = det_res.confidence
                det_source = str(det_res.source)
            else:
                company_detection_failed = True
        else:
            s_name = (normalized.shipper.value or "").upper()
            if "CULTIVOS ARABA" in s_name:
                detected_company_id = "CULTIVOS_ARABA"
                det_confidence = 1.0
                det_source = "FALLBACK"
            elif "TOMATES DE AUTOR" in s_name:
                detected_company_id = "TOMATES_DE_AUTOR"
                det_confidence = 1.0
                det_source = "FALLBACK"
            else:
                company_detection_failed = True

        # Validación multiempresa (multi-tenant) e integridad de pertenencia:
        if authorized_company_id:
            if detected_company_id and detected_company_id != authorized_company_id:
                # Conflicto estricto de tenant: el documento pertenece a otra empresa registrada en la plataforma
                with self._lock:
                    self._processed_hashes.discard(sha256_hash)
                logger.warning(
                    "Rechazado documento '%s': pertenece a '%s' pero el tenant autenticado es '%s'",
                    filename,
                    detected_company_id,
                    authorized_company_id,
                )
                return ImportResultItemDTO(
                    filename=filename,
                    sha256_hash=sha256_hash,
                    format_type=normalized.format_type,
                    reference=ref_val,
                    status="REJECTED",
                    company_id=detected_company_id,
                    message=(
                        f"Conflicto de tenant: el documento pertenece a la empresa "
                        f"'{detected_company_id}', no autorizada para el tenant activo '{authorized_company_id}'."
                    ),
                )
            # Concordancia o cargador externo no registrado: pertenece al tenant autenticado
            effective_company_id = authorized_company_id
        else:
            # Compatibilidad hacia atrás (ejecución sin contexto de autenticación explícito)
            effective_company_id = detected_company_id or ""

        # 3. Deduplicación por clave de negocio según formato y empresa (Prompt 03.5 + 7.5)
        with self._lock:
            business_key: str | None = None
            company_prefix = effective_company_id or "UNKNOWN"
            if normalized.format_type == DocumentFormatType.CMR:
                cmr_ref = (
                    normalized.external_reference.value
                    or normalized.document_number.value
                    or normalized.reference.value
                )
                if cmr_ref:
                    business_key = f"{company_prefix}:CMR:{year_val}:{cmr_ref}"
            elif normalized.format_type == DocumentFormatType.CARTA_DE_PORTE:
                if normalized.external_reference.value:
                    business_key = (
                        f"{company_prefix}:CP_REF:{year_val}:{normalized.external_reference.value}"
                    )
                else:
                    cargo_weight = (
                        normalized.total_gross_weight_kg.value
                        or normalized.total_net_weight_kg.value
                        or normalized.weight_kg.value
                    )
                    dest_val = normalized.destination.value or normalized.consignee.value
                    date_val = str(normalized.loading_date.value)
                    business_key = (
                        f"{company_prefix}:CP_CARGO:{year_val}:{date_val}:{dest_val}:{cargo_weight}"
                    )

            if business_key and business_key in self._in_flight_business_keys:
                return ImportResultItemDTO(
                    filename=filename,
                    sha256_hash=sha256_hash,
                    format_type=normalized.format_type,
                    reference=ref_val,
                    status="DUPLICATE",
                    company_id=effective_company_id or None,
                    message=(
                        f"Ya existe una expedición registrada para esta operación "
                        f"({normalized.format_type} en ejercicio {year_val})."
                    ),
                )

            existing: Expedition | None = None
            if self.expedition_repo:
                if normalized.format_type == DocumentFormatType.CMR:
                    cmr_ref = (
                        normalized.external_reference.value
                        or normalized.document_number.value
                        or normalized.reference.value
                    )
                    if cmr_ref:
                        try:
                            existing = self.expedition_repo.find_by_reference(
                                cmr_ref, year_val, company_id=effective_company_id or None
                            )
                        except TypeError:
                            existing = self.expedition_repo.find_by_reference(cmr_ref, year_val)
                elif normalized.format_type == DocumentFormatType.CARTA_DE_PORTE:
                    if normalized.external_reference.value:
                        try:
                            existing = self.expedition_repo.find_by_reference(
                                normalized.external_reference.value,
                                year_val,
                                company_id=effective_company_id or None,
                            )
                        except TypeError:
                            existing = self.expedition_repo.find_by_reference(
                                normalized.external_reference.value, year_val
                            )
                    else:
                        cargo_weight = (
                            normalized.total_gross_weight_kg.value
                            or normalized.total_net_weight_kg.value
                            or normalized.weight_kg.value
                        )
                        dest_val = normalized.destination.value or normalized.consignee.value
                        if hasattr(self.expedition_repo, "find_duplicate_cargo"):
                            try:
                                existing = self.expedition_repo.find_duplicate_cargo(
                                    fiscal_year=year_val,
                                    transport_date=normalized.loading_date.value,
                                    destination=dest_val,
                                    weight_kg=cargo_weight,
                                    company_id=effective_company_id or None,
                                )
                            except TypeError:
                                existing = self.expedition_repo.find_duplicate_cargo(
                                    fiscal_year=year_val,
                                    transport_date=normalized.loading_date.value,
                                    destination=dest_val,
                                    weight_kg=cargo_weight,
                                )

            if existing:
                return ImportResultItemDTO(
                    filename=filename,
                    sha256_hash=sha256_hash,
                    format_type=normalized.format_type,
                    reference=ref_val,
                    status="DUPLICATE",
                    company_id=effective_company_id or None,
                    expedition_id=str(existing.id),
                    message=(
                        f"Ya existe una expedición registrada para esta operación "
                        f"({normalized.format_type} en ejercicio {year_val})."
                    ),
                )

            if business_key:
                self._in_flight_business_keys.add(business_key)

        # 4. Almacenar el archivo físico de forma inmutable
        storage_rel_path = f"raw/{year_val}/{sha256_hash}.pdf"
        try:
            self.storage.save(content, storage_rel_path)
        except Exception as exc:
            logger.warning("No se pudo guardar copia física de '%s': %s", filename, str(exc))

        # Entidad Documento Fuente (PDF)
        source_doc = Document(
            sha256_hash=sha256_hash,
            original_filename=filename,
            mime_type="application/pdf",
            size_bytes=len(content),
            storage_path=storage_rel_path,
            status=(
                DocumentProcessingStatus.PARSED_OK
                if normalized.format_type != DocumentFormatType.DESCONOCIDO
                else DocumentProcessingStatus.PARSED_ERROR
            ),
        )

        # 5. Determinación del estado operativo (REQUISITOS DE IMPORTACIÓN)
        # En Carta de Porte, transportista, matrículas y albarán pueden estar ausentes en muelle
        fields_needing_review: list[str] = []
        if company_detection_failed or not detected_company_id:
            fields_needing_review.append("empresa_emisora")
        if not normalized.loading_date.is_valid:
            fields_needing_review.append("fecha_transporte")
        if not normalized.shipper.is_valid:
            fields_needing_review.append("cargador")
        if not normalized.origin.is_valid:
            fields_needing_review.append("origen")
        if not (normalized.destination.is_valid or normalized.consignee.is_valid):
            fields_needing_review.append("destino")
        if not normalized.goods.is_valid:
            fields_needing_review.append("mercancia")
        if not (
            normalized.total_gross_weight_kg.is_valid
            or normalized.total_net_weight_kg.is_valid
            or normalized.weight_kg.is_valid
        ):
            fields_needing_review.append("peso")

        if (
            normalized.format_type == DocumentFormatType.DESCONOCIDO
            or not normalized.is_valid_for_import()
            or len(fields_needing_review) > 0
        ):
            exp_status = ExpeditionStatus.PENDIENTE_REVISION
            result_status = "NEEDS_REVIEW"
            review_reasons = (
                ", ".join(fields_needing_review) if fields_needing_review else "confianza baja"
            )
            status_msg = (
                f"Formato detectado: {normalized.format_type}. "
                f"Requiere revisión manual: {review_reasons}."
            )
        else:
            exp_status = ExpeditionStatus.PENDIENTE_MATRICULA
            result_status = "PENDING_VEHICLE"
            status_msg = f"Importado como {normalized.format_type}. Listo para asignar matrícula."

        # 6. Creación de la entidad de Dominio Expedition
        ref_str = (
            ref_val
            or normalized.document_number.value
            or f"EXP-{year_val}-{sha256_hash[:8].upper()}"
        )
        weight_val = (
            normalized.total_gross_weight_kg.value
            or normalized.total_net_weight_kg.value
            or normalized.weight_kg.value
        )
        with self._lock:
            int_id = ""
            if self.expedition_repo and hasattr(self.expedition_repo, "next_internal_id"):
                try:
                    int_id = self.expedition_repo.next_internal_id(
                        year_val, company_id=effective_company_id or None
                    )
                except (NotImplementedError, TypeError):
                    int_id = f"TD-{year_val}-{sha256_hash[:5].upper()}"
            if not int_id:
                int_id = f"TD-{year_val}-{sha256_hash[:5].upper()}"

        expedition = Expedition(
            internal_id=int_id,
            document_id=source_doc.id,
            company_id=effective_company_id,
            issuer_detection_confidence=det_confidence,
            issuer_detection_source=det_source,
            reference=ref_str,
            fiscal_year=year_val,
            transport_date=normalized.loading_date.value or date.today(),
            shipper_name=normalized.shipper.value or "Tomates de Autor S.L.",
            carrier_name_raw=normalized.carrier.value or normalized.raw_carrier_text,
            origin=normalized.origin.value or "",
            destination=normalized.destination.value or normalized.consignee.value or "",
            goods=normalized.goods.value or "",
            weight=Weight(weight_val) if weight_val else None,
            status=exp_status,
            extraction_metadata={
                "format_type": str(normalized.format_type),
                "format_confidence": normalized.format_confidence,
                "company_id": effective_company_id or None,
                "detected_company_id": detected_company_id,
                "company_detection_source": det_source,
                "company_detection_confidence": det_confidence,
                "document_number": normalized.document_number.value,
                "external_reference": normalized.external_reference.value,
                "total_packages": normalized.total_packages.value,
                "gross_weight_kg": normalized.total_gross_weight_kg.value,
                "net_weight_kg": normalized.total_net_weight_kg.value,
                "fields_needing_review": fields_needing_review,
                "filename": filename,
                "sha256": sha256_hash,
                "source_document_id": str(source_doc.id),
            },
        )

        with self._lock:
            if self.expedition_repo:
                if hasattr(self.expedition_repo, "save_with_id_retry"):
                    saved_exp = self.expedition_repo.save_with_id_retry(
                        expedition, fiscal_year=year_val, company_id=effective_company_id or None
                    )
                else:
                    saved_exp = self.expedition_repo.save(
                        expedition, company_id=effective_company_id or None
                    )
                exp_id_str = str(saved_exp.id)
            else:
                exp_id_str = str(expedition.id)

            self._processed_hashes.add(sha256_hash)

        # 7. Auditoría
        if self.audit_service:
            self.audit_service.record(
                AuditEvent(
                    action=AuditAction.EXPEDITION_CREATED,
                    entity_name="EXPEDITION",
                    entity_id=expedition.id,
                    company_id=expedition.company_id or None,
                    new_state={
                        "internal_id": expedition.internal_id,
                        "reference": expedition.reference,
                        "company_id": expedition.company_id,
                        "status": str(expedition.status),
                    },
                )
            )
            if effective_company_id:
                self.audit_service.record(
                    AuditEvent(
                        action=AuditAction.COMPANY_DETECTED,
                        entity_name="EXPEDITION",
                        entity_id=expedition.id,
                        company_id=expedition.company_id,
                        new_state={
                            "company_id": effective_company_id,
                            "detected_company_id": detected_company_id,
                            "confidence": det_confidence,
                            "source": det_source,
                        },
                    )
                )

        return ImportResultItemDTO(
            filename=filename,
            sha256_hash=sha256_hash,
            format_type=normalized.format_type,
            reference=ref_val,
            status=result_status,
            company_id=expedition.company_id or None,
            expedition_id=exp_id_str,
            internal_id=expedition.internal_id,
            message=status_msg,
            fields_needing_review=fields_needing_review,
        )
