from __future__ import annotations

import concurrent.futures
import hashlib
import uuid
from datetime import UTC, date, datetime

import httpx
import pytest

from src.application.dtos.email_dto import (
    EmailAttachmentDTO,
    EmailMessageDTO,
    SendDeCAEmailInputDTO,
)
from src.application.use_cases.send_deca_email import SendDeCAEmailUseCase
from src.domain.entities.deca import DeCA, DeCAVersion
from src.domain.entities.email_delivery import EmailDelivery
from src.domain.entities.expedition import Expedition
from src.domain.enums import (
    AuditAction,
    DeCAStatus,
    EmailDeliveryStatus,
    ExpeditionStatus,
    VehicleType,
)
from src.domain.exceptions import EntityNotFoundException
from src.domain.value_objects import NIF, EmailAddress, Matricula, Weight
from src.infrastructure.email.fake_microsoft_graph_email_sender import (
    FakeMicrosoftGraphEmailSender,
)
from src.infrastructure.email.microsoft_graph_email_sender import (
    MicrosoftGraphEmailSender,
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


@pytest.fixture
def mock_storage(tmp_path):
    storage = LocalPdfStorage(tmp_path)
    return storage


@pytest.fixture
def sample_expedition_with_deca(mock_storage):
    exp_repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    audit_service = InMemoryAuditService()
    email_delivery_repo = InMemoryEmailDeliveryRepository()
    email_sender = FakeMicrosoftGraphEmailSender()

    exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00101",
        reference="ALB-2026-00101",
        fiscal_year="2026",
        transport_date=date(2026, 10, 16),
        shipper_name="Tomates de Autor S.L.",
        shipper_tax_id=NIF("B12345678"),
        shipper_address="Polígono La Redonda, Almería",
        carrier_name_raw="Transportes Hermanos Ruiz S.L.",
        carrier_tax_id=NIF("B04111222"),
        carrier_email="logistica@hermanosruiz.es",
        origin="El Ejido (Almería)",
        destination="Perpignan (Francia)",
        goods="Tomate Pera Gourmet",
        weight=Weight(21500.0),
        status=ExpeditionStatus.DECA_GENERADO,
    )
    exp.assign_vehicle(
        VehicleType.ARTICULADO,
        Matricula("5678JKL"),
        Matricula("R1234MNO"),
    )
    exp.status = ExpeditionStatus.DECA_GENERADO
    exp_repo.save(exp)

    # Crear PDF sintético reproducible
    pdf_content = b"%PDF-1.4 Fake immutable DeCA PDF binary for testing"
    pdf_hash = hashlib.sha256(pdf_content).hexdigest()
    saved_path = mock_storage.save(pdf_content, "deca/2026/DECA-2026-000101.pdf")

    version = DeCAVersion(
        version_number=1,
        pdf_sha256=pdf_hash,
        pdf_storage_path=saved_path,
        pdf_size_bytes=len(pdf_content),
        snapshot_hash="fake-snapshot-hash",
        snapshot_data={"test": "data"},
        created_at=datetime.now(UTC),
    )

    deca = DeCA(
        id=uuid.uuid4(),
        expedition_id=exp.id,
        deca_code="DECA-2026-000101",
        current_version=1,
        status=DeCAStatus.ISSUED,
    )
    deca.add_version(version)
    deca_repo.save(deca)

    use_case = SendDeCAEmailUseCase(
        expedition_repo=exp_repo,
        deca_repo=deca_repo,
        storage_service=mock_storage,
        email_sender=email_sender,
        email_delivery_repo=email_delivery_repo,
        audit_service=audit_service,
        sender_email="pedidos@tomatesdeautor.com",
    )

    return {
        "exp": exp,
        "deca": deca,
        "version": version,
        "pdf_content": pdf_content,
        "pdf_hash": pdf_hash,
        "use_case": use_case,
        "exp_repo": exp_repo,
        "deca_repo": deca_repo,
        "email_delivery_repo": email_delivery_repo,
        "audit_service": audit_service,
        "email_sender": email_sender,
        "storage": mock_storage,
    }


# =========================================================================
# 1. PRUEBAS DE VALUE OBJECT EMAIL ADDRESS Y OFUSCACIÓN
# =========================================================================


def test_email_address_valid_parsing():
    """Valida emails correctos y su normalización a minúsculas sin espacios."""
    email = EmailAddress.create("  Trafico@Poniente.COM  ")
    assert email.value == "trafico@poniente.com"
    assert email.domain == "poniente.com"
    assert email.local_part == "trafico"


