from __future__ import annotations

import hashlib
import uuid
from collections.abc import Generator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.config.companies import TEST_API_KEY_TOMATES
from src.config.settings import Settings
from src.domain.entities.deca import DeCA, DeCAVersion
from src.domain.entities.expedition import Expedition
from src.domain.enums import DeCAStatus, ExpeditionStatus, VehicleType
from src.domain.value_objects import NIF, Matricula, Weight
from src.infrastructure.email.fake_microsoft_graph_email_sender import (
    FakeMicrosoftGraphEmailSender,
)
from src.infrastructure.logging.in_memory_audit_service import InMemoryAuditService
from src.infrastructure.repositories.in_memory_deca_repository import (
    InMemoryDeCARepository,
)
from src.infrastructure.repositories.in_memory_email_delivery_repository import (
    InMemoryEmailDeliveryRepository,
)
from src.infrastructure.repositories.in_memory_expedition_repository import (
    InMemoryExpeditionRepository,
)
from src.infrastructure.storage.local_pdf_storage import LocalPdfStorage
from src.presentation.api.app import create_app
from src.presentation.api.dependencies import (
    get_audit_service,
    get_deca_repository,
    get_email_delivery_repository,
    get_email_sender,
    get_expedition_repository,
    get_storage_service,
)


@pytest.fixture
def email_api_context(
    test_settings: Settings, temp_storage_dir: Path
) -> Generator[tuple, None, None]:
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    audit_service = InMemoryAuditService()
    email_delivery_repo = InMemoryEmailDeliveryRepository()
    email_sender = FakeMicrosoftGraphEmailSender()
    storage = LocalPdfStorage(temp_storage_dir)

    exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00201",
        reference="ALB-2026-00201",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
        transport_date=date(2026, 10, 17),
        shipper_name="Tomates de Autor S.L.",
        shipper_tax_id=NIF("B12345678"),
        shipper_address="Polígono La Redonda, Almería",
        carrier_name_raw="TransAlmería Express S.L.",
        carrier_tax_id=NIF("B04777888"),
        carrier_email="despacho@transalmeria.es",
        origin="El Ejido (Almería)",
        destination="Rungis (Francia)",
        goods="Tomate Rosa de Almería",
        weight=Weight(18400.0),
        status=ExpeditionStatus.DECA_GENERADO,
    )
    exp.assign_vehicle(
        VehicleType.ARTICULADO,
        Matricula("9876XYZ"),
        Matricula("R4321UVW"),
    )
    exp.status = ExpeditionStatus.DECA_GENERADO
    exp_repo.save(exp)

    # Crear y custodiar PDF oficial para el DeCA
    pdf_bytes = b"%PDF-1.4 Official custodial DeCA for API test"
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    saved_path = storage.save(pdf_bytes, "deca/2026/DECA-2026-000201.pdf")

    version = DeCAVersion(
        version_number=1,
        pdf_sha256=pdf_hash,
        pdf_storage_path=saved_path,
        pdf_size_bytes=len(pdf_bytes),
        snapshot_hash="snapshot-sha256-test",
        snapshot_data={"test": "data"},
        created_at=datetime.now(UTC),
    )

    deca = DeCA(
        id=uuid.uuid4(),
        expedition_id=exp.id,
        deca_code="DECA-2026-000201",
        company_id="TOMATES_DE_AUTOR",
        current_version=1,
        status=DeCAStatus.ISSUED,
    )
    deca.add_version(version)
    deca_repo.save(deca)

    app = create_app(test_settings)
    app.dependency_overrides[get_expedition_repository] = lambda: exp_repo
    app.dependency_overrides[get_deca_repository] = lambda: deca_repo
    app.dependency_overrides[get_audit_service] = lambda: audit_service
    app.dependency_overrides[get_storage_service] = lambda: storage
    app.dependency_overrides[get_email_delivery_repository] = lambda: email_delivery_repo
    app.dependency_overrides[get_email_sender] = lambda: email_sender

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {TEST_API_KEY_TOMATES}"
        yield (
            client,
            exp_repo,
            deca_repo,
            email_delivery_repo,
            email_sender,
            audit_service,
            exp,
            deca,
        )


