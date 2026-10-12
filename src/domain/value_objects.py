from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.domain.enums import FieldExtractionStatus
from src.domain.exceptions import ValidationException


@dataclass(frozen=True)
class ExtractedField[T]:
    """Representa el valor y la certeza de extracción de un campo documental."""

    value: T | None
    status: FieldExtractionStatus
    raw_text: str | None = None
    confidence: float = 1.0

    @classmethod
    def extracted(
        cls, value: T, raw_text: str | None = None, confidence: float = 1.0
    ) -> ExtractedField[T]:
        return cls(
            value=value,
            status=FieldExtractionStatus.EXTRAIDO,
            raw_text=raw_text,
            confidence=confidence,
        )

    @classmethod
    def not_present(cls) -> ExtractedField[T]:
        return cls(
            value=None,
            status=FieldExtractionStatus.NO_PRESENTE,
            raw_text=None,
            confidence=1.0,
        )

    @classmethod
    def not_recognized(cls, raw_text: str | None = None) -> ExtractedField[T]:
        return cls(
            value=None,
            status=FieldExtractionStatus.NO_RECONOCIDO,
            raw_text=raw_text,
            confidence=0.0,
        )

    @classmethod
    def requires_review(
        cls,
        value: T | None = None,
        raw_text: str | None = None,
        confidence: float = 0.5,
    ) -> ExtractedField[T]:
        return cls(
            value=value,
            status=FieldExtractionStatus.REQUIERE_REVISION,
            raw_text=raw_text,
            confidence=confidence,
        )

    @property
    def is_valid(self) -> bool:
        return self.status == FieldExtractionStatus.EXTRAIDO and self.value is not None


@dataclass(frozen=True)
class Matricula:
    """Representación inmutable de una matrícula de transporte nacional o extranjera."""

    valor: str
    raw: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if not self.valor or not str(self.valor).strip():
            raise ValidationException("La matrícula no puede estar vacía.")
        raw_val = self.raw if self.raw else str(self.valor)
        cleaned = re.sub(r"[\s\-.]", "", str(self.valor)).upper()
        if not cleaned:
            raise ValidationException("La matrícula no puede estar vacía.")
        if not re.match(r"^[A-Z0-9]+$", cleaned):
            raise ValidationException(f"La matrícula '{raw_val}' contiene caracteres inválidos.")
        if len(cleaned) < 3 or len(cleaned) > 15:
            raise ValidationException(
                f"Longitud de matrícula '{raw_val}' no válida ({len(cleaned)} caracteres). "
                f"Debe tener entre 3 y 15 caracteres alfanuméricos."
            )
        object.__setattr__(self, "valor", cleaned)
        object.__setattr__(self, "raw", raw_val.strip())

    def __str__(self) -> str:
        return self.valor


@dataclass(frozen=True)
class NIF:
    """Representación inmutable y normalizada de un NIF/CIF o Tax ID de transporte."""

    valor: str

    def __post_init__(self) -> None:
        if not self.valor or not str(self.valor).strip():
            raise ValidationException("El NIF/CIF no puede estar vacío.")
        cleaned = re.sub(r"[\s\-.]", "", str(self.valor)).upper()
        if not cleaned:
            raise ValidationException("El NIF/CIF no puede estar vacío.")
        if not re.match(r"^[A-Z0-9]+$", cleaned):
            raise ValidationException(f"El NIF/CIF '{self.valor}' contiene caracteres inválidos.")
        if len(cleaned) < 5 or len(cleaned) > 20:
            raise ValidationException(f"Formato de NIF/CIF inválido: '{self.valor}'")
        object.__setattr__(self, "valor", cleaned)

    def __str__(self) -> str:
        return self.valor


@dataclass(frozen=True)
class Weight:
    """Representación inmutable de peso en kilogramos."""

    kg: float

    def __post_init__(self) -> None:
        if self.kg <= 0:
            raise ValidationException("El peso de la mercancía debe ser mayor que 0 kg.")
        object.__setattr__(self, "kg", round(self.kg, 2))

    def __str__(self) -> str:
        return f"{self.kg:.2f} kg"


@dataclass(frozen=True)
class DeCAToken:
    """Token criptográfico de 256 bits para inspección pública."""

    token: str

    def __post_init__(self) -> None:
        if not self.token or len(self.token) < 32:
            raise ValidationException(
                "Token de acceso público inválido o con entropía insuficiente."
            )

    def __str__(self) -> str:
        return self.token

    def __len__(self) -> int:
        return len(self.token)


_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


@dataclass(frozen=True)
class EmailAddress:
    """Dirección de correo electrónico validada y normalizada según RFC 5322."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not isinstance(self.value, str):
            raise ValidationException("La dirección de correo electrónico no puede estar vacía.")
        clean = self.value.strip().lower()
        if len(clean) > 254 or not _EMAIL_REGEX.match(clean):
            raise ValidationException(
                f"Formato de correo electrónico inválido o no conforme: '{self.value}'"
            )
        object.__setattr__(self, "value", clean)

    @classmethod
    def create(cls, email: str | None) -> EmailAddress:
        """Factoría canónica para construir y validar una dirección de correo."""
        if email is None or not isinstance(email, str) or not email.strip():
            raise ValidationException("La dirección de correo electrónico no puede estar vacía.")
        return cls(email)

    @property
    def domain(self) -> str:
        """Retorna el dominio de la dirección de correo."""
        return self.value.split("@", 1)[1]

    @property
    def local_part(self) -> str:
        """Retorna la parte local (nombre de usuario) de la dirección de correo."""
        return self.value.split("@", 1)[0]

    def __str__(self) -> str:
        return self.value

    @property
    def masked(self) -> str:
        """Devuelve la dirección de correo enmascarada para observabilidad y privacidad."""
        return self.mask_str(self.value)

    @classmethod
    def is_valid(cls, email: str | None) -> bool:
        """Comprueba si una cadena representa un correo sintácticamente válido."""
        if not email or not isinstance(email, str):
            return False
        clean = email.strip()
        return len(clean) <= 254 and bool(_EMAIL_REGEX.match(clean))

    @classmethod
    def mask_str(cls, email: str | None) -> str:
        """Enmascara cualquier dirección de correo protegiendo la privacidad en logs."""
        if not email:
            return "***"
        clean = str(email).strip()
        if "@" not in clean:
            return f"{clean[:2]}***" if len(clean) >= 2 else "***"
        parts = clean.split("@", 1)
        local, domain = parts[0], parts[1]
        if len(local) <= 1:
            masked_local = "*"
        elif len(local) == 2:
            masked_local = f"{local[0]}*"
        elif len(local) == 3:
            masked_local = f"{local[:2]}*"
        else:
            masked_local = f"{local[:2]}***"
        return f"{masked_local}@{domain}"
