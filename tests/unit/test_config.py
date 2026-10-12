from __future__ import annotations

from pathlib import Path

from src.config.settings import Settings, get_settings


def test_settings_default_values() -> None:
    settings = Settings()
    assert settings.APP_NAME == "DECA Light"
    assert settings.APP_VERSION == "0.1.0"
    assert settings.APP_PORT == 8000
    assert settings.EMAIL_PROVIDER in ["stub", "smtp", "m365", "gmail"]


def test_settings_resolved_storage_path(tmp_path: Path) -> None:
    target_storage = tmp_path / "custom_storage"
    settings = Settings(STORAGE_PATH=str(target_storage))
    resolved = settings.resolved_storage_path
    assert resolved.exists()
    assert resolved == target_storage.resolve()


def test_get_settings_singleton() -> None:
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
