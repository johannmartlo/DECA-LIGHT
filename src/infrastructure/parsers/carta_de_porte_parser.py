from __future__ import annotations

from datetime import date

from src.application.dtos.document_dto import NormalizedDocumentDTO, RawDocumentDTO
from src.application.ports.document_parser import DocumentParserPort
from src.domain.enums import DocumentFormatType
from src.domain.value_objects import ExtractedField
from src.infrastructure.parsers.base_parser import BaseDocumentParser


class CartaDePorteParser(BaseDocumentParser, DocumentParserPort):
    """Parser especializado en Cartas de Porte y Albaranes nacionales generados por Hispatec."""

    @property
    def format_type(self) -> DocumentFormatType:
        return DocumentFormatType.CARTA_DE_PORTE

    def can_parse(self, raw_doc: RawDocumentDTO) -> tuple[bool, float]:
        text = raw_doc.extracted_text.upper()
        if not text:
            return False, 0.0

        score = 0.0
        # Marcadores fuertes de Carta de Porte / Albarán nacional
        if "CARTA DE PORTE" in text:
            score += 0.5
        if "ALBARAN" in text or "ALBARÁN" in text:
            score += 0.3
        if "CARGADOR" in text or "EXPEDIDOR" in text:
            score += 0.2
        if "PORTEADOR" in text or "TRANSPORTISTA" in text:
            score += 0.2
        if "HISPATEC" in text:
            score += 0.3

        confidence = min(score, 1.0)
        return (confidence >= 0.5), confidence

    def parse(self, raw_doc: RawDocumentDTO) -> NormalizedDocumentDTO:
        text = self.clean_text(raw_doc.extracted_text)
        _, confidence = self.can_parse(raw_doc)

        # 1. Document Number y External Reference (Albarán)
        # La Carta de Porte actual NO contiene de forma fiable el número de albarán.
        # Si no está presente, external_reference debe ser NO_PRESENTE con valor None.
        doc_patterns = [
            r"(?:carta\s+de\s+porte|documento)\s*(?:n[º°.]|num|nro|n[uú]mero)\s*[:#-]?\s*([A-Za-z0-9_./-]+)",
        ]
        document_number = self.extract_regex_string(text, doc_patterns)

        ext_ref_patterns = [
            r"(?:albar[aá]n\s*(?:n[º°.]|num|nro|n[uú]mero)|ref[.:]?\s*albar[aá]n|n[º°.]?\s*(?:de\s+)?albar[aá]n|albar[aá]n\s+origen)\s*[:#-]?\s*([A-Za-z0-9_./-]+)",
            r"albar[aá]n\s*[:#-]\s*([A-Za-z0-9_./-]+)",
        ]
        external_reference = self.extract_regex_string(text, ext_ref_patterns)
        reference = external_reference if external_reference.is_valid else document_number

        # 2. Fecha de transporte
        date_patterns = [
            r"(?:fecha(?:\s+transporte|\s+carga|\s+albar[aá]n)?|date)\s*[:\-]?\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
            r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{4})",
        ]
        trans_date = self.extract_date(text, date_patterns)
        if not trans_date.is_valid:
            trans_date = ExtractedField.requires_review(
                value=date.today(), raw_text="No encontrada en documento", confidence=0.0
            )

        fiscal_year = ExtractedField.extracted(
            str(trans_date.value.year if trans_date.value else date.today().year)
        )

        # 3. Cargador contractual
        shipper_name_patterns = [
            r"(?:cargador(?:\s+contractual)?|expedidor|remitente)\s*[:\-]\s*([^\n\r]+)",
            r"(?:empresa\s+cargadora)\s*[:\-]\s*([^\n\r]+)",
        ]
        shipper_name = self.extract_regex_string(text, shipper_name_patterns)
        if not shipper_name.is_valid:
            if "CULTIVOS ARABA" in text.upper():
                shipper_name = ExtractedField.extracted("Cultivos Araba S.L.", raw_text="Cabecera")
            elif "TOMATES DE AUTOR" in text.upper():
                shipper_name = ExtractedField.extracted(
                    "Tomates de Autor S.L.", raw_text="Cabecera"
                )

        shipper_tax_patterns = [
            r"(?:cargador[^\n]*?)(?:NIF|CIF)\s*[:\-]?\s*([A-Z0-9]{8,10})",
            r"(?:CIF|NIF)\s*(?:cargador|expedidor)?\s*[:\-]?\s*([A-Z0-9]{8,10})",
        ]
        shipper_tax = self.extract_regex_string(text, shipper_tax_patterns)

        shipper_addr_patterns = [
            r"(?:domicilio\s+cargador|direcci[oó]n\s+cargador)\s*[:\-]\s*([^\n\r]+)",
            r"(?:origen\s+fiscal)\s*[:\-]\s*([^\n\r]+)",
        ]
        shipper_addr = self.extract_regex_string(text, shipper_addr_patterns)

        # 4. Transportista efectivo
        carrier_name_patterns = [
            r"(?:transportista(?:\s+efectivo)?|porteador|empresa\s+de\s+transportes)\s*[:\-]\s*([^\n\r]+)",
            r"(?:conductor\s*\/)?\s*transportista\s*[:\-]\s*([^\n\r]+)",
        ]
        carrier_name = self.extract_regex_string(text, carrier_name_patterns)

        carrier_tax_patterns = [
            r"(?:transportista[^\n]*?)(?:NIF|CIF)\s*[:\-]?\s*([A-Z0-9]{8,10})",
            r"(?:CIF|NIF)\s*(?:transportista|porteador)\s*[:\-]?\s*([A-Z0-9]{8,10})",
        ]
        carrier_tax = self.extract_regex_string(text, carrier_tax_patterns)

        # 5. Origen, destino y consignatario
        origin_patterns = [
            r"(?:lugar\s+de\s+carga|origen\s+del\s+porte|cargado\s+en)\s*[:\-]\s*([^\n\r]+)",
            r"(?<!albar[aá]n\s)(?<!albaran\s)\b(?:lugar\s+de\s+origen|origen)\s*[:\-]\s*([^\n\r]+)",
        ]
        origin = self.extract_regex_string(text, origin_patterns)

        destination_patterns = [
            r"(?:destino|lugar\s+de\s+descarga)\s*[:\-]\s*([^\n\r]+)",
            r"(?:entregar\s+en)\s*[:\-]\s*([^\n\r]+)",
        ]
        destination = self.extract_regex_string(text, destination_patterns)

        consignee_patterns = [
            r"(?:consignatario|destinatario|receptor|cliente)\s*[:\-]\s*([^\n\r]+)",
            r"(?:entregar\s+a)\s*[:\-]\s*([^\n\r]+)",
        ]
        consignee = self.extract_regex_string(text, consignee_patterns)
        if not consignee.is_valid and destination.is_valid:
            consignee = destination

        # 6. Mercancía, bultos y pesos desglosados (bruto y neto)
        goods_patterns = [
            r"(?:mercanc[ií]a|naturaleza(?:\s+de\s+la\s+mercanc[ií]a)?|producto)\s*[:\-]\s*([^\n\r]+)",
            r"(?:art[ií]culo|variedad)\s*[:\-]\s*([^\n\r]+)",
        ]
        goods = self.extract_regex_string(text, goods_patterns)

        pkg_patterns = [
            r"(?:total\s+bultos|n[º°.]?\s*bultos|bultos|cajas|palets)\s*[:\-]?\s*([\d.\s]+)",
            r"([\d.\s]+)\s*(?:bultos|cajas|colis)",
        ]
        total_packages = self.extract_integer(text, pkg_patterns)

        gross_patterns = [
            r"(?:peso\s+bruto|bruto|masa\s+bruta)\s*[:\-]?\s*([\d.,]+\s*(?:kg|t|toneladas)?)",
            r"(?:peso\s+total|peso)\s*[:\-]?\s*([\d.,]+\s*(?:kg|t|toneladas)?)",
            r"([\d.,]+\s*(?:kg|kilos))",
        ]
        total_gross_weight = self.extract_weight(text, gross_patterns)

        net_patterns = [
            r"(?:peso\s+neto|neto|masa\s+neta)\s*[:\-]?\s*([\d.,]+\s*(?:kg|t|toneladas)?)",
        ]
        total_net_weight = self.extract_weight(text, net_patterns)

        weight_kg = total_gross_weight if total_gross_weight.is_valid else total_net_weight

        # 7. Matrículas (habitualmente vacías o no presentes en el PDF inicial)
        tractor_plate = self.extract_regex_string(
            text,
            [
                r"(?:matr[ií]cula(?:\s+tractor)?|tractor)\s*[:\-]?\s*([0-9]{4}\s*[A-Z]{3}|[A-Z0-9-]{6,12})"
            ],
        )
        trailer_plate = self.extract_regex_string(
            text, [r"(?:remolque|semirremolque)\s*[:\-]?\s*([A-Z0-9-]{6,12})"]
        )

        obs = self.extract_regex_string(
            text, [r"(?:observaciones|instrucciones|reservas)\s*[:\-]\s*([^\n\r]+)"]
        )

        return NormalizedDocumentDTO(
            format_type=DocumentFormatType.CARTA_DE_PORTE,
            format_confidence=confidence,
            reference=reference,
            fiscal_year=fiscal_year,
            transport_date=trans_date,
            shipper_name=shipper_name,
            shipper_tax_id=shipper_tax,
            shipper_address=shipper_addr,
            carrier_name=carrier_name,
            carrier_tax_id=carrier_tax,
            origin=origin,
            destination=destination,
            goods=goods,
            weight_kg=weight_kg,
            tractor_plate=tractor_plate,
            trailer_plate=trailer_plate,
            observations=obs,
            document_number=document_number,
            external_reference=external_reference,
            consignee=consignee,
            total_packages=total_packages,
            total_gross_weight_kg=total_gross_weight,
            total_net_weight_kg=total_net_weight,
            raw_carrier_text=carrier_name.value or "",
            metadata={"parser": "CartaDePorteParser", "pages": raw_doc.pages_count},
        )
