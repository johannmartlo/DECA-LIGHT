from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from src.application.ports.audit_service import AuditServicePort
from src.application.ports.deca_repository import DeCARepositoryPort
from src.application.ports.storage_service import StorageServicePort
from src.domain.entities.audit_event import AuditEvent
from src.domain.entities.deca import DeCA
from src.domain.enums import AuditAction
from src.domain.exceptions import StorageException
from src.domain.services.clock import Clock
from src.domain.services.public_token_service import PublicDeCaTokenService
from src.presentation.api.dependencies import (
    get_audit_service,
    get_deca_repository,
    get_storage_service,
)

logger = logging.getLogger("deca_light.public_api")

router = APIRouter(tags=["Inspección Pública DeCA"])

GENERIC_NOT_FOUND_DETAIL = "Documento DeCA no encontrado o no disponible."


def _extract_client_ip(request: Request) -> str:
    """Extrae la dirección IP cliente de forma segura considerando cabeceras de proxy."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@router.get(
    "/d/{token}",
    status_code=status.HTTP_200_OK,
    summary="Acceso público y efímero para inspección oficial de DeCA en carretera",
    description=(
        "Endpoint público no autenticado de visualización en ruta. Protegido contra "
        "enumeración e IDOR mediante token criptográfico de alta entropía. "
        "Expira automáticamente 7 días después de finalizado el transporte."
    ),
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Binario PDF del documento DeCA para visualización inline.",
        },
        404: {
            "description": (
                "Documento inexistente, expirado, revocado o token con sintaxis no válida."
            ),
        },
    },
)
async def get_public_deca(
    token: str,
    request: Request,
    deca_repo: DeCARepositoryPort = Depends(get_deca_repository),
    storage_service: StorageServicePort = Depends(get_storage_service),
    audit_service: AuditServicePort | None = Depends(get_audit_service),
) -> Response:
    client_ip = _extract_client_ip(request)
    user_agent = request.headers.get("user-agent", "unknown")
    token_masked = PublicDeCaTokenService.mask_token(token)

    # 1. Validación sintáctica del token criptográfico (longitud y juego base64url)
    if not PublicDeCaTokenService.is_valid_token_format(token):
        logger.warning(
            "Acceso público denegado por formato inválido de token [%s] desde IP %s",
            token_masked,
            client_ip,
        )
        if audit_service:
            audit_service.record(
                AuditEvent(
                    action=AuditAction.PUBLIC_DECA_ACCESS_NOT_FOUND,
                    user_identifier=f"IP:{client_ip}",
                    entity_name="DECA",
                    entity_id=None,
                    new_state={
                        "token_masked": token_masked,
                        "reason": "INVALID_TOKEN_FORMAT",
                        "client_ip": client_ip,
                        "user_agent": user_agent,
                    },
                )
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=GENERIC_NOT_FOUND_DETAIL,
        )

    # 2. Búsqueda determinista por hash SHA-256 del token (O(1), timing safe)
    deca: DeCA | None = deca_repo.get_by_public_token(token)
    if not deca:
        logger.info(
            "Acceso público: token no encontrado en base de datos [%s] desde IP %s",
            token_masked,
            client_ip,
        )
        if audit_service:
            audit_service.record(
                AuditEvent(
                    action=AuditAction.PUBLIC_DECA_ACCESS_NOT_FOUND,
                    user_identifier=f"IP:{client_ip}",
                    entity_name="DECA",
                    entity_id=None,
                    new_state={
                        "token_masked": token_masked,
                        "reason": "TOKEN_NOT_FOUND",
                        "client_ip": client_ip,
                        "user_agent": user_agent,
                    },
                )
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=GENERIC_NOT_FOUND_DETAIL,
        )

    # 3. Comprobación de vigencia temporal y estado de emisión
    current_time = Clock.now()
    if not deca.is_public_download_allowed(current_time):
        is_expired = deca.service_end_at is not None and current_time > (
            deca.service_end_at + timedelta(days=7)
        )
        action = (
            AuditAction.PUBLIC_DECA_ACCESS_EXPIRED
            if is_expired
            else AuditAction.PUBLIC_DECA_ACCESS_NOT_FOUND
        )

        logger.info(
            "Acceso público denegado para DeCA %s (estado: %s, expirado: %s) desde IP %s",
            deca.deca_code,
            deca.status,
            is_expired,
            client_ip,
        )

        if audit_service:
            audit_service.record(
                AuditEvent(
                    action=action,
                    user_identifier=f"IP:{client_ip}",
                    entity_name="DECA",
                    entity_id=deca.id,
                    new_state={
                        "deca_code": deca.deca_code,
                        "token_masked": token_masked,
                        "status": str(deca.status),
                        "service_end_at": (
                            deca.service_end_at.isoformat() if deca.service_end_at else None
                        ),
                        "client_ip": client_ip,
                        "user_agent": user_agent,
                    },
                )
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=GENERIC_NOT_FOUND_DETAIL,
        )

    # 4. Obtención de la versión activa y del binario custodial
    latest = deca.latest_version
    if not latest or not latest.pdf_storage_path:
        logger.error("DeCA %s no cuenta con archivo físico asociado.", deca.deca_code)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=GENERIC_NOT_FOUND_DETAIL,
        )

    try:
        pdf_bytes = storage_service.read(latest.pdf_storage_path)
    except StorageException as exc:
        logger.error("Error al leer archivo PDF de custodia para %s: %s", deca.deca_code, exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=GENERIC_NOT_FOUND_DETAIL,
        ) from exc

    # 5. Registrar auditoría de acceso exitoso
    if audit_service:
        audit_service.record(
            AuditEvent(
                action=AuditAction.PUBLIC_DECA_ACCESS_SUCCESS,
                user_identifier=f"IP:{client_ip}",
                entity_name="DECA",
                entity_id=deca.id,
                new_state={
                    "deca_code": deca.deca_code,
                    "version": latest.version_number,
                    "pdf_sha256": latest.pdf_sha256,
                    "token_masked": token_masked,
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                },
            )
        )

    logger.info(
        "Acceso público exitoso al DeCA %s por QR/token desde IP %s",
        deca.deca_code,
        client_ip,
    )

    # 6. Retorno de respuesta HTTP segura
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{deca.deca_code}.pdf"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
            "X-Content-Type-Options": "nosniff",
            "X-Robots-Tag": "noindex, nofollow, noarchive",
        },
    )