def test_email_address_invalid_formats():
    """Rechaza direcciones de correo inválidas según RFC 5322."""
    invalid_cases = [
        "no-arroba.com",
        "@sin-usuario.com",
        "usuario@",
        "espacios en@medio.com",
        "usuario@dominio sin punto",
        "",
        "   ",
    ]
    for case in invalid_cases:
        with pytest.raises(ValueError):
            EmailAddress.create(case)


def test_email_address_masking_standard():
    """Comprueba la ofuscación de privacidad de emails estándar."""
    assert EmailAddress.mask_str("juan.perez@transportes.es") == "ju***@transportes.es"
    assert EmailAddress.mask_str("logistica@poniente.com") == "lo***@poniente.com"


def test_email_address_masking_short_or_edge():
    """Comprueba la ofuscación en casos borde y partes locales cortas."""
    assert EmailAddress.mask_str("a@dominio.com") == "*@dominio.com"
    assert EmailAddress.mask_str("ab@dominio.com") == "a*@dominio.com"
    assert EmailAddress.mask_str("abc@dominio.com") == "ab*@dominio.com"
    assert EmailAddress.mask_str("") == "***"
    assert EmailAddress.mask_str("no-valid") == "no***"


# =========================================================================
# 2. PRUEBAS DEL FAKE SENDER Y SIMULACIÓN GRAPH API
# =========================================================================


def test_fake_graph_email_sender_success():
    """El FakeMicrosoftGraphEmailSender emite correctamente y genera message_id."""
    sender = FakeMicrosoftGraphEmailSender()
    msg = EmailMessageDTO(
        sender="pedidos@tomatesdeautor.com",
        recipient="test@carrier.es",
        subject="Test Subject",
        body_text="Test Body",
        attachments=[EmailAttachmentDTO(filename="deca.pdf", content_bytes=b"%PDF-test")],
    )
    result = sender.send(msg)

    assert result.success is True
    assert result.status == EmailDeliveryStatus.EMAIL_SENT
    assert result.status_code == 202
    assert result.message_id is not None
    assert "@tomatesdeautor.com" in result.message_id
    assert len(sender.sent_messages) == 1
    assert sender.send_count == 1


def test_fake_graph_sender_simulate_permanent_error():
    """Simula fallos HTTP 400/401/403/404 marcados como no transitorios."""
    sender = FakeMicrosoftGraphEmailSender()
    sender.configure_failure(status_code=403, error_message="Mail.Send permission denied")

    msg = EmailMessageDTO(
        sender="pedidos@tomatesdeautor.com",
        recipient="test@carrier.es",
        subject="Test",
        body_text="Body",
    )
    result = sender.send(msg)

    assert result.success is False
    assert result.status == EmailDeliveryStatus.EMAIL_FAILED
    assert result.is_transient is False
    assert result.status_code == 403
    assert "Mail.Send permission denied" in result.error_message


def test_fake_graph_sender_simulate_transient_error():
    """Simula fallos HTTP 429 y 500 marcados como reintentables/transitorios."""
    sender = FakeMicrosoftGraphEmailSender()
    sender.configure_failure(status_code=429, error_message="Throttling rate limit exceeded")

    msg = EmailMessageDTO(
        sender="pedidos@tomatesdeautor.com",
        recipient="test@carrier.es",
        subject="Test",
        body_text="Body",
    )
    result = sender.send(msg)

    assert result.success is False
    assert result.status == EmailDeliveryStatus.EMAIL_RETRY_PENDING
    assert result.is_transient is True
    assert result.status_code == 429


def test_fake_graph_sender_simulate_timeout():
    """Simula un timeout de red que se clasifica como transitorio."""
    sender = FakeMicrosoftGraphEmailSender()
    sender.configure_timeout(fail_times=1)

    msg = EmailMessageDTO(
        sender="pedidos@tomatesdeautor.com",
        recipient="test@carrier.es",
        subject="Test",
        body_text="Body",
    )
    result = sender.send(msg)

    assert result.success is False
    assert result.status == EmailDeliveryStatus.EMAIL_RETRY_PENDING
    assert result.is_transient is True
    assert result.status_code == 408


# =========================================================================
# 3. PRUEBAS DEL ADAPTADOR REAL MICROSOFT GRAPH (MOCKEADO CON HTTPX)
# =========================================================================


