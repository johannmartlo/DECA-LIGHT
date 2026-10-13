from __future__ import annotations

import threading
from abc import ABC, abstractmethod


class ExpeditionSequenceGeneratorPort(ABC):
    """Puerto para la generación atómica y concurrente de identificadores de expedición."""

    @abstractmethod
    def next_identifier(
        self, fiscal_year: str, company_id: str | None = None, prefix: str = "TD"
    ) -> str:
        """Genera el siguiente identificador único."""
        pass


class InMemoryExpeditionSequenceGenerator(ExpeditionSequenceGeneratorPort):
    """Implementación thread-safe en memoria para generación de identificadores independientes por empresa."""

    def __init__(self, initial_sequences: dict[tuple[str, str, str], int] | None = None) -> None:
        self._sequences: dict[tuple[str, str, str], int] = initial_sequences.copy() if initial_sequences else {}
        self._lock = threading.Lock()

    def next_identifier(
        self, fiscal_year: str, company_id: str | None = None, prefix: str = "TD"
    ) -> str:
        with self._lock:
            key = (company_id or "", fiscal_year, prefix)
            current = self._sequences.get(key, 0) + 1
            self._sequences[key] = current
            return f"{prefix}-{fiscal_year}-{current:05d}"
