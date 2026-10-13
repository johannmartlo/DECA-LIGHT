from __future__ import annotations


def is_internal_id_collision(exc: Exception) -> bool:
    """Determina si una excepción de integridad física corresponde específicamente
    a una colisión de clave única en la restricción uq_expeditions_internal_id.

    Descarta categóricamente:
    - Violaciones de claves foráneas (FK, p.ej. company_id o carrier_id no configurados).
    - Violaciones de nulidad (NOT NULL).
    - Violaciones de restricciones CHECK.
    - Otras restricciones UNIQUE distintas de internal_id.
    """
    msg = str(exc).lower()

    # 1. Descartar explícitamente errores de clave foránea o nulidad
    if "foreign key" in msg or "not null" in msg or "foreignkey" in msg or "check constraint" in msg:
        return False

    # 2. Comprobación de diagnósticos nativos si están disponibles (PostgreSQL)
    orig = getattr(exc, "orig", None)
    if orig is not None:
        # PostgreSQL pgcode == '23505' (unique_violation)
        pgcode = getattr(orig, "pgcode", None)
        if pgcode is not None and pgcode != "23505":
            return False

        diag = getattr(orig, "diag", None)
        if diag is not None:
            constraint_name = getattr(diag, "constraint_name", None)
            if constraint_name:
                return constraint_name in (
                    "uq_expeditions_company_internal_id",
                    "uq_expeditions_internal_id",
                )

    # 3. Comprobación textual sobre SQLite o drivers estándar
    if (
        "uq_expeditions_company_internal_id" in msg
        or "uq_expeditions_internal_id" in msg
    ):
        return True
    if "unique constraint failed" in msg and "internal_id" in msg:
        return True
    if "unique" in msg and "internal_id" in msg and "expeditions" in msg:
        return True

    return False
