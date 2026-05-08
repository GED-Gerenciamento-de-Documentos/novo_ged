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
    TABLE_DOCUMENTS = "DBAMV.GED_DOCUMENTO"
    TABLE_VERSIONS = "DBAMV.GED_VERSAO_DOCUMENTO"
    TABLE_CONTENT = "DBAMV.GED_CONTEUDO"

    @staticmethod
    async def get_document_content(legacy_document_id: str) -> Optional[bytes]:
        """
        Busca o conteúdo (BLOB) do arquivo no banco Oracle.
        """
        if not OracleLegacyConnection.is_available():
            logger.warning("oracle_unavailable", action="get_document_content")
            return None

        import asyncio
        sql = f"""
            SELECT c.BLOB_CONTEUDO
            FROM {LegacyDocumentRepository.TABLE_CONTENT} c
            JOIN {LegacyDocumentRepository.TABLE_DOCUMENTS} d ON c.CD_DOCUMENTO = d.CD_DOCUMENTO
            WHERE c.CD_DOCUMENTO = :doc_id
              AND c.CD_VERSAO = d.CD_VERSAO_ATUAL
            AND ROWNUM = 1
        """
        result = await asyncio.to_thread(
            OracleLegacyConnection.execute_query_one, sql, {"doc_id": legacy_document_id}
        )
        if result and result.get("blob_conteudo"):
            return result.get("blob_conteudo").read()
        return None

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
        """
        if not OracleLegacyConnection.is_available():
            logger.warning("oracle_unavailable", action="search_documents")
            return []

        conditions = ["1=1"]
        params = {}

        if owner_name:
            # Como não encontramos o nome do paciente, vamos buscar no título do documento (DS_DOCUMENTO)
            conditions.append("UPPER(DS_DOCUMENTO) LIKE UPPER(:nome)")
            params["nome"] = f"%{owner_name}%"

        # CPF ignorado pois não está na tabela

        if document_type:
            conditions.append("CD_TIPO_DOCUMENTO = :tipo")
            params["tipo"] = document_type

        if date_from:
            conditions.append("DT_CRIACAO >= TO_DATE(:data_inicio, 'YYYY-MM-DD')")
            params["data_inicio"] = date_from

        if date_to:
            conditions.append("DT_CRIACAO <= TO_DATE(:data_fim, 'YYYY-MM-DD')")
            params["data_fim"] = date_to

        where_clause = " AND ".join(conditions)
        offset = (page - 1) * page_size

        sql = f"""
            SELECT *
            FROM (
                SELECT d.*, ROWNUM AS RN
                FROM (
                    SELECT
                        d.CD_DOCUMENTO as ID_DOCUMENTO,
                        d.DS_DOCUMENTO as TITULO,
                        d.CD_TIPO_DOCUMENTO as TIPO_DOCUMENTO,
                        'Paciente Legado' as NOME_PROPRIETARIO,
                        '000.000.000-00' as CPF,
                        '' as NUM_PRONTUARIO,
                        d.DT_CRIACAO as DATA_DOCUMENTO,
                        v.TP_FORMATO as FORMATO_ARQUIVO,
                        d.DT_CRIACAO as DATA_CADASTRO
                    FROM {LegacyDocumentRepository.TABLE_DOCUMENTS} d
                    LEFT JOIN {LegacyDocumentRepository.TABLE_VERSIONS} v 
                        ON d.CD_DOCUMENTO = v.CD_DOCUMENTO AND d.CD_VERSAO_ATUAL = v.CD_VERSAO
                    WHERE {where_clause}
                    ORDER BY d.DT_CRIACAO DESC
                ) d
                WHERE ROWNUM <= :max_row
            )
            WHERE RN > :min_row
        """
        params["max_row"] = offset + page_size
        params["min_row"] = offset

        import asyncio
        results = await asyncio.to_thread(OracleLegacyConnection.execute_query, sql, params)
        logger.info("legacy_search", count=len(results), page=page)
        return results

    @staticmethod
    async def get_document_detail(legacy_document_id: str) -> Optional[dict]:
        """Busca detalhes completos de um documento legado."""
        if not OracleLegacyConnection.is_available():
            return None

        sql = f"""
            SELECT
                d.CD_DOCUMENTO as ID_DOCUMENTO,
                d.DS_DOCUMENTO as TITULO,
                d.CD_TIPO_DOCUMENTO as TIPO_DOCUMENTO,
                'Paciente Legado' as NOME_PROPRIETARIO,
                '000.000.000-00' as CPF,
                '' as NUM_PRONTUARIO,
                d.DT_CRIACAO as DATA_DOCUMENTO,
                v.TP_FORMATO as FORMATO_ARQUIVO,
                1 as QTD_PAGINAS,
                d.DT_CRIACAO as DATA_CADASTRO
            FROM {LegacyDocumentRepository.TABLE_DOCUMENTS} d
            LEFT JOIN {LegacyDocumentRepository.TABLE_VERSIONS} v 
                ON d.CD_DOCUMENTO = v.CD_DOCUMENTO AND d.CD_VERSAO_ATUAL = v.CD_VERSAO
            WHERE d.CD_DOCUMENTO = :doc_id
            AND ROWNUM = 1
        """
        import asyncio
        return await asyncio.to_thread(
            OracleLegacyConnection.execute_query_one, sql, {"doc_id": legacy_document_id}
        )
