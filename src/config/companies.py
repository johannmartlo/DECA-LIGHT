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


# Claves de prueba sintéticas para entornos de test y desarrollo local
TEST_API_KEY_TOMATES = "deca_test_tomates_autor_secret_key_12345"
TEST_API_KEY_ARABA = "deca_test_cultivos_araba_secret_key_67890"
TEST_API_KEY_MULTI = "deca_test_multi_company_admin_key_99999"


def build_test_identities() -> list:
    """Construye identidades M2M de prueba precargadas con sus hashes."""
    from src.application.ports.tenant_authenticator_port import ApiKeyIdentity
    from src.infrastructure.auth.api_key_authenticator import hash_api_key

    return [
        ApiKeyIdentity(
            identity_id="m2m-tomates-operator",
            name="Tomates de Autor M2M Client",
            key_hash=hash_api_key(TEST_API_KEY_TOMATES),
            allowed_companies=frozenset([TOMATES_DE_AUTOR_ID]),
            is_active=True,
        ),
        ApiKeyIdentity(
            identity_id="m2m-araba-operator",
            name="Cultivos Araba M2M Client",
            key_hash=hash_api_key(TEST_API_KEY_ARABA),
            allowed_companies=frozenset([CULTIVOS_ARABA_ID]),
            is_active=True,
        ),
        ApiKeyIdentity(
            identity_id="m2m-group-admin",
            name="Group Admin Multi-Tenant Client",
            key_hash=hash_api_key(TEST_API_KEY_MULTI),
            allowed_companies=frozenset([TOMATES_DE_AUTOR_ID, CULTIVOS_ARABA_ID]),
            is_active=True,
        ),
    ]
