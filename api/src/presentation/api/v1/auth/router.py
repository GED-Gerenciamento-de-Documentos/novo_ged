"""
Presentation — Auth Router.
Endpoints de autenticação (login, refresh, logout).
"""
from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.users.user_use_cases import AuthenticateInput, AuthenticateUserUseCase
from src.infrastructure.cache.redis_cache import RedisCache
from src.infrastructure.database.postgres.connection import get_db_session
from src.infrastructure.database.postgres.repositories.pg_audit_repository import PgAuditRepository
from src.infrastructure.database.postgres.repositories.pg_user_repository import PgUserRepository
from src.infrastructure.security.jwt_service import JwtService
from src.presentation.dependencies.auth_dependencies import CurrentUser, get_current_user
from src.presentation.schemas.schemas import (
    LoginRequest,
    MessageResponse,
    RefreshTokenRequest,
    TokenResponse,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["Autenticação"])


def _get_client_info(request: Request) -> tuple[str, str]:
    """Extrai IP e User-Agent da requisição."""
    ip = request.client.host if request.client else "unknown"
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    user_agent = request.headers.get("User-Agent", "unknown")
    return ip, user_agent


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login — obtém tokens JWT",
    status_code=status.HTTP_200_OK,
)
async def login(
    request: Request,
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """
    Autentica o usuário com e-mail e senha.
    Retorna access_token (60min) e refresh_token (7 dias).
    Após 5 tentativas falhas, a conta é bloqueada por 15 minutos.
    """
    ip, user_agent = _get_client_info(request)

    use_case = AuthenticateUserUseCase(
        user_repository=PgUserRepository(session),
        audit_repository=PgAuditRepository(session),
    )

    try:
        output = await use_case.execute(
            AuthenticateInput(
                email=body.email,
                password=body.password,
                ip_address=ip,
                user_agent=user_agent,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    return TokenResponse(
        access_token=output.access_token,
        refresh_token=output.refresh_token,
        expires_in_minutes=output.expires_in_minutes,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar access token via refresh token",
)
async def refresh_token(body: RefreshTokenRequest) -> TokenResponse:
    """Gera novo access_token a partir de um refresh_token válido."""
    is_valid, payload = await JwtService.is_token_valid(body.refresh_token)

    if not is_valid or payload is None or payload.token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado.",
        )

    new_access_token = JwtService.create_access_token(
        user_id=payload.user_id,
        email=payload.email,
        role=payload.role,
    )
    new_refresh_token = JwtService.create_refresh_token(
        user_id=payload.user_id,
        email=payload.email,
        role=payload.role,
    )

    # Revogar o refresh token antigo
    await JwtService.revoke_token(body.refresh_token)

    from src.settings import get_settings
    settings = get_settings()
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout — revoga o token atual",
)
async def logout(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> MessageResponse:
    """
    Revoga o access token atual adicionando-o à blacklist Redis.
    O token não poderá mais ser usado mesmo antes de expirar.
    """
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()

    if token:
        revoked = await JwtService.revoke_token(token)
        if not revoked:
            logger.warning("logout_token_revoke_failed", user=current_user.email)

    logger.info("user_logout", email=current_user.email)
    return MessageResponse(message="Logout realizado com sucesso.")


@router.get(
    "/me",
    summary="Dados do usuário autenticado",
)
async def get_me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Retorna os dados básicos do usuário autenticado extraídos do JWT."""
    return {
        "user_id": str(current_user.user_id),
        "email": current_user.email,
        "role": current_user.role,
    }
