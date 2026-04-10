"""Storage abstraction — Interface e implementações."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncGenerator, Optional


@dataclass
class StorageObject:
    """DTO de resultado de operação de storage."""
    key: str               # Caminho/chave do arquivo no storage
    content_type: str      # MIME type
    size_bytes: int
    checksum_sha256: Optional[str] = None
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class IStorage(ABC):
    """
    Interface de abstração de storage.

    Princípio SOLID: Open/Closed — novas implementações (S3, Azure, GCP)
    podem ser adicionadas sem modificar código existente.
    """

    @abstractmethod
    async def upload(
        self,
        file_key: str,
        file_content: bytes,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> StorageObject:
        """Faz upload de um arquivo para o storage."""
        ...

    @abstractmethod
    async def download(self, file_key: str) -> bytes:
        """Baixa um arquivo do storage."""
        ...

    @abstractmethod
    async def stream(self, file_key: str) -> AsyncGenerator[bytes, None]:
        """Faz streaming de um arquivo (chunk by chunk)."""
        ...

    @abstractmethod
    async def delete(self, file_key: str) -> bool:
        """Remove um arquivo do storage."""
        ...

    @abstractmethod
    async def exists(self, file_key: str) -> bool:
        """Verifica se um arquivo existe no storage."""
        ...

    @abstractmethod
    async def get_metadata(self, file_key: str) -> Optional[StorageObject]:
        """Retorna metadados de um arquivo sem baixá-lo."""
        ...