def test_microsoft_graph_missing_credentials_fails_gracefully():
    """Si faltan credenciales de Entra ID, rechaza permanentemente sin lanzar excepción."""
    sender = MicrosoftGraphEmailSender(
        tenant_id=None,
        client_id=None,
        client_secret=None,
    )
    msg = EmailMessageDTO(
        sender="pedidos@tomatesdeautor.com",
        recipient="test@carrier.es",
        subject="Test",
        body_text="Body",
    )
    result = sender.send(msg)

    assert result.success is False
    assert result.status == EmailDeliveryStatus.EMAIL_FAILED
    assert result.is_transient is False
    assert "Credenciales" in result.error_message


def test_microsoft_graph_successful_token_and_send():
    """Simula una transmisión completa con OAuth2 y sendMail exitosos (202)."""
    calls = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if "oauth2/v2.0/token" in str(request.url):
            return httpx.Response(
                status_code=200,
                json={"access_token": "fake-jwt-token-xyz", "expires_in": 3600},
            )
        if "sendMail" in str(request.url):
            assert request.headers.get("Authorization") == "Bearer fake-jwt-token-xyz"
            return httpx.Response(
                status_code=202,
                headers={"client-request-id": "req-12345-graph-uuid"},
            )
        return httpx.Response(status_code=404)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    sender = MicrosoftGraphEmailSender(
        tenant_id="tenant-123",
        client_id="client-456",
        client_secret="secret-789",
        http_client=client,
    )

    msg = EmailMessageDTO(
        sender="pedidos@tomatesdeautor.com",
        recipient="carrier@test.es",
        subject="DECA Test",
        body_text="Mensaje con adjunto",
        attachments=[EmailAttachmentDTO(filename="deca.pdf", content_bytes=b"%PDF-Mock-Content")],
    )
    result = sender.send(msg)

    assert result.success is True
    assert result.status == EmailDeliveryStatus.EMAIL_SENT
    assert result.message_id == "req-12345-graph-uuid"
    assert len(calls) == 2


def test_microsoft_graph_token_caching():
    """Comprueba que el token OAuth2 se almacena en caché y no se vuelve a pedir."""
    token_requests = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_requests
        if "oauth2/v2.0/token" in str(request.url):
            token_requests += 1
            return httpx.Response(
                status_code=200,
                json={"access_token": "fake-cached-token", "expires_in": 3600},
            )
        if "sendMail" in str(request.url):
            return httpx.Response(status_code=202)
        return httpx.Response(status_code=404)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    sender = MicrosoftGraphEmailSender(
        tenant_id="t-1", client_id="c-1", client_secret="s-1", http_client=client
    )

    msg = EmailMessageDTO(
        sender="pedidos@tomatesdeautor.com",
        recipient="c@test.es",
        subject="DECA",
        body_text="Hi",
    )
    # Primer envío
    res1 = sender.send(msg)
    assert res1.success is True
    assert token_requests == 1

    # Segundo envío debe reutilizar token
    res2 = sender.send(msg)
    assert res2.success is True
    assert token_requests == 1  # No se ha vuelto a pedir el token


def test_microsoft_graph_retry_on_429_then_succeeds():
    """Comprueba que un error 429 transitorio se reintenta automáticamente y finaliza con éxito."""
    attempt_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt_count
        if "oauth2/v2.0/token" in str(request.url):
            return httpx.Response(
                status_code=200,
                json={"access_token": "token-xyz", "expires_in": 3600},
            )
        if "sendMail" in str(request.url):
            attempt_count += 1
            if attempt_count == 1:
                return httpx.Response(
                    status_code=429,
                    headers={"Retry-After": "0"},
                    json={"error": {"message": "Rate limit exceeded"}},
                )
            return httpx.Response(status_code=202)
        return httpx.Response(status_code=404)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    sender = MicrosoftGraphEmailSender(
        tenant_id="t-1",
        client_id="c-1",
        client_secret="s-1",
        http_client=client,
        max_retries=3,
        base_retry_delay=0.01,
    )

    msg = EmailMessageDTO(
        sender="pedidos@tomatesdeautor.com",
        recipient="c@test.es",
        subject="DECA",
        body_text="Hi",
    )
    result = sender.send(msg)

    assert result.success is True
    assert attempt_count == 2


