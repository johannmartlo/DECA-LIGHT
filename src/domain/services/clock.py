from __future__ import annotations

from datetime import UTC, datetime, timedelta


class Clock:
    """Proveedor determinista de tiempo del sistema para desacoplar el dominio del reloj del SO."""

    _frozen_time: datetime | None = None

    @classmethod
    def now(cls) -> datetime:
        """Devuelve el instante actual en UTC o el instante congelado para tests."""
        if cls._frozen_time is not None:
            return cls._frozen_time
        return datetime.now(UTC)

    @classmethod
    def freeze(cls, fixed_time: datetime) -> None:
        """Congela el reloj en una fecha/hora fija (para pruebas deterministas)."""
        if fixed_time.tzinfo is None:
            fixed_time = fixed_time.replace(tzinfo=UTC)
        cls._frozen_time = fixed_time

    @classmethod
    def advance(cls, **delta_kwargs) -> None:
        """Avanza el reloj congelado en el tiempo especificado (ej. days=8, hours=2)."""
        if cls._frozen_time is None:
            cls._frozen_time = datetime.now(UTC)
        cls._frozen_time += timedelta(**delta_kwargs)

    @classmethod
    def unfreeze(cls) -> None:
        """Restaura el reloj al tiempo real del sistema."""
        cls._frozen_time = None
