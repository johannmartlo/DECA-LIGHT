from __future__ import annotations

import threading
from abc import ABC, abstractmethod


class ExpeditionSequenceGeneratorPort(ABC):
    """Puerto para la generación atómica y concurrente de identificadores TD-YYYY-NNNNN."""

    @abstractmethod
    def next_identifier(self, fiscal_year: str) -> str:
        """Genera el siguiente identificador único en formato TD-YYYY-NNNNN."""
        pass


class InMemoryExpeditionSequenceGenerator(ExpeditionSequenceGeneratorPort):
    """Implementación thread-safe en memoria para generación de identificadores TD-YYYY-NNNNN."""

    def __init__(self, initial_sequences: dict[str, int] | None = None) -> None:
        self._sequences: dict[str, int] = initial_sequences.copy() if initial_sequences else {}
        self._lock = threading.Lock()

    def next_identifier(self, fiscal_year: str) -> str:
        with self._lock:
            current = self._sequences.get(fiscal_year, 0) + 1
            self._sequences[fiscal_year] = current
            return f"TD-{fiscal_year}-{current:05d}"
