from __future__ import annotations

import re
from pathlib import Path
from typing import BinaryIO

from src.application.ports.pdf_storage import PdfStoragePort
from src.domain.exceptions import StorageException
from src.infrastructure.storage.filesystem_storage import FilesystemStorageAdapter


class LocalPdfStorage(FilesystemStorageAdapter, PdfStoragePort):
    """Adaptador de almacenamiento local para documentos PDF y DeCAs con custodia determinista."""

    def __init__(self, base_directory: Path | str) -> None:
        super().__init__(base_directory)

    def _resolve_safe_path(self, relative_path: str) -> Path:
        try:
            return super()._resolve_safe_path(relative_path)
        except PermissionError as exc:
            raise StorageException(f"Intento de path traversal detectado: {exc}") from exc

    def save_deca_pdf(
        self,
        fiscal_year: str,
        deca_code: str,
        content: bytes | BinaryIO,
    ) -> str:
        """Almacena el PDF en 'deca/{fiscal_year}/{deca_code}.pdf' con estricta validación de caracteres."""
        # Validación de seguridad contra inyección de rutas en los identificadores
        if not re.match(r"^\d{4}$", str(fiscal_year).strip()):
            raise StorageException(f"Ejercicio fiscal inválido para almacenamiento: '{fiscal_year}'")
        clean_code = str(deca_code).strip()
        if not re.match(r"^[A-Z0-9_-]+$", clean_code):
            raise StorageException(f"Código DeCA inválido para almacenamiento: '{deca_code}'")

        relative_path = f"deca/{fiscal_year}/{clean_code}.pdf"
        self.save(content, relative_path)
        return relative_path

    def save(self, file_content: bytes | BinaryIO, destination_path: str) -> str:
        try:
            return super().save(file_content, destination_path)
        except PermissionError as exc:
            raise StorageException(f"Permiso denegado en almacenamiento: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, StorageException):
                raise
            raise StorageException(f"Error escribiendo en almacenamiento: {exc}") from exc

    def read(self, file_path: str) -> bytes:
        try:
            return super().read(file_path)
        except PermissionError as exc:
            raise StorageException(f"Permiso denegado en lectura: {exc}") from exc
        except FileNotFoundError as exc:
            raise StorageException(f"Archivo no encontrado en almacenamiento: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, StorageException):
                raise
            raise StorageException(f"Error leyendo del almacenamiento: {exc}") from exc
