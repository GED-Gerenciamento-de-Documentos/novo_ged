"""
Infrastructure — Redis Cache & Token Blacklist.

Usado para:
1. Cache de buscas frequentes (TTL configurável)
2. Blacklist de JWT tokens revogados (logout)
3. Rate limiting de tentativas de login
"""
from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as redis
import structlog

from src.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Prefixos de chaves Redis para namespacing
PREFIX_TOKEN_BLACKLIST = "ged:token:blacklist:"
PREFIX_CACHE = "ged:cache:"
PREFIX_LOGIN_ATTEMPTS = "ged:login:attempts:"
PREFIX_USER_SESSION = "ged:session:"


class RedisCache:
    """
    Manager de conexão e operações Redis.
    Padrão Singleton via variável de módulo.
    """

    _client: Optional[redis.Redis] = None

    @classmethod
    async def connect(cls) -> None:
        """Inicializa conexão com Redis."""
        cls._client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        # Testar conexão
        await cls._client.ping()
        logger.info("redis_connected", url=settings.REDIS_URL.split("@")[-1])

    @classmethod
    async def disconnect(cls) -> None:
        """Encerra conexão com Redis."""
        if cls._client:
            await cls._client.aclose()
            cls._client = None

    @classmethod
    def get_client(cls) -> redis.Redis:
        if cls._client is None:
            raise RuntimeError("Redis não inicializado. Chame RedisCache.connect() primeiro.")
        return cls._client

    # ==========================================
    # Token Blacklist (JWT Revogados)
    # ==========================================

    @classmethod
    async def blacklist_token(cls, jti: str, ttl_seconds: int) -> None:
        """Adiciona JTI do token à blacklist. TTL = tempo restante do token."""
        key = f"{PREFIX_TOKEN_BLACKLIST}{jti}"
        await cls.get_client().setex(key, ttl_seconds, "revoked")
        logger.info("token_blacklisted", jti=jti, ttl=ttl_seconds)

    @classmethod
    async def is_token_blacklisted(cls, jti: str) -> bool:
        """Verifica se o token foi revogado."""
        key = f"{PREFIX_TOKEN_BLACKLIST}{jti}"
        result = await cls.get_client().exists(key)
        return bool(result)

    # ==========================================
    # Cache Genérico
    # ==========================================

    @classmethod
    async def set_cache(cls, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Armazena valor no cache com TTL."""
        cache_key = f"{PREFIX_CACHE}{key}"
        serialized = json.dumps(value, default=str)
        await cls.get_client().setex(cache_key, ttl_seconds, serialized)

    @classmethod
    async def get_cache(cls, key: str) -> Optional[Any]:
        """Recupera valor do cache. Retorna None se não existir ou expirado."""
        cache_key = f"{PREFIX_CACHE}{key}"
        value = await cls.get_client().get(cache_key)
        if value is None:
            return None
        return json.loads(value)

    @classmethod
    async def invalidate_cache(cls, pattern: str) -> int:
        """Invalida todas as chaves que correspondem ao padrão."""
        cache_key = f"{PREFIX_CACHE}{pattern}"
        keys = await cls.get_client().keys(cache_key)
        if keys:
            return await cls.get_client().delete(*keys)
        return 0

    # ==========================================
    # Rate Limiting de Login
    # ==========================================

    @classmethod
    async def increment_login_attempts(cls, email: str) -> int:
        """Incrementa contador de tentativas de login. Retorna o total."""
        key = f"{PREFIX_LOGIN_ATTEMPTS}{email}"
        pipe = cls.get_client().pipeline()
        pipe.incr(key)
        pipe.expire(key, 900)  # 15 minutos de janela
        results = await pipe.execute()
        attempts = results[0]
        logger.warning("login_attempt", email=email, attempts=attempts)
        return attempts

    @classmethod
    async def get_login_attempts(cls, email: str) -> int:
        """Retorna o número atual de tentativas de login."""
        key = f"{PREFIX_LOGIN_ATTEMPTS}{email}"
        value = await cls.get_client().get(key)
        return int(value) if value else 0

    @classmethod
    async def reset_login_attempts(cls, email: str) -> None:
        """Reseta contador após login bem-sucedido."""
        key = f"{PREFIX_LOGIN_ATTEMPTS}{email}"
        await cls.get_client().delete(key)

    # ==========================================
    # Health Check
    # ==========================================

    @classmethod
    async def ping(cls) -> bool:
        """Verifica se o Redis está respondendo."""
        try:
            result = await cls.get_client().ping()
            return result
        except Exception:
            return False
