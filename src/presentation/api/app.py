from __future__ import annotations

from collections.abc import AsyncGenerator
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.config.settings import Settings, get_settings
from src.domain.exceptions import (
    DomainException,
    EntityNotFoundException,
    ValidationException,
)
from src.infrastructure.logging.logger import setup_logging
from src.presentation.api.routes.deca_routes import router as deca_router
from src.presentation.api.routes.expedition_routes import router as expedition_router
from src.presentation.api.routes.health import router as health_router
from src.presentation.api.routes.import_routes import router as import_router
from src.presentation.api.routes.public_routes import router as public_router

logger = logging.getLogger("deca_light.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Factoría de la aplicación FastAPI para DECA Light."""
    current_settings = settings or get_settings()

    # Inicializar logging estructurado
    setup_logging(current_settings.LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        logger.info(
            "Iniciando %s v%s (Entorno: %s)",
            current_settings.APP_NAME,
            current_settings.APP_VERSION,
            current_settings.APP_ENV,
        )
        # Asegurar directorio de almacenamiento
        _ = current_settings.resolved_storage_path
        yield
        logger.info("Deteniendo %s...", current_settings.APP_NAME)

    app = FastAPI(
        title=current_settings.APP_NAME,
        version=current_settings.APP_VERSION,
        docs_url="/docs" if current_settings.DEBUG else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Permitir sobreescribir la configuración inyectada
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: current_settings

    @app.exception_handler(EntityNotFoundException)
    async def not_found_exception_handler(
        request: Request, exc: EntityNotFoundException
    ) -> JSONResponse:
        logger.info("Recurso no encontrado en %s: %s", request.url.path, str(exc))
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "not_found", "message": str(exc)},
        )

    @app.exception_handler(ValidationException)
    async def validation_exception_handler(
        request: Request, exc: ValidationException
    ) -> JSONResponse:
        logger.warning("Error de validación de dominio en %s: %s", request.url.path, str(exc))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "validation_error", "message": str(exc)},
        )

    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
        logger.warning("Regla de negocio no satisfecha en %s: %s", request.url.path, str(exc))
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "domain_error", "message": str(exc)},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Error no controlado en %s: %s", request.url.path, str(exc), exc_info=True)
        # En producción nunca se devuelve el stack trace al cliente
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_server_error",
                "message": "Ha ocurrido un error interno. La incidencia ha sido registrada.",
            },
        )

    # Registrar rutas
    app.include_router(health_router)
    app.include_router(import_router)
    app.include_router(expedition_router)
    app.include_router(deca_router)
    app.include_router(public_router)

    return app
