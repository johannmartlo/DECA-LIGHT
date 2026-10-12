import hashlib
import threading
import uuid

from src.application.ports.deca_repository import DeCARepositoryPort
from src.domain.entities.deca import DeCA, DeCAVersion


class InMemoryDeCARepository(DeCARepositoryPort):
    """Implementación en memoria y thread-safe de DeCARepositoryPort."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_id: dict[uuid.UUID, DeCA] = {}
        self._by_expedition_id: dict[uuid.UUID, uuid.UUID] = {}
        self._by_code: dict[str, uuid.UUID] = {}
        self._by_token: dict[str, uuid.UUID] = {}
        self._by_token_hash: dict[str, uuid.UUID] = {}
        self._sequences: dict[str, int] = {}

    def next_deca_code(self, fiscal_year: str) -> str:
        """Genera atómicamente el siguiente código único DECA-YYYY-NNNNNN."""
        with self._lock:
            current = self._sequences.get(fiscal_year, 0) + 1
            self._sequences[fiscal_year] = current
            return f"DECA-{fiscal_year}-{current:06d}"

    def save(self, deca: DeCA) -> DeCA:
        """Guarda o actualiza un DeCA en memoria."""
        with self._lock:
            self._by_id[deca.id] = deca
            if deca.expedition_id:
                self._by_expedition_id[deca.expedition_id] = deca.id
            if deca.deca_code:
                self._by_code[deca.deca_code] = deca.id
            if deca.public_access_token:
                self._by_token[str(deca.public_access_token)] = deca.id
            if deca.public_token_hash:
                self._by_token_hash[deca.public_token_hash] = deca.id
            return deca

    def get_by_id(self, deca_id: uuid.UUID, company_id: str | None = None) -> DeCA | None:
        with self._lock:
            deca = self._by_id.get(deca_id)
            if deca and company_id and not deca.belongs_to(company_id):
                return None
            return deca

    def find_by_expedition_id(
        self, expedition_id: uuid.UUID, company_id: str | None = None
    ) -> DeCA | None:
        with self._lock:
            deca_id = self._by_expedition_id.get(expedition_id)
            if not deca_id:
                return None
            deca = self._by_id.get(deca_id)
            if deca and company_id and not deca.belongs_to(company_id):
                return None
            return deca

    def find_by_code(self, deca_code: str, company_id: str | None = None) -> DeCA | None:
        with self._lock:
            deca_id = self._by_code.get(deca_code)
            if not deca_id:
                return None
            deca = self._by_id.get(deca_id)
            if deca and company_id and not deca.belongs_to(company_id):
                return None
            return deca

    def get_by_public_token(self, token: str) -> DeCA | None:
        with self._lock:
            token_clean = str(token).strip()
            token_hash = hashlib.sha256(token_clean.encode("utf-8")).hexdigest()
            deca_id = self._by_token_hash.get(token_hash) or self._by_token.get(token_clean)
            if not deca_id:
                return None
            return self._by_id.get(deca_id)

    def save_version(self, version: DeCAVersion) -> DeCAVersion:
        with self._lock:
            if version.deca_id and version.deca_id in self._by_id:
                deca = self._by_id[version.deca_id]
                deca.add_version(version)
            return version

    def clear(self) -> None:
        """Limpia los datos del repositorio en memoria (utilidad para tests)."""
        with self._lock:
            self._by_id.clear()
            self._by_expedition_id.clear()
            self._by_code.clear()
            self._by_token.clear()
            self._by_token_hash.clear()
            self._sequences.clear()
