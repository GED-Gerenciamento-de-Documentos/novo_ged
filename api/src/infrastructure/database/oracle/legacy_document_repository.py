"""
Infrastructure — Oracle Legacy Document Repository.

Busca documentos no banco Oracle 11g e no NFS legado.
As queries SQL precisam ser adaptadas ao schema real do sistema legado.
"""
from __future__ import annotations

from typing import Optional

import structlog

from src.infrastructure.database.oracle.legacy_connection import OracleLegacyConnection

logger = structlog.get_logger()


class LegacyDocumentRepository:
    """
    Repositório read-only para documentos no sistema legado Oracle/NFS.

    NOTA: As queries SQL abaixo são exemplos.
    Adapte aos nomes reais das tabelas e colunas do seu Oracle 11g.
    """

    # ==========================================
    # ADAPTAR: Nomes das tabelas legadas
    # ==========================================
    TABLE_DOCUMENTS = "GED_DOCUMENTOS"       # Ajustar para o nome real
    TABLE_METADATA = "GED_METADADOS"         # Ajustar para o nome real

    @staticmethod
    async def find_document_path_by_id(legacy_document_id: str) -> Optional[str]:
        """
        Busca o caminho do arquivo no NFS a partir do ID no sistema legado.
        Retorna o path relativo ao NFS mount point.
        """
        if not OracleLegacyConnection.is_available():
            logger.warning("oracle_unavailable", action="find_document_path")
            return None

        # ADAPTAR: Ajustar SQL ao schema real do Oracle 11g
        sql = f"""
            SELECT CAMINHO_ARQUIVO
            FROM {LegacyDocumentRepository.TABLE_DOCUMENTS}
            WHERE ID_DOCUMENTO = :doc_id
            AND ROWNUM = 1
        """
        result = await OracleLegacyConnection.execute_query_one(
            sql, {"doc_id": legacy_document_id}
        )
        return result.get("caminho_arquivo") if result else None

    @staticmethod
    async def search_documents(
        owner_name: Optional[str] = None,
        owner_cpf: Optional[str] = None,
        document_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict]:
        """
        Busca documentos legados no Oracle 11g.

        ADAPTAR: Ajustar SQL ao schema real do sistema legado.
        """
        if not OracleLegacyConnection.is_available():
            logger.warning("oracle_unavailable", action="search_documents")
            return []

        conditions = ["1=1"]
        params = {}

        if owner_name:
            conditions.append("UPPER(NOME_PROPRIETARIO) LIKE UPPER(:nome)")
            params["nome"] = f"%{owner_name}%"

        if owner_cpf:
            conditions.append("CPF = :cpf")
            params["cpf"] = owner_cpf

        if document_type:
            conditions.append("TIPO_DOCUMENTO = :tipo")
            params["tipo"] = document_type

        if date_from:
            conditions.append("DATA_DOCUMENTO >= TO_DATE(:data_inicio, 'YYYY-MM-DD')")
            params["data_inicio"] = date_from

        if date_to:
            conditions.append("DATA_DOCUMENTO <= TO_DATE(:data_fim, 'YYYY-MM-DD')")
            params["data_fim"] = date_to

        where_clause = " AND ".join(conditions)
        offset = (page - 1) * page_size

        # Oracle 11g não tem OFFSET/FETCH NEXT — usa ROWNUM
        # ADAPTAR: Ajustar SQL ao schema real
        sql = f"""
            SELECT *
            FROM (
                SELECT d.*, ROWNUM AS RN
                FROM (
                    SELECT
                        ID_DOCUMENTO,
                        TITULO,
                        TIPO_DOCUMENTO,
                        NOME_PROPRIETARIO,
                        CPF,
                        NUM_PRONTUARIO,
                        DATA_DOCUMENTO,
                        CAMINHO_ARQUIVO,
                        FORMATO_ARQUIVO,
                        DATA_CADASTRO
                    FROM {LegacyDocumentRepository.TABLE_DOCUMENTS}
                    WHERE {where_clause}
                    ORDER BY DATA_CADASTRO DESC
                ) d
                WHERE ROWNUM <= :max_row
            )
            WHERE RN > :min_row
        """
        params["max_row"] = offset + page_size
        params["min_row"] = offset

        results = await OracleLegacyConnection.execute_query(sql, params)
        logger.info("legacy_search", count=len(results), page=page)
        return results

    @staticmethod
    async def get_document_detail(legacy_document_id: str) -> Optional[dict]:
        """Busca detalhes completos de um documento legado."""
        if not OracleLegacyConnection.is_available():
            return None

        # ADAPTAR: Ajustar SQL ao schema real
        sql = f"""
            SELECT
                ID_DOCUMENTO,
                TITULO,
                TIPO_DOCUMENTO,
                NOME_PROPRIETARIO,
                CPF,
                NUM_PRONTUARIO,
                DATA_DOCUMENTO,
                CAMINHO_ARQUIVO,
                FORMATO_ARQUIVO,
                QTD_PAGINAS,
                DATA_CADASTRO
            FROM {LegacyDocumentRepository.TABLE_DOCUMENTS}
            WHERE ID_DOCUMENTO = :doc_id
            AND ROWNUM = 1
        """
        return await OracleLegacyConnection.execute_query_one(
            sql, {"doc_id": legacy_document_id}
        )
