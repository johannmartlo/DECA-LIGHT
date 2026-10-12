from __future__ import annotations

from abc import ABC, abstractmethod

from src.application.dtos.deca_dto import DeCAStructuredDTO


class PdfRendererPort(ABC):
    """Puerto para el renderizado vectorial de documentos DeCA en PDF con metadatos y QR."""

    @abstractmethod
    def render(self, deca_data: DeCAStructuredDTO) -> bytes:
        """Genera el binario PDF conforme a las especificaciones del BOE (<= 5MB)."""
        pass
