"""
GED API — Entry Point Principal
Aplicação FastAPI para Gerenciamento Eletrônico de Documentos
"""
import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from src.infrastructure.cache.redis_cache import RedisCache
from src.infrastructure.database.postgres.connection import PostgresConnection
from src.infrastructure.database.oracle.legacy_connection import OracleLegacyConnection
from src.presentation.api.v1.router import api_v1_router
from src.presentation.middlewares.logging_middleware import LoggingMiddleware
from src.settings import Settings

logger = structlog.get_logger()
settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Gerencia o ciclo de vida da aplicação (startup/shutdown)."""
    logger.info("🚀 Iniciando GED API...", version=settings.APP_VERSION, env=settings.APP_ENV)

    # Inicializar conexão com PostgreSQL
    try:
        await PostgresConnection.connect()
        logger.info("✅ PostgreSQL conectado")
    except Exception as e:
        logger.warning(f"⚠️ PostgreSQL indisponível: {e}")

    # Inicializar Redis
    try:
        await RedisCache.connect()
        logger.info("✅ Redis conectado")
    except Exception as e:
        logger.warning(f"⚠️ Redis indisponível (Ignorando para testes do Legado): {e}")

    # Inicializando Banco de Dados Legado Oracle de Forma Síncrona
    try:
        OracleLegacyConnection.connect()
        if OracleLegacyConnection.is_available():
            logger.info("✅ Oracle 11g conectado (Thick Mode)")
        else:
            logger.warning("⚠️ Oracle 11g indisponível.")
    except Exception as e:
        logger.error(f"❌ Erro ao conectar no Oracle: {e}")

    yield

    # Cleanup ao encerrar
    logger.info("🛑 Encerrando GED API...")
    try:
        await PostgresConnection.disconnect()
    except Exception:
        pass
    try:
        await RedisCache.disconnect()
    except Exception:
        pass
    OracleLegacyConnection.disconnect()
    logger.info("✅ Conexões encerradas")


def create_application() -> FastAPI:
    """Factory function — cria e configura a instância FastAPI."""

    limiter = Limiter(key_func=get_remote_address)

    app = FastAPI(
        title=settings.APP_NAME,
        description="""
## API de Gerenciamento Eletrônico de Documentos (GED)

Sistema para digitalização, armazenamento e consulta de documentos institucionais.

### Funcionalidades
- 📄 **Upload e visualização** de documentos (JBIG2, JPG, PDF)
- 🔍 **Busca avançada** por metadados (nome, CPF, prontuário, data, tipo)
- 🔐 **Controle de acesso** por perfil (OPERADOR, GESTOR, ADMINISTRADOR)
- 📋 **Audit log** completo de todas as operações
- 🏛️ **Integração com legado** Oracle 11g + NFS
- ☁️ **Pronto para cloud** (abstração de storage configurada)

### Conformidade LGPD
- CPF armazenado com criptografia AES-256
- Logs de acesso a dados sensíveis
- Política de retenção configurável por tipo de documento
        """,
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.APP_DEBUG else None,
        redoc_url="/redoc" if settings.APP_DEBUG else None,
        openapi_url="/openapi.json" if settings.APP_DEBUG else None,
        lifespan=lifespan,
    )

    # Rate Limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS_LIST,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # GZip para respostas grandes
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Logging estruturado de requisições
    app.add_middleware(LoggingMiddleware)

    # Registrar rotas versionadas
    app.include_router(api_v1_router, prefix="/api/v1")

    # Endpoints de infraestrutura
    @app.get("/health", tags=["Infraestrutura"], summary="Health check da API")
    async def health_check() -> JSONResponse:
        return JSONResponse(
            content={
                "status": "healthy",
                "version": settings.APP_VERSION,
                "environment": settings.APP_ENV,
            }
        )

    @app.get("/", tags=["Infraestrutura"], include_in_schema=False)
    async def root() -> JSONResponse:
        return JSONResponse(
            content={
                "name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "docs": "/docs",
            }
        )

    return app


app = create_application()
