from __future__ import annotations

import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest

from src.application.dtos.vehicle_assignment_dto import AssignVehicleInputDTO
from src.application.use_cases.assign_vehicle import AssignVehicleToExpeditionUseCase
from src.application.use_cases.validate_expedition import ValidateExpeditionUseCase
from src.domain.entities.expedition import Expedition
from src.domain.enums import AuditAction, ExpeditionStatus, VehicleType
from src.domain.exceptions import (
    InvalidStateTransitionException,
    InvalidVehicleConfigurationException,
    InvalidVehicleRegistrationException,
    ValidationException,
)
from src.domain.services.deca_validator import DeCAValidator
from src.domain.services.vehicle_normalizer import VehicleRegistrationNormalizer
from src.domain.value_objects import NIF, Matricula, Weight
from src.infrastructure.logging.in_memory_audit_service import InMemoryAuditService
from src.infrastructure.repositories.in_memory_expedition_repository import (
    InMemoryExpeditionRepository,
)


def make_valid_expedition(
    *,
    status: ExpeditionStatus = ExpeditionStatus.PENDIENTE_MATRICULA,
    shipper_name: str = "Tomates de Autor S.L.",
    carrier_name: str = "Transportes Almería S.L.",
    carrier_tax_id: str = "B04123456",
    carrier_email: str | None = "trafico@transportesalmeria.com",
    origin: str = "El Ejido (Almería)",
    destination: str = "Mercamadrid (Madrid)",
    goods: str = "Tomate Rama Extra",
    weight_kg: float = 18500.0,
    reference: str = "ALB-2026-9999",
    internal_id: str = "TD-2026-00001",
) -> Expedition:
    """Crea una entidad Expedition válida con datos completos lista para asignación o validación."""
    return Expedition(
        id=uuid.uuid4(),
        internal_id=internal_id,
        reference=reference,
        fiscal_year="2026",
        transport_date=date.today(),
        shipper_name=shipper_name,
        shipper_tax_id=NIF("B12345678") if shipper_name else None,
        shipper_address="Polígono La Redonda, Almería",
        carrier_name_raw=carrier_name,
        carrier_tax_id=NIF(carrier_tax_id) if carrier_tax_id else None,
        carrier_email=carrier_email,
        origin=origin,
        destination=destination,
        goods=goods,
        weight=Weight(weight_kg) if weight_kg > 0 else None,
        observations="Conservar entre 10 y 12 grados",
        status=status,
    )


# =========================================================================
# 1. Asignación correcta de vehículo rígido
# =========================================================================
def test_01_assign_vehicle_rigid_success() -> None:
    repo = InMemoryExpeditionRepository()
    audit = InMemoryAuditService()
    exp = make_valid_expedition()
    repo.save(exp)

    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo, audit_service=audit)
    input_dto = AssignVehicleInputDTO(
        expedition_id=exp.id,
        vehicle_type="RIGIDO",
        tractor_registration="1234-BCD",
        trailer_registration=None,
        actor="OPERATOR_1",
    )

    result = use_case.execute(input_dto)

    assert result.status == ExpeditionStatus.LISTA_PARA_DECA
    assert result.is_ready_for_deca is True
    assert result.vehicle_type == VehicleType.RIGIDO
    assert result.tractor_plate == "1234BCD"
    assert result.trailer_plate is None
    assert result.validation.valid is True
    assert len(result.validation.errors) == 0

    saved_exp = repo.get_by_id(exp.id)
    assert saved_exp.status == ExpeditionStatus.LISTA_PARA_DECA
    assert saved_exp.tractor_plate == Matricula("1234BCD")
    assert saved_exp.tractor_plate.raw == "1234-BCD"
    assert saved_exp.trailer_plate is None


# =========================================================================
# 2. Asignación correcta de conjunto articulado
# =========================================================================
def test_02_assign_vehicle_articulated_success() -> None:
    repo = InMemoryExpeditionRepository()
    audit = InMemoryAuditService()
    exp = make_valid_expedition()
    repo.save(exp)

    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo, audit_service=audit)
    input_dto = AssignVehicleInputDTO(
        expedition_id=exp.id,
        vehicle_type="ARTICULADO",
        tractor_registration="1234 BCD",
        trailer_registration="R 5678 XYZ",
        actor="OPERATOR_1",
    )

    result = use_case.execute(input_dto)

    assert result.status == ExpeditionStatus.LISTA_PARA_DECA
    assert result.is_ready_for_deca is True
    assert result.vehicle_type == VehicleType.ARTICULADO
    assert result.tractor_plate == "1234BCD"
    assert result.trailer_plate == "R5678XYZ"
    assert result.validation.valid is True


