"""
Application Use Case — Upload de Documento.

Orquestra: validação → armazenamento → persistência de metadados → audit log.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Optional

import structlog

from src.domain.documents.entities.document import (
    CPF,
    Document,
    DocumentType,
    FileFormat,
    StorageType,
)
from src.domain.documents.repositories.document_repository import IDocumentRepository
from src.domain.audit.entities.audit_log import AuditAction, AuditLog
from src.domain.audit.repositories.audit_repository import IAuditRepository
from src.infrastructure.security.encryption import EncryptionService
from src.infrastructure.storage.interfaces import IStorage

logger = structlog.get_logger()


@dataclass
class UploadDocumentInput:
    """DTO de entrada para o caso de uso de upload."""
    title: str
    document_type: DocumentType
    file_format: FileFormat
    file_content: bytes
    file_name: str
    owner_name: str
    uploaded_by_id: uuid.UUID
    uploaded_by_email: str
    uploaded_by_role: str
    ip_address: str
    user_agent: str
    # Opcionais
    owner_cpf: Optional[str] = None
    owner_record_number: Optional[str] = None
    document_date: Optional[date] = None
    is_confidential: bool = False
    tags: Optional[list[str]] = None
    retention_until: Optional[date] = None
    extra_metadata: Optional[dict] = None


@dataclass
class UploadDocumentOutput:
    """DTO de saída — resultado do upload."""
    document_id: str
    title: str
    storage_path: str
    file_size_bytes: int
    checksum_sha256: str
    message: str = "Documento enviado com sucesso."


class UploadDocumentUseCase:
    """
    Caso de uso: Upload de novo documento.

    DDD: Orquestra domínio + infraestrutura sem lógica de apresentação.
    SOLID: Depende de abstrações (IStorage, IDocumentRepository).
    """

    def __init__(
        self,
        document_repository: IDocumentRepository,
        audit_repository: IAuditRepository,
        cloud_storage: IStorage,
        encryption_service: EncryptionService,
    ):
        self._document_repository = document_repository
        self._audit_repository = audit_repository
        self._cloud_storage = cloud_storage
        self._encryption_service = encryption_service

    async def execute(self, input_data: UploadDocumentInput) -> UploadDocumentOutput:
        """Executa o caso de uso de upload."""

        # 1. Calcular checksum SHA256 para integridade
        checksum = hashlib.sha256(input_data.file_content).hexdigest()

        # 2. Gerar chave de storage (caminho no cloud)
        doc_uuid = uuid.uuid4()
        file_extension = input_data.file_format.value.lower()
        storage_key = (
            f"documentos/{input_data.document_type.value.lower()}/"
            f"{doc_uuid}.{file_extension}"
        )

        # 3. Upload para cloud storage
        content_type = self._get_content_type(input_data.file_format)
        storage_object = await self._cloud_storage.upload(
            file_key=storage_key,
            file_content=input_data.file_content,
            content_type=content_type,
            metadata={
                "owner_name": input_data.owner_name,
                "document_type": input_data.document_type.value,
                "uploaded_by": str(input_data.uploaded_by_id),
            },
        )

        # 4. Criptografar CPF (LGPD)
        encrypted_cpf = None
        if input_data.owner_cpf:
            encrypted_cpf = self._encryption_service.encrypt_cpf(input_data.owner_cpf)

        # 5. Criar entidade de domínio
        document = Document.create_new(
            title=input_data.title,
            document_type=input_data.document_type,
            file_format=input_data.file_format,
            storage_path=storage_key,
            storage_type=StorageType.CLOUD,
            owner_name=input_data.owner_name,
            uploaded_by_id=input_data.uploaded_by_id,
            owner_cpf=CPF.from_encrypted(encrypted_cpf) if encrypted_cpf else None,
            owner_record_number=input_data.owner_record_number,
            document_date=input_data.document_date,
            is_confidential=input_data.is_confidential,
            tags=input_data.tags or [],
            retention_until=input_data.retention_until,
            extra_metadata=input_data.extra_metadata or {},
            file_size_bytes=storage_object.size_bytes,
            checksum_sha256=checksum,
        )
        # Sobrescrever ID gerado pelo domain com o uuid que usamos no storage_key
        object.__setattr__(document.id, 'value', doc_uuid)

        # 6. Persistir metadados no PostgreSQL
        saved_document = await self._document_repository.save(document)

        # 7. Registrar audit log
        audit = AuditLog.create(
            action=AuditAction.UPLOAD,
            user_id=input_data.uploaded_by_id,
            user_email=input_data.uploaded_by_email,
            user_role=input_data.uploaded_by_role,
            ip_address=input_data.ip_address,
            user_agent=input_data.user_agent,
            document_id=doc_uuid,
            document_title=input_data.title,
            additional_data={
                "file_format": input_data.file_format.value,
                "file_size_bytes": storage_object.size_bytes,
                "storage_key": storage_key,
            },
        )
        await self._audit_repository.save(audit)

        logger.info(
            "document_uploaded",
            document_id=str(doc_uuid),
            title=input_data.title,
            format=input_data.file_format.value,
            size=storage_object.size_bytes,
        )

        return UploadDocumentOutput(
            document_id=str(doc_uuid),
            title=input_data.title,
            storage_path=storage_key,
            file_size_bytes=storage_object.size_bytes,
            checksum_sha256=checksum,
        )

    @staticmethod
    def _get_content_type(file_format: FileFormat) -> str:
        mime_map = {
            FileFormat.JBIG2: "image/jbig2",
            FileFormat.JPG: "image/jpeg",
            FileFormat.PDF: "application/pdf",
            FileFormat.PNG: "image/png",
            FileFormat.TIFF: "image/tiff",
        }
        return mime_map.get(file_format, "application/octet-stream")
