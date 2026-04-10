"""Infrastructure — AuditLog ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.infrastructure.database.postgres.connection import Base
from src.domain.audit.entities.audit_log import AuditAction


class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_user_id", "user_id"),
        Index("ix_audit_document_id", "document_id"),
        Index("ix_audit_action", "action"),
        Index("ix_audit_timestamp", "timestamp"),
        {"schema": "ged"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action: Mapped[str] = mapped_column(
        SAEnum(AuditAction, name="audit_action_enum", schema="ged"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    user_role: Mapped[str] = mapped_column(String(50), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(50), nullable=False)
    user_agent: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    document_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    additional_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
