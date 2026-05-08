"""
Presentation — Search Dev Router.

Endpoint público de busca para desenvolvimento/testes.
NÃO requer autenticação JWT.
Disponível APENAS quando APP_ENV=development.
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.documents.document_use_cases import (
    SearchDocumentsInput,
    SearchDocumentsUseCase,
)
from src.domain.documents.entities.document import DocumentType, FileFormat, StorageType
from src.infrastructure.database.postgres.connection import get_db_session
from src.infrastructure.database.postgres.repositories.pg_document_repository import PgDocumentRepository
from src.infrastructure.security.encryption import EncryptionService
from src.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()
encryption_service = EncryptionService()

router = APIRouter(prefix="/documents", tags=["Documentos (Dev)"])

# UUID fixo representando usuário anônimo de dev
ANONYMOUS_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


@router.get(
    "/search-dev",
    summary="[DEV] Busca de documentos sem autenticação",
    description=(
        "⚠️ **APENAS PARA DESENVOLVIMENTO**. Endpoint público sem JWT. "
        "Ativo somente quando `APP_ENV=development`. "
        "Permite buscar documentos na Nuvem (AWS S3) ou no Legado (Oracle 11g)."
    ),
)
async def search_documents_dev(
    request: Request,
    owner_name: Optional[str] = Query(None, description="Nome do proprietário / título"),
    owner_record_number: Optional[str] = Query(None, description="Número do prontuário"),
    document_type: Optional[str] = Query(None, description="Tipo do documento (ex: PRONTUARIO)"),
    storage_type: Optional[str] = Query("CLOUD", description="Ambiente: CLOUD ou LEGACY_NFS"),
    date_from: Optional[str] = Query(None, description="Data início (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Data fim (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    # Bloquear em produção
    if settings.APP_ENV != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este endpoint está disponível apenas em ambiente de desenvolvimento.",
        )

    doc_type = None
    if document_type:
        try:
            doc_type = DocumentType(document_type.upper())
        except ValueError:
            pass

    st = None
    if storage_type:
        try:
            st = StorageType(storage_type.upper())
        except ValueError:
            pass

    use_case = SearchDocumentsUseCase(
        document_repository=PgDocumentRepository(session),
        encryption_service=encryption_service,
    )

    result = await use_case.execute(
        SearchDocumentsInput(
            user_id=ANONYMOUS_USER_ID,
            user_role="ADMINISTRADOR",   # dev vê tudo
            owner_name=owner_name,
            owner_record_number=owner_record_number,
            document_type=doc_type,
            storage_type=st,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
    )

    items = []
    for doc in result.items:
        items.append({
            "id": str(doc.id.value),
            "title": doc.title,
            "document_type": doc.document_type.value,
            "file_format": doc.file_format.value,
            "storage_type": doc.storage_type.value,
            "owner_name": doc.owner_name,
            "owner_record_number": doc.owner_record_number,
            "document_date": doc.document_date.isoformat() if doc.document_date else None,
            "is_confidential": doc.is_confidential,
            "status": doc.status.value,
            "file_size_bytes": doc.file_size_bytes,
            "page_count": doc.page_count,
            "tags": doc.tags,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        })

    return {
        "items": items,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
        "has_next": result.has_next,
        "has_previous": result.has_previous,
        "warning": "Busca realizada via endpoint de desenvolvimento (sem autenticação).",
    }
