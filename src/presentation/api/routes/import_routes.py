from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from src.application.dtos.document_dto import BatchImportResultDTO
from src.application.ports.audit_service import AuditServicePort
from src.application.ports.company_repository import CompanyRepositoryPort
from src.application.ports.expedition_repository import ExpeditionRepositoryPort
from src.application.use_cases.import_documents_batch import (
    ImportDocumentsBatchUseCase,
    UploadedFileInput,
)
from src.config.settings import Settings, get_settings
from src.domain.value_objects import CompanyContext
from src.infrastructure.importers.pdf_document_importer import PdfDocumentImporter
from src.infrastructure.storage.filesystem_storage import FilesystemStorageAdapter
from src.presentation.api.dependencies import (
    get_audit_service,
    get_authorized_company_context,
    get_company_repository,
    get_expedition_repository,
)

router = APIRouter(prefix="/api/v1/documents", tags=["Importación Documental"])


@router.post(
    "/import-batch",
    response_model=BatchImportResultDTO,
    status_code=status.HTTP_200_OK,
    summary="Importación masiva de cartas de porte y CMRs",
    description=(
        "Procesa concurrentemente múltiples archivos PDF identificando automáticamente su formato."
    ),
)
async def import_documents_batch(
    files: list[UploadFile],
    company_context: CompanyContext = Depends(get_authorized_company_context),
    settings: Settings = Depends(get_settings),
    expedition_repo: ExpeditionRepositoryPort = Depends(get_expedition_repository),
    company_repo: CompanyRepositoryPort = Depends(get_company_repository),
    audit_service: AuditServicePort | None = Depends(get_audit_service),
) -> BatchImportResultDTO:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe proporcionar al menos un archivo PDF para importar.",
        )

    file_inputs: list[UploadedFileInput] = []
    for file in files:
        content = await file.read()
        file_inputs.append(
            UploadedFileInput(
                filename=file.filename or "documento.pdf",
                stream=io.BytesIO(content),
                content_bytes=content,
            )
        )

    importer = PdfDocumentImporter()
    storage = FilesystemStorageAdapter(settings.resolved_storage_path)
    use_case = ImportDocumentsBatchUseCase(
        importer=importer,
        storage=storage,
        expedition_repo=expedition_repo,
        company_repo=company_repo,
        audit_service=audit_service,
        max_concurrency=settings.BATCH_IMPORT_MAX_CONCURRENCY,
    )

    return use_case.execute(file_inputs, company_id=company_context.company_id)
