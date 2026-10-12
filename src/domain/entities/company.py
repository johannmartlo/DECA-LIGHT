from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.domain.exceptions import ValidationException
from src.domain.value_objects import NIF

REQUIERE_CONFIGURACION = "REQUIERE_CONFIGURACION"

_COMPANY_ID_RE = re.compile(r"^[A-Z0-9_]{2,40}$")
_LEGAL_SUFFIX_RE = re.compile(r"\s+(?:S\s?L\s?U?|SOCIEDAD LIMITADA)$")


def normalize_company_name(name: str | None) -> str:
    """Normaliza una razón social para comparación EXACTA tolerante a formato.

    Elimina tildes, puntuación y mayúsculas/minúsculas, y el sufijo societario
    (S.L., SL, S.L.U.). No realiza coincidencias aproximadas: dos razones
    sociales distintas nunca se normalizan al mismo valor.
    """
    if not name:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(name))
    ascii_text = "".join(c for c in decomposed if not unicodedata.combining(c))
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", ascii_text).upper().strip()
    return _LEGAL_SUFFIX_RE.sub("", cleaned).strip()


@dataclass(frozen=True)
class Company:
    """Sociedad emisora de DeCA (Company / Tenant / Issuer).

    Los datos fiscales NO se inventan: si no están configurados permanecen
    vacíos y se reportan como ``REQUIERE_CONFIGURACION`` en ``pending_fields``.
    """

    company_id: str
    legal_name: str
    tax_id: NIF | None = None
    fiscal_address: str = ""
    active: bool = True
    document_aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _COMPANY_ID_RE.match(self.company_id or ""):
            raise ValidationException(
                "company_id inválido: use 2-40 caracteres A-Z, 0-9 o '_' "
                f"(recibido: '{self.company_id}')."
            )
        if not self.legal_name or not self.legal_name.strip():
            raise ValidationException("La razón social de la empresa no puede estar vacía.")

    @property
    def pending_fields(self) -> tuple[str, ...]:
        pending: list[str] = []
        if self.tax_id is None:
            pending.append("tax_id")
        if not self.fiscal_address.strip():
            pending.append("fiscal_address")
        return tuple(pending)

    @property
    def is_fully_configured(self) -> bool:
        return not self.pending_fields

    def known_names(self) -> frozenset[str]:
        names = {normalize_company_name(self.legal_name)}
        names.update(normalize_company_name(a) for a in self.document_aliases)
        names.discard("")
        return frozenset(names)

    def matches_legal_name(self, name: str | None) -> bool:
        return normalize_company_name(name) == normalize_company_name(self.legal_name)

    def matches_any_name(self, name: str | None) -> bool:
        return normalize_company_name(name) in self.known_names()

    def issuer_snapshot(self) -> dict:
        """Copia inmutable de los datos empresariales para el snapshot del DeCA."""
        return {
            "company_id": self.company_id,
            "legal_name": self.legal_name,
            "tax_id": str(self.tax_id) if self.tax_id else "",
            "fiscal_address": self.fiscal_address,
        }


@dataclass(frozen=True)
class CompanyContext:
    """Contexto explícito de empresa para una operación (sin variables globales)."""

    company_id: str
    detection_confidence: float = 1.0
    detection_source: str = "EXPLICIT"

    def __post_init__(self) -> None:
        if not self.company_id:
            raise ValidationException("CompanyContext requiere un company_id no vacío.")
