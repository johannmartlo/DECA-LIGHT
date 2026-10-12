from __future__ import annotations

import io

import segno
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from src.application.dtos.deca_dto import DeCAStructuredDTO
from src.application.ports.pdf_renderer import PdfRendererPort


class ReportLabPdfRenderer(PdfRendererPort):
    """Renderizador profesional y determinista de documentos DeCA en PDF nativo (A4).

    Cumple con la Orden FOM/2861/2012 y la Resolución BOE-A-2026-12784.
    Diseño sobrio, tipografía vectorial nítida y seleccionable, tamaño optimizado (< 100 KB).
    """

    # Paleta de colores sobria inspirada en interfaces fintech/SaaS de alto rendimiento
    COLOR_PRIMARY = HexColor("#0F172A")  # Slate 900 (Texto principal y títulos)
    COLOR_SECONDARY = HexColor("#334155")  # Slate 700 (Subtítulos y valores)
    COLOR_MUTED = HexColor("#64748B")  # Slate 500 (Etiquetas secundarias)
    COLOR_BORDER = HexColor("#CBD5E1")  # Slate 300 (Bordes de contenedor)
    COLOR_BG_BOX = HexColor("#F8FAFC")  # Slate 50 (Fondo de secciones)
    COLOR_BG_HEADER = HexColor("#F1F5F9")  # Slate 100 (Cabeceras de tablas)
    COLOR_ACCENT = HexColor("#1E3A8A")  # Blue 900 (Acento institucional)
    COLOR_BADGE = HexColor("#991B1B")  # Dark Red (Acento sutil cargador)

    def render(self, deca_data: DeCAStructuredDTO) -> bytes:
        """Renderiza el DeCAEstructurado a binario PDF nativo."""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)

        page_w, page_h = A4  # 595.28 x 841.89 puntos
        margin_x = 36.0  # Margen horizontal (0.5 in)
        content_w = page_w - (2 * margin_x)  # 523.28 pt

        # Metadatos del documento PDF
        c.setTitle(f"DeCA — {deca_data.deca_code}")
        c.setAuthor(deca_data.shipper_name or "Tomates de Autor S.L.")
        c.setSubject("Documento Electrónico de Control Administrativo (DeCA)")
        c.setCreator("DECA Light v1.0 — Compliance FOM/2861/2012")

        # -------------------------------------------------------------
        # 1. CABECERA PRINCIPAL (y = 805 a 735)
        # -------------------------------------------------------------
        top_y = 805.0

        # Bloque izquierdo: Identidad institucional
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(self.COLOR_PRIMARY)
        company_header = (deca_data.shipper_name or "TOMATES DE AUTOR S.L.").upper()
        c.drawString(margin_x, top_y, company_header)

        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(self.COLOR_SECONDARY)
        c.drawString(
            margin_x,
            top_y - 14,
            "DOCUMENTO ELECTRÓNICO DE CONTROL ADMINISTRATIVO (DeCA)",
        )

        c.setFont("Helvetica", 7.5)
        c.setFillColor(self.COLOR_MUTED)
        c.drawString(
            margin_x,
            top_y - 25,
            "Conforme a la Orden FOM/2861/2012 y la Ley 15/2009 del contrato de transporte",
        )

        # Bloque derecho: Tarjeta de identificación del DeCA
        badge_w = 200.0
        badge_h = 62.0
        badge_x = page_w - margin_x - badge_w
        badge_y = top_y - badge_h + 8.0

        c.setFillColor(self.COLOR_BG_BOX)
        c.setStrokeColor(self.COLOR_BORDER)
        c.setLineWidth(0.8)
        c.roundRect(badge_x, badge_y, badge_w, badge_h, 4, fill=1, stroke=1)

        # Franja superior de la tarjeta
        c.setFillColor(self.COLOR_BG_HEADER)
        c.roundRect(badge_x, badge_y + badge_h - 18, badge_w, 18, 4, fill=1, stroke=0)
        c.rect(badge_x, badge_y + badge_h - 18, badge_w, 5, fill=1, stroke=0)
        c.setStrokeColor(self.COLOR_BORDER)
        c.line(badge_x, badge_y + badge_h - 18, badge_x + badge_w, badge_y + badge_h - 18)

        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(self.COLOR_PRIMARY)
        c.drawString(badge_x + 8, badge_y + badge_h - 13, "CONTROL DE EMISIÓN DE TRANSPORTE")

        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(badge_x + 8, badge_y + 30, f"Nº {deca_data.deca_code}")

        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(self.COLOR_ACCENT)
        version_label = f"VERSIÓN {deca_data.version_number}"
        c.drawRightString(badge_x + badge_w - 8, badge_y + 30, version_label)

        c.setFont("Helvetica", 7.5)
        c.setFillColor(self.COLOR_MUTED)
        c.drawString(badge_x + 8, badge_y + 16, "Fecha/hora emisión:")
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(self.COLOR_PRIMARY)
        issue_str = deca_data.issue_datetime.strftime("%Y-%m-%d %H:%M:%S UTC")
        c.drawString(badge_x + 95, badge_y + 16, issue_str)

        if deca_data.internal_id:
            c.setFont("Helvetica", 7.5)
            c.setFillColor(self.COLOR_MUTED)
            c.drawString(badge_x + 8, badge_y + 5, "Ref. Expedición:")
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColor(self.COLOR_PRIMARY)
            c.drawString(badge_x + 95, badge_y + 5, deca_data.internal_id)

        # Línea divisoria horizontal decorativa
        sep_y = 728.0
        c.setStrokeColor(self.COLOR_BORDER)
        c.setLineWidth(0.6)
        c.line(margin_x, sep_y, page_w - margin_x, sep_y)

        # -------------------------------------------------------------
        # 2. INTERVINIENTES (y = 716 a 626, altura 90 pt)
        # -------------------------------------------------------------
        box_y = 626.0
        box_h = 92.0
        col_w = (content_w - 12.0) / 2.0

        # Bloque izquierdo: CARGADOR CONTRACTUAL
        self._draw_section_box(
            c,
            x=margin_x,
            y=box_y,
            w=col_w,
            h=box_h,
            title="1. CARGADOR CONTRACTUAL",
            rows=[
                ("Razón Social:", deca_data.shipper_name or "-"),
                ("NIF / CIF:", deca_data.shipper_tax_id or "-"),
                ("Domicilio:", deca_data.shipper_address or "-"),
            ],
        )

        # Bloque derecho: TRANSPORTISTA EFECTIVO
        self._draw_section_box(
            c,
            x=margin_x + col_w + 12.0,
            y=box_y,
            w=col_w,
            h=box_h,
            title="2. TRANSPORTISTA EFECTIVO",
            rows=[
                ("Razón Social:", deca_data.carrier_name or "-"),
                ("NIF / CIF:", deca_data.carrier_tax_id or "-"),
                ("Ref. Origen:", deca_data.external_reference or "-"),
            ],
        )

        # -------------------------------------------------------------
        # 3. VEHÍCULO Y MATRÍCULAS (y = 614 a 546, altura 68 pt)
        # -------------------------------------------------------------
        v_box_y = 546.0
        v_box_h = 68.0

        is_rigid = "RIGID" in str(deca_data.vehicle_type).upper()
        trailer_display = (
            "No aplica (Vehículo rígido)" if is_rigid else (deca_data.trailer_plate or "-")
        )

        self._draw_multi_column_box(
            c,
            x=margin_x,
            y=v_box_y,
            w=content_w,
            h=v_box_h,
            title="3. VEHÍCULO Y CONFIGURACIÓN DE TRANSPORTE",
            columns=[
                ("Tipo de Transporte", str(deca_data.vehicle_type)),
                ("Matrícula Tractora / Vehículo", deca_data.tractor_plate),
                ("Matrícula Semirremolque", trailer_display),
            ],
        )

        # -------------------------------------------------------------
        # 4. RUTA Y TRANSPORTE (y = 534 a 466, altura 68 pt)
        # -------------------------------------------------------------
        t_box_y = 466.0
        t_box_h = 68.0

        self._draw_multi_column_box(
            c,
            x=margin_x,
            y=t_box_y,
            w=content_w,
            h=t_box_h,
            title="4. SERVICIO DE TRANSPORTE Y RUTA",
            columns=[
                ("Fecha de Transporte", str(deca_data.transport_date)),
                ("Origen / Carga", deca_data.origin or "-"),
                ("Destino / Descarga", deca_data.destination or "-"),
            ],
        )

        # -------------------------------------------------------------
        # 5. MERCANCÍA Y PESO (y = 454 a 386, altura 68 pt)
        # -------------------------------------------------------------
        m_box_y = 386.0
        m_box_h = 68.0

        weight_formatted = f"{deca_data.weight_kg:,.2f} kg"
        weight_display = weight_formatted.replace(",", "@").replace(".", ",").replace("@", ".")

        self._draw_multi_column_box(
            c,
            x=margin_x,
            y=m_box_y,
            w=content_w,
            h=m_box_h,
            title="5. NATURALEZA DE LA MERCANCÍA Y PESO",
            columns=[
                ("Descripción de la Mercancía", deca_data.goods or "-"),
                ("Peso Registrado", weight_display),
                ("Albarán / Doc. Base", deca_data.external_reference or "-"),
            ],
        )

        # -------------------------------------------------------------
        # 6. OBSERVACIONES Y ESPACIO RESERVADO QR (y = 374 a 264, altura 110 pt)
        # -------------------------------------------------------------
        obs_box_y = 264.0
        obs_box_h = 110.0
        qr_box_w = 110.0
        obs_w = content_w - qr_box_w - 12.0

        # Bloque de Observaciones
        self._draw_observations_box(
            c,
            x=margin_x,
            y=obs_box_y,
            w=obs_w,
            h=obs_box_h,
            title="6. INSTRUCCIONES Y OBSERVACIONES DE TRANSPORTE",
            text=deca_data.observations or "Sin observaciones particulares registradas.",
        )

        # Bloque de Código QR de Inspección en Ruta (Fase 6)
        self._draw_qr_block(
            c,
            x=margin_x + obs_w + 12.0,
            y=obs_box_y,
            w=qr_box_w,
            h=obs_box_h,
            deca_data=deca_data,
        )

        # -------------------------------------------------------------
        # 7. DECLARACIÓN NORMATIVA Y VALIDEZ LEGAL (y = 252 a 162, altura 90 pt)
        # -------------------------------------------------------------
        decl_box_y = 162.0
        decl_box_h = 90.0

        self._draw_legal_declaration(
            c,
            x=margin_x,
            y=decl_box_y,
            w=content_w,
            h=decl_box_h,
            deca_data=deca_data,
        )

        # -------------------------------------------------------------
        # 8. PIE DE PÁGINA DOCUMENTAL (y = 80 a 30)
        # -------------------------------------------------------------
        c.setStrokeColor(self.COLOR_BORDER)
        c.setLineWidth(0.6)
        c.line(margin_x, 82.0, page_w - margin_x, 82.0)

        c.setFont("Helvetica", 7.0)
        c.setFillColor(self.COLOR_MUTED)
        brand_name = deca_data.shipper_name or "Tomates de Autor S.L."
        footer_brand = f"DECA Light · {brand_name} · Control de Transporte"
        c.drawString(margin_x, 70.0, footer_brand)
        c.drawRightString(page_w - margin_x, 70.0, "Página 1 de 1")

        hash_display = deca_data.snapshot_hash or "SHA256-PENDIENTE"
        c.drawString(
            margin_x,
            58.0,
            f"Huella criptográfica de integridad (SHA-256): {hash_display}",
        )
        c.drawString(
            margin_x,
            46.0,
            "Custodia interna inmutable garantizada durante un periodo mínimo de 1 año natural.",
        )

        c.showPage()
        c.save()

        buffer.seek(0)
        return buffer.getvalue()

    def _draw_section_box(
        self,
        c: canvas.Canvas,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        rows: list[tuple[str, str]],
    ) -> None:
        """Dibuja un contenedor con cabecera y filas clave-valor."""
        c.setFillColor(self.COLOR_BG_BOX)
        c.setStrokeColor(self.COLOR_BORDER)
        c.setLineWidth(0.6)
        c.roundRect(x, y, w, h, 3, fill=1, stroke=1)

        # Franja de cabecera
        c.setFillColor(self.COLOR_BG_HEADER)
        c.roundRect(x, y + h - 18, w, 18, 3, fill=1, stroke=0)
        c.rect(x, y + h - 18, w, 4, fill=1, stroke=0)
        c.setStrokeColor(self.COLOR_BORDER)
        c.line(x, y + h - 18, x + w, y + h - 18)

        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(self.COLOR_SECONDARY)
        c.drawString(x + 8, y + h - 13, title)

        # Contenido
        curr_y = y + h - 34
        for label, val in rows:
            c.setFont("Helvetica", 8)
            c.setFillColor(self.COLOR_MUTED)
            c.drawString(x + 8, curr_y, label)

            c.setFont("Helvetica-Bold", 8.5)
            c.setFillColor(self.COLOR_PRIMARY)
            # Acortar o truncar si excede el ancho para evitar solapamientos
            display_val = val if len(val) <= 36 else val[:33] + "..."
            c.drawString(x + 72, curr_y, display_val)
            curr_y -= 19

    def _draw_multi_column_box(
        self,
        c: canvas.Canvas,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        columns: list[tuple[str, str]],
    ) -> None:
        """Dibuja una sección con columnas paralelas de datos clave."""
        c.setFillColor(self.COLOR_BG_BOX)
        c.setStrokeColor(self.COLOR_BORDER)
        c.setLineWidth(0.6)
        c.roundRect(x, y, w, h, 3, fill=1, stroke=1)

        # Franja cabecera
        c.setFillColor(self.COLOR_BG_HEADER)
        c.roundRect(x, y + h - 18, w, 18, 3, fill=1, stroke=0)
        c.rect(x, y + h - 18, w, 4, fill=1, stroke=0)
        c.setStrokeColor(self.COLOR_BORDER)
        c.line(x, y + h - 18, x + w, y + h - 18)

        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(self.COLOR_SECONDARY)
        c.drawString(x + 8, y + h - 13, title)

        # Columnas
        col_w = w / float(len(columns))
        max_col_w = col_w - 14.0
        for i, (col_label, col_val) in enumerate(columns):
            col_x = x + (i * col_w) + 8

            c.setFont("Helvetica", 7.5)
            c.setFillColor(self.COLOR_MUTED)
            c.drawString(col_x, y + 34, col_label)

            c.setFillColor(self.COLOR_PRIMARY)
            if c.stringWidth(col_val, "Helvetica-Bold", 9.0) <= max_col_w:
                c.setFont("Helvetica-Bold", 9.0)
                c.drawString(col_x, y + 16, col_val)
            else:
                words = col_val.split()
                line1 = ""
                line2 = ""
                is_line2 = False
                for word in words:
                    if not is_line2:
                        test_l1 = f"{line1} {word}".strip()
                        if c.stringWidth(test_l1, "Helvetica-Bold", 8.0) <= max_col_w:
                            line1 = test_l1
                        else:
                            is_line2 = True
                            line2 = word
                    else:
                        test_l2 = f"{line2} {word}".strip()
                        if c.stringWidth(test_l2, "Helvetica-Bold", 8.0) <= max_col_w:
                            line2 = test_l2
                        else:
                            line2 = test_l2[:22] + "..."
                            break
                c.setFont("Helvetica-Bold", 8.0)
                c.drawString(col_x, y + 21, line1)
                if line2:
                    c.drawString(col_x, y + 10, line2)

    def _draw_observations_box(
        self,
        c: canvas.Canvas,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        text: str,
    ) -> None:
        """Dibuja el bloque de texto multilínea para observaciones."""
        c.setFillColor(self.COLOR_BG_BOX)
        c.setStrokeColor(self.COLOR_BORDER)
        c.setLineWidth(0.6)
        c.roundRect(x, y, w, h, 3, fill=1, stroke=1)

        c.setFillColor(self.COLOR_BG_HEADER)
        c.roundRect(x, y + h - 18, w, 18, 3, fill=1, stroke=0)
        c.rect(x, y + h - 18, w, 4, fill=1, stroke=0)
        c.setStrokeColor(self.COLOR_BORDER)
        c.line(x, y + h - 18, x + w, y + h - 18)

        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(self.COLOR_SECONDARY)
        c.drawString(x + 8, y + h - 13, title)

        # Párrafo simple de observaciones sin desbordamiento
        c.setFont("Helvetica", 8)
        c.setFillColor(self.COLOR_PRIMARY)
        words = text.split()
        line = ""
        line_y = y + h - 34
        for word in words:
            test_line = f"{line} {word}".strip()
            if c.stringWidth(test_line, "Helvetica", 8) < (w - 16):
                line = test_line
            else:
                c.drawString(x + 8, line_y, line)
                line_y -= 13
                line = word
                if line_y < (y + 8):
                    break
        if line and line_y >= (y + 8):
            c.drawString(x + 8, line_y, line)

    def _draw_qr_block(
        self,
        c: canvas.Canvas,
        x: float,
        y: float,
        w: float,
        h: float,
        deca_data: DeCAStructuredDTO,
    ) -> None:
        """Dibuja el bloque de inspección oficial en ruta y el código QR vectorial nativo.

        Si se dispone de payload para el QR (public_url o qr_payload), se genera
        e inserta mediante Segno de forma 100% vectorial sobre el canvas de ReportLab.
        Si no se dispone de payload, se dibuja el marco reservado de cortesía.
        """
        qr_content = (deca_data.qr_payload or deca_data.public_url or "").strip()
        if not qr_content:
            self._draw_qr_placeholder(c, x, y, w, h)
            return

        # Marco contenedor
        c.setFillColor(self.COLOR_BG_BOX)
        c.setStrokeColor(self.COLOR_BORDER)
        c.setLineWidth(0.6)
        c.roundRect(x, y, w, h, 3, fill=1, stroke=1)

        # Franja superior de cabecera
        header_h = 16.0
        c.setFillColor(self.COLOR_BG_HEADER)
        c.roundRect(x, y + h - header_h, w, header_h, 3, fill=1, stroke=0)
        c.rect(x, y + h - header_h, w, 4, fill=1, stroke=0)
        c.setStrokeColor(self.COLOR_BORDER)
        c.line(x, y + h - header_h, x + w, y + h - header_h)

        c.setFont("Helvetica-Bold", 7.0)
        c.setFillColor(self.COLOR_SECONDARY)
        c.drawCentredString(x + (w / 2.0), y + h - 11.5, "INSPECCIÓN / QR")

        # Generación vectorial con Segno
        qr = segno.make(qr_content, error="m")
        # matrix_iter con quiet zone de 2 módulos (la caja externa da margen complementario)
        matrix = list(qr.matrix_iter(border=2))
        num_rows = len(matrix)

        # Dimensiones de renderizado del QR: 70 x 70 pt centrado en el espacio disponible
        qr_display_size = 72.0
        module_size = qr_display_size / num_rows

        qr_offset_x = x + (w - qr_display_size) / 2.0
        qr_offset_y = y + 17.0

        c.setFillColor(self.COLOR_PRIMARY)
        for r_idx, row in enumerate(matrix):
            # En ReportLab y=0 está abajo; la fila 0 debe dibujarse en la parte superior
            y_pos = qr_offset_y + (num_rows - 1 - r_idx) * module_size
            for c_idx, val in enumerate(row):
                if val:
                    x_pos = qr_offset_x + c_idx * module_size
                    c.rect(x_pos, y_pos, module_size, module_size, fill=1, stroke=0)

        # Pie de bloque
        c.setFont("Helvetica-Bold", 6.5)
        c.setFillColor(self.COLOR_MUTED)
        c.drawCentredString(x + (w / 2.0), y + 7.0, "Escaneo oficial en ruta")

    def _draw_qr_placeholder(
        self,
        c: canvas.Canvas,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> None:
        """Dibuja el espacio sutil reservado para el código QR de inspección."""
        c.setFillColor(self.COLOR_BG_BOX)
        c.setStrokeColor(self.COLOR_BORDER)
        c.setLineWidth(0.6)
        c.setDash(3, 2)
        c.roundRect(x, y, w, h, 3, fill=1, stroke=1)
        c.setDash()  # Restaurar línea continua

        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(self.COLOR_MUTED)
        c.drawCentredString(x + (w / 2.0), y + 62, "ESPACIO RESERVADO")
        c.setFont("Helvetica", 7.0)
        c.drawCentredString(x + (w / 2.0), y + 50, "CÓDIGO QR")
        c.drawCentredString(x + (w / 2.0), y + 38, "Inspección en carretera")
        c.setFont("Helvetica-Oblique", 6.5)
        c.drawCentredString(x + (w / 2.0), y + 26, "(Sin URL pública)")

    def _draw_legal_declaration(
        self,
        c: canvas.Canvas,
        x: float,
        y: float,
        w: float,
        h: float,
        deca_data: DeCAStructuredDTO,
    ) -> None:
        """Dibuja la declaración formal de control administrativo y firma documental."""
        c.setFillColor(HexColor("#FAFAFA"))
        c.setStrokeColor(self.COLOR_BORDER)
        c.setLineWidth(0.6)
        c.roundRect(x, y, w, h, 3, fill=1, stroke=1)

        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(self.COLOR_PRIMARY)
        c.drawString(x + 8, y + h - 14, "DECLARACIÓN FORMAL Y CONTROL ADMINISTRATIVO")

        c.setFont("Helvetica", 7.2)
        c.setFillColor(self.COLOR_SECONDARY)
        legal_text = (
            "El presente Documento Electrónico de Control Administrativo (DeCA) acredita el "
            "cumplimiento de las obligaciones documentales exigidas por la Orden FOM/2861/2012 "
            "y la Ley 15/2009, de 11 de noviembre, del contrato de transporte terrestre de "
            "mercancías. La información contenida en este documento ha sido validada y "
            "registrada de forma fehaciente con carácter previo al inicio del transporte."
        )

        words = legal_text.split()
        line = ""
        line_y = y + h - 28
        for word in words:
            test_line = f"{line} {word}".strip()
            if c.stringWidth(test_line, "Helvetica", 7.2) < (w - 16):
                line = test_line
            else:
                c.drawString(x + 8, line_y, line)
                line_y -= 11
                line = word
        if line:
            c.drawString(x + 8, line_y, line)

        # Indicador de estado y emisión
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(self.COLOR_ACCENT)
        status_banner = (
            f"ESTADO: EMITIDO · VERSIÓN {deca_data.version_number} · AUDITADO Y CUSTODIADO"
        )
        c.drawString(x + 8, y + 10, status_banner)
