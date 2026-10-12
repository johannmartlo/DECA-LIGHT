from __future__ import annotations

import re

from src.domain.exceptions import InvalidVehicleRegistrationException
from src.domain.value_objects import Matricula


class VehicleRegistrationNormalizer:
    """Normalizador determinista de matrículas de transporte nacionales y extranjeras.

    Reglas de negocio (Prompt 04):
    - Elimina espacios innecesarios iniciales, intermedios y finales.
    - Normaliza a mayúsculas.
    - Normaliza separadores no significativos (espacios, guiones, puntos).
    - Conserva tanto el valor normalizado como el original introducido para auditoría.
    - Rechaza silencios y caracteres inválidos (símbolos, signos de puntuación extraños).
    - Soporta matrículas españolas (ej. '1234 BCD', 'R-1234-BBB')
      e internacionales (ej. 'AA-123-AA', 'B-MW 1234').
    - Validación sintáctica razonable: caracteres [A-Z0-9] con longitud de 3 a 15 caracteres.
    """

    @classmethod
    def normalize(cls, raw: str | None) -> Matricula | None:
        """Normaliza una matrícula.

        Si raw es None o una cadena vacía tras strip, retorna None.
        Lanza ValidationException o InvalidVehicleRegistrationException si contiene
        caracteres inválidos o longitud fuera de rango.
        """
        if raw is None:
            return None

        stripped = raw.strip()
        if not stripped:
            return None

        cleaned = re.sub(r"[\s\-.]", "", stripped).upper()
        if not cleaned:
            raise InvalidVehicleRegistrationException("La matrícula no puede estar vacía.")

        if not re.match(r"^[A-Z0-9]+$", cleaned):
            raise InvalidVehicleRegistrationException(
                f"La matrícula '{raw}' contiene caracteres o símbolos no permitidos."
            )

        if len(cleaned) < 3 or len(cleaned) > 15:
            raise InvalidVehicleRegistrationException(
                f"Longitud de matrícula '{raw}' no válida ({len(cleaned)} caracteres). "
                f"Debe tener entre 3 y 15 caracteres alfanuméricos."
            )

        return Matricula(valor=cleaned, raw=stripped)
