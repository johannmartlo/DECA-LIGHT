from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from src.domain.entities.company import Company, normalize_company_name
from src.domain.value_objects import NIF


class CompanyDetectionSource(StrEnum):
    TAX_ID = "TAX_ID"
    LEGAL_NAME = "LEGAL_NAME"
    DOCUMENT_ALIAS = "DOCUMENT_ALIAS"
    NONE = "NONE"


class CompanyDetectionStatus(StrEnum):
    DETECTED = "DETECTED"
    UNKNOWN = "UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class CompanyDetectionResult:
    """Resultado trazable de la identificación de la empresa emisora."""

    status: CompanyDetectionStatus
    company_id: str | None = None
    confidence: float = 0.0
    source: CompanyDetectionSource = CompanyDetectionSource.NONE
    reason: str = ""

    @property
    def detected(self) -> bool:
        return self.status == CompanyDetectionStatus.DETECTED and self.company_id is not None


def _clean_tax(tax_id: str | None) -> str:
    if not tax_id or not str(tax_id).strip():
        return ""
    try:
        return str(NIF(str(tax_id)))
    except ValueError:
        return ""


class CompanyDetector:
    """Identifica la sociedad emisora SOLO a partir de datos verificables del documento.

    Prioridad: 1) NIF/CIF del cargador, 2) razón social exacta, 3) alias documentales
    configurados. Nunca infiere por nombre de archivo ni por orden de importación y
    nunca asume una empresa por defecto: ante duda o ausencia devuelve AMBIGUOUS/UNKNOWN.
    """

    @staticmethod
    def detect(
        companies: Iterable[Company],
        shipper_tax_id: str | None,
        shipper_name: str | None,
    ) -> CompanyDetectionResult:
        active = [c for c in companies if c.active]
        doc_tax = _clean_tax(shipper_tax_id)
        doc_name = normalize_company_name(shipper_name)

        tax_matches = [c for c in active if doc_tax and c.tax_id and str(c.tax_id) == doc_tax]
        legal_matches = [c for c in active if doc_name and c.matches_legal_name(shipper_name)]
        alias_matches = [
            c
            for c in active
            if doc_name and c.matches_any_name(shipper_name) and c not in legal_matches
        ]
        name_matches = legal_matches or alias_matches

        # 1. NIF/CIF
        if len(tax_matches) > 1:
            return CompanyDetectionResult(
                status=CompanyDetectionStatus.AMBIGUOUS,
                reason="El NIF/CIF del cargador coincide con varias empresas configuradas.",
            )
        if len(tax_matches) == 1:
            winner = tax_matches[0]
            if name_matches and all(c.company_id != winner.company_id for c in name_matches):
                return CompanyDetectionResult(
                    status=CompanyDetectionStatus.AMBIGUOUS,
                    reason=(
                        "El NIF/CIF y la razón social del cargador apuntan a empresas distintas."
                    ),
                )
            return CompanyDetectionResult(
                status=CompanyDetectionStatus.DETECTED,
                company_id=winner.company_id,
                confidence=1.0,
                source=CompanyDetectionSource.TAX_ID,
                reason="Coincidencia inequívoca por NIF/CIF del cargador.",
            )

        # 2-3. Razón social exacta / alias documentales
        if not name_matches:
            return CompanyDetectionResult(
                status=CompanyDetectionStatus.UNKNOWN,
                reason="El cargador del documento no corresponde a ninguna empresa configurada.",
            )
        if len(name_matches) > 1:
            return CompanyDetectionResult(
                status=CompanyDetectionStatus.AMBIGUOUS,
                reason="La razón social del cargador coincide con varias empresas configuradas.",
            )
        candidate = name_matches[0]
        if doc_tax and candidate.tax_id is not None:
            return CompanyDetectionResult(
                status=CompanyDetectionStatus.AMBIGUOUS,
                reason=(
                    "La razón social coincide con una empresa, pero el NIF/CIF del documento "
                    "no coincide con el configurado para ella."
                ),
            )
        is_legal = bool(legal_matches)
        return CompanyDetectionResult(
            status=CompanyDetectionStatus.DETECTED,
            company_id=candidate.company_id,
            confidence=0.95 if is_legal else 0.85,
            source=(
                CompanyDetectionSource.LEGAL_NAME
                if is_legal
                else CompanyDetectionSource.DOCUMENT_ALIAS
            ),
            reason="Coincidencia exacta de razón social del cargador.",
        )
