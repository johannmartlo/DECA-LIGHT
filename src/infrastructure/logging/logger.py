from __future__ import annotations

import logging
import re
import sys

_SENSITIVE_PATTERNS = [
    re.compile(r"(password|secret|token|authorization)[:=\s]+['\"]?([^'\"\s&]+)", re.IGNORECASE),
]


class SensitiveDataFilter(logging.Filter):
    """Filtra y enmascara secretos y tokens en cualquier mensaje de log."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if record.args:
                record.msg = self.mask_secrets(record.getMessage())
                record.args = ()
            elif isinstance(record.msg, str):
                record.msg = self.mask_secrets(record.msg)
        except Exception:
            pass
        return True

    @staticmethod
    def mask_secrets(message: str) -> str:
        for pattern in _SENSITIVE_PATTERNS:
            message = pattern.sub(r"\1: [MASKED]", message)
        return message


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configura el logging estructurado del sistema DECA Light."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger("deca_light")
    root_logger.setLevel(numeric_level)

    # Evitar duplicar handlers si ya está configurado
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(numeric_level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())
        root_logger.addHandler(handler)

    return root_logger
