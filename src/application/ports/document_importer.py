from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO

from src.application.dtos.document_dto import NormalizedDocumentDTO


class DocumentImporterPort(ABC):
    """Puerto para la importación y parseo determinista de documentos (PDF Hispatec, CMR, etc.)."""

    @abstractmethod
    def can_import(self, stream: BinaryIO, filename: str) -> bool:
        """Determina si este adaptador puede procesar el archivo recibido."""
        pass

    @abstractmethod
    def parse(self, stream: BinaryIO, filename: str) -> NormalizedDocumentDTO:
        """Parsea deterministamente el contenido y extrae los campos requeridos."""
        pass
