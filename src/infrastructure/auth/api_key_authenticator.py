from __future__ import annotations

import hashlib
import secrets
from typing import Dict, Iterable, Tuple

from src.application.ports.tenant_authenticator_port import (
    ApiKeyIdentity,
    TenantAuthenticatorPort,
)
from src.domain.exceptions import (
    ForbiddenTenantException,
    UnauthorizedCompanyContextException,
)


def hash_api_key(raw_key: str) -> str:
    """Genera un hash SHA-256 criptográfico para la API Key."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def generate_api_key(environment: str = "test") -> Tuple[str, str]:
    """Genera una clave API con prefijo identificable y suficiente entropía.

    Retorna:
        tuple[raw_key, key_hash]
    """
    token_part = secrets.token_urlsafe(32)
    raw_key = f"deca_{environment}_{token_part}"
    key_hash = hash_api_key(raw_key)
    return raw_key, key_hash


class InMemoryTenantAuthenticator(TenantAuthenticatorPort):
    """Adaptador de autenticación M2M basado en API Keys seguras en memoria."""

    def __init__(self, initial_identities: Iterable[ApiKeyIdentity] | None = None) -> None:
        self._identities_by_hash: Dict[str, ApiKeyIdentity] = {}
        if initial_identities:
            for ident in initial_identities:
                self.register_identity(ident)

    def register_identity(self, identity: ApiKeyIdentity) -> None:
        """Registra una identidad por el hash de su API Key."""
        self._identities_by_hash[identity.key_hash] = identity

    def authenticate_key(self, raw_api_key: str) -> ApiKeyIdentity | None:
        if not raw_api_key or not isinstance(raw_api_key, str) or not raw_api_key.strip():
            return None

        clean_key = raw_api_key.strip()
        incoming_hash = hash_api_key(clean_key)

        for stored_hash, identity in self._identities_by_hash.items():
            if secrets.compare_digest(stored_hash, incoming_hash):
                if identity.is_active:
                    return identity
                return None
        return None

    def resolve_active_company(
        self, identity: ApiKeyIdentity, requested_company_id: str | None = None
    ) -> str:
        if not identity.is_active:
            raise ForbiddenTenantException("La identidad M2M se encuentra inactiva o revocada.")

        if requested_company_id is not None and requested_company_id.strip():
            target = requested_company_id.strip()
            if target in identity.allowed_companies:
                return target
            raise ForbiddenTenantException("Acceso denegado: empresa no autorizada.")

        # Si no se especifica empresa y solo tiene una asignada, selección unívoca
        if len(identity.allowed_companies) == 1:
            return next(iter(identity.allowed_companies))

        # Si tiene múltiples empresas y no especificó ninguna
        raise UnauthorizedCompanyContextException(
            "La identidad tiene múltiples empresas autorizadas. Debe especificar la empresa activa mediante X-Company-Id."
        )
