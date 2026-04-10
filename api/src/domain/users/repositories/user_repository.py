"""Domain layer — User repository interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID

from src.domain.users.entities.user import User, UserRole


class IUserRepository(ABC):
    """Interface do repositório de usuários."""

    @abstractmethod
    async def save(self, user: User) -> User:
        """Cria novo usuário."""
        ...

    @abstractmethod
    async def update(self, user: User) -> User:
        """Atualiza usuário existente."""
        ...

    @abstractmethod
    async def find_by_id(self, user_id: UUID) -> Optional[User]:
        """Busca usuário pelo ID."""
        ...

    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[User]:
        """Busca usuário pelo e-mail (usado no login)."""
        ...

    @abstractmethod
    async def find_all(
        self,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[User], int]:
        """Lista usuários com filtros opcionais."""
        ...

    @abstractmethod
    async def exists_by_email(self, email: str) -> bool:
        """Verifica se já existe usuário com o e-mail."""
        ...
