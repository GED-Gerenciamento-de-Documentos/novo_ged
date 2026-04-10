"""
Presentation — Router Legacy GED.

Rotas para consultar documentos do sistema legado Oracle (Gemmius)
e servir as imagens JBIG2/JPG armazenadas no servidor 192.168.8.53.

Endpoints:
  GET /api/v1/legacy/patients/{patient_id}/documents   → lista documentos
  GET /api/v1/legacy/documents/{row_id}/view           → visualizar imagem
  GET /api/v1/legacy/documents/{row_id}/download       → download original
  GET /api/v1/legacy/patients/{patient_id}/thumbnail   → thumbnail do 1º doc
  GET /api/v1/legacy/schema/{table}                    → inspecionar colunas (debug)
"""
from __future__ import annotations

from typing import Annotated, Optional
from urllib.parse import quote

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response, StreamingResponse
from fastapi.concurrency import run_in_threadpool

from src.application.legacy.list_patient_documents import ListPatientDocumentsUseCase
from src.infrastructure.converters.image_converter import ImageConverter
from src.infrastructure.database.oracle.gemmius_repository import GemmiusRepository
from src.infrastructure.database.oracle.legacy_connection import OracleLegacyConnection
from src.infrastructure.storage.ged_file_storage import GedFileStorage
from src.presentation.dependencies.auth_dependencies import CurrentUser, get_current_user

logger = structlog.get_logger()

router = APIRouter(prefix="/legacy", tags=["GED Legado (Oracle / Gemmius)"])

# Instâncias compartilhadas dos serviços de infraestrutura
_ged_storage = GedFileStorage()


# ─────────────────────────────────────────────
# 1. Listar documentos de um paciente
# ─────────────────────────────────────────────