# =========================================================================
# 3. Matrícula vacía
# =========================================================================
def test_03_empty_vehicle_registration_rejected() -> None:
    repo = InMemoryExpeditionRepository()
    exp = make_valid_expedition()
    repo.save(exp)
    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo)

    # Espacio en blanco o vacía en el caso de uso
    with pytest.raises(InvalidVehicleConfigurationException, match="no puede estar vacía"):
        use_case.execute(
            AssignVehicleInputDTO(
                expedition_id=exp.id,
                vehicle_type="RIGIDO",
                tractor_registration="   ",
            )
        )

    # Directamente en el Value Object
    with pytest.raises(ValidationException, match="no puede estar vacía"):
        Matricula("")

    # Directamente en el Normalizador
    assert VehicleRegistrationNormalizer.normalize("") is None
    assert VehicleRegistrationNormalizer.normalize("   ") is None


# =========================================================================
# 4. Matrícula sintácticamente inválida
# =========================================================================
def test_04_syntactically_invalid_registration_rejected() -> None:
    # Caracteres no permitidos
    with pytest.raises(InvalidVehicleRegistrationException, match="no permitidos"):
        VehicleRegistrationNormalizer.normalize("1234@#$")

    # Longitud insuficiente (<3 caracteres)
    with pytest.raises(InvalidVehicleRegistrationException, match="Longitud de matrícula"):
        VehicleRegistrationNormalizer.normalize("AB")

    # Longitud excesiva (>15 caracteres alfanuméricos)
    with pytest.raises(InvalidVehicleRegistrationException, match="Longitud de matrícula"):
        VehicleRegistrationNormalizer.normalize("A" * 16)


# =========================================================================
# 5. Rígido con remolque (incompatible)
# =========================================================================
def test_05_rigid_with_trailer_incompatible_rejected() -> None:
    repo = InMemoryExpeditionRepository()
    exp = make_valid_expedition()
    repo.save(exp)
    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo)

    with pytest.raises(
        InvalidVehicleConfigurationException, match="no puede tener remolque o semirremolque"
    ):
        use_case.execute(
            AssignVehicleInputDTO(
                expedition_id=exp.id,
                vehicle_type="RIGIDO",
                tractor_registration="1234BCD",
                trailer_registration="R1234BCD",
            )
        )

    # Entidad de dominio pura
    with pytest.raises(
        InvalidVehicleConfigurationException,
        match="no puede tener asignada una matrícula de remolque",
    ):
        exp.assign_vehicle(VehicleType.RIGIDO, "1234BCD", "R1234BCD")


# =========================================================================
# 6. Articulado sin tractora
# =========================================================================
def test_06_articulated_missing_tractor_rejected() -> None:
    repo = InMemoryExpeditionRepository()
    exp = make_valid_expedition()
    repo.save(exp)
    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo)

    with pytest.raises(InvalidVehicleConfigurationException, match="no puede estar vacía"):
        use_case.execute(
            AssignVehicleInputDTO(
                expedition_id=exp.id,
                vehicle_type="ARTICULADO",
                tractor_registration="",
                trailer_registration="R1234BCD",
            )
        )

    # Verificación en DeCAValidator
    exp.vehicle_type = VehicleType.ARTICULADO
    exp.tractor_plate = None
    exp.trailer_plate = Matricula("R1234BCD")
    validation = DeCAValidator.validate(exp)
    assert validation.valid is False
    assert any(e.code == "TRACTOR_REGISTRATION_MISSING" for e in validation.errors)


# =========================================================================
# 7. Articulado sin semirremolque
# =========================================================================
def test_07_articulated_missing_trailer_rejected() -> None:
    repo = InMemoryExpeditionRepository()
    exp = make_valid_expedition()
    repo.save(exp)
    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo)

    with pytest.raises(
        InvalidVehicleConfigurationException,
        match="exige obligatoriamente la matrícula del semirremolque",
    ):
        use_case.execute(
            AssignVehicleInputDTO(
                expedition_id=exp.id,
                vehicle_type="ARTICULADO",
                tractor_registration="1234BCD",
                trailer_registration=None,
            )
        )