def test_microsoft_graph_permanent_error_no_retry():
    """Un error permanente (400 Bad Request) no debe reintentarse."""
    send_attempts = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal send_attempts
        if "oauth2/v2.0/token" in str(request.url):
            return httpx.Response(
                status_code=200,
                json={"access_token": "token-xyz", "expires_in": 3600},
            )
        if "sendMail" in str(request.url):
            send_attempts += 1
            return httpx.Response(
                status_code=400,
                json={"error": {"message": "Invalid recipient format"}},
            )
        return httpx.Response(status_code=404)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    sender = MicrosoftGraphEmailSender(
        tenant_id="t-1",
        client_id="c-1",
        client_secret="s-1",
        http_client=client,
        max_retries=3,
        base_retry_delay=0.01,
    )

    msg = EmailMessageDTO(
        sender="pedidos@tomatesdeautor.com",
        recipient="c@test.es",
        subject="DECA",
        body_text="Hi",
    )
    result = sender.send(msg)

    assert result.success is False
    assert result.is_transient is False
    assert result.status == EmailDeliveryStatus.EMAIL_FAILED
    assert send_attempts == 1  # Exactamente 1 intento, sin reintentos innecesarios


# =========================================================================
# 4. PRUEBAS DEL CASO DE USO SEND DECA EMAIL (LÓGICA DE NEGOCIO E INVARIANTES)
# =========================================================================


def test_send_deca_email_success(sample_expedition_with_deca):
    """Envío exitoso: transiciona a ENVIADA, registra entrega y audita EMAIL_SENT."""
    ctx = sample_expedition_with_deca
    use_case: SendDeCAEmailUseCase = ctx["use_case"]
    exp: Expedition = ctx["exp"]

    res = use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))

    assert res.email_status == "EMAIL_SENT"
    assert res.recipient == "logistica@hermanosruiz.es"
    assert res.recipient_masked == "lo***@hermanosruiz.es"
    assert res.is_idempotent is False
    assert res.message_id is not None
    assert res.deca_code == "DECA-2026-000101"

    # Invariante: expedición transiciona a ENVIADA
    updated_exp = ctx["exp_repo"].get_by_id(exp.id)
    assert updated_exp.status == ExpeditionStatus.ENVIADA

    # Registro en repositorio de entregas
    deliveries = ctx["email_delivery_repo"].find_by_deca_id(ctx["deca"].id)
    assert len(deliveries) == 1
    assert deliveries[0].status == EmailDeliveryStatus.EMAIL_SENT
    assert deliveries[0].recipient_masked == "lo***@hermanosruiz.es"

    # Auditoría registrada
    actions = [e.action for e in ctx["audit_service"].events]
    assert AuditAction.EMAIL_SEND_REQUESTED in actions
    assert AuditAction.EMAIL_SENT in actions


def test_send_deca_email_subject_and_body_formatting(sample_expedition_with_deca):
    """Verifica que asunto y cuerpo del mensaje contienen referencias exactas."""
    ctx = sample_expedition_with_deca
    use_case: SendDeCAEmailUseCase = ctx["use_case"]
    exp: Expedition = ctx["exp"]
    fake_sender: FakeMicrosoftGraphEmailSender = ctx["email_sender"]

    use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))

    assert len(fake_sender.sent_messages) == 1
    msg = fake_sender.sent_messages[0]

    expected_subject = f"DECA – Expedición {exp.internal_id} – [{exp.destination}]"
    assert msg.subject == expected_subject
    assert msg.sender == "pedidos@tomatesdeautor.com"
    assert msg.recipient == "logistica@hermanosruiz.es"
    assert exp.internal_id in msg.body_text
    assert "DECA-2026-000101" in msg.body_text
    assert exp.destination in msg.body_text
    assert "Tomates de Autor S.L." in msg.body_text

    # Adjunto coincide exactamente byte a byte
    assert len(msg.attachments) == 1
    att = msg.attachments[0]
    assert att.filename == "DECA-2026-000101.pdf"
    assert att.content_bytes == ctx["pdf_content"]
    assert att.content_type == "application/pdf"
    assert att.sha256 == ctx["pdf_hash"]


def test_send_deca_email_idempotency_second_call_ignored(sample_expedition_with_deca):
    """Llamadas repetidas devuelven resultado idempotente sin enviar un segundo correo."""
    ctx = sample_expedition_with_deca
    use_case: SendDeCAEmailUseCase = ctx["use_case"]
    exp: Expedition = ctx["exp"]
    sender: FakeMicrosoftGraphEmailSender = ctx["email_sender"]

    res1 = use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))
    assert res1.is_idempotent is False
    assert sender.send_count == 1

    # Segunda llamada automática
    res2 = use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))
    assert res2.is_idempotent is True
    assert res2.email_status == "EMAIL_SENT"
    assert res2.idempotency_key == res1.idempotency_key
    assert res2.message_id == res1.message_id
    assert sender.send_count == 1  # Cero llamadas adicionales al emisor!


