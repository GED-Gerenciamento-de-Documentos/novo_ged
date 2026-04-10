"""Tests — conftest.py with shared fixtures."""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from src.main import app


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def mock_current_user_operador():
    from src.presentation.dependencies.auth_dependencies import CurrentUser
    return CurrentUser(
        user_id=uuid.uuid4(),
        email="operador@ged.local",
        role="OPERADOR",
    )


@pytest.fixture
def mock_current_user_gestor():
    from src.presentation.dependencies.auth_dependencies import CurrentUser
    return CurrentUser(
        user_id=uuid.uuid4(),
        email="gestor@ged.local",
        role="GESTOR",
    )


@pytest.fixture
def mock_current_user_admin():
    from src.presentation.dependencies.auth_dependencies import CurrentUser
    return CurrentUser(
        user_id=uuid.uuid4(),
        email="admin@ged.local",
        role="ADMINISTRADOR",
    )


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP client assíncrono para testes de integração da API."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.fixture
def sample_jpg_content() -> bytes:
    """Conteúdo mínimo de um arquivo JPEG para testes."""
    # JPEG magic bytes + minimal content
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100


@pytest.fixture
def sample_jbig2_content() -> bytes:
    """Conteúdo simulado de JBIG2 para testes."""
    return b"\x97\x4a\x42\x32\x0d\x0a\x1a\x0a" + b"\x00" * 100
