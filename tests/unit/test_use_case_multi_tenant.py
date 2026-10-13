from __future__ import annotations

import hashlib
import uuid
from datetime import date

import pytest

from src.application.dtos.deca_dto import EmitDeCAInputDTO
from src.application.dtos.email_dto import SendDeCAEmailInputDTO
from src.application.dtos.vehicle_assignment_dto import AssignVehicleInputDTO
from src.application.use_cases.assign_vehicle import AssignVehicleToExpeditionUseCase
from src.application.use_cases.emit_deca import EmitDeCAUseCase
from src.application.use_cases.send_deca_email import SendDeCAEmailUseCase
from src.application.use_cases.validate_expedition import ValidateExpeditionUseCase
from src.domain.entities.deca import DeCA, DeCAVersion
from src.domain.entities.expedition import Expedition
from src.domain.enums import DeCAStatus, ExpeditionStatus, VehicleType
from src.domain.exceptions import (
    EntityNotFoundException,
    UnauthorizedCompanyContextException,
)
from src.domain.value_objects import NIF, Matricula, Weight
from src.infrastructure.document.reportlab_pdf_renderer import ReportLabPdfRenderer
from src.infrastructure.email.fake_microsoft_graph_email_sender import (
    FakeMicrosoftGraphEmailSender,
)
from src.infrastructure.repositories.in_memory_deca_repository import (
    InMemoryDeCARepository,
)
from src.infrastructure.repositories.in_memory_email_delivery_repository import (
    InMemoryEmailDeliveryRepository,
)
from src.infrastructure.repositories.in_memory_expedition_repository import (
    InMemoryExpeditionRepository,
)
from src.infrastructure.storage.local_pdf_storage import LocalPdfStorage


def make_expedition(
    company_id: str = "COMPANY_A",
    status: ExpeditionStatus = ExpeditionStatus.PENDIENTE_MATRICULA,
) -> Expedition:
    return Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00001",
        reference="ALB-2026-001",
        fiscal_year="2026",
        transport_date=date.today(),
        shipper_name="Empresa A S.L.",
        carrier_name_raw="Transportes Express",
        carrier_tax_id=NIF("B04123456"),
        carrier_email="trafico@express.com",
        origin="El Ejido",
        destination="Madrid",
        goods="Tomates",
        weight=Weight(18000.0),
        status=status,
        company_id=company_id,
    )


def test_assign_vehicle_multi_tenant_isolation():
    repo = InMemoryExpeditionRepository()
    exp = make_expedition(company_id="COMPANY_A")
    repo.save(exp, company_id="COMPANY_A")

    use_case = AssignVehicleToExpeditionUseCase(expedition_repo=repo)

    # 1. Access with different tenant -> raises EntityNotFoundException
    input_b = AssignVehicleInputDTO(
        expedition_id=str(exp.id),
        vehicle_type="RIGIDO",
        tractor_registration="1234BBB",
        company_id="COMPANY_B",
    )
    with pytest.raises(EntityNotFoundException):
        use_case.execute(input_b)

    # 2. Access with invalid tenant context -> raises UnauthorizedCompanyContextException
    input_invalid = AssignVehicleInputDTO(
        expedition_id=str(exp.id),
        vehicle_type="RIGIDO",
        tractor_registration="1234BBB",
        company_id="invalid-tenant!",
    )
    with pytest.raises(UnauthorizedCompanyContextException):
        use_case.execute(input_invalid)

    # 3. Access with correct tenant -> succeeds
    input_a = AssignVehicleInputDTO(
        expedition_id=str(exp.id),
        vehicle_type="RIGIDO",
        tractor_registration="1234BBB",
        company_id="COMPANY_A",
    )
    res = use_case.execute(input_a)
    assert res.is_ready_for_deca is True

    # Confirm company_id was preserved on persisted entity
    stored = repo.get_by_id(exp.id, company_id="COMPANY_A")
    assert stored is not None
    assert stored.company_id == "COMPANY_A"
    assert stored.tractor_plate == Matricula("1234BBB")


def test_validate_expedition_multi_tenant_isolation():
    repo = InMemoryExpeditionRepository()
    exp = make_expedition(company_id="COMPANY_A")
    repo.save(exp, company_id="COMPANY_A")

    use_case = ValidateExpeditionUseCase(expedition_repo=repo)

    # Cross-tenant access fails
    with pytest.raises(EntityNotFoundException):
        use_case.execute(exp.id, company_id="COMPANY_B")

    # Invalid context fails
    with pytest.raises(UnauthorizedCompanyContextException):
        use_case.execute(exp.id, company_id="bad-tenant*")

    # Authorized context succeeds
    found_exp, val_res = use_case.execute(exp.id, company_id="COMPANY_A")
    assert found_exp.id == exp.id
    assert found_exp.company_id == "COMPANY_A"