def test_send_deca_email_manual_resend_allowed(sample_expedition_with_deca):
    """Reenvío manual (force_resend=True) transmite nuevo correo y audita reenvío."""
    ctx = sample_expedition_with_deca
    use_case: SendDeCAEmailUseCase = ctx["use_case"]
    exp: Expedition = ctx["exp"]
    sender: FakeMicrosoftGraphEmailSender = ctx["email_sender"]

    # Envío inicial
    res1 = use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))
    assert res1.is_idempotent is False
    assert sender.send_count == 1

    # Reenvío manual explícito
    res2 = use_case.execute(
        SendDeCAEmailInputDTO(expedition_id=str(exp.id), force_resend=True, actor="SUPERVISOR")
    )
    assert res2.is_idempotent is False
    assert res2.email_status == "EMAIL_SENT"
    assert sender.send_count == 2
    assert res2.idempotency_key != res1.idempotency_key

    # Verificamos auditoría de reenvío
    actions = [e.action for e in ctx["audit_service"].events]
    assert AuditAction.EMAIL_RESEND_REQUESTED in actions


def test_send_deca_email_carrier_missing_returns_pending(sample_expedition_with_deca):
    """Si la expedición no tiene email de transportista, retorna EMAIL_PENDING sin lanzar 500."""
    ctx = sample_expedition_with_deca
    use_case: SendDeCAEmailUseCase = ctx["use_case"]
    exp: Expedition = ctx["exp"]

    exp.carrier_email = None
    ctx["exp_repo"].save(exp)

    res = use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))

    assert res.email_status == "EMAIL_PENDING"
    assert res.recipient == ""
    assert "no configurado" in res.message
    # No transiciona a ENVIADA
    assert ctx["exp_repo"].get_by_id(exp.id).status == ExpeditionStatus.DECA_GENERADO


def test_send_deca_email_invalid_email_format(sample_expedition_with_deca):
    """Si el email tiene formato inválido, marca EMAIL_FAILED y no transiciona a ENVIADA."""
    ctx = sample_expedition_with_deca
    use_case: SendDeCAEmailUseCase = ctx["use_case"]
    exp: Expedition = ctx["exp"]

    exp.carrier_email = "correo-invalido-sin-arroba"
    ctx["exp_repo"].save(exp)

    res = use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))

    assert res.email_status == "EMAIL_FAILED"
    assert "inválido" in res.message.lower()
    assert ctx["exp_repo"].get_by_id(exp.id).status == ExpeditionStatus.DECA_GENERADO


def test_send_deca_email_pdf_integrity_mismatch_aborts_immediately(sample_expedition_with_deca):
    """INVARIANTE CRÍTICO: Si el hash SHA-256 del PDF en storage difiere del snapshot inmutable,
    aborta con PDF_INTEGRITY_ERROR sin enviar nada y manteniendo el DeCA inalterado."""
    ctx = sample_expedition_with_deca
    use_case: SendDeCAEmailUseCase = ctx["use_case"]
    exp: Expedition = ctx["exp"]
    sender: FakeMicrosoftGraphEmailSender = ctx["email_sender"]
    storage: LocalPdfStorage = ctx["storage"]

    # Corrompemos intencionadamente el archivo físico en almacenamiento
    corrupted_bytes = b"%PDF-1.4 Corrupted content with tampered bytes"
    storage.save(corrupted_bytes, ctx["version"].pdf_storage_path)

    res = use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))

    assert res.email_status == "EMAIL_FAILED"
    assert "integridad" in res.message.lower()
    assert sender.send_count == 0  # CERO transmisión!

    # La expedición NO pasa a ENVIADA
    assert ctx["exp_repo"].get_by_id(exp.id).status == ExpeditionStatus.DECA_GENERADO

    # El DeCA y su versión siguen existiendo e inmutables
    deca = ctx["deca_repo"].find_by_expedition_id(exp.id)
    assert deca.current_version == 1
    assert deca.status == DeCAStatus.ISSUED

    # Evento de auditoría de fallo registrado
    actions = [e.action for e in ctx["audit_service"].events]
    assert AuditAction.EMAIL_SEND_FAILED in actions


