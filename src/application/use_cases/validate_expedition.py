from __future__ import annotations

import uuid

from src.application.ports.expedition_repository import ExpeditionRepositoryPort
from src.domain.entities.expedition import Expedition
from src.domain.exceptions import EntityNotFoundException
from src.domain.services.deca_validator import DeCAValidator, ValidationResult
from src.domain.value_objects import CompanyContext


class ValidateExpeditionUseCase:
    """Caso de uso de solo lectura para evaluar requisitos DeCA de una expedición."""

    def __init__(self, expedition_repo: ExpeditionRepositoryPort) -> None:
        self.expedition_repo = expedition_repo

    def execute(
        self, expedition_id: uuid.UUID | str, company_id: str | None = None
    ) -> tuple[Expedition, ValidationResult]:
        if company_id:
            CompanyContext.create(company_id)
        exp_id = (
            uuid.UUID(str(expedition_id))
            if not isinstance(expedition_id, uuid.UUID)
            else expedition_id
        )
        expedition = self.expedition_repo.get_by_id(exp_id, company_id=company_id)
        if not expedition:
            raise EntityNotFoundException(f"Expedición con ID '{expedition_id}' no encontrada.")

        result = DeCAValidator.validate(expedition)
        return expedition, result