def test_emit_deca_multi_tenant_isolation(tmp_path):
    repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    storage = LocalPdfStorage(tmp_path)
    renderer = ReportLabPdfRenderer()

    exp = make_expedition(
        company_id="COMPANY_A",
        status=ExpeditionStatus.LISTA_PARA_DECA,
    )
    exp.vehicle_type = VehicleType.RIGIDO
    exp.tractor_plate = Matricula("1234BBB")
    repo.save(exp, company_id="COMPANY_A")

    use_case = EmitDeCAUseCase(
        expedition_repo=repo,
        deca_repo=deca_repo,
        pdf_renderer=renderer,
        storage_service=storage,
    )

    # Cross-tenant emission rejected
    with pytest.raises(EntityNotFoundException):
        use_case.execute(EmitDeCAInputDTO(expedition_id=str(exp.id), company_id="COMPANY_B"))

    # Invalid context rejected
    with pytest.raises(UnauthorizedCompanyContextException):
        use_case.execute(EmitDeCAInputDTO(expedition_id=str(exp.id), company_id="invalid/id"))

    # Authorized emission succeeds
    result = use_case.execute(EmitDeCAInputDTO(expedition_id=str(exp.id), company_id="COMPANY_A"))
    assert result.company_id == "COMPANY_A"
    assert result.status == "ISSUED"

    # Expedition transitioned to DECA_GENERADO in same tenant
    stored = repo.get_by_id(exp.id, company_id="COMPANY_A")
    assert stored is not None
    assert stored.status == ExpeditionStatus.DECA_GENERADO
    assert stored.company_id == "COMPANY_A"


def test_send_deca_email_multi_tenant_isolation(tmp_path):
    repo = InMemoryExpeditionRepository()
    deca_repo = InMemoryDeCARepository()
    email_delivery_repo = InMemoryEmailDeliveryRepository()
    storage = LocalPdfStorage(tmp_path)
    email_sender = FakeMicrosoftGraphEmailSender()

    exp = make_expedition(
        company_id="COMPANY_A",
        status=ExpeditionStatus.DECA_GENERADO,
    )
    exp.vehicle_type = VehicleType.RIGIDO
    exp.tractor_plate = Matricula("1234BBB")
    repo.save(exp, company_id="COMPANY_A")

    # Store a dummy PDF and DeCA
    pdf_content = b"%PDF-1.4 test dummy content"
    pdf_sha = hashlib.sha256(pdf_content).hexdigest()
    storage_path = storage.save(pdf_content, f"COMPANY_A/{exp.internal_id}/DECA-001.pdf")

    deca = DeCA(
        expedition_id=exp.id,
        company_id="COMPANY_A",
        deca_code="DECA-2026-0001",
        service_start_at=date.today(),
        current_version=1,
        status=DeCAStatus.ISSUED,
    )
    v1 = DeCAVersion(
        version_number=1,
        pdf_sha256=pdf_sha,
        pdf_storage_path=storage_path,
        pdf_size_bytes=len(pdf_content),
        snapshot_hash="dummyhash",
        snapshot_data={},
    )
    deca.add_version(v1)
    deca_repo.save(deca)

    use_case = SendDeCAEmailUseCase(
        expedition_repo=repo,
        deca_repo=deca_repo,
        storage_service=storage,
        email_sender=email_sender,
        email_delivery_repo=email_delivery_repo,
    )

    # Cross-tenant send rejected
    with pytest.raises(EntityNotFoundException):
        use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id), company_id="COMPANY_B"))

    # Invalid tenant rejected
    with pytest.raises(UnauthorizedCompanyContextException):
        use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id), company_id="bad tenant!"))

    # Authorized send succeeds
    result = use_case.execute(SendDeCAEmailInputDTO(expedition_id=str(exp.id), company_id="COMPANY_A"))
    assert result.email_status == "EMAIL_SENT"

    # Expedition status transitioned to ENVIADA
    stored = repo.get_by_id(exp.id, company_id="COMPANY_A")
    assert stored is not None
    assert stored.status == ExpeditionStatus.ENVIADA
    assert stored.company_id == "COMPANY_A"
