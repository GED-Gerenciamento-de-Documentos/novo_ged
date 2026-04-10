"""Domain layer — AuditLog entity."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class AuditAction(str, Enum):
    UPLOAD = "UPLOAD"
    VIEW = "VIEW"
    DOWNLOAD = "DOWNLOAD"
    UPDATE_METADATA = "UPDATE_METADATA"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    FAILED_LOGIN = "FAILED_LOGIN"
    SEARCH = "SEARCH"


@dataclass
class AuditLog:
    """
    Entidade de Auditoria — registra toda interação com documentos.
    Imutável por design: logs de auditoria nunca devem ser alterados.
    Conformidade LGPD: art. 37 — responsabilidade pelo tratamento de dados.
    """

    id: uuid.UUID
    action: AuditAction
    user_id: uuid.UUID
    user_email: str           # Desnormalizado para consulta sem JOIN
    user_role: str
    ip_address: str
    user_agent: str
    timestamp: datetime

    # Alvo da operação (opcional — ex: LOGIN não tem documento)
    document_id: Optional[uuid.UUID] = None
    document_title: Optional[str] = None  # Desnormalizado para histórico

    # Contexto adicional (request path, filtros de busca, etc.)
    additional_data: dict = field(default_factory=dict)

    # Resultado da operação
    success: bool = True
    error_message: Optional[str] = None

    @classmethod
    def create(
        cls,
        action: AuditAction,
        user_id: uuid.UUID,
        user_email: str,
        user_role: str,
        ip_address: str,
        user_agent: str,
        document_id: Optional[uuid.UUID] = None,
        document_title: Optional[str] = None,
        additional_data: Optional[dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> "AuditLog":
        return cls(
            id=uuid.uuid4(),
            action=action,
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.utcnow(),
            document_id=document_id,
            document_title=document_title,
            additional_data=additional_data or {},
            success=success,
            error_message=error_message,
        )