@router.get(
    "/patients/{patient_id}/documents",
    summary="Listar documentos do paciente (sistema legado)",
    response_description="Lista paginada de documentos do prontuário",
)
async def list_patient_documents(
    request: Request,
    patient_id: int,
    page: int = Query(1, ge=1, description="Página"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página"),
) -> dict:
    """
    Lista todos os documentos do paciente pelo **PATIENTID** (número do prontuário).

    Consulta as tabelas Oracle:
    - `GEMMIUS.GEDLEGACY` → metadados do documento
    - `GEMMIUS.LOG_GED`   → nome e caminho do arquivo no servidor GED

    Retorna URLs prontas para visualização e download de cada imagem.
    """
    if not OracleLegacyConnection.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco Oracle legado indisponível. Verifique as configurações ORACLE_* no .env",
        )

    base_url = str(request.base_url).rstrip("/")
    use_case = ListPatientDocumentsUseCase(base_url=base_url)

    try:
        result = await run_in_threadpool(use_case.execute, patient_id, page, page_size)
    except Exception as e:
        logger.error("legacy_list_error", patient_id=patient_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Erro ao consultar Oracle: {str(e)}")

    return {
        "patient_id": result.patient_id,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
        "items": [
            {
                "row_id":       item.row_id,
                "patient_id":   item.patient_id,
                "nome_arquivo": item.nome_arquivo,
                "formato":      item.formato,
                "drive":        item.drive_arquivo,
                "view_url":     item.view_url,
                "download_url": item.download_url,
                "thumbnail_url": item.thumbnail_url,
                "metadata":     item.metadata,
            }
            for item in result.items
        ],
    }


# ─────────────────────────────────────────────
# 2. Thumbnail miniatura do documento
# ─────────────────────────────────────────────

@router.get(
    "/documents/{row_id}/thumbnail",
    summary="Pré-visualização miniatura do documento legado",
)
async def get_legacy_document_thumbnail(row_id: str):
    """Retorna uma miniatura (thumbnail) do documento para pré-visualização rápida."""
    if not OracleLegacyConnection.is_available():
        raise HTTPException(status_code=503, detail="Oracle indisponível.")
    try:
        doc = await run_in_threadpool(GemmiusRepository.get_document_by_rowid, row_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro Oracle: {str(e)}")
    if not doc:
        raise HTTPException(status_code=404, detail=f"Documento não encontrado. row_id={row_id}")
    nome_arquivo = doc.get("nome_arquivo") or doc.get("nomearquivo")
    if not nome_arquivo:
        raise HTTPException(status_code=404, detail="Nome do arquivo não encontrado nos metadados Oracle.")
    try:
        raw_content = await run_in_threadpool(_ged_storage.read_file, nome_arquivo)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler arquivo: {str(e)}")
    file_format = _ged_storage.detect_format(nome_arquivo)
    thumbnail = await ImageConverter.generate_thumbnail(raw_content, file_format)
    return Response(
        content=thumbnail,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Row-ID": row_id,
        },
    )


# ─────────────────────────────────────────────
# 3. Visualizar imagem inline no browser
# ─────────────────────────────────────────────

@router.get(
    "/documents/{row_id}/view",
    summary="Visualizar imagem do documento legado",
    responses={
        200: {"description": "Imagem JPEG (JBIG2 convertido) ou original"},
        404: {"description": "Arquivo não encontrado no servidor GED"},
        503: {"description": "Oracle indisponível"},
    },
)
async def view_legacy_document(
    row_id: str,
):
    """
    Retorna a imagem para visualização inline no navegador.

    - **JBIG2 / JB2** → convertido automaticamente para JPEG (navegadores não suportam JBIG2)
    - **JPG / PNG** → retornado no formato original
    - **PDF** → retornado como PDF

    O `row_id` é o ROWID Oracle retornado pela listagem de documentos.
    """
    if not OracleLegacyConnection.is_available():
        raise HTTPException(status_code=503, detail="Oracle indisponível.")

    # Buscar metadados no Oracle
    try:
        doc = await run_in_threadpool(GemmiusRepository.get_document_by_rowid, row_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro Oracle: {str(e)}")

    if not doc:
        raise HTTPException(status_code=404, detail=f"Documento não encontrado. row_id={row_id}")

    nome_arquivo = doc.get("nome_arquivo") or doc.get("nomearquivo")

    if not nome_arquivo:
        raise HTTPException(status_code=404, detail="Nome do arquivo não encontrado nos metadados Oracle.")

    # Ler arquivo do servidor GED
    try:
        raw_content = await run_in_threadpool(_ged_storage.read_file, nome_arquivo)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("ged_read_error", row_id=row_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Erro ao ler arquivo: {str(e)}")

    # Converter para formato compatível com browser
    file_format = _ged_storage.detect_format(nome_arquivo)
    final_content, content_type = await ImageConverter.prepare_for_viewer(raw_content, file_format)

    # Nome do arquivo para o header (sem o path)
    display_name = nome_arquivo.split("\\")[-1].split("/")[-1]
    # Se JBIG2, renomear para .jpg no display
    if file_format in ("jbig2", "jb2"):
        display_name = display_name.rsplit(".", 1)[0] + ".jpg"

    return Response(
        content=final_content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{display_name}"',
            "Content-Length": str(len(final_content)),
            "X-Original-Format": file_format,
            "X-Row-ID": row_id,
        },
    )


# ─────────────────────────────────────────────
# 3. Download do arquivo original
# ─────────────────────────────────────────────

@router.get(
    "/documents/{row_id}/download",
    summary="Download do arquivo original do documento legado",
)
async def download_legacy_document(
    row_id: str,
):
    """
    Faz o download do arquivo no formato original (sem conversão).
    """
    if not OracleLegacyConnection.is_available():
        raise HTTPException(status_code=503, detail="Oracle indisponível.")

    try:
        doc = await run_in_threadpool(GemmiusRepository.get_document_by_rowid, row_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    nome_arquivo = doc.get("nome_arquivo") or doc.get("nomearquivo")

    try:
        raw_content = await run_in_threadpool(_ged_storage.read_file, nome_arquivo)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    file_format  = _ged_storage.detect_format(nome_arquivo or "")
    content_type = ImageConverter.get_content_type(file_format)
    display_name = (nome_arquivo or "documento").split("\\")[-1].split("/")[-1]

    return Response(
        content=raw_content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{display_name}"',
            "Content-Length": str(len(raw_content)),
        },
    )


# ─────────────────────────────────────────────
# 4. Thumbnail do primeiro documento do paciente
# ─────────────────────────────────────────────

@router.get(
    "/patients/{patient_id}/thumbnail",
    summary="Thumbnail do primeiro documento do paciente",
)
async def get_patient_thumbnail(
    patient_id: int,
):
    """Retorna thumbnail PNG (400×400) do primeiro documento encontrado."""
    if not OracleLegacyConnection.is_available():
        raise HTTPException(status_code=503, detail="Oracle indisponível.")

    rows = await run_in_threadpool(GemmiusRepository.list_patient_documents, patient_id, 1, 1)
    if not rows:
        raise HTTPException(status_code=404, detail=f"Nenhum documento encontrado para o paciente {patient_id}.")

    doc          = rows[0]
    nome_arquivo = doc.get("nome_arquivo") or doc.get("nomearquivo")

    try:
        raw_content = await run_in_threadpool(_ged_storage.read_file, nome_arquivo)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    file_format = _ged_storage.detect_format(nome_arquivo or "")
    thumbnail   = await ImageConverter.generate_thumbnail(raw_content, file_format)

    return Response(
        content=thumbnail,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ─────────────────────────────────────────────
# 5. Diagnóstico — inspecionar colunas Oracle
# ─────────────────────────────────────────────

@router.get(
    "/schema/{table_name}",
    summary="[DEBUG] Inspecionar colunas de uma tabela Gemmius",
    tags=["GED Legado (Oracle / Gemmius)", "Debug"],
)
async def inspect_table_schema(
    table_name: str,
):
    """
    Retorna as colunas e tipos da tabela informada no schema GEMMIUS.

    Útil para ajustar as queries caso os nomes das colunas sejam diferentes.

    Exemplos: `GEDLEGACY`, `LOG_GED`
    """
    if not OracleLegacyConnection.is_available():
        raise HTTPException(status_code=503, detail="Oracle indisponível.")

    try:
        columns = await run_in_threadpool(GemmiusRepository.inspect_columns, table_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "schema": "GEMMIUS",
        "table": table_name.upper(),
        "columns": columns,
    }
