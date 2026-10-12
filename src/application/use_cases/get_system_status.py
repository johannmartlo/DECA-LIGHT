from __future__ import annotations

from dataclasses import dataclass

from src.config.settings import Settings


@dataclass(frozen=True)
class SystemStatusDTO:
    status: str
    app_name: str
    version: str
    environment: str
    database: str
    storage: str


class GetSystemStatusUseCase:
    """Caso de uso para consultar el estado de salud y operatividad del sistema."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def execute(self) -> SystemStatusDTO:
        # Comprobar acceso al directorio de almacenamiento
        storage_ok = "ok" if self._settings.resolved_storage_path.exists() else "error"

        return SystemStatusDTO(
            status="ok",
            app_name=self._settings.APP_NAME,
            version=self._settings.APP_VERSION,
            environment=self._settings.APP_ENV,
            database="ready",
            storage=storage_ok,
        )
