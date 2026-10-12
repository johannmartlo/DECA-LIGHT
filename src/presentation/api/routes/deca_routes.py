from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from src.application.dtos.deca_dto import EmitDeCAInputDTO, EmitDeCAResultDTO
from src.application.dtos.email_dto import (
    SendDeCAEmailInputDTO,
    SendDeCAEmailResultDTO,
)
from src.application.ports.audit_service import AuditServicePort
from src.application.ports.deca_repository import DeCARepositoryPort
from src.application.ports.email_delivery_repository import (
    EmailDeliveryRepositoryPort,
)
from src.application.ports.email_sender import EmailSenderPort
from src.application.ports.expedition_repository import ExpeditionRepositoryPort
from src.application.ports.pdf_renderer import PdfRendererPort
from src.application.ports.storage_service import StorageServicePort
from src.application.use_cases.emit_deca import EmitDeCAUseCase
from src.application.use_cases.send_deca_email import SendDeCAEmailUseCase
from src.config.settings import Settings, get_settings
from src.domain.entities.audit_event import AuditEvent
from src.domain.entities.deca import DeCA
from src.domain.enums import AuditAction
from src.domain.exceptions import (
    DeCAEmissionException,
    EntityNotFoundException,
    ExpeditionNotReadyException,
    ImmutableDeCAException,
    StorageException,
)
from src.domain.services.public_token_service import PublicDeCaTokenService
from src.domain.value_objects import EmailAddress
from src.presentation.api.dependencies import (
    get_audit_service,
    get_deca_repository,
    get_email_delivery_repository,
    get_email_sender,
    get_expedition_repository,
    get_pdf_renderer,
    get_storage_service,
)

router = APIRouter(tags=["Documento DeCA"])


class EmitDeCARequest(BaseModel):
    """Solicitud de emisión formal de DeCA."""

    actor: str = Field("OPERATOR", description="Identificador del usuario que emite el DeCA")


class DeCAResponseDTO(BaseModel):
    """Respuesta estructurada de emisión de DeCA."""

    deca_id: str
    company_id: str = "TOMATES_DE_AUTOR"
    version: int
    expedition_id: str
    status: str
    pdf_filename: str
    pdf_sha256: str
    issued_at: str
    public_token: str | None = None
    public_url: str | None = None


class SendDeCAEmailRequest(BaseModel):
    """Solicitud para enviar el documento DeCA por correo al transportista."""

    actor: str = Field("OPERATOR", description="Identificador del usuario u operador solicitante")
    force_resend: bool = Field(
        False,
        description="Fuerza un reenvío explícito incluso si ya fue enviado previamente",
    )


class SendDeCAEmailResponse(BaseModel):
    """Respuesta tras procesar el envío del DeCA por correo."""

    deca_code: str
    expedition_id: str
    email_status: str
    recipient: str
    recipient_masked: str
    idempotency_key: str
    message_id: str | None = None
    sent_at: str | None = None
    is_idempotent: bool = False
    message: str = ""


class EmailDeliveryHistoryItemDTO(BaseModel):
    """Registro individual de un intento o entrega de correo."""

    delivery_id: str
    company_id: str = "TOMATES_DE_AUTOR"
    status: str
    attempts: int
    recipient_masked: str
    message_id: str | None = None
    sent_at: str | None = None
    last_error: str | None = None
    idempotency_key: str
    is_resend: bool
    created_at: str


class ExpeditionEmailStatusResponse(BaseModel):
    """Estado acumulado de entregas de correo para una expedición."""

    expedition_id: str
    carrier_email_masked: str
    current_status: str
    total_deliveries: int
    latest_delivery: EmailDeliveryHistoryItemDTO | None = None
    history: list[EmailDeliveryHistoryItemDTO] = Field(default_factory=list)


