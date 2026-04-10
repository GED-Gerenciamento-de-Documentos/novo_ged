"""
Presentation — Auth Dependencies (FastAPI DI).

Fornece o usuário autenticado atual via JWT para todas as rotas protegidas.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.infrastructure.security.jwt_service import JwtService, TokenPayload

logger = structlog.get_logger()

security = HTTPBearer(auto_error=True)


@dataclass
class CurrentUser:
    """DTO representando o usuário autenticado extraído do JWT."""
    user_id: uuid.UUID
    email: str
    role: str


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> CurrentUser:
    """
    Dependency: Valida JWT e retorna o usuário autenticado.
    Verifica blacklist Redis para tokens revogados (logout).
    """
    token = credentials.credentials
    is_valid, payload = await JwtService.is_token_valid(token)

    if not is_valid or payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tipo de token inválido. Use o access token.",
        )

    return CurrentUser(
        user_id=uuid.UUID(payload.user_id),
        email=payload.email,
        role=payload.role,
    )


def require_role(*roles: str):
    """
    Dependency factory — restringe acesso por perfil de usuário.

    Uso:
        @router.get("/admin-only")
        async def admin_only(user = Depends(require_role("ADMINISTRADOR"))):
            ...
    """
    async def check_role(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.role not in roles:
            logger.warning(
                "unauthorized_access_attempt",
                user_email=current_user.email,
                user_role=current_user.role,
                required_roles=roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Perfis necessários: {', '.join(roles)}.",
            )
        return current_user

    return check_role


# Alias convenientes para os perfis mais comuns
RequireOperador = Depends(require_role("OPERADOR", "GESTOR", "ADMINISTRADOR"))
RequireGestor = Depends(require_role("GESTOR", "ADMINISTRADOR"))
RequireAdministrador = Depends(require_role("ADMINISTRADOR"))
