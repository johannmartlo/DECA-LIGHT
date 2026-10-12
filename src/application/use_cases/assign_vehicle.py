from __future__ import annotations

import logging
import uuid

from src.application.dtos.vehicle_assignment_dto import (
    AssignVehicleInputDTO,
    AssignVehicleResultDTO,
)
from src.application.ports.audit_service import AuditServicePort
from src.application.ports.expedition_repository import ExpeditionRepositoryPort
from src.domain.entities.audit_event import AuditEvent
from src.domain.entities.expedition import Expedition
from src.domain.enums import AuditAction, ExpeditionStatus, VehicleType
from src.domain.exceptions import (
    EntityNotFoundException,
    InvalidStateTransitionException,
    InvalidVehicleConfigurationException,
)
from src.domain.services.deca_validator import DeCAValidator
from src.domain.services.vehicle_normalizer import VehicleRegistrationNormalizer

logger = logging.getLogger("deca_light.use_cases.assign_vehicle")


class AssignVehicleToExpeditionUseCase:
    """Caso de uso operativo para asignación y normalización de vehículos y transportistas."""

    def __init__(
        self,
        expedition_repo: ExpeditionRepositoryPort,
        audit_service: AuditServicePort | None = None,
    ) -> None:
        self.expedition_repo = expedition_repo
        self.audit_service = audit_service

    def execute(self, input_dto: AssignVehicleInputDTO) -> AssignVehicleResultDTO:
        # 1. Comprobar que la expedición existe
        exp_id = (
            uuid.UUID(str(input_dto.expedition_id))
            if not isinstance(input_dto.expedition_id, uuid.UUID)
            else input_dto.expedition_id
        )
        expedition: Expedition | None = self.expedition_repo.get_by_id(exp_id)
        if not expedition:
            raise EntityNotFoundException(
                f"Expedición con ID '{input_dto.expedition_id}' no encontrada."
            )

        # 2. Comprobar estado compatible
        if expedition.status == ExpeditionStatus.PENDIENTE_REVISION:
            raise InvalidStateTransitionException(
                "Una expedición en PENDIENTE_REVISION no puede recibir asignación de vehículo "
                "ni pasar a LISTA_PARA_DECA sin resolver la revisión previa."
            )
        if expedition.status in (ExpeditionStatus.CANCELADA, ExpeditionStatus.ENVIADA):
            raise InvalidStateTransitionException(
                "No se puede modificar el vehículo de una expedición en estado terminal "
                f"({expedition.status})."
            )

        # 3. Normalizar matrículas
        norm_tractor = VehicleRegistrationNormalizer.normalize(input_dto.tractor_registration)
        norm_trailer = VehicleRegistrationNormalizer.normalize(input_dto.trailer_registration)

        if norm_tractor is None or not norm_tractor.valor:
            raise InvalidVehicleConfigurationException("La matrícula no puede estar vacía.")

        # 4. Validar combinación vehículo/matrículas
        v_type = VehicleType.from_str(input_dto.vehicle_type)

        if v_type == VehicleType.RIGIDO and norm_trailer is not None and norm_trailer.valor:
            raise InvalidVehicleConfigurationException(
                "Un vehículo rígido no puede tener remolque o semirremolque asignado."
            )
        if v_type == VehicleType.ARTICULADO and (norm_trailer is None or not norm_trailer.valor):
            raise InvalidVehicleConfigurationException(
                "Un conjunto articulado exige obligatoriamente la matrícula "
                "del semirremolque/remolque."
            )

        # 5. Comprobación de idempotencia (asignar dos veces exactamente lo mismo)
        is_same_vehicle = (
            expedition.vehicle_type == v_type
            and expedition.tractor_plate == norm_tractor
            and expedition.trailer_plate == norm_trailer
        )
        is_same_carrier = True
        if input_dto.carrier_name and input_dto.carrier_name.strip() != expedition.carrier_name_raw:
            is_same_carrier = False
        if input_dto.carrier_tax_id and str(input_dto.carrier_tax_id).strip() != str(
            expedition.carrier_tax_id or ""
        ):
            is_same_carrier = False
        if input_dto.carrier_email is not None and input_dto.carrier_email.strip() != (
            expedition.carrier_email or ""
        ):
            is_same_carrier = False

        if is_same_vehicle and is_same_carrier:
            validation = DeCAValidator.validate(expedition)
            return AssignVehicleResultDTO(
                expedition_id=str(expedition.id),
                internal_id=expedition.internal_id,
                status=expedition.status,
                vehicle_type=v_type,
                tractor_plate=str(norm_tractor),
                trailer_plate=str(norm_trailer) if norm_trailer else None,
                carrier_name=expedition.carrier_name_raw,
                carrier_tax_id=str(expedition.carrier_tax_id)
                if expedition.carrier_tax_id
                else None,
                carrier_email=expedition.carrier_email,
                validation=validation,
                is_ready_for_deca=(expedition.status == ExpeditionStatus.LISTA_PARA_DECA),
                message="Operación idempotente: los datos del vehículo ya estaban asignados.",
                audit_events_recorded=[],
            )

        events_recorded: list[str] = []
        is_first_assignment = expedition.vehicle_type is None
        old_vehicle_state = {
            "vehicle_type": str(expedition.vehicle_type) if expedition.vehicle_type else None,
            "tractor_plate": str(expedition.tractor_plate) if expedition.tractor_plate else None,
            "trailer_plate": str(expedition.trailer_plate) if expedition.trailer_plate else None,
        }
        new_vehicle_state = {
            "vehicle_type": str(v_type),
            "tractor_plate": str(norm_tractor),
            "trailer_plate": str(norm_trailer) if norm_trailer else None,
        }

        # 6. Actualizar datos del transportista si se proporcionan
        if (
            input_dto.carrier_name
            or input_dto.carrier_tax_id
            or input_dto.carrier_email is not None
        ):
            old_carrier_state = {
                "carrier_name": expedition.carrier_name_raw,
                "carrier_tax_id": str(expedition.carrier_tax_id)
                if expedition.carrier_tax_id
                else None,
                "carrier_email": expedition.carrier_email,
            }
            expedition.update_carrier(
                carrier_name=input_dto.carrier_name,
                carrier_tax_id=input_dto.carrier_tax_id,
                carrier_email=input_dto.carrier_email,
            )
            if self.audit_service:
                self.audit_service.record(
                    AuditEvent(
                        action=AuditAction.CARRIER_ASSIGNED,
                        user_identifier=input_dto.actor,
                        entity_name="EXPEDITION",
                        entity_id=expedition.id,
                        old_state=old_carrier_state,
                        new_state={
                            "carrier_name": expedition.carrier_name_raw,
                            "carrier_tax_id": str(expedition.carrier_tax_id)
                            if expedition.carrier_tax_id
                            else None,
                            "carrier_email": expedition.carrier_email,
                        },
                    )
                )
                events_recorded.append(AuditAction.CARRIER_ASSIGNED)

        # 7. Asignar el vehículo a la entidad de Dominio
        expedition.assign_vehicle(v_type, norm_tractor, norm_trailer)

        vehicle_action = (
            AuditAction.VEHICLE_ASSIGNED if is_first_assignment else AuditAction.VEHICLE_UPDATED
        )
        if self.audit_service:
            self.audit_service.record(
                AuditEvent(
                    action=vehicle_action,
                    user_identifier=input_dto.actor,
                    entity_name="EXPEDITION",
                    entity_id=expedition.id,
                    old_state=old_vehicle_state if not is_first_assignment else None,
                    new_state=new_vehicle_state,
                )
            )
            events_recorded.append(vehicle_action)

        # 8. Ejecutar DeCAValidator
        validation = DeCAValidator.validate(expedition)
        if self.audit_service:
            self.audit_service.record(
                AuditEvent(
                    action=AuditAction.VALIDATION_EXECUTED,
                    user_identifier=input_dto.actor,
                    entity_name="EXPEDITION",
                    entity_id=expedition.id,
                    new_state={
                        "valid": validation.valid,
                        "error_count": len(validation.errors),
                        "warning_count": len(validation.warnings),
                        "error_codes": [e.code for e in validation.errors],
                    },
                )
            )
            events_recorded.append(AuditAction.VALIDATION_EXECUTED)

        # 9. Transición de estado basada en la validación
        if validation.valid:
            expedition.status = ExpeditionStatus.LISTA_PARA_DECA
            status_message = (
                "Vehículo asignado y validación superada. La expedición está LISTA_PARA_DECA."
            )
            if self.audit_service:
                self.audit_service.record(
                    AuditEvent(
                        action=AuditAction.EXPEDITION_READY_FOR_DECA,
                        user_identifier=input_dto.actor,
                        entity_name="EXPEDITION",
                        entity_id=expedition.id,
                        new_state={
                            "internal_id": expedition.internal_id,
                            "status": str(expedition.status),
                        },
                    )
                )
                events_recorded.append(AuditAction.EXPEDITION_READY_FOR_DECA)
        else:
            expedition.status = ExpeditionStatus.PENDIENTE_MATRICULA
            reasons = ", ".join(e.code for e in validation.errors)
            status_message = (
                f"Vehículo asignado, pero la expedición queda bloqueada por: {reasons}."
            )
            if self.audit_service:
                self.audit_service.record(
                    AuditEvent(
                        action=AuditAction.VALIDATION_FAILED,
                        user_identifier=input_dto.actor,
                        entity_name="EXPEDITION",
                        entity_id=expedition.id,
                        new_state={"errors": [e.code for e in validation.errors]},
                    )
                )
                events_recorded.append(AuditAction.VALIDATION_FAILED)

        # 10. Persistir cambios
        self.expedition_repo.save(expedition)

        return AssignVehicleResultDTO(
            expedition_id=str(expedition.id),
            internal_id=expedition.internal_id,
            status=expedition.status,
            vehicle_type=v_type,
            tractor_plate=str(norm_tractor),
            trailer_plate=str(norm_trailer) if norm_trailer else None,
            carrier_name=expedition.carrier_name_raw,
            carrier_tax_id=str(expedition.carrier_tax_id) if expedition.carrier_tax_id else None,
            carrier_email=expedition.carrier_email,
            validation=validation,
            is_ready_for_deca=(expedition.status == ExpeditionStatus.LISTA_PARA_DECA),
            message=status_message,
            audit_events_recorded=events_recorded,
        )
