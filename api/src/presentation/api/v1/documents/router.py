"""
Presentation — Documents Router.
Endpoints para upload, busca, visualização, download e exclusão.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Optional

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.documents.document_use_cases import (
    DeleteDocumentInput,
    DeleteDocumentUseCase,
    DownloadDocumentInput,
    DownloadDocumentUseCase,
    SearchDocumentsInput,
    SearchDocumentsUseCase,
)
from src.application.documents.upload_document import UploadDocumentInput, UploadDocumentUseCase
from src.application.documents.view_document import ViewDocumentInput, ViewDocumentUseCase
from src.domain.documents.entities.document import DocumentType, FileFormat, StorageType
from src.infrastructure.converters.image_converter import ImageConverter
from src.infrastructure.database.postgres.connection import get_db_session
from src.infrastructure.database.postgres.repositories.pg_audit_repository import PgAuditRepository
from src.infrastructure.database.postgres.repositories.pg_document_repository import PgDocumentRepository
from src.infrastructure.security.encryption import EncryptionService
from src.infrastructure.storage.cloud_storage_stub import get_cloud_storage
from src.infrastructure.storage.nfs_storage import NfsStorage
from src.presentation.dependencies.auth_dependencies import (
    CurrentUser,
    get_current_user,
    require_role,
)
from src.presentation.schemas.schemas import (
    DeleteDocumentRequest,
    DocumentListResponse,
    DocumentResponse,
    MessageResponse,
    UpdateDocumentRequest,
)
from src.settings import get_settings

logger = structlog.get_logger()
router = APIRouter(prefix="/documents", tags=["Documentos"])
settings = get_settings()
encryption_service = EncryptionService()


def _get_client_info(request: Request) -> tuple[str, str]:
    ip = request.client.host if request.client else "unknown"
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    return ip, request.headers.get("User-Agent", "unknown")


def _build_view_use_case(session: AsyncSession) -> ViewDocumentUseCase:
    return ViewDocumentUseCase(
        document_repository=PgDocumentRepository(session),
        audit_repository=PgAuditRepository(session),
        cloud_storage=get_cloud_storage(),
        nfs_storage=NfsStorage(),
    )


# ==========================================
# Upload
# ==========================================

@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload de novo documento",
)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="Arquivo do documento (JBIG2, JPG, PDF, PNG, TIFF)"),
    title: str = Form(..., min_length=3),
    document_type: str = Form(...),
    owner_name: str = Form(...),
    owner_cpf: Optional[str] = Form(None),
    owner_record_number: Optional[str] = Form(None),
    document_date: Optional[str] = Form(None),
    is_confidential: bool = Form(False),
    tags: Optional[str] = Form(None),
    retention_until: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """
    Faz upload de um documento para o storage em nuvem e salva metadados no PostgreSQL.

    **Formatos aceitos**: JBIG2, JPG, JPEG, PNG, TIFF, PDF

    **Metadados obrigatórios**: título, tipo, nome do proprietário

    **Segurança**: CPF é criptografado com AES-256-GCM antes de ser armazenado.
    """
    # Validar extensão
    file_ext = (file.filename or "").split(".")[-1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS_LIST:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Formato não suportado: .{file_ext}. Aceitos: {settings.ALLOWED_EXTENSIONS}",
        )

    # Ler conteúdo e validar tamanho
    file_content = await file.read()
    if len(file_content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo muito grande. Máximo: {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    # Mapear formato
    format_map = {
        "jbig2": FileFormat.JBIG2, "jb2": FileFormat.JBIG2,
        "jpg": FileFormat.JPG, "jpeg": FileFormat.JPG,
        "pdf": FileFormat.PDF, "png": FileFormat.PNG,
        "tiff": FileFormat.TIFF, "tif": FileFormat.TIFF,
    }
    file_format = format_map.get(file_ext, FileFormat.JPG)

    try:
        doc_type = DocumentType(document_type.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo de documento inválido: {document_type}")

    from datetime import date
    doc_date = None
    if document_date:
        try:
            doc_date = date.fromisoformat(document_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de data inválido. Use YYYY-MM-DD.")

    retention = None
    if retention_until:
        try:
            retention = date.fromisoformat(retention_until)
        except ValueError:
            pass

    tags_list = [t.strip() for t in tags.split(",")] if tags else []
    ip, user_agent = _get_client_info(request)

    use_case = UploadDocumentUseCase(
        document_repository=PgDocumentRepository(session),
        audit_repository=PgAuditRepository(session),
        cloud_storage=get_cloud_storage(),
        encryption_service=encryption_service,
    )

    try:
        output = await use_case.execute(
            UploadDocumentInput(
                title=title,
                document_type=doc_type,
                file_format=file_format,
                file_content=file_content,
                file_name=file.filename or "documento",
                owner_name=owner_name,
                owner_cpf=owner_cpf,
                owner_record_number=owner_record_number,
                document_date=doc_date,
                is_confidential=is_confidential,
                tags=tags_list,
                retention_until=retention,
                uploaded_by_id=current_user.user_id,
                uploaded_by_email=current_user.email,
                uploaded_by_role=current_user.role,
                ip_address=ip,
                user_agent=user_agent,
            )
        )
    except Exception as e:
        logger.error("upload_failed", error=str(e), user=current_user.email)
        raise HTTPException(status_code=500, detail=f"Erro ao processar upload: {str(e)}")

    return {
        "document_id": output.document_id,
        "title": output.title,
        "file_size_bytes": output.file_size_bytes,
        "checksum_sha256": output.checksum_sha256,
        "message": output.message,
    }


# ==========================================
# Search
# ==========================================

@router.get(
    "",
    response_model=DocumentListResponse,
    summary="Buscar documentos",
)
async def search_documents(
    owner_name: Optional[str] = Query(None, description="Nome do proprietário"),
    owner_record_number: Optional[str] = Query(None, description="Número do prontuário/processo"),
    owner_cpf: Optional[str] = Query(None, description="CPF"),
    document_type: Optional[str] = Query(None),
    file_format: Optional[str] = Query(None),
    storage_type: Optional[str] = Query(None, description="LEGACY_NFS ou CLOUD"),
    date_from: Optional[str] = Query(None, description="Data início (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Data fim (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_by: str = Query("created_at"),
    order_direction: str = Query("desc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> DocumentListResponse:
    """
    Busca documentos com filtros avançados.

    **OPERADOR**: vê apenas documentos não-confidenciais.
    **GESTOR/ADMINISTRADOR**: vê todos.
    """
    doc_type = None
    if document_type:
        try:
            doc_type = DocumentType(document_type.upper())
        except ValueError:
            pass

    fmt = None
    if file_format:
        try:
            fmt = FileFormat(file_format.upper())
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
            user_id=current_user.user_id,
            user_role=current_user.role,
            owner_name=owner_name,
            owner_record_number=owner_record_number,
            owner_cpf=owner_cpf,
            document_type=doc_type,
            file_format=fmt,
            storage_type=st,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
            order_by=order_by,
            order_direction=order_direction,
        )
    )

    return DocumentListResponse(
        items=[_doc_to_response(doc) for doc in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next=result.has_next,
        has_previous=result.has_previous,
    )


# ==========================================
# Get Single Document
# ==========================================

@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Metadados de um documento",
)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> DocumentResponse:
    """Retorna os metadados de um documento pelo ID."""
    repo = PgDocumentRepository(session)
    document = await repo.find_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    if not document.is_accessible_by(current_user.role):
        raise HTTPException(status_code=403, detail="Acesso negado a documento confidencial.")
    return _doc_to_response(document)


# ==========================================
# View (inline no browser)
# ==========================================

@router.get(
    "/{document_id}/view",
    summary="Visualizar documento no navegador",
    responses={
        200: {"description": "Conteúdo do documento (JPEG, PNG ou PDF)"},
        404: {"description": "Documento não encontrado"},
        403: {"description": "Sem permissão"},
    },
)
async def view_document(
    document_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Retorna o documento para visualização inline no navegador.

    - **JBIG2/JB2** → convertido para JPEG automaticamente
    - **JPG, PNG, PDF** → retornados no formato original
    - Registra **audit log** de visualização
    """
    ip, user_agent = _get_client_info(request)
    use_case = _build_view_use_case(session)

    try:
        output = await use_case.execute(
            ViewDocumentInput(
                document_id=document_id,
                user_id=current_user.user_id,
                user_email=current_user.email,
                user_role=current_user.role,
                ip_address=ip,
                user_agent=user_agent,
                convert_for_browser=True,
            )
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return Response(
        content=output.content,
        media_type=output.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{output.file_name}"',
            "Content-Length": str(output.file_size),
            "X-Document-ID": str(document_id),
            "X-Converted": str(output.is_converted).lower(),
        },
    )


