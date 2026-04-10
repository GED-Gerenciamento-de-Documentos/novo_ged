"""
Application Use Cases — Search, Download, Delete Documents.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import structlog

from src.domain.audit.entities.audit_log import AuditAction, AuditLog
from src.domain.audit.repositories.audit_repository import IAuditRepository
from src.domain.documents.entities.document import Document, DocumentType, FileFormat, StorageType
from src.domain.documents.repositories.document_repository import (
    DocumentFilter,
    IDocumentRepository,
    PaginatedResult,
)
from src.infrastructure.security.encryption import EncryptionService
from src.infrastructure.storage.interfaces import IStorage
from src.infrastructure.storage.nfs_storage import NfsStorage

logger = structlog.get_logger()


# ==========================================
# Search Use Case
# ==========================================

@dataclass
class SearchDocumentsInput:
    user_id: uuid.UUID
    user_role: str
    # Filtros
    owner_name: Optional[str] = None
    owner_record_number: Optional[str] = None
    owner_cpf: Optional[str] = None       # CPF em texto — será criptografado para busca
    document_type: Optional[DocumentType] = None
    file_format: Optional[FileFormat] = None
    storage_type: Optional[StorageType] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    tags: Optional[list[str]] = None
    # Paginação
    page: int = 1
    page_size: int = 20
    order_by: str = "created_at"
    order_direction: str = "desc"


class SearchDocumentsUseCase:
    """Busca documentos com filtros, respeitando permissões de confidencialidade."""

    def __init__(
        self,
        document_repository: IDocumentRepository,
        encryption_service: EncryptionService,
    ):
        self._document_repository = document_repository
        self._encryption_service = encryption_service

    async def execute(self, input_data: SearchDocumentsInput) -> PaginatedResult:
        # Criptografar CPF para busca (busca pelo hash criptografado)
        encrypted_cpf = None
        if input_data.owner_cpf:
            try:
                encrypted_cpf = self._encryption_service.encrypt_cpf(input_data.owner_cpf)
            except ValueError:
                encrypted_cpf = None   # CPF inválido — ignorar filtro

        # OPERADORs não veem documentos confidenciais
        is_confidential_filter = None
        if input_data.user_role == "OPERADOR":
            is_confidential_filter = False

        filters = DocumentFilter(
            owner_name=input_data.owner_name,
            owner_record_number=input_data.owner_record_number,
            owner_cpf_encrypted=encrypted_cpf,
            document_type=input_data.document_type,
            file_format=input_data.file_format,
            storage_type=input_data.storage_type,
            date_from=input_data.date_from,
            date_to=input_data.date_to,
            tags=input_data.tags,
            is_confidential=is_confidential_filter,
            page=input_data.page,
            page_size=min(input_data.page_size, 100),  # Máximo 100 por página
            order_by=input_data.order_by,
            order_direction=input_data.order_direction,
        )

        return await self._document_repository.find_by_filters(filters)


# ==========================================
# Download Use Case
# ==========================================

@dataclass
class DownloadDocumentInput:
    document_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_role: str
    ip_address: str
    user_agent: str


@dataclass
class DownloadDocumentOutput:
    content: bytes
    content_type: str
    file_name: str
    file_size: int


class DownloadDocumentUseCase:
    """Download do arquivo original (sem conversão)."""

    def __init__(
        self,
        document_repository: IDocumentRepository,
        audit_repository: IAuditRepository,
        cloud_storage: IStorage,
        nfs_storage: NfsStorage,
    ):
        self._document_repository = document_repository
        self._audit_repository = audit_repository
        self._cloud_storage = cloud_storage
        self._nfs_storage = nfs_storage

    async def execute(self, input_data: DownloadDocumentInput) -> DownloadDocumentOutput:
        document = await self._document_repository.find_by_id(input_data.document_id)
        if not document:
            raise FileNotFoundError(f"Documento não encontrado: {input_data.document_id}")

        if not document.is_accessible_by(input_data.user_role):
            raise PermissionError("Sem permissão para baixar este documento.")

        storage = self._nfs_storage if document.is_from_legacy() else self._cloud_storage
        content = await storage.download(document.storage_path)

        # Audit log de download
        audit = AuditLog.create(
            action=AuditAction.DOWNLOAD,
            user_id=input_data.user_id,
            user_email=input_data.user_email,
            user_role=input_data.user_role,
            ip_address=input_data.ip_address,
            user_agent=input_data.user_agent,
            document_id=document.id.value,
            document_title=document.title,
        )
        await self._audit_repository.save(audit)

        from src.infrastructure.converters.image_converter import ImageConverter
        content_type = ImageConverter.get_content_type(document.file_format.value)
        file_name = f"{document.title.replace(' ', '_')}.{document.extension}"

        return DownloadDocumentOutput(
            content=content,
            content_type=content_type,
            file_name=file_name,
            file_size=len(content),
        )


# ==========================================
# Delete Use Case
# ==========================================

@dataclass
class DeleteDocumentInput:
    document_id: uuid.UUID
    deleted_by_id: uuid.UUID
    deleted_by_email: str
    deleted_by_role: str
    ip_address: str
    user_agent: str
    reason: Optional[str] = None


class DeleteDocumentUseCase:
    """Soft delete de documento — apenas ADMINISTRADOR."""

    def __init__(
        self,
        document_repository: IDocumentRepository,
        audit_repository: IAuditRepository,
    ):
        self._document_repository = document_repository
        self._audit_repository = audit_repository

    async def execute(self, input_data: DeleteDocumentInput) -> bool:
        if input_data.deleted_by_role != "ADMINISTRADOR":
            raise PermissionError("Somente ADMINISTRADOR pode excluir documentos.")

        document = await self._document_repository.find_by_id(input_data.document_id)
        if not document:
            raise FileNotFoundError(f"Documento não encontrado: {input_data.document_id}")

        # Aplicar soft delete via entidade de domínio
        document.mark_as_deleted(input_data.deleted_by_id)
        await self._document_repository.update(document)

        # Audit log de exclusão
        audit = AuditLog.create(
            action=AuditAction.DELETE,
            user_id=input_data.deleted_by_id,
            user_email=input_data.deleted_by_email,
            user_role=input_data.deleted_by_role,
            ip_address=input_data.ip_address,
            user_agent=input_data.user_agent,
            document_id=document.id.value,
            document_title=document.title,
            additional_data={"reason": input_data.reason or "Não informado"},
        )
        await self._audit_repository.save(audit)

        logger.info(
            "document_deleted",
            document_id=str(input_data.document_id),
            deleted_by=input_data.deleted_by_email,
        )
        return True
