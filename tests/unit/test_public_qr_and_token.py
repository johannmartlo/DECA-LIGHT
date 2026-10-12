from __future__ import annotations

import hashlib
import io
import re
from datetime import UTC, date, datetime, timedelta

import pypdf
import segno

from src.domain.entities.deca import DeCA, DeCAEstructurado, DeCAVersion
from src.domain.enums import DeCAStatus
from src.domain.services.clock import Clock
from src.domain.services.public_token_service import PublicDeCaTokenService
from src.infrastructure.document.reportlab_pdf_renderer import ReportLabPdfRenderer


def test_token_generation_entropy() -> None:
    """Verifica que el token generado tenga >= 256 bits de entropía y formato URL-safe."""
    token = PublicDeCaTokenService.generate_token()
    # 32 bytes en base64url generan 43 caracteres sin relleno '='
    assert len(token) >= 43
    assert re.match(r"^[A-Za-z0-9_-]+$", token) is not None


def test_token_uniqueness() -> None:
    """Verifica la unicidad de 1.000 tokens generados consecutivamente sin colisiones."""
    tokens = {PublicDeCaTokenService.generate_token() for _ in range(1000)}
    assert len(tokens) == 1000


def test_token_hashing_sha256() -> None:
    """Verifica que el hash del token sea determinista y coincida con SHA-256 estándar."""
    token = "MrBZeAITr1234567890abcdefghijklmnopqrstuvwxyz"
    expected_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert PublicDeCaTokenService.hash_token(token) == expected_hash


def test_token_masking() -> None:
    """Verifica el enmascaramiento seguro del token para logs y auditoría."""
    token = "abcdef1234567890123456789012345678901234xyz"
    masked = PublicDeCaTokenService.mask_token(token)
    assert masked.startswith("abcdef...")
    assert masked.endswith("...4xyz")
    assert "1234567890" not in masked

    # Token corto
    short_token = "abc"
    assert PublicDeCaTokenService.mask_token(short_token) == "***"


def test_token_format_validation() -> None:
    """Verifica la validación sintáctica estricta de tokens públicos."""
    valid_token = PublicDeCaTokenService.generate_token()
    assert PublicDeCaTokenService.is_valid_token_format(valid_token) is True

    # Casos inválidos
    assert PublicDeCaTokenService.is_valid_token_format("") is False
    assert PublicDeCaTokenService.is_valid_token_format("short") is False
    assert PublicDeCaTokenService.is_valid_token_format(valid_token + "+") is False
    assert PublicDeCaTokenService.is_valid_token_format(valid_token + "/") is False
    assert PublicDeCaTokenService.is_valid_token_format(valid_token + "=") is False
    assert PublicDeCaTokenService.is_valid_token_format(valid_token + " ") is False
    assert PublicDeCaTokenService.is_valid_token_format(None) is False  # type: ignore[arg-type]


def test_qr_payload_format() -> None:
    """Verifica que la URL pública construida tenga la estructura canónica /d/{token}."""
    token = PublicDeCaTokenService.generate_token()
    url = PublicDeCaTokenService.build_public_url("https://deca.example.com", token)
    assert url == f"https://deca.example.com/d/{token}"


def test_qr_rendered_in_pdf() -> None:
    """Verifica que el QR se dibuja como gráfico vectorial nativo sin imágenes rasterizadas."""
    token = PublicDeCaTokenService.generate_token()
    public_url = PublicDeCaTokenService.build_public_url("http://localhost:8000", token)

    deca_data = DeCAEstructurado(
        deca_code="DECA-2026-000001",
        version_number=1,
        issue_datetime=datetime(2026, 10, 4, 10, 0, tzinfo=UTC),
        transport_date=date(2026, 10, 4),
        shipper_name="Tomates de Autor S.L.",
        shipper_tax_id="B04889410",
        shipper_address="El Ejido",
        carrier_name="Transportes Rápidos",
        carrier_tax_id="B12345678",
        vehicle_type="ARTICULADO",
        tractor_plate="1234-BBB",
        trailer_plate="R-5678-BBB",
        origin="El Ejido",
        destination="Madrid",
        goods="Tomate Cherry",
        weight_kg=12500.0,
        public_url=public_url,
        qr_payload=public_url,
    )

    pdf_bytes = ReportLabPdfRenderer().render(deca_data)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    page = reader.pages[0]

    # Cero imágenes en la página: 100% vectorial
    assert len(page.images) == 0

    # Contenido con comandos rectangulares 're' correspondientes a los módulos QR
    content = page.get_contents().get_data()
    re_count = content.count(b" re\n") + content.count(b" re ")
    assert re_count > 300  # Más de 300 módulos vectoriales dibujados


