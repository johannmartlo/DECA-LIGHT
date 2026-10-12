from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO

from src.application.ports.storage_service import StorageServicePort


class FilesystemStorageAdapter(StorageServicePort):
    """Adaptador de almacenamiento privado en sistema de archivos local con prevención de path traversal."""

    def __init__(self, base_directory: Path | str):
        self.base_dir = Path(base_directory).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, relative_path: str) -> Path:
        """Resuelve la ruta y asegura que no escape del directorio base."""
        # Eliminar barras iniciales para que sea tratada como relativa
        clean_rel = relative_path.lstrip("/\\")
        target = (self.base_dir / clean_rel).resolve()
        if not target.is_relative_to(self.base_dir):
            raise PermissionError(
                f"Intento de acceso no autorizado fuera del almacenamiento: '{relative_path}'"
            )
        return target

    def save(self, file_content: bytes | BinaryIO, destination_path: str) -> str:
        target_file = self._resolve_safe_path(destination_path)
        target_file.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(file_content, (bytes, bytearray)):
            target_file.write_bytes(file_content)
        elif isinstance(file_content, (io.IOBase, BinaryIO)):
            with open(target_file, "wb") as f:
                f.write(file_content.read())
        else:
            raise TypeError("El contenido debe ser bytes o un flujo binario.")

        return str(target_file)

    def read(self, file_path: str) -> bytes:
        target_file = self._resolve_safe_path(file_path)
        if not target_file.is_file():
            raise FileNotFoundError(f"Archivo no encontrado en almacenamiento: '{file_path}'")
        return target_file.read_bytes()

    def exists(self, file_path: str) -> bool:
        target_file = self._resolve_safe_path(file_path)
        return target_file.is_file()
