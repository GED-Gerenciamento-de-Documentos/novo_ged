"""Infrastructure — Oracle 11g Legacy Connection (Read-Only)."""
from __future__ import annotations

from typing import Any, Optional
from contextlib import contextmanager

import oracledb
import structlog

from src.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()


class OracleLegacyConnection:
    """
    Conexão read-only com o banco Oracle 11g legado.

    Usa oracledb em modo thick (obrigatório para Oracle 11g) que não suporta conexões assíncronas nativas.
    Toda interação deve ser jogada para um threadpool via FastAPI (def sem async).
    """

    _pool: Optional[oracledb.ConnectionPool] = None

    @classmethod
    def connect(cls) -> None:
        """Inicializa pool síncrono de conexões com Oracle 11g."""
        try:
            import os
            # Configuração Híbrida de Driver OCI (Docker vs Computador Local)
            if os.path.exists("/opt/oracle"):
                oracledb.init_oracle_client(lib_dir="/opt/oracle")
            else:
                oracledb.init_oracle_client(lib_dir=r"C:\app\product\19.0.0\client_1\bin")

            cls._pool = oracledb.create_pool(
                user=settings.ORACLE_USER,
                password=settings.ORACLE_PASSWORD,
                dsn=settings.ORACLE_DSN,
                min=2,
                max=10,
                increment=1,
            )
            logger.info("oracle_connected", dsn=settings.ORACLE_DSN, user=settings.ORACLE_USER)
        except Exception as e:
            logger.error("oracle_connection_failed", error=str(e), dsn=settings.ORACLE_DSN)
            # Não levanta exceção — o sistema principal (Postgres) pode funcionar sem o legado
            cls._pool = None

    @classmethod
    def disconnect(cls) -> None:
        """Encerra o pool Oracle de forma síncrona."""
        if cls._pool:
            cls._pool.close()
            cls._pool = None

    @classmethod
    def is_available(cls) -> bool:
        """Verifica se a conexão Oracle está disponível."""
        return cls._pool is not None

    @classmethod
    @contextmanager
    def get_connection(cls):
        """Context manager para obter uma conexão do pool síncrono."""
        if cls._pool is None:
            raise ConnectionError(
                "Banco Oracle legado não está disponível. "
                "Verifique as configurações ORACLE_* no .env"
            )
        with cls._pool.acquire() as conn:
            yield conn

    @classmethod
    def execute_query(
        cls,
        sql: str,
        params: Optional[dict] = None,
    ) -> list[dict[str, Any]]:
        """
        Executa uma query SELECT no Oracle e retorna lista de dicionários.
        """
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            raise PermissionError(
                "OracleLegacyConnection: Somente consultas SELECT são permitidas."
            )

        with cls.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params or {})
                columns = [col[0].lower() for col in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]

    @classmethod
    def execute_query_one(
        cls,
        sql: str,
        params: Optional[dict] = None,
    ) -> Optional[dict[str, Any]]:
        """Executa query via bloco síncrono e retorna apenas o primeiro resultado."""
        results = cls.execute_query(sql, params)
        return results[0] if results else None
