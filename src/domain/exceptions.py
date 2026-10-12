"""Excepciones puras de la capa de dominio de DECA Light."""


class DomainException(Exception):
    """Excepción base para todos los errores de la capa de dominio."""


class EntityNotFoundException(DomainException):
    """Lanzada cuando una entidad de negocio requerida no existe."""


class ValidationException(DomainException, ValueError):
    """Lanzada cuando una entidad o Value Object incumple reglas de negocio o normativas."""


class InvalidVehicleConfigurationException(ValidationException):
    """Lanzada cuando la matrícula o combinación de vehículos es inválida para su tipo."""


class DuplicateEntityException(DomainException):
    """Lanzada cuando se intenta registrar una entidad que colisiona con una clave única."""


class InvalidStateTransitionException(DomainException):
    """Lanzada cuando se intenta una transición de estado ilegal en el ciclo de vida."""


class InvalidVehicleRegistrationException(ValidationException):
    """Lanzada cuando una matrícula contiene sintaxis o caracteres inadmisibles."""


class ExpeditionNotReadyException(DomainException):
    """Lanzada cuando se intenta emitir DeCA para una expedición incompleta."""


class ImmutableDeCAException(DomainException):
    """Lanzada cuando se intenta alterar o sobrescribir un DeCA o snapshot ya emitido."""


class DeCAEmissionException(DomainException):
    """Lanzada cuando falla la emisión de un DeCA por no superar la validación legal."""


class StorageException(DomainException):
    """Lanzada ante un error o violación de seguridad en el almacenamiento de documentos."""


class CompanyMismatchException(DomainException):
    """Lanzada cuando los datos de una expedición/DeCA no corresponden a la empresa emisora."""


class CompanyNotConfiguredException(DomainException):
    """Lanzada cuando la empresa emisora no existe, está inactiva o carece de configuración."""