# =========================================================================
# 8. Matrícula extranjera válida (Francia, Alemania, Países Bajos, etc.)
# =========================================================================
def test_08_valid_international_plates_accepted() -> None:
    # Francia: formato AB-123-CD
    fr = VehicleRegistrationNormalizer.normalize("AB-123-CD")
    assert fr is not None
    assert fr.valor == "AB123CD"
    assert fr.raw == "AB-123-CD"

    # Alemania: formato B-MW 1234
    de = VehicleRegistrationNormalizer.normalize("B-MW 1234")
    assert de is not None
    assert de.valor == "BMW1234"

    # Países Bajos: formato 12-AB-34
    nl = VehicleRegistrationNormalizer.normalize("12-AB-34")
    assert nl is not None
    assert nl.valor == "12AB34"

    # Portugal: formato 01-AB-23
    pt = VehicleRegistrationNormalizer.normalize("01-AB-23")
    assert pt is not None
    assert pt.valor == "01AB23"

    # Caso de uso con tractora francesa y semirremolque alemán
    repo = InMemoryExpeditionRepository()
    exp = make_valid_expedition()
    repo.save(exp)
    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo)

    result = use_case.execute(
        AssignVehicleInputDTO(
            expedition_id=exp.id,
            vehicle_type="ARTICULADO",
            tractor_registration="AB-123-CD",
            trailer_registration="B-MW 1234",
        )
    )
    assert result.status == ExpeditionStatus.LISTA_PARA_DECA
    assert result.tractor_plate == "AB123CD"
    assert result.trailer_plate == "BMW1234"


# =========================================================================
# 9. Transportista ausente
# =========================================================================
def test_09_missing_carrier_prevents_ready_for_deca() -> None:
    repo = InMemoryExpeditionRepository()
    # Expedición sin transportista
    exp = make_valid_expedition(carrier_name="", carrier_tax_id="")
    exp.carrier_name_raw = ""
    exp.carrier_tax_id = None
    repo.save(exp)

    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo)
    result = use_case.execute(
        AssignVehicleInputDTO(
            expedition_id=exp.id,
            vehicle_type="RIGIDO",
            tractor_registration="1234BCD",
        )
    )

    # Asigna vehículo pero queda bloqueada en PENDIENTE_MATRICULA
    assert result.status == ExpeditionStatus.PENDIENTE_MATRICULA
    assert result.is_ready_for_deca is False
    assert result.validation.valid is False
    error_codes = [e.code for e in result.validation.errors]
    assert "CARRIER_MISSING" in error_codes
    assert "CARRIER_TAX_ID_MISSING" in error_codes


# =========================================================================
# 10. Transportista completo
# =========================================================================
def test_10_complete_carrier_enables_ready_for_deca() -> None:
    repo = InMemoryExpeditionRepository()
    # Inicialmente sin transportista
    exp = make_valid_expedition(carrier_name="", carrier_tax_id="")
    exp.carrier_name_raw = ""
    exp.carrier_tax_id = None
    repo.save(exp)

    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo)
    # Se introduce el transportista al mismo tiempo que el vehículo
    result = use_case.execute(
        AssignVehicleInputDTO(
            expedition_id=exp.id,
            vehicle_type="RIGIDO",
            tractor_registration="1234BCD",
            carrier_name="LOGISTICA DEL SUR S.L.",
            carrier_tax_id="B04998877",
            carrier_email="trafico@sur.com",
        )
    )

    assert result.status == ExpeditionStatus.LISTA_PARA_DECA
    assert result.is_ready_for_deca is True
    assert result.carrier_name == "LOGISTICA DEL SUR S.L."
    assert result.carrier_tax_id == "B04998877"
    assert result.carrier_email == "trafico@sur.com"


# =========================================================================
# 11. NIF/CIF inválido
# =========================================================================
def test_11_invalid_carrier_tax_id_rejected() -> None:
    # Caracteres no permitidos en NIF
    with pytest.raises(ValidationException, match="caracteres inválidos"):
        NIF("B-1234#56")

    # Longitud fuera de rango
    with pytest.raises(ValidationException, match="inválido"):
        NIF("12")

    # Verificación en DeCAValidator
    exp = make_valid_expedition()
    # Manipulamos carrier_tax_id para probar detección en validator
    object.__setattr__(exp, "carrier_tax_id", "XYZ")
    validation = DeCAValidator.validate(exp)
    assert validation.valid is False
    assert any(e.code == "CARRIER_TAX_ID_INVALID" for e in validation.errors)


# =========================================================================
# 12. Expedición lista para DeCA
# =========================================================================
def test_12_expedition_ready_for_deca_all_invariants_met() -> None:
    exp = make_valid_expedition()
    exp.assign_vehicle(VehicleType.RIGIDO, "1234BCD")
    validation = DeCAValidator.validate(exp)

    assert validation.valid is True
    assert len(validation.errors) == 0

    exp.transition_to(ExpeditionStatus.LISTA_PARA_DECA)
    assert exp.status == ExpeditionStatus.LISTA_PARA_DECA