@router.post(
    "/api/v1/expeditions/{expedition_id}/deca",
    response_model=DeCAResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Emitir DeCA v1 reproducible para una expedición validada",
    description=(
        "Transforma una expedición en estado LISTA_PARA_DECA en un DeCA v1 oficial con "
        "snapshot inmutable, renderizado PDF y custodia física."
    ),
)
async def emit_deca(
    expedition_id: str,
    payload: EmitDeCARequest = EmitDeCARequest(),
    x_company_id: str | None = Header(None, alias="X-Company-Id"),
    expedition_repo: ExpeditionRepositoryPort = Depends(get_expedition_repository),
    deca_repo: DeCARepositoryPort = Depends(get_deca_repository),
    pdf_renderer: PdfRendererPort = Depends(get_pdf_renderer),
    storage_service: StorageServicePort = Depends(get_storage_service),
    audit_service: AuditServicePort | None = Depends(get_audit_service),
    settings: Settings = Depends(get_settings),
) -> DeCAResponseDTO:
    try:
        exp_uuid = uuid.UUID(expedition_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de identificador UUID inválido: '{expedition_id}'",
        ) from None

    if x_company_id:
        existing = expedition_repo.get_by_id(exp_uuid)
        if existing and not existing.belongs_to(x_company_id):
            if audit_service:
                audit_service.record(
                    AuditEvent(
                        action=AuditAction.COMPANY_ACCESS_DENIED,
                        entity_name="EXPEDITION",
                        entity_id=existing.id,
                        company_id=x_company_id,
                        new_state={
                            "requested_company": x_company_id,
                            "actual_company": existing.company_id,
                        },
                    )
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Acceso denegado: la expedición pertenece a otra empresa "
                    f"({existing.company_id})."
                ),
            )

    use_case = EmitDeCAUseCase(
        expedition_repo=expedition_repo,
        deca_repo=deca_repo,
        pdf_renderer=pdf_renderer,
        storage_service=storage_service,
        audit_service=audit_service,
        public_base_url=settings.resolved_public_deca_url,
    )

    input_dto = EmitDeCAInputDTO(
        expedition_id=expedition_id,
        actor=payload.actor,
    )

    try:
        result: EmitDeCAResultDTO = use_case.execute(input_dto)
        return DeCAResponseDTO(
            deca_id=result.deca_id,
            company_id=result.company_id,
            version=result.version,
            expedition_id=result.expedition_id,
            status=result.status,
            pdf_filename=result.pdf_filename,
            pdf_sha256=result.pdf_sha256,
            issued_at=result.issued_at,
            public_token=str(result.public_token) if result.public_token else None,
            public_url=result.public_url or None,
        )
    except EntityNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ExpeditionNotReadyException, DeCAEmissionException) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ImmutableDeCAException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except StorageException as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en custodia documental: {exc}",
        ) from exc


@router.get(
    "/api/v1/expeditions/{expedition_id}/deca",
    response_model=DeCAResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Consultar el DeCA emitido para una expedición",
)
async def get_expedition_deca(
    expedition_id: str,
    x_company_id: str | None = Header(None, alias="X-Company-Id"),
    deca_repo: DeCARepositoryPort = Depends(get_deca_repository),
    settings: Settings = Depends(get_settings),
) -> DeCAResponseDTO:
    try:
        exp_uuid = uuid.UUID(expedition_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de identificador UUID inválido: '{expedition_id}'",
        ) from None

    deca: DeCA | None = deca_repo.find_by_expedition_id(exp_uuid)
    if not deca or not deca.versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se ha encontrado ningún DeCA emitido para la expedición '{expedition_id}'.",
        )

    if x_company_id and not deca.belongs_to(x_company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acceso denegado: el DeCA pertenece a otra empresa ({deca.company_id}).",
        )

    v1 = deca.get_version(1)
    if not v1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El DeCA '{deca.deca_code}' no dispone de la versión v1.",
        )

    pub_token = str(deca.public_access_token) if deca.public_access_token else None
    pub_url = (
        PublicDeCaTokenService.build_public_url(settings.resolved_public_deca_url, pub_token)
        if pub_token
        else None
    )

    return DeCAResponseDTO(
        deca_id=str(deca.id),
        company_id=deca.company_id,
        version=v1.version_number,
        expedition_id=str(exp_uuid),
        status=str(deca.status),
        pdf_filename=f"{deca.deca_code}.pdf",
        pdf_sha256=v1.pdf_sha256,
        issued_at=v1.created_at.isoformat(),
        public_token=pub_token,
        public_url=pub_url,
    )


@router.get(
    "/api/v1/deca/{deca_code}/pdf",
    status_code=status.HTTP_200_OK,
    summary="Descargar o visualizar el binario PDF del DeCA",
)
async def get_deca_pdf(
    deca_code: str,
    x_company_id: str | None = Header(None, alias="X-Company-Id"),
    deca_repo: DeCARepositoryPort = Depends(get_deca_repository),
    storage_service: StorageServicePort = Depends(get_storage_service),
) -> Response:
    deca: DeCA | None = deca_repo.find_by_code(deca_code)
    if not deca:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DeCA con código '{deca_code}' no encontrado.",
        )

    if x_company_id and not deca.belongs_to(x_company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acceso denegado: el DeCA pertenece a otra empresa ({deca.company_id}).",
        )

    latest = deca.latest_version
    if not latest or not latest.pdf_storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El DeCA '{deca_code}' no cuenta con archivo PDF físico registrado.",
        )

    try:
        pdf_bytes = storage_service.read(latest.pdf_storage_path)
    except StorageException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Archivo PDF no disponible en almacenamiento: {exc}",
        ) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{deca_code}.pdf"',
            "X-DeCA-Version": str(latest.version_number),
            "X-DeCA-SHA256": latest.pdf_sha256,
        },
    )


