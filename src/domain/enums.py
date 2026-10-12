from __future__ import annotations

from enum import StrEnum


class ExpeditionStatus(StrEnum):
    """Estados del ciclo de vida operativo de una expedición."""

    IMPORTADA = "IMPORTADA"
    PENDIENTE_REVISION = "PENDIENTE_REVISION"
    PENDIENTE_MATRICULA = "PENDIENTE_MATRICULA"
    LISTA_PARA_DECA = "LISTA_PARA_DECA"
    DECA_GENERADO = "DECA_GENERADO"
    ENVIADA = "ENVIADA"
    ERROR = "ERROR"
    CANCELADA = "CANCELADA"


class VehicleType(StrEnum):
    """Tipificación estricta de vehículos según requerimientos de tracción y carga."""

    RIGIDO = "RIGIDO"
    ARTICULADO = "ARTICULADO"

    @classmethod
    def from_str(cls, val: str | VehicleType) -> VehicleType:
        if isinstance(val, cls):
            return val
        s = str(val).upper().strip()
        if "RIGID" in s:
            return cls.RIGIDO
        if "ARTICUL" in s or "TRAILER" in s or "REMOLQUE" in s:
            return cls.ARTICULADO
        raise ValueError(f"Tipo de vehículo desconocido o incompatible: '{val}'")


class DeCAStatus(StrEnum):
    """Estados documentales y legales del DeCA."""

    ISSUED = "ISSUED"
    MODIFIED = "MODIFIED"
    REVOKED = "REVOKED"
    EXPIRED_PUBLIC = "EXPIRED_PUBLIC"


class DocumentProcessingStatus(StrEnum):
    """Estado de importación y análisis del documento fuente."""

    PENDING = "PENDING"
    PARSED_OK = "PARSED_OK"
    PARSED_ERROR = "PARSED_ERROR"
    DUPLICATE = "DUPLICATE"


class DocumentFormatType(StrEnum):
    """Formatos documentales de transporte soportados."""

    CARTA_DE_PORTE = "CARTA_DE_PORTE"
    CMR = "CMR"
    DESCONOCIDO = "DESCONOCIDO"


class FieldExtractionStatus(StrEnum):
    """Calidad y estado de extracción de cada campo individual del documento."""

    EXTRAIDO = "EXTRAIDO"
    NO_PRESENTE = "NO_PRESENTE"
    NO_RECONOCIDO = "NO_RECONOCIDO"
    REQUIERE_REVISION = "REQUIERE_REVISION"


class EmailDeliveryStatus(StrEnum):
    """Estado del ciclo de vida de entrega de correo electrónico al transportista."""

    PENDING = "PENDING"
    EMAIL_PENDING = "EMAIL_PENDING"
    EMAIL_SENDING = "EMAIL_SENDING"
    EMAIL_SENT = "EMAIL_SENT"
    EMAIL_FAILED = "EMAIL_FAILED"
    EMAIL_RETRY_PENDING = "EMAIL_RETRY_PENDING"
    RETRYING = "RETRYING"


class AuditAction(StrEnum):
    """Acciones auditadas formalmente en el sistema."""

    DOCUMENT_IMPORTED = "DOCUMENT_IMPORTED"
    DATA_EXTRACTED = "DATA_EXTRACTED"
    EXPEDITION_CREATED = "EXPEDITION_CREATED"
    VEHICLE_ASSIGNED = "VEHICLE_ASSIGNED"
    VEHICLE_UPDATED = "VEHICLE_UPDATED"
    CARRIER_ASSIGNED = "CARRIER_ASSIGNED"
    VALIDATION_EXECUTED = "VALIDATION_EXECUTED"
    VALIDATION_PASSED = "VALIDATION_PASSED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    EXPEDITION_READY_FOR_DECA = "EXPEDITION_READY_FOR_DECA"
    DECA_EMISSION_STARTED = "DECA_EMISSION_STARTED"
    DECA_EMITTED = "DECA_EMITTED"
    DECA_EMISSION_FAILED = "DECA_EMISSION_FAILED"
    DECA_GENERATED = "DECA_GENERATED"
    DECA_MODIFIED = "DECA_MODIFIED"
    EMAIL_SEND_REQUESTED = "EMAIL_SEND_REQUESTED"
    EMAIL_SENT = "EMAIL_SENT"
    EMAIL_FAILED = "EMAIL_FAILED"
    EMAIL_SEND_FAILED = "EMAIL_SEND_FAILED"
    EMAIL_SEND_RETRY = "EMAIL_SEND_RETRY"
    EMAIL_RESEND_REQUESTED = "EMAIL_RESEND_REQUESTED"
    DECA_DOWNLOADED = "DECA_DOWNLOADED"
    PUBLIC_DECA_ACCESS_SUCCESS = "PUBLIC_DECA_ACCESS_SUCCESS"
    PUBLIC_DECA_ACCESS_NOT_FOUND = "PUBLIC_DECA_ACCESS_NOT_FOUND"
    PUBLIC_DECA_ACCESS_EXPIRED = "PUBLIC_DECA_ACCESS_EXPIRED"
    COMPANY_DETECTED = "COMPANY_DETECTED"
    COMPANY_ACCESS_DENIED = "COMPANY_ACCESS_DENIED"
