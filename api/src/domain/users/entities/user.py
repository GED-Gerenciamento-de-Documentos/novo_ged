"""Domain layer — User entity."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    OPERADOR = "OPERADOR"          # Upload, busca, visualização (não confidencial)
    GESTOR = "GESTOR"              # + confidenciais, atualizar metadados, audit logs
    ADMINISTRADOR = "ADMINISTRADOR"  # + deletar, gerenciar usuários


@dataclass
class User:
    """
    Entidade de domínio — Usuário do sistema GED.
    Contém apenas regras de negócio do domínio de usuários.
    """

    id: uuid.UUID
    name: str
    email: str
    password_hash: str
    role: UserRole
    department: str
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None

    # ==========================================
    # Regras de negócio do domínio
    # ==========================================

    def can_upload(self) -> bool:
        return self.is_active

    def can_view_confidential(self) -> bool:
        return self.role in (UserRole.GESTOR, UserRole.ADMINISTRADOR) and self.is_active

    def can_update_metadata(self) -> bool:
        return self.role in (UserRole.GESTOR, UserRole.ADMINISTRADOR) and self.is_active

    def can_delete_documents(self) -> bool:
        return self.role == UserRole.ADMINISTRADOR and self.is_active

    def can_view_audit_logs(self) -> bool:
        return self.role in (UserRole.GESTOR, UserRole.ADMINISTRADOR) and self.is_active

    def can_manage_users(self) -> bool:
        return self.role == UserRole.ADMINISTRADOR and self.is_active

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = datetime.utcnow()

    def activate(self) -> None:
        self.is_active = True
        self.updated_at = datetime.utcnow()

    def record_login(self) -> None:
        self.last_login_at = datetime.utcnow()

    def update_role(self, new_role: UserRole) -> None:
        self.role = new_role
        self.updated_at = datetime.utcnow()

    @classmethod
    def create_new(
        cls,
        name: str,
        email: str,
        password_hash: str,
        role: UserRole,
        department: str,
    ) -> "User":
        return cls(
            id=uuid.uuid4(),
            name=name,
            email=email,
            password_hash=password_hash,
            role=role,
            department=department,
        )