# ==========================================
# Thumbnail
# ==========================================

@router.get(
    "/{document_id}/thumbnail",
    summary="Thumbnail da primeira página",
)
async def get_thumbnail(
    document_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Retorna um thumbnail PNG (400x400) da primeira página do documento."""
    ip, user_agent = _get_client_info(request)
    use_case = _build_view_use_case(session)

    try:
        output = await use_case.execute(
            ViewDocumentInput(
                document_id=document_id,
                user_id=current_user.user_id,
                user_email=current_user.email,
                user_role=current_user.role,
                ip_address=ip,
                user_agent=user_agent,
                convert_for_browser=True,
            )
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    thumbnail = await ImageConverter.generate_thumbnail(
        output.content, output.content_type.split("/")[-1]
    )

    return Response(
        content=thumbnail,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ==========================================
# Download
# ==========================================

@router.get(
    "/{document_id}/download",
    summary="Download do documento original",
)
async def download_document(
    document_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Download do arquivo original sem conversão. Registra audit log."""
    ip, user_agent = _get_client_info(request)

    use_case = DownloadDocumentUseCase(
        document_repository=PgDocumentRepository(session),
        audit_repository=PgAuditRepository(session),
        cloud_storage=get_cloud_storage(),
        nfs_storage=NfsStorage(),
    )

    try:
        output = await use_case.execute(
            DownloadDocumentInput(
                document_id=document_id,
                user_id=current_user.user_id,
                user_email=current_user.email,
                user_role=current_user.role,
                ip_address=ip,
                user_agent=user_agent,
            )
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return Response(
        content=output.content,
        media_type=output.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{output.file_name}"',
            "Content-Length": str(output.file_size),
        },
    )


# ==========================================
# Update Metadata
# ==========================================

@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Atualizar metadados (GESTOR+)",
    dependencies=[Depends(require_role("GESTOR", "ADMINISTRADOR"))],
)
async def update_document(
    document_id: uuid.UUID,
    body: UpdateDocumentRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> DocumentResponse:
    """Atualiza metadados do documento. Não altera o arquivo físico."""
    repo = PgDocumentRepository(session)
    document = await repo.find_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    document.update_metadata(
        title=body.title,
        tags=body.tags,
        is_confidential=body.is_confidential,
        retention_until=body.retention_until,
        extra_metadata=body.extra_metadata,
    )
    updated = await repo.update(document)
    return _doc_to_response(updated)


# ==========================================
# Delete (Soft)
# ==========================================

@router.delete(
    "/{document_id}",
    response_model=MessageResponse,
    summary="Excluir documento (ADMINISTRADOR)",
    dependencies=[Depends(require_role("ADMINISTRADOR"))],
)
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    body: DeleteDocumentRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """Soft delete de documento. Apenas ADMINISTRADOR."""
    ip, user_agent = _get_client_info(request)

    use_case = DeleteDocumentUseCase(
        document_repository=PgDocumentRepository(session),
        audit_repository=PgAuditRepository(session),
    )

    try:
        await use_case.execute(
            DeleteDocumentInput(
                document_id=document_id,
                deleted_by_id=current_user.user_id,
                deleted_by_email=current_user.email,
                deleted_by_role=current_user.role,
                ip_address=ip,
                user_agent=user_agent,
                reason=body.reason,
            )
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return MessageResponse(message="Documento excluído com sucesso.")


# ==========================================
# Helper
# ==========================================

def _doc_to_response(doc) -> DocumentResponse:
    from src.domain.documents.entities.document import Document
    return DocumentResponse(
        id=doc.id.value,
        title=doc.title,
        document_type=doc.document_type.value,
        file_format=doc.file_format.value,
        storage_type=doc.storage_type.value,
        owner_name=doc.owner_name,
        owner_record_number=doc.owner_record_number,
        document_date=doc.document_date,
        is_confidential=doc.is_confidential,
        status=doc.status.value,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        tags=doc.tags,
        retention_until=doc.retention_until,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
