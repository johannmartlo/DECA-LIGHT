from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.domain.entities.deca import DeCA
from src.domain.entities.vehicle import Vehicle
from src.domain.enums import VehicleType
from src.domain.exceptions import (
    InvalidVehicleConfigurationException,
    ValidationException,
)
from src.domain.value_objects import NIF, DeCAToken, Matricula, Weight


def test_matricula_normalization() -> None:
    m = Matricula(" 1234-abc ")
    assert m.valor == "1234ABC"
    assert str(m) == "1234ABC"


def test_matricula_empty_raises() -> None:
    with pytest.raises(ValidationException, match="no puede estar vacía"):
        Matricula("")


def test_nif_normalization() -> None:
    n = NIF(" b-12345678 ")
    assert n.valor == "B12345678"


def test_weight_validation() -> None:
    w = Weight(1250.456)
    assert w.kg == 1250.46
    with pytest.raises(ValidationException, match="mayor que 0"):
        Weight(0.0)


def test_deca_token_validation() -> None:
    with pytest.raises(ValidationException, match="entropía insuficiente"):
        DeCAToken("short-token")

    valid_token = DeCAToken("a" * 32)
    assert str(valid_token) == "a" * 32


def test_vehicle_rigid_valid() -> None:
    v = Vehicle(
        vehicle_type=VehicleType.RIGIDO,
        tractor_plate=Matricula("1234ABC"),
        trailer_plate=None,
    )
    v.validate_configuration()  # No debe lanzar excepción


def test_vehicle_rigid_with_trailer_raises() -> None:
    v = Vehicle(
        vehicle_type=VehicleType.RIGIDO,
        tractor_plate=Matricula("1234ABC"),
        trailer_plate=Matricula("R1234BCD"),
    )
    msg = "no puede tener asignada una matrícula de remolque"
    with pytest.raises(InvalidVehicleConfigurationException, match=msg):
        v.validate_configuration()


def test_vehicle_articulated_valid() -> None:
    v = Vehicle(
        vehicle_type=VehicleType.ARTICULADO,
        tractor_plate=Matricula("1234ABC"),
        trailer_plate=Matricula("R5678DEF"),
    )
    v.validate_configuration()  # No debe lanzar excepción


def test_vehicle_articulated_missing_trailer_raises() -> None:
    v = Vehicle(
        vehicle_type=VehicleType.ARTICULADO,
        tractor_plate=Matricula("1234ABC"),
        trailer_plate=None,
    )
    msg = "exige matrícula del semirremolque/remolque"
    with pytest.raises(InvalidVehicleConfigurationException, match=msg):
        v.validate_configuration()


def test_deca_public_download_and_expiration() -> None:
    now = datetime.now(UTC)
    deca = DeCA(service_start_at=now)

    # Durante el transporte, la descarga está permitida
    assert deca.is_public_download_allowed(now) is True

    # Se registra el fin del servicio
    end_time = now + timedelta(days=2)
    deca.record_service_end(end_time)

    # A los 3 días de finalizar, sigue permitida (dentro de los 7 días naturales)
    assert deca.is_public_download_allowed(end_time + timedelta(days=3)) is True

    # A los 8 días de finalizar, ya expiró
    assert deca.is_public_download_allowed(end_time + timedelta(days=8)) is False
