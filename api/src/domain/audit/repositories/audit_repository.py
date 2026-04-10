"""Domain layer — Audit repository interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from src.domain.audit.entities.audit_log import AuditLog, AuditAction


class IAuditRepository(ABC):
    """Interface do repositório de logs de auditoria."""

    @abstractmethod
    async def save(self, audit_log: AuditLog) -> AuditLog:
        """Persiste um log de auditoria."""
        ...

    @abstractmethod
    async def find_by_document(
        self,
        document_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[AuditLog], int]:
        """Histórico de ações em um documento específico."""
        ...

    @abstractmethod
    async def find_by_filters(
        self,
        user_id: Optional[UUID] = None,
        action: Optional[AuditAction] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        document_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[AuditLog], int]:
        """Busca logs com filtros."""
        ...
