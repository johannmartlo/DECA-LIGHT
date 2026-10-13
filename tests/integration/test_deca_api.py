from __future__ import annotations

import hashlib
import uuid
from collections.abc import Generator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.config.companies import TEST_API_KEY_TOMATES
from src.config.settings import Settings
from src.domain.entities.expedition import Expedition
from src.domain.enums import ExpeditionStatus, VehicleType
from src.domain.value_objects import NIF, Matricula, Weight
from src.infrastructure.logging.in_memory_audit_service import InMemoryAuditService
from src.infrastructure.repositories.in_memory_deca_repository import (
    InMemoryDeCARepository,
)
from src.infrastructure.repositories.in_memory_expedition_repository import (
    InMemoryExpeditionRepository,
)
from src.infrastructure.storage.local_pdf_storage import LocalPdfStorage
from src.presentation.api.app import create_app
from src.presentation.api.dependencies import (
    get_audit_service,
    get_deca_repository,
    get_expedition_repository,
    get_storage_service,
)


@pytest.fixture
def isolated_context(
    test_settings: Settings, temp_storage_dir: Path
) -> Generator[tuple, None, None]:
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    audit_service = InMemoryAuditService()
    storage = LocalPdfStorage(temp_storage_dir)

    exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00001",
        reference="ALB-2026-9999",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
        transport_date=date(2026, 10, 15),
        shipper_name="Tomates de Autor S.L.",
        shipper_tax_id=NIF("B12345678"),
        shipper_address="Polígono La Redonda, Almería",
        carrier_name_raw="Transportes del Poniente S.L.",
        carrier_tax_id=NIF("B04999888"),
        carrier_email="trafico@poniente.com",
        origin="El Ejido (Almería)",
        destination="Mercamadrid (Madrid)",
        goods="Tomate Rama Extra",
        weight=Weight(19200.0),
        observations="Temperatura controlada 12ºC",
        status=ExpeditionStatus.LISTA_PARA_DECA,
    )
    exp.assign_vehicle(
        VehicleType.ARTICULADO,
        Matricula("1234BCD"),
        Matricula("R5678EFG"),
    )
    exp.status = ExpeditionStatus.LISTA_PARA_DECA
    exp_repo.save(exp)

    app = create_app(test_settings)
    app.dependency_overrides[get_expedition_repository] = lambda: exp_repo
    app.dependency_overrides[get_deca_repository] = lambda: deca_repo
    app.dependency_overrides[get_audit_service] = lambda: audit_service
    app.dependency_overrides[get_storage_service] = lambda: storage

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {TEST_API_KEY_TOMATES}"
        yield client, exp_repo, deca_repo, audit_service, storage, exp


def test_api_emit_deca_endpoint_success(isolated_context) -> None:
    """POST /api/v1/expeditions/{id}/deca emite correctamente el DeCA y devuelve 201."""
    client, exp_repo, deca_repo, audit_service, storage, exp = isolated_context

    response = client.post(
        f"/api/v1/expeditions/{exp.id}/deca",
        json={"actor": "OPERATOR_ALMERIA"},
    )

    assert response.status_code == 201
    data = response.json()

    assert "deca_id" in data
    assert data["version"] == 1
    assert data["expedition_id"] == str(exp.id)
    assert data["status"] == "ISSUED"
    assert data["pdf_filename"] == "DECA-2026-000001.pdf"
    assert len(data["pdf_sha256"]) == 64
    assert "issued_at" in data

    # Estado de la expedición actualizado a DECA_GENERADO
    updated_exp = exp_repo.get_by_id(exp.id)
    assert updated_exp.status == ExpeditionStatus.DECA_GENERADO


