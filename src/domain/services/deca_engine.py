from __future__ import annotations

import hashlib
import json
from datetime import datetime

from src.domain.entities.deca import DeCAEstructurado
from src.domain.entities.expedition import Expedition
from src.domain.enums import ExpeditionStatus
from src.domain.exceptions import DeCAEmissionException, ExpeditionNotReadyException
from src.domain.services.deca_validator import DeCAValidator


class DeCAEngine:
    """Motor de dominio para la transformación de expediciones validadas en DeCA estructurado."""

    @classmethod
    def create_deca_estructurado(
        cls,
        expedition: Expedition,
        deca_code: str,
        version_number: int = 1,
        issue_datetime: datetime | None = None,
        public_url: str = "",
        qr_payload: str = "",
    ) -> tuple[DeCAEstructurado, dict, str]:
        """Evalúa las reglas de negocio y produce el DeCA estructurado con su snapshot inmutable.

        Retorna:
            tuple[DeCAEstructurado, dict, str]:
                1. Objeto de dominio DeCAEstructurado.
                2. Diccionario snapshot_data canónico.
                3. Hash SHA-256 del snapshot.

        Lanza:
            ExpeditionNotReadyException: Si la expedición no está en estado LISTA_PARA_DECA.
            DeCAEmissionException: Si la revalidación legal encuentra errores bloqueantes.
        """
        from src.domain.services.clock import Clock

        # 1. Comprobación de estado operativo
        if expedition.status != ExpeditionStatus.LISTA_PARA_DECA:
            ref = expedition.internal_id or str(expedition.id)
            raise ExpeditionNotReadyException(
                f"La expedición '{ref}' no está preparada para emitir DeCA "
                f"(estado actual: {expedition.status}). Debe estar en LISTA_PARA_DECA."
            )

        # 2. Revalidación exhaustiva con DeCAValidator (defensa en profundidad)
        validation = DeCAValidator.validate(expedition)
        if not validation.valid:
            errors_str = "; ".join(f"[{e.code}] {e.message}" for e in validation.errors)
            raise DeCAEmissionException(
                f"Revalidación legal fallida para la expedición '{expedition.internal_id}': "
                f"{errors_str}"
            )

        # 3. Determinación de fecha/hora de emisión formal
        issue_dt = issue_datetime if issue_datetime is not None else Clock.now()

        # 4. Construcción del snapshot inmutable canónico
        trailer_str = str(expedition.trailer_plate) if expedition.trailer_plate else None
        company_id = expedition.company_id or "TOMATES_DE_AUTOR"
        snapshot_dict: dict = {
            "deca_code": deca_code,
            "version": version_number,
            "company_id": company_id,
            "expedition_id": str(expedition.id),
            "internal_id": expedition.internal_id or None,
            "external_reference": expedition.reference or None,
            "fiscal_year": expedition.fiscal_year,
            "issue_datetime": issue_dt.isoformat(),
            "transport_date": expedition.transport_date.isoformat(),
            "public_url": public_url,
            "shipper": {
                "name": expedition.shipper_name,
                "tax_id": str(expedition.shipper_tax_id) if expedition.shipper_tax_id else "",
                "address": expedition.shipper_address,
            },
            "carrier": {
                "name": expedition.carrier_name_raw,
                "tax_id": str(expedition.carrier_tax_id) if expedition.carrier_tax_id else "",
                "email": expedition.carrier_email or None,
            },
            "vehicle": {
                "type": str(expedition.vehicle_type),
                "tractor_plate": str(expedition.tractor_plate),
                "trailer_plate": trailer_str,
            },
            "route_and_goods": {
                "origin": expedition.origin,
                "destination": expedition.destination,
                "goods": expedition.goods,
                "weight_kg": expedition.weight.kg if expedition.weight else 0.0,
            },
            "observations": expedition.observations or None,
        }

        # 5. Cálculo del hash criptográfico del snapshot
        canonical_json = json.dumps(snapshot_dict, sort_keys=True, ensure_ascii=False)
        snapshot_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        # 6. Construcción del objeto inmutable DeCAEstructurado
        deca_estructurado = DeCAEstructurado(
            deca_code=deca_code,
            version_number=version_number,
            company_id=company_id,
            issue_datetime=issue_dt,
            transport_date=expedition.transport_date,
            shipper_name=expedition.shipper_name,
            shipper_tax_id=str(expedition.shipper_tax_id) if expedition.shipper_tax_id else "",
            shipper_address=expedition.shipper_address,
            carrier_name=expedition.carrier_name_raw,
            carrier_tax_id=str(expedition.carrier_tax_id) if expedition.carrier_tax_id else "",
            vehicle_type=str(expedition.vehicle_type),
            tractor_plate=str(expedition.tractor_plate),
            trailer_plate=str(expedition.trailer_plate) if expedition.trailer_plate else None,
            origin=expedition.origin,
            destination=expedition.destination,
            goods=expedition.goods,
            weight_kg=expedition.weight.kg if expedition.weight else 0.0,
            internal_id=expedition.internal_id or None,
            external_reference=expedition.reference or None,
            observations=expedition.observations or None,
            snapshot_hash=snapshot_hash,
            public_url=public_url,
            qr_payload=qr_payload or public_url,
        )

        return deca_estructurado, snapshot_dict, snapshot_hash
