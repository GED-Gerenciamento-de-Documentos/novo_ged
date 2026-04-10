"""
Infrastructure — PostgreSQL Connection Manager.
SQLAlchemy 2.0 async com asyncpg.
"""
from __future__ import annotations

from typing import AsyncGenerator, Optional

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from src.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()


class Base(DeclarativeBase):
    """Base declarativa para todos os models SQLAlchemy."""
    pass


class PostgresConnection:
    """Manager de conexão com PostgreSQL. Padrão Singleton."""

    _engine: Optional[AsyncEngine] = None
    _session_factory: Optional[async_sessionmaker] = None

    @classmethod
    async def connect(cls) -> None:
        """Inicializa engine e session factory."""
        cls._engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.APP_DEBUG,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        cls._session_factory = async_sessionmaker(
            cls._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        logger.info("postgres_connected", db=settings.POSTGRES_DB)

    @classmethod
    async def disconnect(cls) -> None:
        """Encerra o engine e todas as conexões do pool."""
        if cls._engine:
            await cls._engine.dispose()
            cls._engine = None
            cls._session_factory = None

    @classmethod
    def get_session_factory(cls) -> async_sessionmaker:
        if cls._session_factory is None:
            raise RuntimeError("PostgreSQL não inicializado. Chame PostgresConnection.connect().")
        return cls._session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency Injection — FastAPI.
    Fornece uma sessão de banco de dados por request, com commit/rollback automático.
    """
    session_factory = PostgresConnection.get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
