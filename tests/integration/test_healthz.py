from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz_endpoint_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == "DECA Light Test"
    assert data["version"] == "0.1.0-test"
    assert data["environment"] == "test"
    assert data["database"] == "ready"
    assert data["storage"] == "ok"
