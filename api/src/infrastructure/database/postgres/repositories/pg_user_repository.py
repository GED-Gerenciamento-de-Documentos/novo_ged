"""Infrastructure — PostgreSQL repositories for User and AuditLog."""
from __future__ import annotations

import uuid
from typing import Optional, List
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.users.entities.user import User, UserRole
from src.domain.users.repositories.user_repository import IUserRepository
from src.infrastructure.database.postgres.models.user_model import UserModel


def _user_model_to_entity(model: UserModel) -> User:
    return User(
        id=model.id,
        name=model.name,
        email=model.email,
        password_hash=model.password_hash,
        role=UserRole(model.role),
        department=model.department,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
        last_login_at=model.last_login_at,
    )


class PgUserRepository(IUserRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, user: User) -> User:
        model = UserModel(
            id=user.id,
            name=user.name,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role.value,
            department=user.department,
            is_active=user.is_active,
        )
        self._session.add(model)
        await self._session.flush()
        return user

    async def update(self, user: User) -> User:
        await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user.id)
            .values(
                name=user.name,
                role=user.role.value,
                department=user.department,
                is_active=user.is_active,
                last_login_at=user.last_login_at,
            )
        )
        return user

    async def find_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        return _user_model_to_entity(model) if model else None

    async def find_by_email(self, email: str) -> Optional[User]:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        model = result.scalar_one_or_none()
        return _user_model_to_entity(model) if model else None

    async def find_all(
        self,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[User], int]:
        stmt = select(UserModel)
        count_stmt = select(func.count()).select_from(UserModel)

        if role:
            stmt = stmt.where(UserModel.role == role.value)
            count_stmt = count_stmt.where(UserModel.role == role.value)
        if is_active is not None:
            stmt = stmt.where(UserModel.is_active == is_active)
            count_stmt = count_stmt.where(UserModel.is_active == is_active)

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(stmt)
        count_result = await self._session.execute(count_stmt)

        users = [_user_model_to_entity(m) for m in result.scalars().all()]
        total = count_result.scalar_one()
        return users, total

    async def exists_by_email(self, email: str) -> bool:
        result = await self._session.execute(
            select(func.count()).select_from(UserModel).where(UserModel.email == email)
        )
        return result.scalar_one() > 0