def test_api_emit_deca_idempotency(isolated_context) -> None:
    """POST /api/v1/expeditions/{id}/deca invocado múltiples veces es idempotente."""
    client, exp_repo, deca_repo, audit_service, storage, exp = isolated_context

    # 1ª llamada
    r1 = client.post(f"/api/v1/expeditions/{exp.id}/deca", json={"actor": "OPERATOR_1"})
    assert r1.status_code == 201
    d1 = r1.json()

    # 2ª llamada
    r2 = client.post(f"/api/v1/expeditions/{exp.id}/deca", json={"actor": "OPERATOR_2"})
    assert r2.status_code == 201
    d2 = r2.json()

    assert d1["deca_id"] == d2["deca_id"]
    assert d1["pdf_sha256"] == d2["pdf_sha256"]
    assert d1["pdf_filename"] == d2["pdf_filename"]


def test_api_emit_deca_not_ready_returns_400(isolated_context) -> None:
    """POST /api/v1/expeditions/{id}/deca con expedición no preparada devuelve 400."""
    client, exp_repo, _, _, _, exp = isolated_context

    exp.status = ExpeditionStatus.PENDIENTE_MATRICULA
    exp_repo.save(exp)

    response = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    assert response.status_code == 400
    assert "LISTA_PARA_DECA" in response.json()["detail"]


def test_api_emit_deca_not_found_returns_404(isolated_context) -> None:
    """POST /api/v1/expeditions/{id}/deca con ID inexistente devuelve 404."""
    client, _, _, _, _, _ = isolated_context
    non_existent = uuid.uuid4()

    response = client.post(f"/api/v1/expeditions/{non_existent}/deca")
    assert response.status_code == 404


def test_api_emit_deca_invalid_uuid_returns_400(isolated_context) -> None:
    """POST /api/v1/expeditions/{id}/deca con UUID malformado devuelve 400."""
    client, _, _, _, _, _ = isolated_context

    response = client.post("/api/v1/expeditions/not-a-valid-uuid/deca")
    assert response.status_code == 400
    assert "UUID inválido" in response.json()["detail"]


def test_api_get_expedition_deca_success(isolated_context) -> None:
    """GET /api/v1/expeditions/{id}/deca devuelve los metadatos del DeCA emitido."""
    client, _, _, _, _, exp = isolated_context

    # Emitir primero
    post_res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    assert post_res.status_code == 201

    # Consultar
    get_res = client.get(f"/api/v1/expeditions/{exp.id}/deca")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["deca_id"] == post_res.json()["deca_id"]
    assert data["version"] == 1
    assert data["expedition_id"] == str(exp.id)


def test_api_get_expedition_deca_not_found(isolated_context) -> None:
    """GET /api/v1/expeditions/{id}/deca cuando aún no se ha emitido devuelve 404."""
    client, _, _, _, _, exp = isolated_context

    response = client.get(f"/api/v1/expeditions/{exp.id}/deca")
    assert response.status_code == 404
    assert "No se ha encontrado ningún DeCA" in response.json()["detail"]


def test_api_get_deca_pdf_download_success(isolated_context) -> None:
    """GET /api/v1/deca/{deca_code}/pdf descarga el binario PDF con cabeceras de integridad."""
    client, _, _, _, _, exp = isolated_context

    # Emitir DeCA
    client.post(f"/api/v1/expeditions/{exp.id}/deca")

    deca_code = "DECA-2026-000001"
    response = client.get(f"/api/v1/deca/{deca_code}/pdf")

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert f'inline; filename="{deca_code}.pdf"' in response.headers["Content-Disposition"]
    assert response.headers["X-DeCA-Version"] == "1"

    pdf_bytes = response.content
    assert pdf_bytes.startswith(b"%PDF-")
    computed_hash = hashlib.sha256(pdf_bytes).hexdigest()
    assert response.headers["X-DeCA-SHA256"] == computed_hash


def test_api_get_deca_pdf_not_found(isolated_context) -> None:
    """GET /api/v1/deca/{deca_code}/pdf con código inexistente devuelve 404."""
    client, _, _, _, _, _ = isolated_context

    response = client.get("/api/v1/deca/DECA-2026-999999/pdf")
    assert response.status_code == 404
    assert "no encontrado" in response.json()["detail"]
