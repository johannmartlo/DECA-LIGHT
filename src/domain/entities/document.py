from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.enums import DocumentProcessingStatus


@dataclass
class Document:
    """Documento físico importado (carta de porte Hispatec o CMR)."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    sha256_hash: str = ""
    original_filename: str = ""
    mime_type: str = "application/pdf"
    size_bytes: int = 0
    storage_path: str = ""
    status: DocumentProcessingStatus = DocumentProcessingStatus.PENDING
    user_id: uuid.UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
