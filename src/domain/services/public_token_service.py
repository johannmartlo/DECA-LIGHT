from __future__ import annotations

import hashlib
import re
import secrets

from src.domain.value_objects import DeCAToken

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


class PublicDeCaTokenService:
    """Servicio de generación, validación, hashing y enmascaramiento de tokens públicos."""

    @classmethod
    def generate_token(cls) -> str:
        """Genera un token de 256 bits de entropía utilizando un CSPRNG seguro."""
        return secrets.token_urlsafe(32)

    @classmethod
    def hash_token(cls, token: str | DeCAToken) -> str:
        """Calcula el hash SHA-256 canónico del token para búsqueda e indexación segura O(1)."""
        raw_token = str(token).strip()
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @classmethod
    def mask_token(cls, token: str | DeCAToken) -> str:
        """Genera representación truncada para observabilidad y logs sin exponer el secreto."""
        raw_token = str(token).strip()
        if len(raw_token) <= 10:
            return "***"
        return f"{raw_token[:6]}...{raw_token[-4:]}"

    @classmethod
    def is_valid_token_format(cls, token: str | DeCAToken) -> bool:
        """Valida que el token cumpla con las especificaciones de entropía y caracteres seguros."""
        if not token:
            return False
        raw = str(token)
        return bool(TOKEN_PATTERN.match(raw))

    @classmethod
    def build_public_url(cls, base_url: str, token: str | DeCAToken) -> str:
        """Construye la URL canónica pública para el código QR y el endpoint de inspección."""
        clean_base = base_url.strip().rstrip("/")
        return f"{clean_base}/d/{token}"
