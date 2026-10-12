from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from src.application.dtos.deca_dto import DeCAStructuredDTO
from src.application.ports.pdf_renderer import PdfRendererPort


class StubPdfRenderer(PdfRendererPort):
    """Implementación de prueba y desarrollo para generación de PDF nativo con ReportLab."""

    def render(self, deca_data: DeCAStructuredDTO) -> bytes:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        c.setTitle(f"DeCA — {deca_data.deca_code}")
        c.setAuthor(deca_data.shipper_name or "Tomates de Autor S.L.")

        c.drawString(100, 800, "DOCUMENTO ELECTRÓNICO DE CONTROL ADMINISTRATIVO (DeCA)")
        c.drawString(100, 780, f"Código DeCA: {deca_data.deca_code} (v{deca_data.version_number})")
        c.drawString(100, 760, f"Cargador: {deca_data.shipper_name} - {deca_data.shipper_tax_id}")
        c.drawString(
            100, 740, f"Transportista: {deca_data.carrier_name} - {deca_data.carrier_tax_id}"
        )
        c.drawString(100, 720, f"Tipo Vehículo: {deca_data.vehicle_type}")
        c.drawString(100, 700, f"Matrícula: {deca_data.tractor_plate}")
        if deca_data.trailer_plate:
            c.drawString(250, 700, f"Remolque: {deca_data.trailer_plate}")
        c.drawString(100, 680, f"Origen: {deca_data.origin} -> Destino: {deca_data.destination}")
        c.drawString(100, 660, f"Mercancía: {deca_data.goods} ({deca_data.weight_kg:.2f} kg)")
        c.drawString(100, 640, f"URL de Inspección: {deca_data.public_url}")

        c.showPage()
        c.save()

        buffer.seek(0)
        return buffer.getvalue()
