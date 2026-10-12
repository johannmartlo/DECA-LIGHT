from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageServicePort(ABC):
    """Puerto para el almacenamiento y recuperación de archivos (PDFs originales y DeCAs)."""

    @abstractmethod
    def save(self, file_content: bytes | BinaryIO, destination_path: str) -> str:
        """Guarda un archivo y retorna la ruta o URI de acceso interno."""
        pass

    @abstractmethod
    def read(self, file_path: str) -> bytes:
        """Lee el contenido binario de un archivo."""
        pass

    @abstractmethod
    def exists(self, file_path: str) -> bool:
        """Comprueba si un archivo existe en el almacenamiento."""
        pass
