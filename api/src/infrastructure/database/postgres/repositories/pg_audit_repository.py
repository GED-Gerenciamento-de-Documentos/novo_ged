"""Infrastructure — PostgreSQL AuditLog repository."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.audit.entities.audit_log import AuditAction, AuditLog
from src.domain.audit.repositories.audit_repository import IAuditRepository
from src.infrastructure.database.postgres.models.audit_model import AuditLogModel


def _model_to_entity(model: AuditLogModel) -> AuditLog:
    return AuditLog(
        id=model.id,
        action=AuditAction(model.action),
        user_id=model.user_id,
        user_email=model.user_email,
        user_role=model.user_role,
        ip_address=model.ip_address,
        user_agent=model.user_agent,
        timestamp=model.timestamp,
        document_id=model.document_id,
        document_title=model.document_title,
        additional_data=model.additional_data or {},
        success=model.success,
        error_message=model.error_message,
    )


class PgAuditRepository(IAuditRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, audit_log: AuditLog) -> AuditLog:
        model = AuditLogModel(
            id=audit_log.id,
            action=audit_log.action.value,
            user_id=audit_log.user_id,
            user_email=audit_log.user_email,
            user_role=audit_log.user_role,
            ip_address=audit_log.ip_address,
            user_agent=audit_log.user_agent,
            timestamp=audit_log.timestamp,
            document_id=audit_log.document_id,
            document_title=audit_log.document_title,
            additional_data=audit_log.additional_data,
            success=audit_log.success,
            error_message=audit_log.error_message,
        )
        self._session.add(model)
        await self._session.flush()
        return audit_log

    async def find_by_document(
        self, document_id: uuid.UUID, page: int = 1, page_size: int = 50
    ) -> tuple[List[AuditLog], int]:
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.document_id == document_id)
            .order_by(AuditLogModel.timestamp.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_stmt = (
            select(func.count())
            .select_from(AuditLogModel)
            .where(AuditLogModel.document_id == document_id)
        )
        results = await self._session.execute(stmt)
        count = await self._session.execute(count_stmt)
        return [_model_to_entity(m) for m in results.scalars().all()], count.scalar_one()

    async def find_by_filters(
        self,
        user_id: Optional[uuid.UUID] = None,
        action: Optional[AuditAction] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        document_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[AuditLog], int]:
        stmt = select(AuditLogModel)
        count_stmt = select(func.count()).select_from(AuditLogModel)

        if user_id:
            stmt = stmt.where(AuditLogModel.user_id == user_id)
            count_stmt = count_stmt.where(AuditLogModel.user_id == user_id)
        if action:
            stmt = stmt.where(AuditLogModel.action == action.value)
            count_stmt = count_stmt.where(AuditLogModel.action == action.value)
        if date_from:
            stmt = stmt.where(AuditLogModel.timestamp >= date_from)
            count_stmt = count_stmt.where(AuditLogModel.timestamp >= date_from)
        if date_to:
            stmt = stmt.where(AuditLogModel.timestamp <= date_to)
            count_stmt = count_stmt.where(AuditLogModel.timestamp <= date_to)
        if document_id:
            stmt = stmt.where(AuditLogModel.document_id == document_id)
            count_stmt = count_stmt.where(AuditLogModel.document_id == document_id)

        stmt = stmt.order_by(AuditLogModel.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)

        results = await self._session.execute(stmt)
        count = await self._session.execute(count_stmt)
        return [_model_to_entity(m) for m in results.scalars().all()], count.scalar_one()
