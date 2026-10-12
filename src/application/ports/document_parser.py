from __future__ import annotations

from abc import ABC, abstractmethod

from src.application.dtos.document_dto import NormalizedDocumentDTO, RawDocumentDTO
from src.domain.enums import DocumentFormatType


class DocumentParserPort(ABC):
    """Contrato base para un parser especializado en un formato documental concreto."""

    @property
    @abstractmethod
    def format_type(self) -> DocumentFormatType:
        """Tipo de formato documental que procesa este parser."""
        pass

    @abstractmethod
    def can_parse(self, raw_doc: RawDocumentDTO) -> tuple[bool, float]:
        """Evalúa si el documento corresponde a este formato y calcula la confianza de detección.

        Retorna:
            (coincide: bool, nivel_confianza: float entre 0.0 y 1.0)
        """
        pass

    @abstractmethod
    def parse(self, raw_doc: RawDocumentDTO) -> NormalizedDocumentDTO:
        """Extrae y normaliza los campos desde el texto bruto sin inventar datos."""
        pass
