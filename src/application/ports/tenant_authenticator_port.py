from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Set


@dataclass(frozen=True)
class ApiKeyIdentity:
    """Identidad M2M autenticada mediante API Key en el servidor."""

    identity_id: str
    name: str
    key_hash: str
    allowed_companies: frozenset[str]
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def can_access_company(self, company_id: str) -> bool:
        """Verifica si la identidad tiene autorización explícita para la empresa indicada."""
        if not self.is_active:
            return False
        return company_id in self.allowed_companies


class TenantAuthenticatorPort(ABC):
    """Puerto de autenticación y resolución de tenant para clientes M2M."""

    @abstractmethod
    def authenticate_key(self, raw_api_key: str) -> ApiKeyIdentity | None:
        """Valida una API Key sin procesar y retorna la identidad asociada si es válida y está activa."""
        pass

    @abstractmethod
    def resolve_active_company(
        self, identity: ApiKeyIdentity, requested_company_id: str | None = None
    ) -> str:
        """Resuelve y autoriza la empresa activa para la petición.

        Reglas:
        - Si identity solo tiene 1 empresa y no se indica requested_company_id -> selecciona automáticamente esa empresa.
        - Si requested_company_id se especifica -> valida que esté en allowed_companies.
        - Si identity tiene múltiples empresas y no se indica requested_company_id -> eleva excepción por falta de especificidad.
        """
        pass
