"""
Infrastructure — Repositório Gemmius GED Legado.

Consulta as tabelas Oracle:
  - GEMMIUS.GEDLEGACY (t) → metadados dos documentos principais
  - GEMMIUS.GED (g)       → contém o filename real salvo na rede
"""
from __future__ import annotations

from typing import Any, Optional
import structlog

from src.infrastructure.database.oracle.legacy_connection import OracleLegacyConnection

logger = structlog.get_logger()


class GemmiusRepository:
    """
    Repositório read-only síncrono para as tabelas do schema GEMMIUS.
    Todas as queries são executadas em Thick Mode através de Threadpools do FastAPI.
    """

    SCHEMA = "GEMMIUS"

    @classmethod
    def list_patient_documents(
        cls,
        patient_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Retorna os documentos do paciente com o nome do arquivo.
        """
        if not OracleLegacyConnection.is_available():
            logger.warning("oracle_unavailable", action="list_patient_documents")
            return []

        offset   = (page - 1) * page_size
        max_row  = offset + page_size
        min_row  = offset

        sql = f"""
            SELECT *
            FROM (
                SELECT inner_q.*, ROWNUM AS RN
                FROM (
                    SELECT
                        t.patientid,
                        t.patientname,
                        g.gedid,
                        g.filename     AS nome_arquivo,
                        g.creationdate AS dt_inclusao_log,
                        t.ROWID        AS row_id
                    FROM {cls.SCHEMA}.GEDLEGACY t
                    JOIN {cls.SCHEMA}.GED g ON t.gedid = g.gedid
                    WHERE t.patientid = :patient_id
                    ORDER BY g.creationdate ASC
                ) inner_q
                WHERE ROWNUM <= :max_row
            )
            WHERE RN > :min_row
        """

        try:
            rows = OracleLegacyConnection.execute_query(
                sql,
                {"patient_id": patient_id, "max_row": max_row, "min_row": min_row},
            )
            logger.info("gemmius_list", patient_id=patient_id, found=len(rows), page=page)
            return rows
        except Exception as e:
            logger.error("gemmius_list_error", patient_id=patient_id, error=str(e))
            raise

    @classmethod
    def count_patient_documents(cls, patient_id: int) -> int:
        if not OracleLegacyConnection.is_available():
            return 0

        sql = f"""
            SELECT COUNT(*) AS total
            FROM {cls.SCHEMA}.GEDLEGACY t
            JOIN {cls.SCHEMA}.GED g ON t.gedid = g.gedid
            WHERE t.PATIENTID = :patient_id
        """
        result = OracleLegacyConnection.execute_query_one(sql, {"patient_id": patient_id})
        return int(result.get("total", 0)) if result else 0

    @classmethod
    def get_document_by_rowid(cls, row_id: str) -> Optional[dict[str, Any]]:
        """Busca propriedades do documento pelo ROW_ID (único do Oracle)."""
        if not OracleLegacyConnection.is_available():
            return None

        sql = f"""
            SELECT
                t.patientid,
                t.patientname,
                g.gedid,
                g.filename     AS nome_arquivo,
                g.creationdate AS dt_inclusao_log,
                t.ROWID        AS row_id
            FROM {cls.SCHEMA}.GEDLEGACY t
            JOIN {cls.SCHEMA}.GED g ON t.gedid = g.gedid
            WHERE t.ROWID = CHARTOROWID(:row_id)
            AND ROWNUM = 1
        """
        return OracleLegacyConnection.execute_query_one(sql, {"row_id": row_id})

    @classmethod
    def inspect_columns(cls, table_name: str) -> list[dict]:
        """Retorna as colunas de uma tabela do schema GEMMIUS (útil para debug)."""
        sql = """
            SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE
            FROM ALL_TAB_COLUMNS
            WHERE OWNER = :schema
              AND TABLE_NAME = :table_name
            ORDER BY COLUMN_ID
        """
        return OracleLegacyConnection.execute_query(
            sql, {"schema": cls.SCHEMA, "table_name": table_name.upper()}
        )
