"""
Infrastructure — PostgreSQL Document Repository.
Implementação concreta da interface IDocumentRepository.
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.documents.entities.document import (
    CPF,
    Document,
    DocumentId,
    DocumentStatus,
    DocumentType,
    FileFormat,
    StorageType,
)
from src.domain.documents.repositories.document_repository import (
    DocumentFilter,
    IDocumentRepository,
    PaginatedResult,
)
from src.infrastructure.database.postgres.models.document_model import DocumentModel

logger = structlog.get_logger()


def _model_to_entity(model: DocumentModel) -> Document:
    """Converte ORM Model → Entidade de domínio."""
    return Document(
        id=DocumentId(value=model.id),
        title=model.title,
        document_type=DocumentType(model.document_type),
        file_format=FileFormat(model.file_format),
        storage_type=StorageType(model.storage_type),
        storage_path=model.storage_path,
        owner_name=model.owner_name,
        owner_cpf=CPF.from_encrypted(model.owner_cpf_encrypted) if model.owner_cpf_encrypted else None,
        owner_record_number=model.owner_record_number,
        document_date=model.document_date,
        category_id=model.category_id,
        tags=model.tags or [],
        extra_metadata=model.extra_metadata or {},
        file_size_bytes=model.file_size_bytes,
        page_count=model.page_count,
        checksum_sha256=model.checksum_sha256,
        is_confidential=model.is_confidential,
        status=DocumentStatus(model.status),
        retention_until=model.retention_until,
        uploaded_by_id=model.uploaded_by_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


def _entity_to_model(entity: Document) -> DocumentModel:
    """Converte Entidade de domínio → ORM Model."""
    return DocumentModel(
        id=entity.id.value,
        title=entity.title,
        document_type=entity.document_type.value,
        file_format=entity.file_format.value,
        storage_type=entity.storage_type.value,
        storage_path=entity.storage_path,
        owner_name=entity.owner_name,
        owner_cpf_encrypted=entity.owner_cpf.encrypted_value if entity.owner_cpf else None,
        owner_record_number=entity.owner_record_number,
        document_date=entity.document_date,
        category_id=entity.category_id,
        tags=entity.tags,
        extra_metadata=entity.extra_metadata,
        file_size_bytes=entity.file_size_bytes,
        page_count=entity.page_count,
        checksum_sha256=entity.checksum_sha256,
        is_confidential=entity.is_confidential,
        status=entity.status.value,
        retention_until=entity.retention_until,
        uploaded_by_id=entity.uploaded_by_id,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        deleted_at=entity.deleted_at,
    )


class PgDocumentRepository(IDocumentRepository):
    """Repositório PostgreSQL de documentos."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, document: Document) -> Document:
        model = _entity_to_model(document)
        self._session.add(model)
        await self._session.flush()
        logger.info("document_saved", document_id=str(document.id))
        return document

    async def update(self, document: Document) -> Document:
        stmt = (
            update(DocumentModel)
            .where(DocumentModel.id == document.id.value)
            .values(
                title=document.title,
                tags=document.tags,
                is_confidential=document.is_confidential,
                retention_until=document.retention_until,
                extra_metadata=document.extra_metadata,
                status=document.status.value,
                deleted_at=document.deleted_at,
                updated_at=document.updated_at,
            )
        )
        await self._session.execute(stmt)
        return document

    async def find_by_id(self, document_id: uuid.UUID) -> Optional[Document]:
        stmt = select(DocumentModel).where(
            DocumentModel.id == document_id,
            DocumentModel.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _model_to_entity(model) if model else None

    async def find_by_filters(self, filters: DocumentFilter) -> PaginatedResult:
        stmt = select(DocumentModel)
        count_stmt = select(func.count()).select_from(DocumentModel)

        # Aplicar filtros
        conditions = []
        if not filters.include_deleted:
            conditions.append(DocumentModel.deleted_at.is_(None))

        if filters.owner_name:
            conditions.append(
                DocumentModel.owner_name.ilike(f"%{filters.owner_name}%")
            )
        if filters.owner_record_number:
            conditions.append(
                DocumentModel.owner_record_number.ilike(f"%{filters.owner_record_number}%")
            )
        if filters.owner_cpf_encrypted:
            conditions.append(DocumentModel.owner_cpf_encrypted == filters.owner_cpf_encrypted)
        if filters.document_type:
            conditions.append(DocumentModel.document_type == filters.document_type.value)
        if filters.file_format:
            conditions.append(DocumentModel.file_format == filters.file_format.value)
        if filters.storage_type:
            conditions.append(DocumentModel.storage_type == filters.storage_type.value)
        if filters.is_confidential is not None:
            conditions.append(DocumentModel.is_confidential == filters.is_confidential)
        if filters.date_from:
            conditions.append(DocumentModel.document_date >= filters.date_from)
        if filters.date_to:
            conditions.append(DocumentModel.document_date <= filters.date_to)

        if conditions:
            for cond in conditions:
                stmt = stmt.where(cond)
                count_stmt = count_stmt.where(cond)

        # Ordenação
        order_col = getattr(DocumentModel, filters.order_by, DocumentModel.created_at)
        if filters.order_direction == "asc":
            stmt = stmt.order_by(order_col.asc())
        else:
            stmt = stmt.order_by(order_col.desc())

        # Paginação
        stmt = stmt.offset(filters.offset).limit(filters.page_size)

        result = await self._session.execute(stmt)
        count_result = await self._session.execute(count_stmt)

        models = result.scalars().all()
        total = count_result.scalar_one()

        return PaginatedResult(
            items=[_model_to_entity(m) for m in models],
            total=total,
            page=filters.page,
            page_size=filters.page_size,
        )

    async def delete(self, document_id: uuid.UUID) -> bool:
        from datetime import datetime
        stmt = (
            update(DocumentModel)
            .where(DocumentModel.id == document_id)
            .values(
                deleted_at=datetime.utcnow(),
                status=DocumentStatus.DELETED.value,
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def count_by_type(self) -> dict:
        stmt = (
            select(DocumentModel.document_type, func.count().label("total"))
            .where(DocumentModel.deleted_at.is_(None))
            .group_by(DocumentModel.document_type)
        )
        result = await self._session.execute(stmt)
        return {row.document_type: row.total for row in result}