@router.post(
    "/api/v1/expeditions/{expedition_id}/deca/email",
    response_model=SendDeCAEmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Enviar documento DeCA por correo electrónico al transportista",
    description=(
        "Transmite el PDF oficial del DeCA mediante Microsoft Graph API al transportista "
        "asignado a la expedición. Protege contra dobles envíos mediante idempotencia."
    ),
)
async def send_deca_email(
    expedition_id: str,
    payload: SendDeCAEmailRequest = SendDeCAEmailRequest(),
    x_company_id: str | None = Header(None, alias="X-Company-Id"),
    expedition_repo: ExpeditionRepositoryPort = Depends(get_expedition_repository),
    deca_repo: DeCARepositoryPort = Depends(get_deca_repository),
    storage_service: StorageServicePort = Depends(get_storage_service),
    email_sender: EmailSenderPort = Depends(get_email_sender),
    email_delivery_repo: EmailDeliveryRepositoryPort = Depends(get_email_delivery_repository),
    audit_service: AuditServicePort | None = Depends(get_audit_service),
    settings: Settings = Depends(get_settings),
) -> SendDeCAEmailResponse:
    try:
        exp_uuid = uuid.UUID(expedition_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de identificador UUID inválido: '{expedition_id}'",
        ) from None

    if x_company_id:
        exp = expedition_repo.get_by_id(exp_uuid)
        if exp and not exp.belongs_to(x_company_id):
            if audit_service:
                audit_service.record(
                    AuditEvent(
                        action=AuditAction.COMPANY_ACCESS_DENIED,
                        entity_name="EXPEDITION",
                        entity_id=exp.id,
                        company_id=x_company_id,
                        new_state={
                            "requested_company": x_company_id,
                            "actual_company": exp.company_id,
                        },
                    )
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Acceso denegado: la expedición pertenece a otra empresa ({exp.company_id})."
                ),
            )

    use_case = SendDeCAEmailUseCase(
        expedition_repo=expedition_repo,
        deca_repo=deca_repo,
        storage_service=storage_service,
        email_sender=email_sender,
        email_delivery_repo=email_delivery_repo,
        audit_service=audit_service,
        sender_email=settings.MS_GRAPH_SENDER_EMAIL,
    )

    input_dto = SendDeCAEmailInputDTO(
        expedition_id=expedition_id,
        actor=payload.actor,
        force_resend=payload.force_resend,
    )

    try:
        result: SendDeCAEmailResultDTO = use_case.execute(input_dto)
        return SendDeCAEmailResponse(
            deca_code=result.deca_code,
            expedition_id=result.expedition_id,
            email_status=result.email_status,
            recipient=result.recipient,
            recipient_masked=result.recipient_masked,
            idempotency_key=result.idempotency_key,
            message_id=result.message_id,
            sent_at=result.sent_at,
            is_idempotent=result.is_idempotent,
            message=result.message,
        )
    except EntityNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/api/v1/expeditions/{expedition_id}/deca/email",
    response_model=ExpeditionEmailStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar el estado y trazabilidad del envío de correo de la expedición",
)
async def get_expedition_email_status(
    expedition_id: str,
    x_company_id: str | None = Header(None, alias="X-Company-Id"),
    expedition_repo: ExpeditionRepositoryPort = Depends(get_expedition_repository),
    deca_repo: DeCARepositoryPort = Depends(get_deca_repository),
    email_delivery_repo: EmailDeliveryRepositoryPort = Depends(get_email_delivery_repository),
) -> ExpeditionEmailStatusResponse:
    try:
        exp_uuid = uuid.UUID(expedition_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de identificador UUID inválido: '{expedition_id}'",
        ) from None

    expedition = expedition_repo.get_by_id(exp_uuid)
    if not expedition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expedición '{expedition_id}' no encontrada.",
        )

    if x_company_id and not expedition.belongs_to(x_company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Acceso denegado: la expedición pertenece a otra empresa "
                f"({expedition.company_id})."
            ),
        )

    carrier_masked = (
        EmailAddress.mask_str(expedition.carrier_email)
        if expedition.carrier_email
        else "NO_CONFIGURADO"
    )

    deca = deca_repo.find_by_expedition_id(exp_uuid)
    deliveries = email_delivery_repo.find_by_deca_id(deca.id) if deca else []

    history_items: list[EmailDeliveryHistoryItemDTO] = [
        EmailDeliveryHistoryItemDTO(
            delivery_id=str(d.id),
            company_id=d.company_id,
            status=d.status.value,
            attempts=d.attempts,
            recipient_masked=d.recipient_masked,
            message_id=d.message_id,
            sent_at=d.sent_at.isoformat() if d.sent_at else None,
            last_error=d.last_error,
            idempotency_key=d.idempotency_key,
            is_resend=d.is_resend,
            created_at=d.created_at.isoformat(),
        )
        for d in deliveries
    ]

    latest_item = history_items[-1] if history_items else None
    current_status = latest_item.status if latest_item else "NOT_ATTEMPTED"

    return ExpeditionEmailStatusResponse(
        expedition_id=str(exp_uuid),
        carrier_email_masked=carrier_masked,
        current_status=current_status,
        total_deliveries=len(deliveries),
        latest_delivery=latest_item,
        history=history_items,
    )
