from __future__ import annotations

from abc import abstractmethod
from typing import BinaryIO

from src.application.ports.storage_service import StorageServicePort


class PdfStoragePort(StorageServicePort):
    """Puerto de almacenamiento custodial especializado en documentos PDF y DeCAs oficiales."""

    @abstractmethod
    def save_deca_pdf(
        self,
        fiscal_year: str,
        deca_code: str,
        content: bytes | BinaryIO,
    ) -> str:
        """Almacena el PDF en la ruta determinista 'deca/{fiscal_year}/{deca_code}.pdf'.
        Retorna la ruta relativa del archivo almacenado.
        """
        pass