def test_send_deca_email_failure_does_not_modify_deca_or_transition(sample_expedition_with_deca):
    """Si el envío falla por el proveedor, el DeCA no se altera y la expedición no es ENVIADA."""
    ctx = sample_expedition_with_deca
    use_case: SendDeCAEmailUseCase = ctx["use_case"]
    exp: Expedition = ctx["exp"]
    sender: FakeMicrosoftGraphEmailSender = ctx["email_sender"]

    # Forzar error permanente en el emisor
    sender.configure_failure(status_code=500, error_message="Graph API server internal error")

    res = use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))

    assert res.email_status in ("EMAIL_RETRY_PENDING", "EMAIL_FAILED")
    assert ctx["exp_repo"].get_by_id(exp.id).status == ExpeditionStatus.DECA_GENERADO

    # DeCA sigue perfectamente válido
    deca = ctx["deca_repo"].find_by_expedition_id(exp.id)
    assert deca.status == DeCAStatus.ISSUED


def test_send_deca_email_audit_masks_privacy_and_hides_secrets(sample_expedition_with_deca):
    """Las entradas de auditoría registran la dirección ofuscada y nunca credenciales ni tokens."""
    ctx = sample_expedition_with_deca
    use_case: SendDeCAEmailUseCase = ctx["use_case"]
    exp: Expedition = ctx["exp"]

    use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))

    for event in ctx["audit_service"].events:
        state_str = str(event.new_state or {})
        # Nunca debe aparecer el email completo sin enmascarar en la auditoría
        assert "logistica@hermanosruiz.es" not in state_str
        # Debe aparecer la versión enmascarada
        assert "lo***@hermanosruiz.es" in state_str
        # Nunca contraseñas o tokens
        assert "secret" not in state_str.lower()
        assert "token" not in state_str.lower() or "token_masked" in state_str


def test_send_deca_email_concurrency_race_condition_protection(sample_expedition_with_deca):
    """Dos hilos concurrentes solicitando envío para el mismo DeCA no provocan envíos duplicados."""
    ctx = sample_expedition_with_deca
    use_case: SendDeCAEmailUseCase = ctx["use_case"]
    exp: Expedition = ctx["exp"]
    sender: FakeMicrosoftGraphEmailSender = ctx["email_sender"]

    results = []

    def task():
        return use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(task)
        f2 = executor.submit(task)
        results = [f1.result(), f2.result()]

    statuses = [r.email_status for r in results]
    assert "EMAIL_SENT" in statuses

    # Uno es el original y el otro es detectado como idempotente
    idempotent_count = sum(1 for r in results if r.is_idempotent)
    assert idempotent_count >= 1
    assert sender.send_count == 1  # Solamente 1 llamada física efectuada al sender


def test_in_memory_email_delivery_repository_crud():
    """Prueba métodos CRUD y búsqueda por id y latest del repositorio en memoria."""
    repo = InMemoryEmailDeliveryRepository()
    exp_id = uuid.uuid4()
    deca_id = uuid.uuid4()
    deliv = EmailDelivery(
        expedition_id=exp_id,
        deca_id=deca_id,
        deca_code="DECA-2026-000001",
        deca_version=1,
        recipient_email="t@domain.com",
        subject="Test",
        idempotency_key="key-1",
    )
    repo.save(deliv)

    found = repo.find_by_id(deliv.id)
    assert found is not None
    assert found.id == deliv.id

    latest = repo.find_latest_by_expedition_id(exp_id)
    assert latest is not None
    assert latest.id == deliv.id

    assert repo.find_latest_by_expedition_id(uuid.uuid4()) is None

    repo.clear()
    assert repo.find_by_id(deliv.id) is None


def test_send_deca_email_storage_read_failure(sample_expedition_with_deca):
    """Comprueba el fallo seguro cuando el PDF no se encuentra en el almacenamiento."""
    ctx = sample_expedition_with_deca
    use_case: SendDeCAEmailUseCase = ctx["use_case"]
    exp: Expedition = ctx["exp"]

    # Apuntar la versión a una ruta inexistente
    ctx["version"].pdf_storage_path = "deca/non_existent_path.pdf"

    res = use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id)))
    assert res.email_status == "EMAIL_FAILED"
    assert "no disponible" in res.message.lower()


def test_send_deca_email_invalid_uuid(sample_expedition_with_deca):
    """Lanzar EntityNotFoundException ante un UUID malformado."""
    ctx = sample_expedition_with_deca
    use_case: SendDeCAEmailUseCase = ctx["use_case"]

    with pytest.raises(EntityNotFoundException):
        use_case.execute(SendDeCAEmailInputDTO(expedition_id="not-a-valid-uuid"))
