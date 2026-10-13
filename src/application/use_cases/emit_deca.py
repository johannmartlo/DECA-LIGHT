from __future__ import annotations

import hashlib
import threading
import uuid

from src.application.dtos.deca_dto import EmitDeCAInputDTO, EmitDeCAResultDTO
from src.application.ports.audit_service import AuditServicePort
from src.application.ports.deca_repository import DeCARepositoryPort
from src.application.ports.expedition_repository import ExpeditionRepositoryPort
from src.application.ports.pdf_renderer import PdfRendererPort
from src.application.ports.storage_service import StorageServicePort
from src.domain.entities.audit_event import AuditEvent
from src.domain.entities.deca import DeCA, DeCAVersion
from src.domain.entities.expedition import Expedition
from src.domain.enums import AuditAction, DeCAStatus, ExpeditionStatus
from src.domain.exceptions import (
    DeCAEmissionException,
    EntityNotFoundException,
    ExpeditionNotReadyException,
    StorageException,
)
from src.domain.services.deca_engine import DeCAEngine
from src.domain.services.public_token_service import PublicDeCaTokenService
from src.domain.value_objects import CompanyContext


class EmitDeCAUseCase:
    """Caso de uso de aplicación para la emisión atómica, inmutable y auditable de DeCA v1."""

    def __init__(
        self,
        expedition_repo: ExpeditionRepositoryPort,
        deca_repo: DeCARepositoryPort,
        pdf_renderer: PdfRendererPort,
        storage_service: StorageServicePort,
        audit_service: AuditServicePort | None = None,
        public_base_url: str = "http://localhost:8000",
    ) -> None:
        self.expedition_repo = expedition_repo
        self.deca_repo = deca_repo
        self.pdf_renderer = pdf_renderer
        self.storage_service = storage_service
        self.audit_service = audit_service
        self.public_base_url = (public_base_url or "http://localhost:8000").rstrip("/")
        self._lock = threading.Lock()

    def execute(self, input_dto: EmitDeCAInputDTO) -> EmitDeCAResultDTO:
        """Ejecuta la emisión del DeCA garantizando atomicidad, idempotencia e inmutabilidad."""
        if input_dto.company_id:
            CompanyContext.create(input_dto.company_id, actor=input_dto.actor)

        try:
            exp_uuid = (
                uuid.UUID(str(input_dto.expedition_id))
                if not isinstance(input_dto.expedition_id, uuid.UUID)
                else input_dto.expedition_id
            )
        except ValueError as exc:
            raise EntityNotFoundException(
                f"Identificador de expedición UUID inválido: '{input_dto.expedition_id}'"
            ) from exc

        with self._lock:
            # 1. Comprobar existencia de la expedición
            expedition: Expedition | None = self.expedition_repo.get_by_id(
                exp_uuid, company_id=input_dto.company_id
            )
            if not expedition:
                raise EntityNotFoundException(
                    f"Expedición con ID '{input_dto.expedition_id}' no encontrada."
                )

            # 2. Comprobación de idempotencia: Si ya existe un DeCA emitido para esta expedición
            existing_deca = self.deca_repo.find_by_expedition_id(expedition.id)
            if existing_deca and existing_deca.versions:
                v1 = existing_deca.get_version(1)
                if v1:
                    existing_token = existing_deca.public_access_token or ""
                    existing_url = (
                        PublicDeCaTokenService.build_public_url(
                            self.public_base_url, existing_token
                        )
                        if existing_token
                        else ""
                    )
                    return EmitDeCAResultDTO(
                        deca_id=str(existing_deca.id),
                        version=v1.version_number,
                        expedition_id=str(expedition.id),
                        status=str(existing_deca.status),
                        pdf_filename=f"{existing_deca.deca_code}.pdf",
                        pdf_sha256=v1.pdf_sha256,
                        pdf_size_bytes=v1.pdf_size_bytes,
                        issued_at=v1.created_at.isoformat(),
                        company_id=existing_deca.company_id,
                        public_token=existing_token,
                        public_url=existing_url,
                        is_idempotent=True,
                        message=(
                            "Operación idempotente: el DeCA v1 para esta expedición ya fue emitido."
                        ),
                    )

            # 3. Registrar auditoría de inicio de emisión
            if self.audit_service:
                self.audit_service.record(
                    AuditEvent(
                        action=AuditAction.DECA_EMISSION_STARTED,
                        user_identifier=input_dto.actor,
                        entity_name="EXPEDITION",
                        entity_id=expedition.id,
                        company_id=expedition.company_id or None,
                        new_state={
                            "internal_id": expedition.internal_id,
                            "company_id": expedition.company_id,
                            "status": str(expedition.status),
                        },
                    )
                )

            # 4. Validar estado y generar DeCAEstructurado con DeCAEngine
            try:
                # Asignar código oficial único
                deca_code = self.deca_repo.next_deca_code(expedition.fiscal_year)

                # Generar token criptográfico y URL pública (Estrategia A)
                public_token = PublicDeCaTokenService.generate_token()
                public_token_hash = PublicDeCaTokenService.hash_token(public_token)
                public_url = PublicDeCaTokenService.build_public_url(
                    self.public_base_url, public_token
                )

                deca_estructurado, snapshot_dict, snapshot_hash = (
                    DeCAEngine.create_deca_estructurado(
                        expedition=expedition,
                        deca_code=deca_code,
                        version_number=1,
                        public_url=public_url,
                        qr_payload=public_url,
                    )
                )
            except (ExpeditionNotReadyException, DeCAEmissionException) as exc:
                if self.audit_service:
                    self.audit_service.record(
                        AuditEvent(
                            action=AuditAction.DECA_EMISSION_FAILED,
                            user_identifier=input_dto.actor,
                            entity_name="EXPEDITION",
                            entity_id=expedition.id,
                            company_id=expedition.company_id or None,
                            new_state={"error": str(exc)},
                        )
                    )
                raise

            # 5. Renderizado del documento PDF
            try:
                pdf_bytes = self.pdf_renderer.render(deca_estructurado)
            except Exception as exc:
                if self.audit_service:
                    self.audit_service.record(
                        AuditEvent(
                            action=AuditAction.DECA_EMISSION_FAILED,
                            user_identifier=input_dto.actor,
                            entity_name="EXPEDITION",
                            entity_id=expedition.id,
                            company_id=expedition.company_id or None,
                            new_state={"error": f"Fallo en renderizado PDF: {exc}"},
                        )
                    )
                raise DeCAEmissionException(f"Error renderizando el documento PDF: {exc}") from exc

            # 6. Cálculo del hash SHA-256 del binario final
            pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

            # 7. Almacenamiento custodial del PDF
            storage_path = f"deca/{expedition.fiscal_year}/{deca_code}.pdf"
            try:
                saved_path = self.storage_service.save(pdf_bytes, storage_path)
            except Exception as exc:
                if self.audit_service:
                    self.audit_service.record(
                        AuditEvent(
                            action=AuditAction.DECA_EMISSION_FAILED,
                            user_identifier=input_dto.actor,
                            entity_name="EXPEDITION",
                            entity_id=expedition.id,
                            company_id=expedition.company_id or None,
                            new_state={"error": f"Fallo en custodia física: {exc}"},
                        )
                    )
                raise StorageException(f"Error almacenando el documento PDF: {exc}") from exc

            # 8. Creación de la versión física inmutable y la entidad DeCA
            deca_version = DeCAVersion(
                version_number=1,
                pdf_sha256=pdf_sha256,
                pdf_storage_path=saved_path,
                pdf_size_bytes=len(pdf_bytes),
                snapshot_hash=snapshot_hash,
                snapshot_data=snapshot_dict,
                created_at=deca_estructurado.issue_datetime,
            )

            deca = DeCA(
                expedition_id=expedition.id,
                company_id=expedition.company_id or "TOMATES_DE_AUTOR",
                deca_code=deca_code,
                service_start_at=deca_estructurado.issue_datetime,
                current_version=1,
                status=DeCAStatus.ISSUED,
                public_access_token=public_token,
                public_token_hash=public_token_hash,
            )
            deca.add_version(deca_version)

            # Persistir DeCA
            self.deca_repo.save(deca)

            # 9. Transición de estado de la Expedición a DECA_GENERADO
            expedition.status = ExpeditionStatus.DECA_GENERADO
            self.expedition_repo.save(expedition, company_id=input_dto.company_id)

            # 10. Registrar auditoría de emisión exitosa
            if self.audit_service:
                self.audit_service.record(
                    AuditEvent(
                        action=AuditAction.DECA_EMITTED,
                        user_identifier=input_dto.actor,
                        entity_name="DECA",
                        entity_id=deca.id,
                        company_id=deca.company_id,
                        new_state={
                            "deca_code": deca_code,
                            "version": 1,
                            "company_id": deca.company_id,
                            "expedition_id": str(expedition.id),
                            "pdf_sha256": pdf_sha256,
                            "pdf_storage_path": saved_path,
                            "public_token_masked": PublicDeCaTokenService.mask_token(public_token),
                            "public_url_masked": (
                                f"{self.public_base_url}/d/"
                                f"{PublicDeCaTokenService.mask_token(public_token)}"
                            ),
                        },
                    )
                )

            return EmitDeCAResultDTO(
                deca_id=str(deca.id),
                version=1,
                expedition_id=str(expedition.id),
                status=str(deca.status),
                pdf_filename=f"{deca_code}.pdf",
                pdf_sha256=pdf_sha256,
                pdf_size_bytes=len(pdf_bytes),
                issued_at=deca_estructurado.issue_datetime.isoformat(),
                company_id=deca.company_id,
                public_token=public_token,
                public_url=public_url,
                is_idempotent=False,
                message="DeCA emitido y custodiado correctamente.",
            )