# =========================================================================
# 13. Transición bloqueada por error
# =========================================================================
def test_13_state_transition_blocked_by_missing_data() -> None:
    repo = InMemoryExpeditionRepository()
    audit = InMemoryAuditService()
    # Expedición sin peso válido
    exp = make_valid_expedition()
    exp.weight = None
    repo.save(exp)

    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo, audit_service=audit)
    result = use_case.execute(
        AssignVehicleInputDTO(
            expedition_id=exp.id,
            vehicle_type="RIGIDO",
            tractor_registration="1234BCD",
        )
    )

    # Queda retenida en PENDIENTE_MATRICULA
    assert result.status == ExpeditionStatus.PENDIENTE_MATRICULA
    assert result.is_ready_for_deca is False
    assert any(e.code == "WEIGHT_INVALID" for e in result.validation.errors)

    events = audit.get_events(exp.id)
    assert any(e.action == AuditAction.VALIDATION_FAILED for e in events)


# =========================================================================
# 14. PENDIENTE_REVISION no puede saltar a LISTA_PARA_DECA
# =========================================================================
def test_14_pendiente_revision_cannot_transition_to_lista_para_deca() -> None:
    repo = InMemoryExpeditionRepository()
    exp = make_valid_expedition(status=ExpeditionStatus.PENDIENTE_REVISION)
    repo.save(exp)

    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo)
    with pytest.raises(InvalidStateTransitionException, match="PENDIENTE_REVISION"):
        use_case.execute(
            AssignVehicleInputDTO(
                expedition_id=exp.id,
                vehicle_type="RIGIDO",
                tractor_registration="1234BCD",
            )
        )

    # Intento de transición directa en la entidad
    with pytest.raises(InvalidStateTransitionException, match="PENDIENTE_REVISION"):
        exp.transition_to(ExpeditionStatus.LISTA_PARA_DECA)


# =========================================================================
# 15. Idempotencia de asignación de vehículo
# =========================================================================
def test_15_assign_vehicle_idempotency() -> None:
    repo = InMemoryExpeditionRepository()
    audit = InMemoryAuditService()
    exp = make_valid_expedition()
    repo.save(exp)
    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo, audit_service=audit)

    dto = AssignVehicleInputDTO(
        expedition_id=exp.id,
        vehicle_type="RIGIDO",
        tractor_registration="1234BCD",
    )

    # Primer intento
    res1 = use_case.execute(dto)
    assert res1.status == ExpeditionStatus.LISTA_PARA_DECA
    assert len(res1.audit_events_recorded) > 0

    events_count_first = len(audit.get_events(exp.id))

    # Segundo intento idéntico
    res2 = use_case.execute(dto)
    assert res2.status == ExpeditionStatus.LISTA_PARA_DECA
    assert res2.is_ready_for_deca is True
    assert "idempotente" in res2.message.lower()
    assert len(res2.audit_events_recorded) == 0

    # No se generaron eventos de auditoría duplicados
    assert len(audit.get_events(exp.id)) == events_count_first


# =========================================================================
# 16. Modificación de matrícula (auditoría VEHICLE_UPDATED)
# =========================================================================
def test_16_modify_plate_records_vehicle_updated_audit() -> None:
    repo = InMemoryExpeditionRepository()
    audit = InMemoryAuditService()
    exp = make_valid_expedition()
    repo.save(exp)
    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo, audit_service=audit)

    # Primera asignación
    use_case.execute(
        AssignVehicleInputDTO(
            expedition_id=exp.id,
            vehicle_type="RIGIDO",
            tractor_registration="1234BCD",
        )
    )

    # Modificación de matrícula por corrección de muelle
    res_mod = use_case.execute(
        AssignVehicleInputDTO(
            expedition_id=exp.id,
            vehicle_type="RIGIDO",
            tractor_registration="5678XYZ",
        )
    )

    assert res_mod.tractor_plate == "5678XYZ"
    assert AuditAction.VEHICLE_UPDATED in res_mod.audit_events_recorded

    events = audit.get_events(exp.id)
    update_event = next(e for e in events if e.action == AuditAction.VEHICLE_UPDATED)
    assert update_event.old_state is not None
    assert update_event.old_state["tractor_plate"] == "1234BCD"
    assert update_event.new_state["tractor_plate"] == "5678XYZ"


