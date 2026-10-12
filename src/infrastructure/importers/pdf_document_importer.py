from __future__ import annotations

import hashlib
import io
import logging
from typing import BinaryIO

from pypdf import PdfReader

from src.application.dtos.document_dto import NormalizedDocumentDTO, RawDocumentDTO
from src.application.ports.document_importer import DocumentImporterPort
from src.domain.enums import DocumentFormatType
from src.infrastructure.parsers.composite_parser import CompositeDocumentParser

logger = logging.getLogger("deca_light.importers")


class PdfDocumentImporter(DocumentImporterPort):
    """Importador de documentos PDF nativos con validación de cabeceras y extracción de texto."""

    def __init__(self, parser: CompositeDocumentParser | None = None) -> None:
        self.parser = parser or CompositeDocumentParser()

    def can_import(self, stream: BinaryIO, filename: str) -> bool:
        """Comprueba que el archivo tenga extensión .pdf y cabecera mágica %PDF-."""
        if not filename.lower().endswith(".pdf"):
            return False

        current_pos = stream.tell()
        header = stream.read(10)
        stream.seek(current_pos)

        return header.startswith(b"%PDF-")

    def extract_raw(self, stream: BinaryIO, filename: str) -> RawDocumentDTO:
        """Lee el binario, calcula su SHA-256 y extrae la capa de texto vectorial."""
        stream.seek(0)
        content_bytes = stream.read()
        stream.seek(0)

        sha256 = hashlib.sha256(content_bytes).hexdigest()

        try:
            reader = PdfReader(io.BytesIO(content_bytes))
            extracted_pages: list[str] = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                extracted_pages.append(page_text)
            extracted_text = "\n".join(extracted_pages)
            pages_count = len(reader.pages)
        except Exception as exc:
            logger.warning("Error leyendo estructura del PDF '%s': %s", filename, str(exc))
            extracted_text = ""
            pages_count = 0

        return RawDocumentDTO(
            content_bytes=content_bytes,
            filename=filename,
            sha256_hash=sha256,
            extracted_text=extracted_text,
            pages_count=pages_count,
        )

    def parse(
        self,
        stream: BinaryIO,
        filename: str,
        forced_format: DocumentFormatType | None = None,
    ) -> NormalizedDocumentDTO:
        """Extrae el texto del PDF y ejecuta el composite parser determinista."""
        raw_doc = self.extract_raw(stream, filename)
        return self.parser.parse(raw_doc, forced_format=forced_format)
