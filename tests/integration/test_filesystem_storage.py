from __future__ import annotations

from pathlib import Path

import pytest

from src.infrastructure.storage.filesystem_storage import FilesystemStorageAdapter


def test_storage_save_and_read(tmp_path: Path) -> None:
    storage = FilesystemStorageAdapter(tmp_path)
    sample_data = b"CONTENIDO BINARIO PDF DE PRUEBA"

    rel_path = "deca/2026/test_doc.pdf"
    full_path = storage.save(sample_data, rel_path)

    assert storage.exists(rel_path) is True
    assert storage.read(rel_path) == sample_data
    assert Path(full_path).exists()


def test_storage_blocks_path_traversal(tmp_path: Path) -> None:
    storage = FilesystemStorageAdapter(tmp_path)

    with pytest.raises(PermissionError, match="acceso no autorizado"):
        storage.save(b"malicious", "../outside.txt")

    with pytest.raises(PermissionError, match="acceso no autorizado"):
        storage.read("../../etc/passwd")
