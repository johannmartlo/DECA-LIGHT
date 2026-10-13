from __future__ import annotations

import threading
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.application.ports.audit_service import AuditServicePort
from src.application.ports.company_repository import CompanyRepositoryPort
from src.application.ports.deca_repository import DeCARepositoryPort
from src.application.ports.email_delivery_repository import (
    EmailDeliveryRepositoryPort,
)
from src.application.ports.email_sender import EmailSenderPort
from src.application.ports.expedition_repository import ExpeditionRepositoryPort
from src.application.ports.pdf_renderer import PdfRendererPort
from src.application.ports.storage_service import StorageServicePort
from src.application.ports.tenant_authenticator_port import TenantAuthenticatorPort
from src.config.companies import build_companies, build_test_identities
from src.config.settings import Settings, get_settings
from src.domain.exceptions import (
    ForbiddenTenantException,
    UnauthorizedCompanyContextException,
)
from src.domain.value_objects import CompanyContext
from src.infrastructure.auth.api_key_authenticator import InMemoryTenantAuthenticator
from src.infrastructure.document.reportlab_pdf_renderer import ReportLabPdfRenderer
from src.infrastructure.email.fake_microsoft_graph_email_sender import (
    FakeMicrosoftGraphEmailSender,
)
from src.infrastructure.email.microsoft_graph_email_sender import (
    MicrosoftGraphEmailSender,
)
from src.infrastructure.logging.in_memory_audit_service import InMemoryAuditService
from src.infrastructure.repositories.in_memory_company_repository import (
    InMemoryCompanyRepository,
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

bearer_scheme = HTTPBearer(auto_error=False)

_authenticator_instance: TenantAuthenticatorPort | None = None
_authenticator_lock = threading.Lock()


def get_tenant_authenticator() -> TenantAuthenticatorPort:
    """Provee la instancia del autenticador M2M precargado con identidades seguras."""
    global _authenticator_instance
    with _authenticator_lock:
        if _authenticator_instance is None:
            _authenticator_instance = InMemoryTenantAuthenticator(build_test_identities())
        return _authenticator_instance


def reset_tenant_authenticator_instance() -> None:
    """Reinicia la instancia del autenticador para pruebas."""
    global _authenticator_instance
    with _authenticator_lock:
        _authenticator_instance = None


def get_authorized_company_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_company_id: str | None = Header(None, alias="X-Company-Id"),
    authenticator: TenantAuthenticatorPort = Depends(get_tenant_authenticator),
) -> CompanyContext:
    """Resuelve, autentica y autoriza el contexto multiempresa activo en el servidor.

    Garantiza que ninguna cabecera HTTP no verificada cree un contexto confiable.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de autenticación requeridas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    identity = authenticator.authenticate_key(credentials.credentials)
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial inválida o revocada.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        active_company = authenticator.resolve_active_company(identity, x_company_id)
    except ForbiddenTenantException as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: empresa no autorizada.",
        ) from exc
    except UnauthorizedCompanyContextException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return CompanyContext.create(company_id=active_company, actor=identity.identity_id, is_verified=True)


_email_sender_instance: EmailSenderPort | None = None
_email_sender_lock = threading.Lock()

_email_delivery_repo_instance: EmailDeliveryRepositoryPort | None = None
_email_delivery_repo_lock = threading.Lock()


@lru_cache
def get_company_repository() -> CompanyRepositoryPort:
    """Provee el repositorio de empresas con las sociedades iniciales del grupo."""
    settings = get_settings()
    repo = InMemoryCompanyRepository()
    for company in build_companies(settings):
        repo.save(company)
    return repo


@lru_cache
def get_expedition_repository() -> ExpeditionRepositoryPort:
    """Provee la instancia del repositorio de expediciones (InMemory en MVP / SQLite / Postgres)."""
    return InMemoryExpeditionRepository()


@lru_cache
def get_deca_repository() -> DeCARepositoryPort:
    """Provee la instancia del repositorio de documentos DeCA y versiones inmutables."""
    return InMemoryDeCARepository()


@lru_cache
def get_audit_service() -> AuditServicePort:
    """Provee el servicio de auditoría inmutable."""
    return InMemoryAuditService()


@lru_cache
def get_pdf_renderer() -> PdfRendererPort:
    """Provee el motor de renderizado vectorial de PDFs con ReportLab."""
    return ReportLabPdfRenderer()


def get_storage_service(
    settings: Settings = Depends(get_settings),
) -> StorageServicePort:
    """Provee el servicio custodial de almacenamiento con prevención de path traversal."""
    return LocalPdfStorage(settings.resolved_storage_path)


def get_email_delivery_repository() -> EmailDeliveryRepositoryPort:
    """Provee la instancia del repositorio de envíos de correo."""
    global _email_delivery_repo_instance
    with _email_delivery_repo_lock:
        if _email_delivery_repo_instance is None:
            _email_delivery_repo_instance = InMemoryEmailDeliveryRepository()
        return _email_delivery_repo_instance


def reset_email_delivery_repository_instance() -> None:
    """Reinicia la instancia del repositorio para pruebas."""
    global _email_delivery_repo_instance
    with _email_delivery_repo_lock:
        _email_delivery_repo_instance = None


def get_email_sender(
    settings: Settings = Depends(get_settings),
) -> EmailSenderPort:
    """Provee el adaptador de envío según configuración (Microsoft Graph, Fake, Stub)."""
    if settings.EMAIL_PROVIDER == "graph":
        return MicrosoftGraphEmailSender(
            tenant_id=settings.MS_GRAPH_TENANT_ID,
            client_id=settings.MS_GRAPH_CLIENT_ID,
            client_secret=settings.MS_GRAPH_CLIENT_SECRET,
            sender_email=settings.MS_GRAPH_SENDER_EMAIL,
        )
    global _email_sender_instance
    with _email_sender_lock:
        if _email_sender_instance is None:
            _email_sender_instance = FakeMicrosoftGraphEmailSender(
                sender_email=settings.MS_GRAPH_SENDER_EMAIL
            )
        return _email_sender_instance


def reset_email_sender_instance() -> None:
    """Reinicia la instancia del sender para pruebas."""
    global _email_sender_instance
    with _email_sender_lock:
        _email_sender_instance = None
