from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from src.application.use_cases.get_system_status import GetSystemStatusUseCase
from src.config.settings import Settings, get_settings

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    environment: str
    database: str
    storage: str


@router.get(
    "/healthz",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Healthcheck del sistema",
    description="Endpoint de comprobación de salud y disponibilidad del servicio.",
)
def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    use_case = GetSystemStatusUseCase(settings)
    result = use_case.execute()
    return HealthResponse(
        status=result.status,
        app_name=result.app_name,
        version=result.version,
        environment=result.environment,
        database=result.database,
        storage=result.storage,
    )
