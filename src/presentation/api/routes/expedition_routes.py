from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from src.application.dtos.vehicle_assignment_dto import (
    AssignVehicleInputDTO,
    AssignVehicleResultDTO,
)
from src.application.ports.audit_service import AuditServicePort
from src.application.ports.expedition_repository import ExpeditionRepositoryPort
from src.application.use_cases.assign_vehicle import AssignVehicleToExpeditionUseCase
from src.application.use_cases.validate_expedition import ValidateExpeditionUseCase
from src.domain.entities.audit_event import AuditEvent
from src.domain.entities.expedition import Expedition
from src.domain.enums import AuditAction, ExpeditionStatus
from src.domain.exceptions import (
    EntityNotFoundException,
    InvalidStateTransitionException,
    InvalidVehicleConfigurationException,
    ValidationException,
)
from src.presentation.api.dependencies import (
    get_audit_service,
    get_expedition_repository,
)

router = APIRouter(prefix="/api/v1/expeditions", tags=["Expediciones"])


class AssignVehicleRequest(BaseModel):
    """Esquema de solicitud para captura y normalización de vehículo y transportista."""

    vehicle_type: str = Field(..., description="Tipo de vehículo: RIGIDO o ARTICULADO")
    tractor_registration: str = Field(
        ..., description="Matrícula del vehículo o tractora (nacional o extranjera)"
    )
    trailer_registration: str | None = Field(
        None,
        description=(
            "Matrícula del semirremolque/remolque (obligatoria en articulado, prohibida en rígido)"
        ),
    )
    carrier_name: str | None = Field(
        None, description="Razón social o nombre comercial del transportista"
    )
    carrier_tax_id: str | None = Field(
        None, description="NIF/CIF o Tax ID internacional del transportista"
    )
    carrier_email: str | None = Field(
        None, description="Email de contacto de tráfico para entrega del DeCA"
    )
    actor: str = Field("OPERATOR", description="Identificador del usuario o sistema en muelle")


class ExpeditionDetailDTO(BaseModel):
    """Detalle visible de una expedición logística."""

    id: str
    company_id: str = "TOMATES_DE_AUTOR"
    internal_id: str
    reference: str
    fiscal_year: str
    transport_date: str
    shipper_name: str
    carrier_name: str
    carrier_tax_id: str | None
    carrier_email: str | None
    vehicle_type: str | None
    tractor_plate: str | None
    trailer_plate: str | None
    origin: str
    destination: str
    goods: str
    weight_kg: float | None
    status: str
    is_ready_for_deca: bool


@router.patch(
    "/{expedition_id}/vehicle",
    response_model=AssignVehicleResultDTO,
    status_code=status.HTTP_200_OK,
    summary="Asignar o modificar vehículo y transportista en muelle",
    description=(
        "Normaliza matrículas, valida la configuración (Rígido vs. Articulado), "
        "ejecuta DeCAValidator y transiciona a LISTA_PARA_DECA si se superan "
        "los requisitos legales."
    ),
)
async def assign_vehicle(
    expedition_id: str,
    payload: AssignVehicleRequest,
    x_company_id: str | None = Header(None, alias="X-Company-Id"),
    expedition_repo: ExpeditionRepositoryPort = Depends(get_expedition_repository),
    audit_service: AuditServicePort | None = Depends(get_audit_service),
) -> AssignVehicleResultDTO:
    try:
        exp_uuid = uuid.UUID(expedition_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de identificador UUID inválido: '{expedition_id}'",
        ) from None

    # Verificación de aislamiento multiempresa si se especifica cabecera de contexto
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

    use_case = AssignVehicleToExpeditionUseCase(
        expedition_repo=expedition_repo, audit_service=audit_service
    )
    input_dto = AssignVehicleInputDTO(
        expedition_id=exp_uuid,
        vehicle_type=payload.vehicle_type,
        tractor_registration=payload.tractor_registration,
        trailer_registration=payload.trailer_registration,
        carrier_name=payload.carrier_name,
        carrier_tax_id=payload.carrier_tax_id,
        carrier_email=payload.carrier_email,
        actor=payload.actor,
    )

    try:
        return use_case.execute(input_dto)
    except EntityNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (
        InvalidVehicleConfigurationException,
        InvalidStateTransitionException,
        ValidationException,
    ) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/{expedition_id}/validation",
    status_code=status.HTTP_200_OK,
    summary="Consultar resultado de validación DeCA de una expedición",
)
async def get_expedition_validation(
    expedition_id: str,
    x_company_id: str | None = Header(None, alias="X-Company-Id"),
    expedition_repo: ExpeditionRepositoryPort = Depends(get_expedition_repository),
) -> dict:
    try:
        exp_uuid = uuid.UUID(expedition_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de identificador UUID inválido: '{expedition_id}'",
        ) from None

    use_case = ValidateExpeditionUseCase(expedition_repo=expedition_repo)
    try:
        expedition, validation = use_case.execute(exp_uuid)
    except EntityNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if x_company_id and not expedition.belongs_to(x_company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Acceso denegado: la expedición pertenece a otra empresa "
                f"({expedition.company_id})."
            ),
        )

    return {
        "expedition_id": str(expedition.id),
        "internal_id": expedition.internal_id,
        "company_id": expedition.company_id or "TOMATES_DE_AUTOR",
        "status": str(expedition.status),
        "valid": validation.valid,
        "is_ready_for_deca": validation.valid,
        "errors": [
            {"code": e.code, "field": e.field, "message": e.message} for e in validation.errors
        ],
        "warnings": [
            {"code": w.code, "field": w.field, "message": w.message} for w in validation.warnings
        ],
    }


@router.get(
    "/{expedition_id}",
    response_model=ExpeditionDetailDTO,
    status_code=status.HTTP_200_OK,
    summary="Consultar detalle de una expedición",
)
async def get_expedition_detail(
    expedition_id: str,
    x_company_id: str | None = Header(None, alias="X-Company-Id"),
    expedition_repo: ExpeditionRepositoryPort = Depends(get_expedition_repository),
) -> ExpeditionDetailDTO:
    try:
        exp_uuid = uuid.UUID(expedition_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de identificador UUID inválido: '{expedition_id}'",
        ) from None

    expedition: Expedition | None = expedition_repo.get_by_id(exp_uuid)
    if not expedition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expedición con ID '{expedition_id}' no encontrada.",
        )

    if x_company_id and not expedition.belongs_to(x_company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Acceso denegado: la expedición pertenece a otra empresa "
                f"({expedition.company_id})."
            ),
        )

    return ExpeditionDetailDTO(
        id=str(expedition.id),
        company_id=expedition.company_id or "TOMATES_DE_AUTOR",
        internal_id=expedition.internal_id,
        reference=expedition.reference,
        fiscal_year=expedition.fiscal_year,
        transport_date=str(expedition.transport_date),
        shipper_name=expedition.shipper_name,
        carrier_name=expedition.carrier_name_raw,
        carrier_tax_id=str(expedition.carrier_tax_id) if expedition.carrier_tax_id else None,
        carrier_email=expedition.carrier_email,
        vehicle_type=str(expedition.vehicle_type) if expedition.vehicle_type else None,
        tractor_plate=str(expedition.tractor_plate) if expedition.tractor_plate else None,
        trailer_plate=str(expedition.trailer_plate) if expedition.trailer_plate else None,
        origin=expedition.origin,
        destination=expedition.destination,
        goods=expedition.goods,
        weight_kg=expedition.weight.kg if expedition.weight else None,
        status=str(expedition.status),
        is_ready_for_deca=(expedition.status == ExpeditionStatus.LISTA_PARA_DECA),
    )
