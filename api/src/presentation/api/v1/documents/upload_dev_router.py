"""
Presentation — Upload Dev Router.

Endpoint público de upload para desenvolvimento/testes.
NÃO requer autenticação JWT.
Disponível APENAS quando APP_ENV=development.
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from src.application.documents.upload_document import UploadDocumentInput, UploadDocumentUseCase
from src.domain.documents.entities.document import DocumentType, FileFormat, StorageType
from src.infrastructure.database.postgres.connection import get_db_session
from src.infrastructure.database.postgres.repositories.pg_audit_repository import PgAuditRepository
from src.infrastructure.database.postgres.repositories.pg_document_repository import PgDocumentRepository
from src.infrastructure.security.encryption import EncryptionService
from src.infrastructure.storage.cloud_storage_stub import get_cloud_storage
from src.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()
encryption_service = EncryptionService()

router = APIRouter(prefix="/documents", tags=["Documentos (Dev)"])

# UUID fixo representando upload anônimo (sem login)
ANONYMOUS_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

FORMAT_MAP = {
    "jbig2": FileFormat.JBIG2, "jb2": FileFormat.JBIG2,
    "jpg": FileFormat.JPG, "jpeg": FileFormat.JPG,
    "pdf": FileFormat.PDF, "png": FileFormat.PNG,
    "tiff": FileFormat.TIFF, "tif": FileFormat.TIFF,
}


@router.post(
    "/upload-dev",
    status_code=status.HTTP_201_CREATED,
    summary="[DEV] Upload de um ou múltiplos documentos sem autenticação",
    description=(
        "⚠️ **APENAS PARA DESENVOLVIMENTO**. Endpoint público sem JWT. "
        "Ativo somente quando `APP_ENV=development`. "
        "Simula digitalização em lote (múltiplos arquivos por requisição)."
    ),
)
async def upload_document_dev(
    request: Request,
    files: list[UploadFile] = File(..., description="Um ou mais arquivos (PDF, JPG, PNG)"),
    title: str = Form(..., min_length=3, description="Título base do documento"),
    document_type: str = Form(..., description="Ex: EXAME, LAUDO, PRONTUARIO"),
    owner_name: str = Form(..., description="Nome do paciente ou titular"),
    owner_record_number: Optional[str] = Form(None, description="Número do prontuário (opcional)"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    # Bloquear em produção
    if settings.APP_ENV != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este endpoint está disponível apenas em ambiente de desenvolvimento.",
        )

    try:
        doc_type = DocumentType(document_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo inválido: '{document_type}'. Use: {[t.value for t in DocumentType]}",
        )

    ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("User-Agent", "dev-client")

    results = []
    errors = []

    for index, file in enumerate(files):
        file_ext = (file.filename or "").split(".")[-1].lower()

        if file_ext not in settings.ALLOWED_EXTENSIONS_LIST:
            errors.append({
                "file": file.filename,
                "error": f"Formato .{file_ext} não suportado. Aceitos: {settings.ALLOWED_EXTENSIONS}",
            })
            continue

        file_content = await file.read()

        if len(file_content) > settings.MAX_UPLOAD_SIZE_BYTES:
            errors.append({
                "file": file.filename,
                "error": f"Arquivo muito grande. Máximo: {settings.MAX_UPLOAD_SIZE_MB}MB",
            })
            continue

        file_format = FORMAT_MAP.get(file_ext, FileFormat.PDF)

        # Título com numeração automática quando múltiplos arquivos
        doc_title = title if len(files) == 1 else f"{title} ({index + 1}/{len(files)})"

        use_case = UploadDocumentUseCase(
            document_repository=PgDocumentRepository(session),
            audit_repository=PgAuditRepository(session),
            cloud_storage=get_cloud_storage(),
            encryption_service=encryption_service,
        )

        try:
            output = await use_case.execute(
                UploadDocumentInput(
                    title=doc_title,
                    document_type=doc_type,
                    file_format=file_format,
                    file_content=file_content,
                    file_name=file.filename or "documento",
                    owner_name=owner_name,
                    owner_record_number=owner_record_number,
                    uploaded_by_id=ANONYMOUS_USER_ID,
                    uploaded_by_email="dev@localhost",
                    uploaded_by_role="ADMINISTRADOR",
                    ip_address=ip,
                    user_agent=user_agent,
                )
            )
            results.append({
                "file": file.filename,
                "document_id": output.document_id,
                "title": output.title,
                "file_size_bytes": output.file_size_bytes,
                "storage_path": output.storage_path,
                "checksum_sha256": output.checksum_sha256,
            })
        except Exception as e:
            logger.error("upload_dev_failed", file=file.filename, error=str(e))
            errors.append({"file": file.filename, "error": str(e)})

    return {
        "total_enviados": len(files),
        "total_sucesso": len(results),
        "total_erros": len(errors),
        "documentos": results,
        "erros": errors,
        "message": f"{len(results)}/{len(files)} documento(s) enviado(s) com sucesso.",
        "warning": "Upload realizado via endpoint de desenvolvimento (sem autenticação).",
    }