def test_api_send_deca_email_endpoint_success(email_api_context):
    """POST /api/v1/expeditions/{id}/deca/email envía correctamente el DeCA y retorna 200."""
    client, exp_repo, deca_repo, email_delivery_repo, email_sender, audit_service, exp, deca = (
        email_api_context
    )

    response = client.post(
        f"/api/v1/expeditions/{exp.id}/deca/email",
        json={"actor": "OPERATOR_CENTRAL", "force_resend": False},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["deca_code"] == "DECA-2026-000201"
    assert data["expedition_id"] == str(exp.id)
    assert data["email_status"] == "EMAIL_SENT"
    assert data["recipient"] == "despacho@transalmeria.es"
    assert data["recipient_masked"] == "de***@transalmeria.es"
    assert data["is_idempotent"] is False
    assert data["message_id"] is not None

    # Estado de expedición transicionado a ENVIADA
    updated_exp = exp_repo.get_by_id(exp.id)
    assert updated_exp.status == ExpeditionStatus.ENVIADA

    # Un mensaje enviado físicamente
    assert email_sender.send_count == 1


def test_api_send_deca_email_endpoint_idempotency(email_api_context):
    """POST repetido al endpoint devuelve resultado idempotente con 200 y sin duplicar correo."""
    client, exp_repo, deca_repo, email_delivery_repo, email_sender, audit_service, exp, deca = (
        email_api_context
    )

    # Primer envío
    res1 = client.post(f"/api/v1/expeditions/{exp.id}/deca/email", json={})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["is_idempotent"] is False

    # Segundo envío (automático sin force_resend)
    res2 = client.post(f"/api/v1/expeditions/{exp.id}/deca/email", json={})
    assert res2.status_code == 200
    data2 = res2.json()

    assert data2["is_idempotent"] is True
    assert data2["email_status"] == "EMAIL_SENT"
    assert data2["idempotency_key"] == data1["idempotency_key"]
    assert data2["message_id"] == data1["message_id"]
    assert email_sender.send_count == 1  # Cero retransmisiones!


def test_api_send_deca_email_manual_resend(email_api_context):
    """POST con force_resend=True fuerza un nuevo envío auditable y transmite el correo."""
    client, exp_repo, deca_repo, email_delivery_repo, email_sender, audit_service, exp, deca = (
        email_api_context
    )

    # Primer envío
    client.post(f"/api/v1/expeditions/{exp.id}/deca/email", json={})
    assert email_sender.send_count == 1

    # Reenvío manual explícito
    res = client.post(
        f"/api/v1/expeditions/{exp.id}/deca/email",
        json={"actor": "JEFE_TRAFICO", "force_resend": True},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_idempotent"] is False
    assert data["email_status"] == "EMAIL_SENT"
    assert email_sender.send_count == 2


def test_api_send_deca_email_missing_carrier_email(email_api_context):
    """POST para expedición sin email de transportista retorna EMAIL_PENDING (HTTP 200, no 500)."""
    client, exp_repo, deca_repo, email_delivery_repo, email_sender, audit_service, exp, deca = (
        email_api_context
    )

    exp.carrier_email = None
    exp_repo.save(exp)

    res = client.post(f"/api/v1/expeditions/{exp.id}/deca/email", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["email_status"] == "EMAIL_PENDING"
    assert "no configurado" in data["message"].lower()
    assert email_sender.send_count == 0


def test_api_send_deca_email_non_existent_expedition(email_api_context):
    """POST para expedición inexistente retorna 404 Not Found."""
    client, exp_repo, deca_repo, email_delivery_repo, email_sender, audit_service, exp, deca = (
        email_api_context
    )

    random_id = uuid.uuid4()
    res = client.post(f"/api/v1/expeditions/{random_id}/deca/email", json={})
    assert res.status_code == 404


def test_api_send_deca_email_deca_not_emitted(email_api_context):
    """POST cuando la expedición existe pero no tiene DeCA emitido retorna 404."""
    client, exp_repo, deca_repo, email_delivery_repo, email_sender, audit_service, exp, deca = (
        email_api_context
    )

    exp2 = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00202",
        company_id="TOMATES_DE_AUTOR",
        carrier_email="trans@test.es",
        status=ExpeditionStatus.LISTA_PARA_DECA,
    )
    exp_repo.save(exp2)

    res = client.post(f"/api/v1/expeditions/{exp2.id}/deca/email", json={})
    assert res.status_code == 404
    assert "no existe" in res.json()["detail"].lower()


def test_api_send_deca_email_invalid_uuid(email_api_context):
    """POST con UUID malformado retorna 400 Bad Request."""
    client, exp_repo, deca_repo, email_delivery_repo, email_sender, audit_service, exp, deca = (
        email_api_context
    )

    res = client.post("/api/v1/expeditions/not-a-valid-uuid/deca/email", json={})
    assert res.status_code == 400


def test_api_send_deca_email_ignores_recipient_in_body(email_api_context):
    """INVARIANTE DE SEGURIDAD: El endpoint nunca permite inyectar recipient en el body."""
    client, exp_repo, deca_repo, email_delivery_repo, email_sender, audit_service, exp, deca = (
        email_api_context
    )

    # Intentar enviar a un email atacante o externo en el payload JSON
    payload = {
        "actor": "ATTACKER",
        "force_resend": False,
        "recipient": "attacker@external-leak.com",
        "to": "attacker@external-leak.com",
    }
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca/email", json=payload)
    assert res.status_code == 200
    data = res.json()

    # El recipient utilizado debe seguir siendo estrictamente el de la expedición
    assert data["recipient"] == "despacho@transalmeria.es"
    assert email_sender.sent_messages[0].recipient == "despacho@transalmeria.es"


def test_api_get_expedition_email_status(email_api_context):
    """GET /api/v1/expeditions/{id}/deca/email consulta el historial de envíos de la expedición."""
    client, exp_repo, deca_repo, email_delivery_repo, email_sender, audit_service, exp, deca = (
        email_api_context
    )

    # Antes de enviar
    res_before = client.get(f"/api/v1/expeditions/{exp.id}/deca/email")
    assert res_before.status_code == 200
    data_before = res_before.json()
    assert data_before["current_status"] == "NOT_ATTEMPTED"
    assert data_before["total_deliveries"] == 0
    assert data_before["carrier_email_masked"] == "de***@transalmeria.es"

    # Enviar correo
    client.post(f"/api/v1/expeditions/{exp.id}/deca/email", json={})

    # Tras enviar
    res_after = client.get(f"/api/v1/expeditions/{exp.id}/deca/email")
    assert res_after.status_code == 200
    data_after = res_after.json()
    assert data_after["current_status"] == "EMAIL_SENT"
    assert data_after["total_deliveries"] == 1
    assert data_after["latest_delivery"] is not None
    assert data_after["latest_delivery"]["status"] == "EMAIL_SENT"
    assert data_after["latest_delivery"]["recipient_masked"] == "de***@transalmeria.es"


def test_api_get_expedition_email_status_not_found(email_api_context):
    """GET /api/v1/expeditions/{id}/deca/email para expedición inexistente devuelve 404."""
    client, exp_repo, deca_repo, email_delivery_repo, email_sender, audit_service, exp, deca = (
        email_api_context
    )

    random_id = uuid.uuid4()
    res = client.get(f"/api/v1/expeditions/{random_id}/deca/email")
    assert res.status_code == 404
