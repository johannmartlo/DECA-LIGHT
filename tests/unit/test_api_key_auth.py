from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient

from src.application.ports.tenant_authenticator_port import ApiKeyIdentity
from src.config.companies import (
    TEST_API_KEY_ARABA,
    TEST_API_KEY_MULTI,
    TEST_API_KEY_TOMATES,
    build_test_identities,
)
from src.domain.entities.expedition import Expedition
from src.domain.enums import ExpeditionStatus
from src.domain.exceptions import (
    ForbiddenTenantException,
    UnauthorizedCompanyContextException,
)
from src.domain.value_objects import CompanyContext, NIF, Weight
from src.infrastructure.auth.api_key_authenticator import (
    InMemoryTenantAuthenticator,
    generate_api_key,
    hash_api_key,
)
from src.infrastructure.repositories.in_memory_expedition_repository import (
    InMemoryExpeditionRepository,
)
from src.presentation.api.dependencies import (
    get_authorized_company_context,
    get_expedition_repository,
    get_tenant_authenticator,
)
from src.presentation.api.routes.expedition_routes import router as expedition_router


def test_api_key_generation_and_hashing() -> None:
    raw_key, key_hash = generate_api_key(environment="test")
    assert raw_key.startswith("deca_test_")
    assert len(raw_key) > 30
    assert hash_api_key(raw_key) == key_hash


def test_authenticator_valid_and_revoked_keys() -> None:
    raw1, hash1 = generate_api_key(environment="test")
    raw2, hash2 = generate_api_key(environment="test")

    id1 = ApiKeyIdentity(
        identity_id="client_active",
        name="Cliente Activo",
        key_hash=hash1,
        allowed_companies=frozenset({"TOMATES_DE_AUTOR"}),
        is_active=True,
    )
    id2 = ApiKeyIdentity(
        identity_id="client_revoked",
        name="Cliente Revocado",
        key_hash=hash2,
        allowed_companies=frozenset({"TOMATES_DE_AUTOR"}),
        is_active=False,
    )

    auth = InMemoryTenantAuthenticator([id1, id2])

    assert auth.authenticate_key(raw1) == id1
    assert auth.authenticate_key(raw2) is None
    assert auth.authenticate_key("invalid_key_format") is None
    assert auth.authenticate_key("deca_test_nonexistent999999999999999999999999") is None


def test_resolve_active_company_single_tenant() -> None:
    identity = ApiKeyIdentity(
        identity_id="tomates_bot",
        name="Tomates Bot",
        key_hash="hash1",
        allowed_companies=frozenset({"TOMATES_DE_AUTOR"}),
    )
    auth = InMemoryTenantAuthenticator([identity])

    # 1. Sin cabecera: resolución automática
    assert auth.resolve_active_company(identity, None) == "TOMATES_DE_AUTOR"

    # 2. Con cabecera válida
    assert auth.resolve_active_company(identity, "TOMATES_DE_AUTOR") == "TOMATES_DE_AUTOR"

    # 3. Con cabecera de otra empresa: 403 ForbiddenTenantException
    with pytest.raises(ForbiddenTenantException):
        auth.resolve_active_company(identity, "CULTIVOS_ARABA")


def test_resolve_active_company_multi_tenant() -> None:
    identity = ApiKeyIdentity(
        identity_id="central_erp",
        name="Central ERP",
        key_hash="hash_multi",
        allowed_companies=frozenset({"TOMATES_DE_AUTOR", "CULTIVOS_ARABA"}),
    )
    auth = InMemoryTenantAuthenticator([identity])

    # 1. Sin cabecera en multiempresa: error por ambigüedad
    with pytest.raises(UnauthorizedCompanyContextException):
        auth.resolve_active_company(identity, None)

    # 2. Con cabeceras autorizadas
    assert auth.resolve_active_company(identity, "TOMATES_DE_AUTOR") == "TOMATES_DE_AUTOR"
    assert auth.resolve_active_company(identity, "CULTIVOS_ARABA") == "CULTIVOS_ARABA"

    # 3. Con empresa no autorizada
    with pytest.raises(ForbiddenTenantException):
        auth.resolve_active_company(identity, "OTRA_EMPRESA_SL")


