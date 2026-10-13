from __future__ import annotations

from dataclasses import dataclass

from src.domain.entities.deca import DeCAEstructurado

# Alias canónico entre el DTO de aplicación y el modelo estructurado de dominio
DeCAStructuredDTO = DeCAEstructurado


@dataclass(frozen=True)
class EmitDeCAInputDTO:
    """Parámetros de entrada para el caso de uso de emisión de DeCA."""

    expedition_id: str
    actor: str = "OPERATOR"
    company_id: str | None = None


@dataclass(frozen=True)
class EmitDeCAResultDTO:
    """Resultado estructurado de la emisión del DeCA."""

    deca_id: str
    version: int
    expedition_id: str
    status: str
    pdf_filename: str
    pdf_sha256: str
    pdf_size_bytes: int
    issued_at: str
    company_id: str = "TOMATES_DE_AUTOR"
    public_token: str = ""
    public_url: str = ""
    is_idempotent: bool = False
    message: str = "DeCA emitido y custodiado correctamente."
