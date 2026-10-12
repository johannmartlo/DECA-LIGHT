from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.presentation.api.app import create_app


@pytest.fixture
def temp_storage_dir() -> Generator[Path, None, None]:
    """Crea un directorio temporal aislado para pruebas de almacenamiento."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings(temp_storage_dir: Path) -> Settings:
    """Configuración aislada para pruebas unitarias y de integración."""
    return Settings(
        APP_ENV="test",
        APP_NAME="DECA Light Test",
        APP_VERSION="0.1.0-test",
        DEBUG=True,
        SECRET_KEY="test-secret-key-only",
        DATABASE_URL="sqlite:///:memory:",
        STORAGE_PATH=str(temp_storage_dir),
        LOG_LEVEL="DEBUG",
        EMAIL_PROVIDER="stub",
    )


@pytest.fixture
def client(test_settings: Settings) -> Generator[TestClient, None, None]:
    """Cliente HTTP de prueba para la API FastAPI."""
    app = create_app(test_settings)
    with TestClient(app) as test_client:
        yield test_client