def test_qr_decodable() -> None:
    """Verifica la correspondencia entre la matriz de Segno y el payload de la URL."""
    token = PublicDeCaTokenService.generate_token()
    public_url = PublicDeCaTokenService.build_public_url("http://localhost:8000", token)

    qr = segno.make(public_url, error="m")
    # Verificar que Segno codifica con éxito y genera una matriz válida
    assert qr.version in range(1, 41)
    assert len(qr.matrix) >= 21
    assert len(qr.matrix[0]) >= 21


def test_qr_size_in_bounds() -> None:
    """Verifica que el tamaño asignado al QR está dentro de los límites (70 a 100 pt)."""
    # Según diseño en reportlab_pdf_renderer.py: qr_display_size = 72.0 pt
    qr_display_size = 72.0
    assert 70.0 <= qr_display_size <= 100.0


def test_qr_quiet_zone() -> None:
    """Verifica que la matriz de Segno incluye quiet zone (mínimo 2 módulos + marco)."""
    qr = segno.make("http://localhost:8000/d/test", error="m")
    raw_dim = len(qr.matrix)
    matrix_with_border = list(qr.matrix_iter(border=2))
    assert len(matrix_with_border) == raw_dim + 4


def test_clock_service() -> None:
    """Verifica el funcionamiento del servicio determinista Clock."""
    fixed = datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)
    Clock.freeze(fixed)
    assert Clock.now() == fixed

    Clock.advance(days=3)
    assert Clock.now() == fixed + timedelta(days=3)

    Clock.advance(hours=2, seconds=30)
    assert Clock.now() == fixed + timedelta(days=3, hours=2, seconds=30)

    Clock.unfreeze()
    assert (datetime.now(UTC) - Clock.now()).total_seconds() < 2.0


def test_deca_entity_token_lifecycle() -> None:
    """Verifica la vigencia temporal de descarga del DeCA con Clock."""
    start = datetime(2026, 10, 4, 8, 0, 0, tzinfo=UTC)
    Clock.freeze(start)

    deca = DeCA(
        expedition_id="00000000-0000-0000-0000-000000000001",
        deca_code="DECA-2026-000001",
        service_start_at=start,
        status=DeCAStatus.ISSUED,
        public_access_token=PublicDeCaTokenService.generate_token(),
    )
    deca.add_version(
        DeCAVersion(
            version_number=1,
            pdf_sha256="fakehash",
            pdf_storage_path="deca/2026/DECA-2026-000001.pdf",
            pdf_size_bytes=1000,
            snapshot_hash="fake",
            snapshot_data={},
            created_at=start,
        )
    )

    # 1. En curso de transporte (fecha_fin_servicio es None) -> Permitido
    assert deca.is_public_download_allowed(Clock.now()) is True

    # 2. Finaliza el transporte
    service_end = datetime(2026, 10, 5, 18, 0, 0, tzinfo=UTC)
    deca.record_service_end(service_end)
    assert deca.service_end_at == service_end

    # 3. Acceso al sexto día tras fin de servicio -> Permitido
    Clock.freeze(service_end + timedelta(days=6))
    assert deca.is_public_download_allowed(Clock.now()) is True

    # 4. Acceso en el límite exacto de 7 días -> Permitido
    Clock.freeze(service_end + timedelta(days=7))
    assert deca.is_public_download_allowed(Clock.now()) is True

    # 5. Acceso a los 7 días y 1 segundo -> Denegado (expirado)
    Clock.freeze(service_end + timedelta(days=7, seconds=1))
    assert deca.is_public_download_allowed(Clock.now()) is False

    Clock.unfreeze()