# =========================================================================
# 17. Eventos de auditoría registrados
# =========================================================================
def test_17_audit_trail_events_recorded() -> None:
    repo = InMemoryExpeditionRepository()
    audit = InMemoryAuditService()
    exp = make_valid_expedition()
    repo.save(exp)
    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo, audit_service=audit)

    use_case.execute(
        AssignVehicleInputDTO(
            expedition_id=exp.id,
            vehicle_type="ARTICULADO",
            tractor_registration="1234BCD",
            trailer_registration="R1234BCD",
            carrier_name="TRANS SUR",
            carrier_tax_id="B04111222",
            actor="SUPERVISOR_MUELLE",
        )
    )

    actions = [e.action for e in audit.get_events(exp.id)]
    assert AuditAction.CARRIER_ASSIGNED in actions
    assert AuditAction.VEHICLE_ASSIGNED in actions
    assert AuditAction.VALIDATION_EXECUTED in actions
    assert AuditAction.EXPEDITION_READY_FOR_DECA in actions


# =========================================================================
# 18. Generación concurrente de identificadores TD-YYYY-NNNNN
# =========================================================================
def test_18_concurrent_identifier_generation_no_collisions() -> None:
    repo = InMemoryExpeditionRepository()
    num_requests = 50

    def generate_id() -> str:
        return repo.next_internal_id("2026")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(generate_id) for _ in range(num_requests)]
        generated_ids = [f.result() for f in futures]

    assert len(generated_ids) == num_requests
    # Todos son únicos
    assert len(set(generated_ids)) == num_requests

    # Formato canónico TD-2026-NNNNN
    pattern = re.compile(r"^TD-2026-\d{5}$")
    for identifier in generated_ids:
        assert pattern.match(identifier)

    # Secuencia correlativa sin huecos
    numbers = sorted(int(id_str.split("-")[2]) for id_str in generated_ids)
    assert numbers == list(range(1, num_requests + 1))


# =========================================================================
# 19. Expedición internacional (warning no bloqueante)
# =========================================================================
def test_19_international_transport_warning_non_blocking() -> None:
    repo = InMemoryExpeditionRepository()
    # Destino a Francia sin indicar CMR en referencia
    exp = make_valid_expedition(
        destination="Marché de Rungis (Francia)",
        reference="ALB-9876",
    )
    repo.save(exp)

    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo)
    result = use_case.execute(
        AssignVehicleInputDTO(
            expedition_id=exp.id,
            vehicle_type="RIGIDO",
            tractor_registration="1234BCD",
        )
    )

    # El aviso no bloquea: status es LISTA_PARA_DECA y valid=True
    assert result.status == ExpeditionStatus.LISTA_PARA_DECA
    assert result.validation.valid is True
    assert any(
        w.code == "INTERNATIONAL_TRANSPORT_CMR_RECOMMENDED" for w in result.validation.warnings
    )


# =========================================================================
# 20. Warnings no bloqueantes (email ausente, etc.)
# =========================================================================
def test_20_non_blocking_warnings_missing_email_observations_reference() -> None:
    repo = InMemoryExpeditionRepository()
    # Sin email, sin observaciones, referencia autogenerada "EXP-..."
    exp = make_valid_expedition(
        carrier_email=None,
        reference="EXP-AUTOGENERATED",
    )
    exp.carrier_email = None
    exp.observations = None
    repo.save(exp)

    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo)
    result = use_case.execute(
        AssignVehicleInputDTO(
            expedition_id=exp.id,
            vehicle_type="RIGIDO",
            tractor_registration="1234BCD",
        )
    )

    assert result.status == ExpeditionStatus.LISTA_PARA_DECA
    assert result.validation.valid is True
    warning_codes = [w.code for w in result.validation.warnings]
    assert "CARRIER_EMAIL_MISSING" in warning_codes
    assert "OBSERVATIONS_MISSING" in warning_codes
    assert "EXTERNAL_REFERENCE_MISSING" in warning_codes


# =========================================================================
# Test adicional: Consulta de validación pura via ValidateExpeditionUseCase
# =========================================================================
def test_validate_expedition_use_case() -> None:
    repo = InMemoryExpeditionRepository()
    exp = make_valid_expedition()
    repo.save(exp)

    val_use_case = ValidateExpeditionUseCase(expedition_repo=repo)
    exp_out, validation = val_use_case.execute(exp.id)

    assert exp_out.id == exp.id
    # No tiene vehículo todavía
    assert validation.valid is False
    assert any(e.code == "VEHICLE_TYPE_MISSING" for e in validation.errors)
