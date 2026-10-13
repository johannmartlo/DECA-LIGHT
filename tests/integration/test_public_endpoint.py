from __future__ import annotations

import hashlib
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.config.companies import TEST_API_KEY_TOMATES
from src.config.settings import Settings
from src.domain.entities.expedition import Expedition
from src.domain.enums import AuditAction, DeCAStatus, ExpeditionStatus, VehicleType
from src.domain.services.clock import Clock
from src.domain.services.public_token_service import PublicDeCaTokenService
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
def public_setup(
    test_settings: Settings, temp_storage_dir: Path
) -> tuple[
    TestClient,
    InMemoryExpeditionRepository,
    InMemoryDeCARepository,
    InMemoryAuditService,
    LocalPdfStorage,
    Expedition,
]:
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    audit_service = InMemoryAuditService()
    storage = LocalPdfStorage(temp_storage_dir)

    exp = Expedition(
        id=uuid.uuid4(),
        company_id="TOMATES_DE_AUTOR",
        internal_id="TD-2026-00088",
        reference="ALB-2026-12345",
        fiscal_year="2026",
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
        observations="Inspección en ruta",
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

    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {TEST_API_KEY_TOMATES}"
    return client, exp_repo, deca_repo, audit_service, storage, exp


# =============================================================================
# 22.3. Endpoint público /d/{token} — Casos positivos
# =============================================================================


def test_public_access_valid_token_returns_200(public_setup) -> None:
    client, _, _, _, _, exp = public_setup
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca", json={"actor": "OPERATOR"})
    assert res.status_code == 201
    data = res.json()
    token = data["public_token"]
    assert token is not None

    pub_res = client.get(f"/d/{token}")
    assert pub_res.status_code == 200
    assert pub_res.headers["content-type"] == "application/pdf"


def test_public_access_returns_inline_disposition(public_setup) -> None:
    client, _, _, _, _, exp = public_setup
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    data = res.json()
    token = data["public_token"]

    pub_res = client.get(f"/d/{token}")
    assert pub_res.status_code == 200
    cd = pub_res.headers["content-disposition"]
    assert "inline" in cd
    assert "DECA-2026-" in cd
    assert ".pdf" in cd


def test_public_access_security_headers(public_setup) -> None:
    client, _, _, _, _, exp = public_setup
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    token = res.json()["public_token"]

    pub_res = client.get(f"/d/{token}")
    assert pub_res.status_code == 200
    assert pub_res.headers["cache-control"] == "private, no-cache, no-store, must-revalidate"
    assert pub_res.headers["x-content-type-options"] == "nosniff"
    assert pub_res.headers["x-robots-tag"] == "noindex, nofollow, noarchive"


def test_public_access_pdf_integrity(public_setup) -> None:
    client, _, _, _, _, exp = public_setup
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    data = res.json()
    expected_hash = data["pdf_sha256"]
    token = data["public_token"]

    pub_res = client.get(f"/d/{token}")
    assert pub_res.status_code == 200
    actual_hash = hashlib.sha256(pub_res.content).hexdigest()
    assert actual_hash == expected_hash


def test_public_access_transport_in_progress(public_setup) -> None:
    client, _, deca_repo, _, _, exp = public_setup
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    token = res.json()["public_token"]

    deca = deca_repo.find_by_expedition_id(exp.id)
    assert deca is not None
    assert deca.service_end_at is None

    pub_res = client.get(f"/d/{token}")
    assert pub_res.status_code == 200


def test_public_access_within_7_days(public_setup) -> None:
    client, _, deca_repo, _, _, exp = public_setup
    now = datetime(2026, 10, 4, 10, 0, 0, tzinfo=UTC)
    Clock.freeze(now)

    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    token = res.json()["public_token"]

    deca = deca_repo.find_by_expedition_id(exp.id)
    end_time = now + timedelta(hours=5)
    deca.record_service_end(end_time)

    # 6 días después del fin de transporte
    Clock.freeze(end_time + timedelta(days=6))
    pub_res = client.get(f"/d/{token}")
    assert pub_res.status_code == 200

    Clock.unfreeze()


def test_public_access_exact_7_days(public_setup) -> None:
    client, _, deca_repo, _, _, exp = public_setup
    now = datetime(2026, 10, 4, 10, 0, 0, tzinfo=UTC)
    Clock.freeze(now)

    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    token = res.json()["public_token"]

    deca = deca_repo.find_by_expedition_id(exp.id)
    end_time = now + timedelta(hours=5)
    deca.record_service_end(end_time)

    # Exactamente 7 días después
    Clock.freeze(end_time + timedelta(days=7))
    pub_res = client.get(f"/d/{token}")
    assert pub_res.status_code == 200

    Clock.unfreeze()


# =============================================================================
# 22.4. Endpoint público /d/{token} — Casos negativos y seguridad anti-IDOR
# =============================================================================


def test_public_access_invalid_token_returns_404(public_setup) -> None:
    client, _, _, _, _, _ = public_setup
    random_valid_syntax_token = PublicDeCaTokenService.generate_token()
    res = client.get(f"/d/{random_valid_syntax_token}")
    assert res.status_code == 404
    assert res.json()["detail"] == "Documento DeCA no encontrado o no disponible."


def test_public_access_malformed_token_returns_404(public_setup) -> None:
    client, _, _, _, _, _ = public_setup
    res = client.get("/d/token_with_invalid_char$#@!")
    assert res.status_code == 404
    assert res.json()["detail"] == "Documento DeCA no encontrado o no disponible."


def test_public_access_short_token_returns_404(public_setup) -> None:
    client, _, _, _, _, _ = public_setup
    res = client.get("/d/tooshort")
    assert res.status_code == 404
    assert res.json()["detail"] == "Documento DeCA no encontrado o no disponible."


def test_public_access_empty_token_returns_404(public_setup) -> None:
    client, _, _, _, _, _ = public_setup
    res = client.get("/d/")
    # FastAPI devolverá 404 por ruta no coincidente
    assert res.status_code == 404


def test_public_access_expired_token_returns_404(public_setup) -> None:
    client, _, deca_repo, _, _, exp = public_setup
    now = datetime(2026, 10, 4, 10, 0, 0, tzinfo=UTC)
    Clock.freeze(now)

    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    token = res.json()["public_token"]

    deca = deca_repo.find_by_expedition_id(exp.id)
    deca.record_service_end(now)

    # 7 días y 1 segundo después -> 404
    Clock.freeze(now + timedelta(days=7, seconds=1))
    pub_res = client.get(f"/d/{token}")
    assert pub_res.status_code == 404
    assert pub_res.json()["detail"] == "Documento DeCA no encontrado o no disponible."

    Clock.unfreeze()


def test_public_access_revoked_deca_returns_404(public_setup) -> None:
    client, _, deca_repo, _, _, exp = public_setup
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    token = res.json()["public_token"]

    deca = deca_repo.find_by_expedition_id(exp.id)
    deca.status = DeCAStatus.REVOKED

    pub_res = client.get(f"/d/{token}")
    assert pub_res.status_code == 404
    assert pub_res.json()["detail"] == "Documento DeCA no encontrado o no disponible."


def test_public_access_internal_id_rejected(public_setup) -> None:
    client, _, deca_repo, _, _, exp = public_setup
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    data = res.json()
    deca_id = data["deca_id"]
    deca = deca_repo.find_by_expedition_id(exp.id)
    deca_code = deca.deca_code

    # Intentar acceder mediante UUID interno
    res1 = client.get(f"/d/{deca_id}")
    assert res1.status_code == 404

    # Intentar acceder mediante código DeCA oficial
    res2 = client.get(f"/d/{deca_code}")
    assert res2.status_code == 404

    # Intentar acceder mediante ID de la expedición
    res3 = client.get(f"/d/{exp.id}")
    assert res3.status_code == 404


def test_public_access_no_info_leak_on_404(public_setup) -> None:
    client, _, deca_repo, _, _, exp = public_setup
    now = datetime(2026, 10, 4, 10, 0, 0, tzinfo=UTC)
    Clock.freeze(now)

    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    token = res.json()["public_token"]

    deca = deca_repo.find_by_expedition_id(exp.id)
    deca.record_service_end(now)

    # 1. Token expirado
    Clock.freeze(now + timedelta(days=10))
    res_expired = client.get(f"/d/{token}")
    Clock.unfreeze()

    # 2. Token sintácticamente inválido
    res_invalid = client.get("/d/invalid_syntax_123")

    # 3. Token con sintaxis válida pero inexistente
    non_existent = PublicDeCaTokenService.generate_token()
    res_nonexistent = client.get(f"/d/{non_existent}")

    # Indistinguibles: exactamente el mismo código y mensaje JSON
    assert res_expired.status_code == 404
    assert res_invalid.status_code == 404
    assert res_nonexistent.status_code == 404
    assert res_expired.json() == res_invalid.json() == res_nonexistent.json()


def test_public_access_timing_uniformity(public_setup) -> None:
    """Verifica que no existan discrepancias temporales aberrantes entre errores."""
    client, _, _, _, _, _ = public_setup
    invalid_token = "invalid!@"
    nonexistent_token = PublicDeCaTokenService.generate_token()

    # Realizar 5 mediciones rápidas para mitigar jitter
    times_invalid = []
    times_nonexistent = []
    for _ in range(5):
        t0 = time.perf_counter()
        client.get(f"/d/{invalid_token}")
        times_invalid.append(time.perf_counter() - t0)

        t1 = time.perf_counter()
        client.get(f"/d/{nonexistent_token}")
        times_nonexistent.append(time.perf_counter() - t1)

    avg_inv = sum(times_invalid) / len(times_invalid)
    avg_non = sum(times_nonexistent) / len(times_nonexistent)
    # Comprobar que ambos responden en orden similar de milisegundos (< 100 ms de diferencia)
    assert abs(avg_inv - avg_non) < 0.100


def test_public_access_sql_injection_in_token(public_setup) -> None:
    client, _, _, _, _, _ = public_setup
    payloads = [
        "' OR '1'='1",
        "1; DROP TABLE deca;--",
        "' UNION SELECT * FROM deca--",
    ]
    for p in payloads:
        res = client.get(f"/d/{p}")
        assert res.status_code == 404
        assert res.json()["detail"] == "Documento DeCA no encontrado o no disponible."


def test_public_access_path_traversal_in_token(public_setup) -> None:
    client, _, _, _, _, _ = public_setup
    payloads = [
        "../../etc/passwd",
        "..%2F..%2Fdeca.sqlite3",
        "....//....//deca",
    ]
    for p in payloads:
        res = client.get(f"/d/{p}")
        assert res.status_code == 404


# =============================================================================
# 22.5. Auditoría y observabilidad
# =============================================================================


def test_public_access_audit_success(public_setup) -> None:
    client, _, _, audit_service, _, exp = public_setup
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    token = res.json()["public_token"]

    client.get(f"/d/{token}")

    events = [e for e in audit_service.events if e.action == AuditAction.PUBLIC_DECA_ACCESS_SUCCESS]
    assert len(events) == 1
    assert "token_masked" in events[0].new_state
    assert events[0].new_state["token_masked"] != token


def test_public_access_audit_not_found(public_setup) -> None:
    client, _, _, audit_service, _, _ = public_setup
    token = PublicDeCaTokenService.generate_token()
    client.get(f"/d/{token}")

    events = [
        e for e in audit_service.events if e.action == AuditAction.PUBLIC_DECA_ACCESS_NOT_FOUND
    ]
    assert len(events) >= 1
    assert events[-1].new_state["reason"] == "TOKEN_NOT_FOUND"


def test_public_access_audit_expired(public_setup) -> None:
    client, _, deca_repo, audit_service, _, exp = public_setup
    now = datetime(2026, 10, 4, 10, 0, 0, tzinfo=UTC)
    Clock.freeze(now)

    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    token = res.json()["public_token"]

    deca = deca_repo.find_by_expedition_id(exp.id)
    deca.record_service_end(now)

    Clock.freeze(now + timedelta(days=8))
    client.get(f"/d/{token}")
    Clock.unfreeze()

    events = [e for e in audit_service.events if e.action == AuditAction.PUBLIC_DECA_ACCESS_EXPIRED]
    assert len(events) == 1


def test_public_access_audit_no_cleartext_token(public_setup) -> None:
    client, _, _, audit_service, _, exp = public_setup
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    token = res.json()["public_token"]

    client.get(f"/d/{token}")

    for e in audit_service.events:
        # En ningún campo de estado debe constar el token en claro
        state_str = str(e.new_state)
        assert token not in state_str


def test_public_access_audit_captures_client_ip(public_setup) -> None:
    client, _, _, audit_service, _, exp = public_setup
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    token = res.json()["public_token"]

    client.get(f"/d/{token}", headers={"X-Forwarded-For": "198.51.100.42"})

    events = [e for e in audit_service.events if e.action == AuditAction.PUBLIC_DECA_ACCESS_SUCCESS]
    assert len(events) == 1
    assert events[0].user_identifier == "IP:198.51.100.42"
    assert events[0].new_state["client_ip"] == "198.51.100.42"


# =============================================================================
# 22.6. Integración del flujo completo (Fase 5 + Fase 6)
# =============================================================================


def test_end_to_end_emission_to_public_access(public_setup) -> None:
    client, _, _, _, _, exp = public_setup
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    assert res.status_code == 201
    data = res.json()

    token = data["public_token"]
    public_url = data["public_url"]
    assert public_url.endswith(f"/d/{token}")

    # Acceso por la ruta relativa
    pdf_res = client.get(f"/d/{token}")
    assert pdf_res.status_code == 200
    assert len(pdf_res.content) > 1000
    assert hashlib.sha256(pdf_res.content).hexdigest() == data["pdf_sha256"]


def test_idempotent_emission_maintains_same_token(public_setup) -> None:
    client, _, _, _, _, exp = public_setup
    res1 = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    assert res1.status_code == 201
    data1 = res1.json()

    # Segunda emisión idéntica
    res2 = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    assert res2.status_code == 201
    data2 = res2.json()

    assert data1["public_token"] == data2["public_token"]
    assert data1["public_url"] == data2["public_url"]
    assert data1["pdf_sha256"] == data2["pdf_sha256"]


def test_clock_advance_lifecycle(public_setup) -> None:
    client, _, deca_repo, _, _, exp = public_setup
    t0 = datetime(2026, 10, 4, 8, 0, 0, tzinfo=UTC)
    Clock.freeze(t0)

    # 1. Emisión
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    token = res.json()["public_token"]

    # 2. Acceso en ruta (transporte en curso)
    Clock.advance(hours=10)
    assert client.get(f"/d/{token}").status_code == 200

    # 3. Fin de servicio registrado
    deca = deca_repo.find_by_expedition_id(exp.id)
    deca.record_service_end(Clock.now())

    # 4. Acceso en el día 6 post-servicio
    Clock.advance(days=6)
    assert client.get(f"/d/{token}").status_code == 200

    # 5. Caducidad en el día 8 post-servicio -> 404
    Clock.advance(days=2)
    assert client.get(f"/d/{token}").status_code == 404

    Clock.unfreeze()


# =============================================================================
# 23. PRUEBA END-TO-END DE CONFIRMACIÓN OBLIGATORIA
# =============================================================================


def test_section_23_full_end_to_end_audit_confirmation(public_setup) -> None:
    """Ejecuta los 9 pasos exhaustivos del protocolo de confirmación de la Sección 23."""
    client, exp_repo, deca_repo, audit_service, storage, exp = public_setup
    t0 = datetime(2026, 10, 4, 9, 0, 0, tzinfo=UTC)
    Clock.freeze(t0)

    # 1 & 2. Emitir DeCA v1 para expedición lista
    emit_res = client.post(f"/api/v1/expeditions/{exp.id}/deca", json={"actor": "TRAFFIC_MANAGER"})
    assert emit_res.status_code == 201
    emit_data = emit_res.json()

    # 3. Verificar campos de respuesta
    deca_code = (
        emit_data["deca_code"]
        if "deca_code" in emit_data
        else deca_repo.find_by_expedition_id(exp.id).deca_code
    )
    pdf_sha256 = emit_data["pdf_sha256"]
    public_token = emit_data["public_token"]
    public_url = emit_data["public_url"]

    assert deca_code.startswith("DECA-2026-")
    assert len(pdf_sha256) == 64
    assert len(public_token) >= 43
    assert public_url == f"http://localhost:8000/d/{public_token}"

    # 4. Verificar que el PDF en custodia física contiene el QR y el hash exacto
    deca = deca_repo.find_by_expedition_id(exp.id)
    storage_path = deca.latest_version.pdf_storage_path
    pdf_on_disk = storage.read(storage_path)
    assert hashlib.sha256(pdf_on_disk).hexdigest() == pdf_sha256

    # 5. Petición GET a la public_url
    get_res = client.get(f"/d/{public_token}")
    assert get_res.status_code == 200
    assert get_res.headers["content-type"] == "application/pdf"
    assert get_res.headers["cache-control"] == "private, no-cache, no-store, must-revalidate"
    assert get_res.headers["x-content-type-options"] == "nosniff"
    assert get_res.headers["x-robots-tag"] == "noindex, nofollow, noarchive"
    assert get_res.content == pdf_on_disk  # Coincidencia byte a byte

    # 6. Ataques simulados
    # - Modificar un carácter
    tampered_token = public_token[:-1] + ("A" if public_token[-1] != "A" else "B")
    assert client.get(f"/d/{tampered_token}").status_code == 404
    # - Truncar el token
    assert client.get(f"/d/{public_token[:30]}").status_code == 404
    # - Añadir caracteres al token
    assert client.get(f"/d/{public_token}EXTRA").status_code == 404
    # - Acceder con deca_code
    assert client.get(f"/d/{deca_code}").status_code == 404
    # - Acceder con expedition_id
    assert client.get(f"/d/{exp.id}").status_code == 404

    # 7. Simular fin de transporte y ciclo temporal
    finish_time = Clock.now()
    deca.record_service_end(finish_time)

    # Avanzar 3 días -> 200
    Clock.advance(days=3)
    assert client.get(f"/d/{public_token}").status_code == 200

    # Avanzar hasta superar los 7 días (4 días más y 1 segundo) -> 404
    Clock.advance(days=4, seconds=1)
    assert client.get(f"/d/{public_token}").status_code == 404

    # 8. Modificar la expedición fuente y verificar inmutabilidad del DeCA v1
    exp.observations = "MUTACIÓN POSTERIOR ILEGAL DEL OPERADOR"
    exp.goods = "MERCANCÍA ALTERADA TRAS EMISIÓN"
    exp_repo.save(exp)

    # El PDF en disco y en la versión custodial mantiene el hash original intacto
    pdf_after_mutation = storage.read(storage_path)
    assert hashlib.sha256(pdf_after_mutation).hexdigest() == pdf_sha256

    # 9. Verificación de auditoría: sin token en texto plano y con acciones requeridas
    actions_recorded = [e.action for e in audit_service.events]
    assert AuditAction.DECA_EMITTED in actions_recorded
    assert AuditAction.PUBLIC_DECA_ACCESS_SUCCESS in actions_recorded
    assert AuditAction.PUBLIC_DECA_ACCESS_NOT_FOUND in actions_recorded
    assert AuditAction.PUBLIC_DECA_ACCESS_EXPIRED in actions_recorded

    for event in audit_service.events:
        assert public_token not in str(event.new_state)

    Clock.unfreeze()


def test_public_access_without_any_authorization_header(public_setup) -> None:
    """Verifica que el endpoint público /d/{token} funciona sin credenciales de autenticación."""
    client, _, _, _, _, exp = public_setup
    res = client.post(f"/api/v1/expeditions/{exp.id}/deca")
    assert res.status_code == 201
    token = res.json()["public_token"]

    unauth_client = TestClient(client.app)
    pub_res = unauth_client.get(f"/d/{token}")
    assert pub_res.status_code == 200
    assert pub_res.headers["content-type"] == "application/pdf"

