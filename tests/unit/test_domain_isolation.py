from __future__ import annotations

import importlib
import sys

DOMAIN_MODULES = [
    "src.domain",
    "src.domain.enums",
    "src.domain.exceptions",
    "src.domain.value_objects",
    "src.domain.entities",
    "src.domain.entities.carrier",
    "src.domain.entities.vehicle",
    "src.domain.entities.document",
    "src.domain.entities.expedition",
    "src.domain.entities.deca",
    "src.domain.entities.audit_event",
]

FORBIDDEN_FRAMEWORKS = [
    "fastapi",
    "starlette",
    "sqlalchemy",
    "uvicorn",
]


def test_domain_modules_import_cleanly() -> None:
    """Verifica que todos los módulos de dominio se pueden importar sin error."""
    for mod_name in DOMAIN_MODULES:
        mod = importlib.import_module(mod_name)
        assert mod is not None


def test_domain_does_not_depend_on_frameworks() -> None:
    """Verifica que los módulos de dominio no importen infraestructura ni presentación."""
    for mod_name in DOMAIN_MODULES:
        mod = sys.modules[mod_name]
        mod_file = getattr(mod, "__file__", "")
        if not mod_file:
            continue
        with open(mod_file, encoding="utf-8") as f:
            code = f.read()

        for framework in FORBIDDEN_FRAMEWORKS:
            assert f"import {framework}" not in code, (
                f"Violación de arquitectura limpia: '{mod_name}' importa '{framework}'"
            )
            assert f"from {framework}" not in code, (
                f"Violación de arquitectura limpia: '{mod_name}' importa de '{framework}'"
            )
