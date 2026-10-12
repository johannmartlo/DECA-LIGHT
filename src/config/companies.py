from __future__ import annotations

from src.config.settings import Settings
from src.domain.entities.company import Company
from src.domain.value_objects import NIF

TOMATES_DE_AUTOR_ID = "TOMATES_DE_AUTOR"
CULTIVOS_ARABA_ID = "CULTIVOS_ARABA"


def _tax(value: str | None) -> NIF | None:
    return NIF(value) if value and value.strip() else None


def build_companies(settings: Settings) -> list[Company]:
    """Construye las compañías iniciales desde configuración.

    Los datos fiscales ausentes NO se inventan: quedan vacíos y la empresa los
    reporta como pendientes (REQUIERE_CONFIGURACION).
    """
    return [
        Company(
            company_id=TOMATES_DE_AUTOR_ID,
            legal_name=settings.COMPANY_TOMATES_LEGAL_NAME,
            tax_id=_tax(settings.COMPANY_TOMATES_TAX_ID),
            fiscal_address=(settings.COMPANY_TOMATES_ADDRESS or "").strip(),
        ),
        Company(
            company_id=CULTIVOS_ARABA_ID,
            legal_name=settings.COMPANY_ARABA_LEGAL_NAME,
            tax_id=_tax(settings.COMPANY_ARABA_TAX_ID),
            fiscal_address=(settings.COMPANY_ARABA_ADDRESS or "").strip(),
        ),
    ]
