from __future__ import annotations

from datetime import UTC, date, datetime

from src.application.dtos.deca_dto import DeCAStructuredDTO
from src.infrastructure.document.stub_pdf_renderer import StubPdfRenderer
from src.infrastructure.email.stub_email_service import StubEmailService


def test_stub_pdf_renderer_generates_valid_pdf() -> None:
    renderer = StubPdfRenderer()
    dto = DeCAStructuredDTO(
        deca_code="DECA-2026-000001",
        version_number=1,
        public_url="http://localhost:8000/d/sample-token-12345678901234567890",
        qr_payload="http://localhost:8000/d/sample-token-12345678901234567890",
        issue_datetime=datetime.now(UTC),
        transport_date=date.today(),
        shipper_name="Tomates de Autor S.L.",
        shipper_tax_id="B12345678",
        shipper_address="Polígono Industrial La Redonda, Almería",
        carrier_name="Transportes Rápidos S.L.",
        carrier_tax_id="B87654321",
        vehicle_type="ARTICULADO",
        tractor_plate="1234ABC",
        trailer_plate="R1234BCD",
        origin="El Ejido (Almería)",
        destination="Mercamadrid (Madrid)",
        goods="Tomate Rama Extra",
        weight_kg=18500.0,
    )

    pdf_bytes = renderer.render(dto)
    assert len(pdf_bytes) > 0
    # Verificación de bytes mágicos de PDF (%PDF-)
    assert pdf_bytes.startswith(b"%PDF-")


def test_stub_email_service_idempotency() -> None:
    email_service = StubEmailService()
    idempotency_key = "unique-key-porte-45821"

    success1, msg1 = email_service.send_deca(
        recipient_email="trafico@transportes.com",
        subject="DeCA Oficial",
        body_text="Adjunto DeCA",
        attachment_bytes=b"%PDF-mock",
        attachment_filename="DECA-2026-000001.pdf",
        idempotency_key=idempotency_key,
    )
    assert success1 is True
    assert msg1 is not None
    assert len(email_service.sent_emails) == 1

    # Segundo intento con la misma clave de idempotencia
    success2, msg2 = email_service.send_deca(
        recipient_email="trafico@transportes.com",
        subject="DeCA Oficial",
        body_text="Adjunto DeCA",
        attachment_bytes=b"%PDF-mock",
        attachment_filename="DECA-2026-000001.pdf",
        idempotency_key=idempotency_key,
    )
    assert success2 is True
    assert "idempotent-replay" in str(msg2)
    assert len(email_service.sent_emails) == 1  # No se duplicó el envío
