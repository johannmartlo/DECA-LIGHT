from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.domain.entities.expedition import Expedition
from src.domain.enums import VehicleType


@dataclass(frozen=True)
class ValidationErrorItem:
    """Error bloqueante que impide considerar la expedición lista para emitir DeCA."""

    code: str
    field: str
    message: str


@dataclass(frozen=True)
class ValidationWarningItem:
    """Advertencia no bloqueante visible para el operador."""

    code: str
    field: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    """Resultado estructurado de la validación legal y operativa del DeCA."""

    valid: bool
    errors: list[ValidationErrorItem] = field(default_factory=list)
    warnings: list[ValidationWarningItem] = field(default_factory=list)


class DeCAValidator:
    """Servicio de dominio puro para la validación legal y operativa del DeCA.

    Independiente de frameworks (FastAPI), bases de datos (SQLAlchemy),
    librerías gráficas (ReportLab), códigos QR y servicios de mensajería (Microsoft Graph).
    """

    @classmethod
    def validate(cls, expedition: Expedition) -> ValidationResult:
        """Evalúa una expedición y devuelve un ValidationResult con errores y advertencias."""
        errors: list[ValidationErrorItem] = []
        warnings: list[ValidationWarningItem] = []

        # 1. Configuración de Vehículo y Matrículas
        if expedition.vehicle_type is None:
            errors.append(
                ValidationErrorItem(
                    code="VEHICLE_TYPE_MISSING",
                    field="vehicle_type",
                    message="Debe seleccionarse el tipo de transporte (RIGIDO o ARTICULADO).",
                )
            )
        else:
            if expedition.vehicle_type == VehicleType.RIGIDO:
                if not expedition.tractor_plate or not expedition.tractor_plate.valor:
                    errors.append(
                        ValidationErrorItem(
                            code="TRACTOR_REGISTRATION_MISSING",
                            field="tractor_plate",
                            message=(
                                "Un vehículo rígido exige obligatoriamente la matrícula "
                                "del vehículo."
                            ),
                        )
                    )
                if expedition.trailer_plate is not None and expedition.trailer_plate.valor:
                    errors.append(
                        ValidationErrorItem(
                            code="INVALID_VEHICLE_CONFIGURATION",
                            field="trailer_plate",
                            message=(
                                "Un vehículo rígido no puede tener asignada una matrícula de "
                                "remolque/semirremolque."
                            ),
                        )
                    )
            elif expedition.vehicle_type == VehicleType.ARTICULADO:
                if not expedition.tractor_plate or not expedition.tractor_plate.valor:
                    errors.append(
                        ValidationErrorItem(
                            code="TRACTOR_REGISTRATION_MISSING",
                            field="tractor_plate",
                            message=(
                                "Un conjunto articulado exige obligatoriamente la matrícula "
                                "de la cabeza tractora."
                            ),
                        )
                    )
                if not expedition.trailer_plate or not expedition.trailer_plate.valor:
                    errors.append(
                        ValidationErrorItem(
                            code="TRAILER_REGISTRATION_MISSING",
                            field="trailer_plate",
                            message=(
                                "Un conjunto articulado exige obligatoriamente la matrícula "
                                "del semirremolque/remolque."
                            ),
                        )
                    )

        # 2. Identificación del Transportista Efectivo
        carrier_name = expedition.carrier_name_raw.strip() if expedition.carrier_name_raw else ""
        if not carrier_name:
            errors.append(
                ValidationErrorItem(
                    code="CARRIER_MISSING",
                    field="carrier_name_raw",
                    message=(
                        "El transportista efectivo debe quedar identificado antes de emitir DeCA."
                    ),
                )
            )

        if expedition.carrier_tax_id is None or not str(expedition.carrier_tax_id).strip():
            errors.append(
                ValidationErrorItem(
                    code="CARRIER_TAX_ID_MISSING",
                    field="carrier_tax_id",
                    message="Falta el NIF/CIF o Tax ID del transportista efectivo.",
                )
            )
        else:
            tax_str = str(expedition.carrier_tax_id).strip()
            cleaned_tax = re.sub(r"[\s\-.]", "", tax_str).upper()
            if (
                len(cleaned_tax) < 5
                or len(cleaned_tax) > 20
                or not re.match(r"^[A-Z0-9]+$", cleaned_tax)
            ):
                errors.append(
                    ValidationErrorItem(
                        code="CARRIER_TAX_ID_INVALID",
                        field="carrier_tax_id",
                        message=(
                            f"El NIF/CIF '{tax_str}' del transportista no tiene un formato válido."
                        ),
                    )
                )

        # 3. Cargador Contractual y Empresa Emisora
        if not expedition.company_id or not expedition.company_id.strip():
            errors.append(
                ValidationErrorItem(
                    code="COMPANY_MISSING",
                    field="company_id",
                    message="La expedición no tiene asignada una empresa emisora (company_id).",
                )
            )

        if not expedition.shipper_name or not expedition.shipper_name.strip():
            errors.append(
                ValidationErrorItem(
                    code="SHIPPER_MISSING",
                    field="shipper_name",
                    message="Falta la razón social del cargador contractual.",
                )
            )
        else:
            s_upper = expedition.shipper_name.upper()
            if expedition.company_id == "TOMATES_DE_AUTOR" and "CULTIVOS ARABA" in s_upper:
                errors.append(
                    ValidationErrorItem(
                        code="COMPANY_MISMATCH",
                        field="company_id",
                        message=(
                            "Incoherencia: empresa emisora TOMATES_DE_AUTOR "
                            "con cargador CULTIVOS ARABA."
                        ),
                    )
                )
            elif expedition.company_id == "CULTIVOS_ARABA" and "TOMATES DE AUTOR" in s_upper:
                errors.append(
                    ValidationErrorItem(
                        code="COMPANY_MISMATCH",
                        field="company_id",
                        message=(
                            "Incoherencia: empresa emisora CULTIVOS_ARABA "
                            "con cargador TOMATES DE AUTOR."
                        ),
                    )
                )

        # 4. Datos de Carga y Ruta
        if not expedition.transport_date:
            errors.append(
                ValidationErrorItem(
                    code="LOADING_DATE_MISSING",
                    field="transport_date",
                    message="Falta la fecha de transporte y carga.",
                )
            )

        if not expedition.origin or not expedition.origin.strip():
            errors.append(
                ValidationErrorItem(
                    code="ORIGIN_MISSING",
                    field="origin",
                    message="Falta el lugar de origen/carga de la mercancía.",
                )
            )

        if not expedition.destination or not expedition.destination.strip():
            errors.append(
                ValidationErrorItem(
                    code="DESTINATION_MISSING",
                    field="destination",
                    message="Falta el lugar de destino/descarga de la mercancía.",
                )
            )

        if not expedition.goods or not expedition.goods.strip():
            errors.append(
                ValidationErrorItem(
                    code="GOODS_MISSING",
                    field="goods",
                    message="Falta la naturaleza de la mercancía transportada.",
                )
            )

        if expedition.weight is None or expedition.weight.kg <= 0:
            errors.append(
                ValidationErrorItem(
                    code="WEIGHT_INVALID",
                    field="weight",
                    message="El peso de la mercancía debe ser mayor que 0 kg.",
                )
            )

        # 5. Advertencias (Warnings no bloqueantes)
        if not expedition.carrier_email or not expedition.carrier_email.strip():
            warnings.append(
                ValidationWarningItem(
                    code="CARRIER_EMAIL_MISSING",
                    field="carrier_email",
                    message=(
                        "El transportista no dispone de email registrado; "
                        "el DeCA requerirá descarga o visualización QR en muelle."
                    ),
                )
            )

        if not expedition.observations or not expedition.observations.strip():
            warnings.append(
                ValidationWarningItem(
                    code="OBSERVATIONS_MISSING",
                    field="observations",
                    message="No se han registrado observaciones ni instrucciones de transporte.",
                )
            )

        dest_upper = expedition.destination.upper() if expedition.destination else ""
        foreign_keywords = (
            "FRANCIA",
            "FRANCE",
            "ALEMANIA",
            "GERMANY",
            "DEUTSCHLAND",
            "ITALIA",
            "ITALY",
            "HOLANDA",
            "NETHERLANDS",
            "PAISES BAJOS",
            "PORTUGAL",
            "REINO UNIDO",
            "UK",
            "BELGICA",
            "BELGIQUE",
        )
        if any(country in dest_upper for country in foreign_keywords):
            ref_upper = expedition.reference.upper() if expedition.reference else ""
            if "CMR" not in ref_upper:
                warnings.append(
                    ValidationWarningItem(
                        code="INTERNATIONAL_TRANSPORT_CMR_RECOMMENDED",
                        field="destination",
                        message=(
                            "Destino internacional detectado sin indicación expresa de CMR; "
                            "se aconseja verificar la documentación internacional."
                        ),
                    )
                )

        if not expedition.reference or expedition.reference.startswith("EXP-"):
            warnings.append(
                ValidationWarningItem(
                    code="EXTERNAL_REFERENCE_MISSING",
                    field="reference",
                    message="La expedición no dispone de número de albarán comercial explícito.",
                )
            )

        return ValidationResult(valid=(len(errors) == 0), errors=errors, warnings=warnings)
