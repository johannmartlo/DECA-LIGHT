from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.session import Base


class CompanyORM(Base):
    """Modelo ORM para las sociedades emisoras del grupo (multiempresa / cargadores)."""

    __tablename__ = "companies"

    company_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fiscal_address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    document_aliases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    expeditions: Mapped[list[ExpeditionORM]] = relationship(
        "ExpeditionORM", back_populates="company"
    )
    decas: Mapped[list[DeCAORM]] = relationship("DeCAORM", back_populates="company")


class CarrierORM(Base):
    """Modelo ORM para transportistas homologados."""

    __tablename__ = "carriers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tax_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    aliases: Mapped[list[CarrierAliasORM]] = relationship(
        "CarrierAliasORM", back_populates="carrier", cascade="all, delete-orphan"
    )
    vehicles: Mapped[list[VehicleORM]] = relationship("VehicleORM", back_populates="carrier")
    expeditions: Mapped[list[ExpeditionORM]] = relationship(
        "ExpeditionORM", back_populates="carrier"
    )


class CarrierAliasORM(Base):
    """Modelo ORM para variaciones textuales y alias de transportistas."""

    __tablename__ = "carrier_aliases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    carrier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("carriers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    normalized_alias: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # Relaciones
    carrier: Mapped[CarrierORM] = relationship("CarrierORM", back_populates="aliases")


class VehicleORM(Base):
    """Modelo ORM para combinaciones y conjuntos de vehículos."""

    __tablename__ = "vehicles"

    __table_args__ = (
        CheckConstraint(
            "(tipo_vehiculo = 'RIGIDO' AND matricula_tractor IS NOT NULL AND "
            "matricula_remolque IS NULL) OR "
            "(tipo_vehiculo = 'ARTICULADO' AND matricula_tractor IS NOT NULL AND "
            "matricula_remolque IS NOT NULL)",
            name="ck_vehicle_type_plates",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    carrier_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("carriers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tipo_vehiculo: Mapped[str] = mapped_column(String(20), nullable=False)
    matricula_tractor: Mapped[str | None] = mapped_column(String(20), nullable=True)
    matricula_remolque: Mapped[str | None] = mapped_column(String(20), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    carrier: Mapped[CarrierORM | None] = relationship("CarrierORM", back_populates="vehicles")


class DocumentORM(Base):
    """Modelo ORM para documentos PDF importados (Carta de Porte o CMR)."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="application/pdf")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING", index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # Relaciones
    expeditions: Mapped[list[ExpeditionORM]] = relationship(
        "ExpeditionORM", back_populates="document"
    )


class ExpeditionORM(Base):
    """Modelo ORM para expediciones de transporte."""

    __tablename__ = "expeditions"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "internal_id", name="uq_expeditions_company_internal_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    internal_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reference: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    fiscal_year: Mapped[str] = mapped_column(String(10), nullable=False, default="2026")
    transport_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Empresa y cargador
    company_id: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("companies.company_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    issuer_detection_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    issuer_detection_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    shipper_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    shipper_tax_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    shipper_address: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Transportista
    carrier_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("carriers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    carrier_name_raw: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    carrier_tax_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    carrier_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Vehículo
    vehicle_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tractor_plate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    trailer_plate: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Mercancía y ruta
    origin: Mapped[str] = mapped_column(Text, nullable=False, default="")
    destination: Mapped[Text] = mapped_column(Text, nullable=False, default="")
    goods: Mapped[str] = mapped_column(Text, nullable=False, default="")
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Estado y metadatos
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="IMPORTADA", index=True)
    extraction_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    document: Mapped[DocumentORM | None] = relationship("DocumentORM", back_populates="expeditions")
    company: Mapped[CompanyORM | None] = relationship("CompanyORM", back_populates="expeditions")
    carrier: Mapped[CarrierORM | None] = relationship("CarrierORM", back_populates="expeditions")
    deca: Mapped[DeCAORM | None] = relationship(
        "DeCAORM", back_populates="expedition", uselist=False
    )
    email_deliveries: Mapped[list[EmailDeliveryORM]] = relationship(
        "EmailDeliveryORM", back_populates="expedition"
    )


class DeCAORM(Base):
    """Modelo ORM para el documento formal administrativo DeCA."""

    __tablename__ = "decas"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expedition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("expeditions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    company_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("companies.company_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    deca_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    public_access_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    public_token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    service_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    service_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    public_download_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    legal_custody_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    public_download_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ISSUED", index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    expedition: Mapped[ExpeditionORM] = relationship("ExpeditionORM", back_populates="deca")
    company: Mapped[CompanyORM] = relationship("CompanyORM", back_populates="decas")
    versions: Mapped[list[DeCAVersionORM]] = relationship(
        "DeCAVersionORM",
        back_populates="deca",
        order_by="DeCAVersionORM.version_number",
    )
    email_deliveries: Mapped[list[EmailDeliveryORM]] = relationship(
        "EmailDeliveryORM", back_populates="deca"
    )


class DeCAVersionORM(Base):
    """Modelo ORM para las versiones inmutables y snapshots de cada emisión de DeCA."""

    __tablename__ = "deca_versions"

    __table_args__ = (
        UniqueConstraint("deca_id", "version_number", name="uq_deca_version_number"),
        Index("ix_deca_versions_deca_version", "deca_id", "version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deca_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decas.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pdf_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    pdf_storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    pdf_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    modification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # Relaciones
    deca: Mapped[DeCAORM] = relationship("DeCAORM", back_populates="versions")


class EmailDeliveryORM(Base):
    """Modelo ORM para auditoría transaccional de envíos de correo."""

    __tablename__ = "email_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expedition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("expeditions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    deca_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decas.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    deca_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    deca_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    company_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("companies.company_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="EMAIL_PENDING", index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="graph")
    message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_resend: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relaciones
    expedition: Mapped[ExpeditionORM] = relationship(
        "ExpeditionORM", back_populates="email_deliveries"
    )
    deca: Mapped[DeCAORM] = relationship("DeCAORM", back_populates="email_deliveries")


class AuditEventORM(Base):
    """Modelo ORM append-only para el registro de auditoría."""

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    user_identifier: Mapped[str] = mapped_column(String(100), nullable=False, default="SYSTEM")
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    old_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    company_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
