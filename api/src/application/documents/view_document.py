"""
Application Use Case — Visualização de Documento.

Serve o arquivo (JBIG2/JPG/PDF) com conversão para o navegador e audit log.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import AsyncGenerator, Optional, Tuple

import structlog

from src.domain.audit.entities.audit_log import AuditAction, AuditLog
from src.domain.audit.repositories.audit_repository import IAuditRepository
from src.domain.documents.entities.document import Document, StorageType
from src.domain.documents.repositories.document_repository import IDocumentRepository
from src.infrastructure.converters.image_converter import ImageConverter
from src.infrastructure.storage.interfaces import IStorage
from src.infrastructure.storage.nfs_storage import NfsStorage

logger = structlog.get_logger()


@dataclass
class ViewDocumentInput:
    document_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_role: str
    ip_address: str
    user_agent: str
    convert_for_browser: bool = True  # False = retorna formato original


@dataclass
class ViewDocumentOutput:
    content: bytes
    content_type: str
    file_name: str
    file_size: int
    is_converted: bool = False  # True se JBIG2 foi convertido para JPEG


class ViewDocumentUseCase:
    """
    Caso de uso: Visualização de documento.

    Suporta documentos legados (NFS + Oracle) e novos (cloud).
    Converte JBIG2 → JPEG para compatibilidade com navegadores.
    """

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

    async def execute(self, input_data: ViewDocumentInput) -> ViewDocumentOutput:
        # 1. Buscar metadados do documento
        document = await self._document_repository.find_by_id(input_data.document_id)
        if document is None:
            raise FileNotFoundError(f"Documento não encontrado: {input_data.document_id}")

        # 2. Verificar permissão de acesso
        if not document.is_accessible_by(input_data.user_role):
            raise PermissionError(
                f"Usuário sem permissão para acessar documento confidencial: {input_data.document_id}"
            )

        # 3. Escolher storage correto baseado no tipo
        storage = self._select_storage(document)

        # 4. Baixar o conteúdo do arquivo
        raw_content = await storage.download(document.storage_path)

        # 5. Converter para formato compatível com browser
        file_format = document.file_format.value.lower()
        is_converted = False

        if input_data.convert_for_browser:
            final_content, content_type = await ImageConverter.prepare_for_viewer(
                raw_content, file_format
            )
            is_converted = (file_format in ("jbig2", "jb2"))
        else:
            final_content = raw_content
            content_type = ImageConverter.get_content_type(file_format)

        # 6. Registrar audit log de visualização
        await self._register_audit(input_data, document, success=True)

        extension = "jpg" if is_converted else file_format
        file_name = f"{document.title.replace(' ', '_')}.{extension}"

        return ViewDocumentOutput(
            content=final_content,
            content_type=content_type,
            file_name=file_name,
            file_size=len(final_content),
            is_converted=is_converted,
        )

    async def stream(self, input_data: ViewDocumentInput) -> AsyncGenerator[bytes, None]:
        """Versão de streaming para arquivos grandes (evita carregar tudo na memória)."""
        document = await self._document_repository.find_by_id(input_data.document_id)
        if document is None:
            raise FileNotFoundError(f"Documento não encontrado: {input_data.document_id}")

        if not document.is_accessible_by(input_data.user_role):
            raise PermissionError("Sem permissão para acessar este documento.")

        storage = self._select_storage(document)
        await self._register_audit(input_data, document, success=True)

        # Stream direto para formatos que não precisam de conversão
        file_format = document.file_format.value.lower()
        if file_format not in ("jbig2", "jb2"):
            async for chunk in storage.stream(document.storage_path):
                yield chunk
        else:
            # JBIG2 requer download completo para conversão
            content = await storage.download(document.storage_path)
            converted, _ = await ImageConverter.prepare_for_viewer(content, file_format)
            yield converted

    def _select_storage(self, document: Document) -> IStorage:
        """Seleciona o storage correto baseado no tipo do documento."""
        if document.storage_type == StorageType.LEGACY_NFS:
            return self._nfs_storage
        return self._cloud_storage

    async def _register_audit(
        self,
        input_data: ViewDocumentInput,
        document: Document,
        success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """Registra audit log de visualização."""
        audit = AuditLog.create(
            action=AuditAction.VIEW,
            user_id=input_data.user_id,
            user_email=input_data.user_email,
            user_role=input_data.user_role,
            ip_address=input_data.ip_address,
            user_agent=input_data.user_agent,
            document_id=document.id.value,
            document_title=document.title,
            additional_data={
                "file_format": document.file_format.value,
                "storage_type": document.storage_type.value,
                "convert_for_browser": input_data.convert_for_browser,
            },
            success=success,
            error_message=error_message,
        )
        await self._audit_repository.save(audit)
