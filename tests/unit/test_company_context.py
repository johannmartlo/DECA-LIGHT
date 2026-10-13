from __future__ import annotations

import pytest

from src.domain.exceptions import UnauthorizedCompanyContextException
from src.domain.value_objects import CompanyContext


def test_company_context_valid():
    ctx = CompanyContext.create("TOMATES_DE_AUTOR", actor="ADMIN")
    assert ctx.company_id == "TOMATES_DE_AUTOR"
    assert ctx.actor == "ADMIN"
    assert ctx.is_verified is True


def test_company_context_strip_whitespace():
    ctx = CompanyContext.create("  COMPANY_01  ", actor=" OPERATOR ")
    assert ctx.company_id == "COMPANY_01"
    assert ctx.actor == "OPERATOR"


@pytest.mark.parametrize("invalid_id", [None, "", "   ", "\t\n"])
def test_company_context_empty_rejected(invalid_id):
    with pytest.raises(UnauthorizedCompanyContextException, match=r"nulo ni vac"):
        CompanyContext.create(invalid_id)


@pytest.mark.parametrize("invalid_format", [
    "c",  # too short (< 2)
    "company-with-hyphens",  # hyphens not allowed
    "lowercase_company",  # lowercase not allowed
    "COMPANY with spaces",  # space not allowed
    "COMPANY@123",  # @ not allowed
    "A" * 45,  # too long (> 40)
])
def test_company_context_invalid_format_rejected(invalid_format):
    with pytest.raises(UnauthorizedCompanyContextException, match=r"formato can"):
        CompanyContext.create(invalid_format)


def test_company_context_unverified_rejected():
    with pytest.raises(UnauthorizedCompanyContextException, match=r"carece de autorizaci"):
        CompanyContext.create("COMPANY_01", is_verified=False)
