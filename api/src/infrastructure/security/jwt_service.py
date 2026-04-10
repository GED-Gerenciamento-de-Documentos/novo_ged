"""
Infrastructure — JWT Security Service.

Geração, validação e revogação de tokens JWT.
Usa Redis para blacklist de tokens revogados (logout).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
import structlog

from src.infrastructure.cache.redis_cache import RedisCache
from src.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()


class TokenPayload:
    """DTO para payload do JWT."""

    def __init__(
        self,
        user_id: str,
        email: str,
        role: str,
        jti: str,
        token_type: str = "access",
    ):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.jti = jti
        self.token_type = token_type


class JwtService:
    """
    Serviço de JWT — criação e validação de tokens.

    Single Responsibility: apenas operações relacionadas a JWT.
    """

    @staticmethod
    def _create_token(
        data: dict,
        expires_delta: timedelta,
        token_type: str = "access",
    ) -> str:
        """Cria um token JWT com JTI único para suporte a revogação."""
        payload = data.copy()
        now = datetime.now(timezone.utc)
        jti = str(uuid.uuid4())

        payload.update({
            "iat": now,
            "exp": now + expires_delta,
            "jti": jti,
            "type": token_type,
        })

        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @classmethod
    def create_access_token(cls, user_id: str, email: str, role: str) -> str:
        """Cria token de acesso com validade curta."""
        return cls._create_token(
            data={"sub": user_id, "email": email, "role": role},
            expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
            token_type="access",
        )

    @classmethod
    def create_refresh_token(cls, user_id: str, email: str, role: str) -> str:
        """Cria refresh token com validade longa."""
        return cls._create_token(
            data={"sub": user_id, "email": email, "role": role},
            expires_delta=timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            token_type="refresh",
        )

    @classmethod
    def decode_token(cls, token: str) -> Optional[TokenPayload]:
        """
        Decodifica e valida um token JWT.
        Retorna None se inválido ou expirado.
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            return TokenPayload(
                user_id=payload.get("sub"),
                email=payload.get("email"),
                role=payload.get("role"),
                jti=payload.get("jti"),
                token_type=payload.get("type", "access"),
            )
        except JWTError as e:
            logger.warning("jwt_decode_failed", error=str(e))
            return None

    @classmethod
    async def revoke_token(cls, token: str) -> bool:
        """
        Revoga um token adicionando-o à blacklist Redis.
        O TTL é calculado com base no tempo restante do token.
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            jti = payload.get("jti")
            exp = payload.get("exp")
            if not jti or not exp:
                return False

            # TTL = segundos restantes até expiração
            now = datetime.now(timezone.utc).timestamp()
            ttl = max(int(exp - now), 1)

            await RedisCache.blacklist_token(jti, ttl)
            return True

        except JWTError:
            return False

    @classmethod
    async def is_token_valid(cls, token: str) -> tuple[bool, Optional[TokenPayload]]:
        """
        Verificação completa de token:
        1. Valida assinatura e expiração
        2. Verifica se está na blacklist (revogado)

        Returns: (is_valid, payload)
        """
        payload = cls.decode_token(token)
        if payload is None:
            return False, None

        # Verificar se foi revogado (logout)
        if await RedisCache.is_token_blacklisted(payload.jti):
            logger.warning("token_blacklisted_access_attempt", jti=payload.jti)
            return False, None

        return True, payload