# ---------------------------------------------------------------------------
# Pruebas HTTP con FastAPI TestClient
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_test_app() -> FastAPI:
    app = FastAPI()
    repo = InMemoryExpeditionRepository()

    # Sembrar expedición para TOMATES_DE_AUTOR
    exp_tomates = Expedition(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        internal_id="TD-2026-00001",
        reference="ALB-TOM-001",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
        transport_date=date.today(),
        shipper_name="Tomates de Autor S.L.",
        origin="Almería",
        destination="Madrid",
        goods="Tomates",
        status=ExpeditionStatus.PENDIENTE_MATRICULA,
    )
    # Sembrar expedición para CULTIVOS_ARABA
    exp_araba = Expedition(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        internal_id="TD-2026-00001",  # Mismo internal_id permitido
        reference="ALB-ARA-001",
        fiscal_year="2026",
        company_id="CULTIVOS_ARABA",
        transport_date=date.today(),
        shipper_name="Cultivos Araba S.L.",
        origin="Vitoria",
        destination="Bilbao",
        goods="Patatas",
        status=ExpeditionStatus.PENDIENTE_MATRICULA,
    )
    repo.save(exp_tomates)
    repo.save(exp_araba)

    authenticator = InMemoryTenantAuthenticator(build_test_identities())

    app.dependency_overrides[get_expedition_repository] = lambda: repo
    app.dependency_overrides[get_tenant_authenticator] = lambda: authenticator
    app.include_router(expedition_router)
    return app


def test_api_missing_auth_header_returns_401(auth_test_app: FastAPI) -> None:
    client = TestClient(auth_test_app)
    res = client.get("/api/v1/expeditions/11111111-1111-1111-1111-111111111111")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert "WWW-Authenticate" in res.headers
    assert res.headers["WWW-Authenticate"] == "Bearer"


def test_api_invalid_api_key_returns_401(auth_test_app: FastAPI) -> None:
    client = TestClient(auth_test_app)
    res = client.get(
        "/api/v1/expeditions/11111111-1111-1111-1111-111111111111",
        headers={"Authorization": "Bearer deca_test_invalidkey000000000000000000"},
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.headers["WWW-Authenticate"] == "Bearer"


def test_api_single_tenant_auto_selects_active_company(auth_test_app: FastAPI) -> None:
    client = TestClient(auth_test_app)
    res = client.get(
        "/api/v1/expeditions/11111111-1111-1111-1111-111111111111",
        headers={"Authorization": f"Bearer {TEST_API_KEY_TOMATES}"},
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["company_id"] == "TOMATES_DE_AUTOR"
    assert res.json()["reference"] == "ALB-TOM-001"


def test_api_multi_tenant_without_header_returns_400(auth_test_app: FastAPI) -> None:
    client = TestClient(auth_test_app)
    res = client.get(
        "/api/v1/expeditions/11111111-1111-1111-1111-111111111111",
        headers={"Authorization": f"Bearer {TEST_API_KEY_MULTI}"},
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "x-company-id" in res.json()["detail"].lower()


def test_api_multi_tenant_with_authorized_header_success(auth_test_app: FastAPI) -> None:
    client = TestClient(auth_test_app)
    res = client.get(
        "/api/v1/expeditions/11111111-1111-1111-1111-111111111111",
        headers={
            "Authorization": f"Bearer {TEST_API_KEY_MULTI}",
            "X-Company-Id": "TOMATES_DE_AUTOR",
        },
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["company_id"] == "TOMATES_DE_AUTOR"

    res_araba = client.get(
        "/api/v1/expeditions/22222222-2222-2222-2222-222222222222",
        headers={
            "Authorization": f"Bearer {TEST_API_KEY_MULTI}",
            "X-Company-Id": "CULTIVOS_ARABA",
        },
    )
    assert res_araba.status_code == status.HTTP_200_OK
    assert res_araba.json()["company_id"] == "CULTIVOS_ARABA"


def test_api_unauthorized_company_header_returns_403(auth_test_app: FastAPI) -> None:
    client = TestClient(auth_test_app)
    # Token de Tomates intentando hacerse pasar por Araba
    res = client.get(
        "/api/v1/expeditions/11111111-1111-1111-1111-111111111111",
        headers={
            "Authorization": f"Bearer {TEST_API_KEY_TOMATES}",
            "X-Company-Id": "CULTIVOS_ARABA",
        },
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_anti_idor_uniform_404_no_information_leak(auth_test_app: FastAPI) -> None:
    """Intento de acceder a la expedición de Araba usando la credencial de Tomates.
    Debe responder 404 Not Found (exactamente igual que si el ID no existiera)
    para evitar que atacantes descubran la existencia o metadatos de otras empresas."""
    client = TestClient(auth_test_app)
    res = client.get(
        "/api/v1/expeditions/22222222-2222-2222-2222-222222222222",
        headers={"Authorization": f"Bearer {TEST_API_KEY_TOMATES}"},
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert "no encontrada" in res.json()["detail"].lower()
    # Confirmar que no hay mención de la empresa ajena
    assert "CULTIVOS_ARABA" not in res.text
