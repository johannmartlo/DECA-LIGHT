from __future__ import annotations

import logging
from collections.abc import Sequence

from src.application.dtos.document_dto import NormalizedDocumentDTO, RawDocumentDTO
from src.application.ports.document_parser import DocumentParserPort
from src.domain.enums import DocumentFormatType
from src.domain.value_objects import ExtractedField
from src.infrastructure.parsers.carta_de_porte_parser import CartaDePorteParser
from src.infrastructure.parsers.cmr_parser import CMRParser

logger = logging.getLogger("deca_light.parsers")


class CompositeDocumentParser:
    """Orquestador multiformato con detección automática y selección de parser por confianza."""

    def __init__(
        self,
        parsers: Sequence[DocumentParserPort] | None = None,
        min_confidence_threshold: float = 0.5,
    ) -> None:
        self.parsers = (
            list(parsers)
            if parsers is not None
            else [
                CartaDePorteParser(),
                CMRParser(),
            ]
        )
        self.min_confidence_threshold = min_confidence_threshold

    def detect_format(self, raw_doc: RawDocumentDTO) -> tuple[DocumentParserPort | None, float]:
        """Identifica automáticamente el tipo de documento evaluando la certeza de cada parser."""
        best_parser: DocumentParserPort | None = None
        best_confidence: float = 0.0

        for parser in self.parsers:
            can_handle, confidence = parser.can_parse(raw_doc)
            logger.debug(
                "Evaluando parser %s: coincide=%s, confianza=%.2f",
                parser.__class__.__name__,
                can_handle,
                confidence,
            )
            if can_handle and confidence > best_confidence:
                best_confidence = confidence
                best_parser = parser

        if best_confidence < self.min_confidence_threshold:
            logger.warning(
                "Documento '%s' no alcanzó el umbral mínimo de confianza (%.2f < %.2f)",
                raw_doc.filename,
                best_confidence,
                self.min_confidence_threshold,
            )
            return None, best_confidence

        return best_parser, best_confidence

    def parse(
        self,
        raw_doc: RawDocumentDTO,
        forced_format: DocumentFormatType | None = None,
    ) -> NormalizedDocumentDTO:
        """Parsea el documento detectando automáticamente su formato o usando el especificado."""
        target_parser: DocumentParserPort | None = None

        if forced_format and forced_format != DocumentFormatType.DESCONOCIDO:
            for p in self.parsers:
                if p.format_type == forced_format:
                    target_parser = p
                    break

        if not target_parser:
            target_parser, confidence = self.detect_format(raw_doc)

        if target_parser:
            logger.info(
                "Parseando documento '%s' usando %s (formato: %s)",
                raw_doc.filename,
                target_parser.__class__.__name__,
                target_parser.format_type,
            )
            return target_parser.parse(raw_doc)

        # Si no se pudo clasificar o procesar, se retorna en estado DESCONOCIDO
        # marcando todos los campos para revisión humana (nunca se inventan datos)
        logger.warning(
            "Documento '%s' marcado como DESCONOCIDO -> PENDIENTE_REVISION",
            raw_doc.filename,
        )
        return NormalizedDocumentDTO(
            format_type=DocumentFormatType.DESCONOCIDO,
            format_confidence=0.0,
            reference=ExtractedField.requires_review(raw_text="No reconocido", confidence=0.0),
            fiscal_year=ExtractedField.not_recognized(),
            transport_date=ExtractedField.requires_review(raw_text="No reconocida", confidence=0.0),
            shipper_name=ExtractedField.requires_review(raw_text="No reconocido", confidence=0.0),
            shipper_tax_id=ExtractedField.not_recognized(),
            shipper_address=ExtractedField.not_recognized(),
            carrier_name=ExtractedField.requires_review(raw_text="No reconocido", confidence=0.0),
            carrier_tax_id=ExtractedField.not_recognized(),
            origin=ExtractedField.requires_review(raw_text="No reconocido", confidence=0.0),
            destination=ExtractedField.requires_review(raw_text="No reconocido", confidence=0.0),
            goods=ExtractedField.requires_review(raw_text="No reconocido", confidence=0.0),
            weight_kg=ExtractedField.requires_review(raw_text="No reconocido", confidence=0.0),
            tractor_plate=ExtractedField.not_present(),
            trailer_plate=ExtractedField.not_present(),
            observations=ExtractedField.not_present(),
            raw_carrier_text="",
            metadata={"status": "NO_RECONOCIDO", "filename": raw_doc.filename},
        )
