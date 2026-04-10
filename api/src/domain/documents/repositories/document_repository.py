"""
Domain layer — Repository interfaces (abstrações puras).

Princípio SOLID: Dependency Inversion — a camada de domínio
depende de abstrações, não de implementações concretas.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID

from src.domain.documents.entities.document import Document, DocumentType, FileFormat, StorageType


class DocumentFilter:
    """DTO para filtros de busca de documentos."""

    def __init__(
        self,
        owner_name: Optional[str] = None,
        owner_record_number: Optional[str] = None,
        owner_cpf_encrypted: Optional[str] = None,
        document_type: Optional[DocumentType] = None,
        file_format: Optional[FileFormat] = None,
        storage_type: Optional[StorageType] = None,
        category_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        is_confidential: Optional[bool] = None,
        include_deleted: bool = False,
        # Paginação
        page: int = 1,
        page_size: int = 20,
        # Ordenação
        order_by: str = "created_at",
        order_direction: str = "desc",
    ):
        self.owner_name = owner_name
        self.owner_record_number = owner_record_number
        self.owner_cpf_encrypted = owner_cpf_encrypted
        self.document_type = document_type
        self.file_format = file_format
        self.storage_type = storage_type
        self.category_id = category_id
        self.tags = tags or []
        self.date_from = date_from
        self.date_to = date_to
        self.is_confidential = is_confidential
        self.include_deleted = include_deleted
        self.page = page
        self.page_size = page_size
        self.order_by = order_by
        self.order_direction = order_direction

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResult:
    """DTO de resultado paginado."""

    def __init__(self, items: List[Document], total: int, page: int, page_size: int):
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size

    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1


class IDocumentRepository(ABC):
    """Interface do repositório de documentos."""

    @abstractmethod
    async def save(self, document: Document) -> Document:
        """Persiste um novo documento."""
        ...

    @abstractmethod
    async def update(self, document: Document) -> Document:
        """Atualiza um documento existente."""
        ...

    @abstractmethod
    async def find_by_id(self, document_id: UUID) -> Optional[Document]:
        """Busca um documento pelo ID."""
        ...

    @abstractmethod
    async def find_by_filters(self, filters: DocumentFilter) -> PaginatedResult:
        """Busca documentos com filtros e paginação."""
        ...

    @abstractmethod
    async def delete(self, document_id: UUID) -> bool:
        """Soft delete de um documento."""
        ...

    @abstractmethod
    async def count_by_type(self) -> dict:
        """Conta documentos por tipo (para dashboard)."""
        ...
