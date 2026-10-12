from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración tipada y centralizada del sistema DECA Light."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Entorno y metadatos
    APP_ENV: Literal["development", "staging", "production", "test"] = Field(
        default="development", description="Entorno de ejecución de la aplicación"
    )
    APP_NAME: str = Field(default="DECA Light", description="Nombre del sistema")
    APP_VERSION: str = Field(default="0.1.0", description="Versión del software")
    DEBUG: bool = Field(default=False, description="Activa trazas detalladas de desarrollo")

    # Servidor Web
    APP_HOST: str = Field(default="0.0.0.0", description="Host de enlace para Uvicorn")
    APP_PORT: int = Field(default=8000, description="Puerto de enlace")

    # Criptografía y Seguridad
    SECRET_KEY: str = Field(
        default="insecure-development-secret-key-change-in-production",
        description="Clave secreta para cookies y tokens de sesión",
    )
    PUBLIC_DECA_BASE_URL: str = Field(
        default="http://localhost:8000",
        description="URL canónica pública para el QR y el endpoint de inspección en carretera",
    )
    PUBLIC_BASE_URL: str = Field(
        default="http://localhost:8000",
        description="URL canónica pública heredada de la aplicación",
    )

    # Persistencia y Almacenamiento
    DATABASE_URL: str = Field(
        default="sqlite:///./instance/deca.sqlite3",
        description="Cadena de conexión SQLAlchemy (SQLite o PostgreSQL)",
    )
    STORAGE_PATH: str = Field(
        default="./storage",
        description="Directorio físico privado para custodia de PDFs",
    )

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Nivel mínimo de registro de eventos"
    )

    # Concurrencia e Importación
    BATCH_IMPORT_MAX_CONCURRENCY: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Máximo número de hilos concurrentes para la importación por lotes",
    )

    # Sociedades emisoras (multiempresa). NIF/domicilio ausentes = REQUIERE_CONFIGURACION.
    COMPANY_TOMATES_LEGAL_NAME: str = Field(default="Tomates de Autor S.L.")
    COMPANY_TOMATES_TAX_ID: str | None = Field(default=None)
    COMPANY_TOMATES_ADDRESS: str | None = Field(default=None)
    COMPANY_ARABA_LEGAL_NAME: str = Field(default="Cultivos Araba S.L.")
    COMPANY_ARABA_TAX_ID: str | None = Field(default=None)
    COMPANY_ARABA_ADDRESS: str | None = Field(default=None)

    # Correo Electrónico y Microsoft Graph
    EMAIL_PROVIDER: Literal["stub", "fake", "graph", "m365", "smtp", "gmail"] = Field(
        default="stub", description="Proveedor del servicio de mensajería (graph, stub, fake, smtp)"
    )
    MS_GRAPH_TENANT_ID: str | None = Field(
        default=None, description="Azure Entra ID Directory (tenant) ID"
    )
    MS_GRAPH_CLIENT_ID: str | None = Field(
        default=None, description="Azure Entra ID Application (client) ID"
    )
    MS_GRAPH_CLIENT_SECRET: str | None = Field(
        default=None, description="Azure Entra ID Application Client Secret"
    )
    MS_GRAPH_SENDER_EMAIL: str = Field(
        default="pedidos@tomatesdeautor.com",
        description="Buzón de Microsoft 365 remitente oficial para el envío de DeCA",
    )
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = "pedidos@tomatesdeautor.com"
    SMTP_USE_TLS: bool = True

    @property
    def resolved_storage_path(self) -> Path:
        """Devuelve la ruta absoluta del almacenamiento y asegura su existencia."""
        path = Path(self.STORAGE_PATH).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def resolved_public_deca_url(self) -> str:
        """Devuelve la URL base canónica configurada para el acceso público y QR."""
        if self.PUBLIC_DECA_BASE_URL:
            return self.PUBLIC_DECA_BASE_URL.rstrip("/")
        if self.PUBLIC_BASE_URL:
            return self.PUBLIC_BASE_URL.rstrip("/")
        return "http://localhost:8000"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la instancia singleton en caché de la configuración del sistema."""
    return Settings()
