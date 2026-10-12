from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from src.config.settings import Settings
from src.domain.entities.expedition import Expedition
from src.domain.enums import ExpeditionStatus
from src.domain.value_objects import NIF, Weight
from src.infrastructure.repositories.in_memory_expedition_repository import (
    InMemoryExpeditionRepository,
)
from src.presentation.api.app import create_app
from src.presentation.api.dependencies import get_expedition_repository


@pytest.fixture
def repo_with_expedition() -> tuple[InMemoryExpeditionRepository, Expedition]:
    repo = InMemoryExpeditionRepository()
    exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00001",
        reference="ALB-9999",
        fiscal_year="2026",
        transport_date=date.today(),
        shipper_name="Tomates de Autor S.L.",
        shipper_tax_id=NIF("B12345678"),
        shipper_address="Polígono La Redonda, Almería",
        carrier_name_raw="Transportes del Poniente S.L.",
        carrier_tax_id=NIF("B04999888"),
        carrier_email="trafico@poniente.com",
        origin="El Ejido (Almería)",
        destination="Mercamadrid (Madrid)",
        goods="Tomate Pera Selección",
        weight=Weight(21000.0),
        status=ExpeditionStatus.PENDIENTE_MATRICULA,
    )
    repo.save(exp)
    return repo, exp


@pytest.fixture
def expedition_client(
    test_settings: Settings,
    repo_with_expedition: tuple[InMemoryExpeditionRepository, Expedition],
) -> TestClient:
    repo, _ = repo_with_expedition
    app = create_app(test_settings)
    app.dependency_overrides[get_expedition_repository] = lambda: repo
    with TestClient(app) as client:
        yield client


def test_api_patch_vehicle_rigid_success(
    expedition_client: TestClient,
    repo_with_expedition: tuple[InMemoryExpeditionRepository, Expedition],
) -> None:
    _, exp = repo_with_expedition
    url = f"/api/v1/expeditions/{exp.id}/vehicle"
    payload = {
        "vehicle_type": "RIGIDO",
        "tractor_registration": "1234 BCD",
        "trailer_registration": None,
        "actor": "OPERATOR_TEST",
    }

    response = expedition_client.patch(url, json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "LISTA_PARA_DECA"
    assert data["is_ready_for_deca"] is True
    assert data["tractor_plate"] == "1234BCD"
    assert data["trailer_plate"] is None
    assert data["validation"]["valid"] is True


def test_api_patch_vehicle_articulated_success(
    expedition_client: TestClient,
    repo_with_expedition: tuple[InMemoryExpeditionRepository, Expedition],
) -> None:
    _, exp = repo_with_expedition
    url = f"/api/v1/expeditions/{exp.id}/vehicle"
    payload = {
        "vehicle_type": "ARTICULADO",
        "tractor_registration": "1234-BCD",
        "trailer_registration": "R-9999-ZZZ",
        "carrier_name": "Transportes Rápidos S.L.",
        "carrier_tax_id": "B04112233",
        "carrier_email": "trafico@rapidos.com",
        "actor": "OPERATOR_TEST",
    }

    response = expedition_client.patch(url, json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "LISTA_PARA_DECA"
    assert data["is_ready_for_deca"] is True
    assert data["tractor_plate"] == "1234BCD"
    assert data["trailer_plate"] == "R9999ZZZ"
    assert data["carrier_name"] == "Transportes Rápidos S.L."


def test_api_patch_vehicle_invalid_combination_returns_400(
    expedition_client: TestClient,
    repo_with_expedition: tuple[InMemoryExpeditionRepository, Expedition],
) -> None:
    _, exp = repo_with_expedition
    url = f"/api/v1/expeditions/{exp.id}/vehicle"
    # Rígido con semirremolque -> error 400
    payload = {
        "vehicle_type": "RIGIDO",
        "tractor_registration": "1234BCD",
        "trailer_registration": "R1234BCD",
    }

    response = expedition_client.patch(url, json=payload)
    assert response.status_code == 400
    assert "no puede tener remolque" in response.json()["detail"]


def test_api_patch_vehicle_invalid_plate_format_returns_400(
    expedition_client: TestClient,
    repo_with_expedition: tuple[InMemoryExpeditionRepository, Expedition],
) -> None:
    _, exp = repo_with_expedition
    url = f"/api/v1/expeditions/{exp.id}/vehicle"
    payload = {
        "vehicle_type": "RIGIDO",
        "tractor_registration": "12@#34",
    }

    response = expedition_client.patch(url, json=payload)
    assert response.status_code == 400
    assert "no permitidos" in response.json()["detail"]


def test_api_patch_vehicle_not_found_returns_404(expedition_client: TestClient) -> None:
    random_id = uuid.uuid4()
    url = f"/api/v1/expeditions/{random_id}/vehicle"
    payload = {
        "vehicle_type": "RIGIDO",
        "tractor_registration": "1234BCD",
    }

    response = expedition_client.patch(url, json=payload)
    assert response.status_code == 404


def test_api_get_expedition_validation(
    expedition_client: TestClient,
    repo_with_expedition: tuple[InMemoryExpeditionRepository, Expedition],
) -> None:
    _, exp = repo_with_expedition
    url = f"/api/v1/expeditions/{exp.id}/validation"

    response = expedition_client.get(url)
    assert response.status_code == 200
    data = response.json()

    assert data["expedition_id"] == str(exp.id)
    assert data["internal_id"] == "TD-2026-00001"
    # Al no tener vehículo todavía, valid es False y hay errores
    assert data["valid"] is False
    assert len(data["errors"]) > 0


def test_api_get_expedition_detail(
    expedition_client: TestClient,
    repo_with_expedition: tuple[InMemoryExpeditionRepository, Expedition],
) -> None:
    _, exp = repo_with_expedition
    url = f"/api/v1/expeditions/{exp.id}"

    response = expedition_client.get(url)
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(exp.id)
    assert data["internal_id"] == "TD-2026-00001"
    assert data["shipper_name"] == "Tomates de Autor S.L."
    assert data["carrier_name"] == "Transportes del Poniente S.L."
    assert data["origin"] == "El Ejido (Almería)"
    assert data["destination"] == "Mercamadrid (Madrid)"
    assert data["status"] == "PENDIENTE_MATRICULA"
    assert data["is_ready_for_deca"] is False


def test_api_get_expedition_not_found(expedition_client: TestClient) -> None:
    random_id = uuid.uuid4()
    response = expedition_client.get(f"/api/v1/expeditions/{random_id}")
    assert response.status_code == 404
