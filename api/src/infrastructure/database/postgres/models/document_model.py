"""
Infrastructure — SQLAlchemy ORM Models.
Mapeamento da entidade Document para o banco PostgreSQL.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.infrastructure.database.postgres.connection import Base
from src.domain.documents.entities.document import DocumentType, FileFormat, StorageType, DocumentStatus


class DocumentModel(Base):
    """ORM Model para a tabela de documentos."""

    __tablename__ = "documents"
    __table_args__ = (
        # Índices para buscas frequentes
        Index("ix_documents_owner_name", "owner_name"),
        Index("ix_documents_owner_record_number", "owner_record_number"),
        Index("ix_documents_document_type", "document_type"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_created_at", "created_at"),
        Index("ix_documents_document_date", "document_date"),
        Index("ix_documents_uploaded_by_id", "uploaded_by_id"),
        {"schema": "ged"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[str] = mapped_column(
        SAEnum(DocumentType, name="document_type_enum", schema="ged"),
        nullable=False,
    )
    file_format: Mapped[str] = mapped_column(
        SAEnum(FileFormat, name="file_format_enum", schema="ged"),
        nullable=False,
    )
    storage_type: Mapped[str] = mapped_column(
        SAEnum(StorageType, name="storage_type_enum", schema="ged"),
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadados de identificação
    owner_name: Mapped[str] = mapped_column(String(300), nullable=False)
    owner_cpf_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_record_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Metadados de negócio
    document_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=list)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    # Metadados técnicos
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Controle de acesso
    is_confidential: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Ciclo de vida
    status: Mapped[str] = mapped_column(
        SAEnum(DocumentStatus, name="document_status_enum", schema="ged"),
        nullable=False,
        default=DocumentStatus.ACTIVE.value,
    )
    retention_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Auditoria
    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ged.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
