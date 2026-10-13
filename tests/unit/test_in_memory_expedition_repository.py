from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.domain.entities.expedition import Expedition
from src.domain.enums import ExpeditionStatus
from src.domain.exceptions import CompanyMismatchException
from src.infrastructure.repositories.in_memory_expedition_repository import (
    InMemoryExpeditionRepository,
)


def test_in_memory_cross_tenant_get_by_id() -> None:
    repo = InMemoryExpeditionRepository()
    exp_id = uuid.uuid4()
    exp = Expedition(
        id=exp_id,
        internal_id="TD-2026-00001",
        reference="REF-01",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    repo.save(exp)

    # 1. Mismo tenant
    assert repo.get_by_id(exp_id, company_id="TOMATES_DE_AUTOR") is not None

    # 2. Distinto tenant (IDOR prevención)
    assert repo.get_by_id(exp_id, company_id="CULTIVOS_ARABA") is None
    assert repo.get_by_id(exp_id, company_id="INEXISTENTE") is None


def test_in_memory_cross_tenant_find_by_internal_id() -> None:
    repo = InMemoryExpeditionRepository()
    exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00042",
        reference="REF-02",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    repo.save(exp)

    assert repo.find_by_internal_id("TD-2026-00042", company_id="TOMATES_DE_AUTOR") is not None
    assert repo.find_by_internal_id("TD-2026-00042", company_id="CULTIVOS_ARABA") is None


def test_in_memory_cross_tenant_save_update_rejection() -> None:
    repo = InMemoryExpeditionRepository()
    exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00050",
        reference="REF-03",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    repo.save(exp)

    # Contexto no autorizado
    with pytest.raises(CompanyMismatchException):
        repo.save(exp, company_id="CULTIVOS_ARABA")

    # Reasignación de tenant
    exp.company_id = "CULTIVOS_ARABA"
    with pytest.raises(CompanyMismatchException):
        repo.save(exp)

    # Limpieza no autorizada
    exp.company_id = ""
    with pytest.raises(CompanyMismatchException):
        repo.save(exp)


def test_in_memory_cross_tenant_save_insert_mismatch() -> None:
    repo = InMemoryExpeditionRepository()
    new_exp = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00060",
        reference="REF-04",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
    )
    with pytest.raises(CompanyMismatchException):
        repo.save(new_exp, company_id="CULTIVOS_ARABA")


def test_in_memory_list_pending_vehicle_filtering() -> None:
    repo = InMemoryExpeditionRepository()
    e1 = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00071",
        reference="P-01",
        fiscal_year="2026",
        company_id="TOMATES_DE_AUTOR",
        status=ExpeditionStatus.PENDIENTE_MATRICULA,
    )
    e2 = Expedition(
        id=uuid.uuid4(),
        internal_id="TD-2026-00072",
        reference="P-02",
        fiscal_year="2026",
        company_id="CULTIVOS_ARABA",
        status=ExpeditionStatus.PENDIENTE_MATRICULA,
    )
    repo.save(e1)
    repo.save(e2)

    assert len(repo.list_pending_vehicle()) == 2
    assert len(repo.list_pending_vehicle(company_id="TOMATES_DE_AUTOR")) == 1
    assert len(repo.list_pending_vehicle(company_id="CULTIVOS_ARABA")) == 1
    assert len(repo.list_pending_vehicle(company_id="OTRO")) == 0
