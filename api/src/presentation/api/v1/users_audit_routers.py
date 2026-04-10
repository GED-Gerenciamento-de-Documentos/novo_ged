"""Presentation — Users and Audit routers + main v1 aggregator."""
from __future__ import annotations

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from src.infrastructure.database.postgres.connection import get_db_session
from src.infrastructure.database.postgres.repositories.pg_user_repository import PgUserRepository
from src.infrastructure.database.postgres.repositories.pg_audit_repository import PgAuditRepository
from src.application.users.user_use_cases import CreateUserInput, CreateUserUseCase
from src.domain.users.entities.user import UserRole
from src.domain.audit.entities.audit_log import AuditAction
from src.presentation.dependencies.auth_dependencies import CurrentUser, get_current_user, require_role
from src.presentation.schemas.schemas import (
    AuditListResponse,
    AuditLogResponse,
    CreateUserRequest,
    MessageResponse,
    UserListResponse,
    UserResponse,
)

# ==========================================
# Users Router
# ==========================================
users_router = APIRouter(prefix="/users", tags=["Usuários"])


@users_router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar usuário (ADMINISTRADOR)",
    dependencies=[Depends(require_role("ADMINISTRADOR"))],
)
async def create_user(
    body: CreateUserRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserResponse:
    """Cria um novo usuário no sistema."""
    use_case = CreateUserUseCase(user_repository=PgUserRepository(session))
    try:
        user = await use_case.execute(
            CreateUserInput(
                name=body.name,
                email=body.email,
                password=body.password,
                role=UserRole(body.role),
                department=body.department,
                created_by_role=current_user.role,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.value,
        department=user.department,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@users_router.get(
    "",
    response_model=UserListResponse,
    summary="Listar usuários (ADMINISTRADOR)",
    dependencies=[Depends(require_role("ADMINISTRADOR"))],
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserListResponse:
    repo = PgUserRepository(session)
    users, total = await repo.find_all(page=page, page_size=page_size)
    total_pages = (total + page_size - 1) // page_size
    return UserListResponse(
        items=[
            UserResponse(
                id=u.id, name=u.name, email=u.email, role=u.role.value,
                department=u.department, is_active=u.is_active,
                created_at=u.created_at, last_login_at=u.last_login_at,
            )
            for u in users
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@users_router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Desativar usuário (ADMINISTRADOR)",
    dependencies=[Depends(require_role("ADMINISTRADOR"))],
)
async def deactivate_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    repo = PgUserRepository(session)
    user = await repo.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    user.deactivate()
    await repo.update(user)
    return MessageResponse(message=f"Usuário {user.email} desativado com sucesso.")


# ==========================================
# Audit Router
# ==========================================
audit_router = APIRouter(prefix="/audit", tags=["Auditoria"])


@audit_router.get(
    "/logs",
    response_model=AuditListResponse,
    summary="Logs de auditoria (GESTOR+)",
    dependencies=[Depends(require_role("GESTOR", "ADMINISTRADOR"))],
)
async def get_audit_logs(
    user_id: Optional[uuid.UUID] = Query(None),
    action: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> AuditListResponse:
    """Retorna logs de auditoria com filtros."""
    from datetime import datetime
    repo = PgAuditRepository(session)

    action_enum = None
    if action:
        try:
            action_enum = AuditAction(action.upper())
        except ValueError:
            pass

    dt_from = datetime.fromisoformat(date_from) if date_from else None
    dt_to = datetime.fromisoformat(date_to) if date_to else None

    logs, total = await repo.find_by_filters(
        user_id=user_id,
        action=action_enum,
        date_from=dt_from,
        date_to=dt_to,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size

    return AuditListResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                action=log.action.value,
                user_email=log.user_email,
                user_role=log.user_role,
                ip_address=log.ip_address,
                timestamp=log.timestamp,
                document_id=log.document_id,
                document_title=log.document_title,
                success=log.success,
                error_message=log.error_message,
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@audit_router.get(
    "/documents/{document_id}",
    response_model=AuditListResponse,
    summary="Histórico de um documento (GESTOR+)",
    dependencies=[Depends(require_role("GESTOR", "ADMINISTRADOR"))],
)
async def get_document_history(
    document_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> AuditListResponse:
    """Retorna o histórico completo de ações em um documento."""
    repo = PgAuditRepository(session)
    logs, total = await repo.find_by_document(document_id, page=page, page_size=page_size)
    total_pages = (total + page_size - 1) // page_size

    return AuditListResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                action=log.action.value,
                user_email=log.user_email,
                user_role=log.user_role,
                ip_address=log.ip_address,
                timestamp=log.timestamp,
                document_id=log.document_id,
                document_title=log.document_title,
                success=log.success,
                error_message=log.error_message,
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
