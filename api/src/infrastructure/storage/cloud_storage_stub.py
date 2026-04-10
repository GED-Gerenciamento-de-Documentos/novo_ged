"""
Infrastructure — Cloud Storage Stub.

Placeholder para integração futura com provedor de nuvem (AWS S3, Azure Blob, GCP).
Quando o provedor for definido, implementar a classe concreta correspondente
e atualizar a factory `get_cloud_storage()`.

Arquitetura: Open/Closed Principle — esta interface não muda,
apenas a implementação concreta é substituída.
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
from typing import AsyncGenerator, Optional

import aiofiles
import structlog

from src.infrastructure.storage.interfaces import IStorage, StorageObject
from src.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()

CHUNK_SIZE = 65536  # 64KB


class LocalCloudStorageStub(IStorage):
    """
    Stub local para desenvolvimento — simula storage em nuvem usando o disco.
    NÃO usar em produção.

    Em produção, substituir por:
    - AwsS3Storage (quando AWS for escolhida)
    - AzureBlobStorage (quando Azure for escolhida)
    - GcpCloudStorage (quando GCP for escolhida)
    """

    def __init__(self, base_path: Optional[str] = None):
        # Prioriza: argumento explícito > LOCAL_STORAGE_PATH do .env > padrão
        resolved_path = base_path or settings.LOCAL_STORAGE_PATH or "./local_cloud_storage"
        self._base_path = Path(resolved_path)
        self._base_path.mkdir(parents=True, exist_ok=True)
        logger.warning(
            "cloud_storage_stub_active",
            message="⚠️  Usando storage LOCAL (stub). Configure o provedor de nuvem em produção.",
            base_path=str(self._base_path),
        )

    def _resolve_path(self, file_key: str) -> Path:
        resolved = (self._base_path / file_key).resolve()
        if not str(resolved).startswith(str(self._base_path.resolve())):
            raise PermissionError(f"Path traversal detectado: {file_key}")
        return resolved

    async def upload(
        self,
        file_key: str,
        file_content: bytes,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> StorageObject:
        file_path = self._resolve_path(file_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        checksum = hashlib.sha256(file_content).hexdigest()

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_content)

        logger.info("cloud_stub_upload", key=file_key, size=len(file_content))

        return StorageObject(
            key=file_key,
            content_type=content_type,
            size_bytes=len(file_content),
            checksum_sha256=checksum,
            metadata=metadata or {},
        )

    async def download(self, file_key: str) -> bytes:
        file_path = self._resolve_path(file_key)
        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado no storage: {file_key}")

        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def stream(self, file_key: str) -> AsyncGenerator[bytes, None]:
        file_path = self._resolve_path(file_key)
        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado no storage: {file_key}")

        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(CHUNK_SIZE):
                yield chunk

    async def delete(self, file_key: str) -> bool:
        file_path = self._resolve_path(file_key)
        if file_path.exists():
            file_path.unlink()
            logger.info("cloud_stub_delete", key=file_key)
            return True
        return False

    async def exists(self, file_key: str) -> bool:
        try:
            return self._resolve_path(file_key).exists()
        except (PermissionError, OSError):
            return False

    async def get_metadata(self, file_key: str) -> Optional[StorageObject]:
        file_path = self._resolve_path(file_key)
        if not file_path.exists():
            return None
        stat = file_path.stat()
        return StorageObject(
            key=file_key,
            content_type="application/octet-stream",
            size_bytes=stat.st_size,
        )


def get_cloud_storage() -> IStorage:
    """
    Factory para o storage em nuvem.
    Retorna a implementação correta baseada na configuração CLOUD_STORAGE_PROVIDER.

    Para adicionar novo provider:
    1. Criar classe concreta implementando IStorage
    2. Adicionar case aqui
    3. Sem modificar código existente (Open/Closed Principle)
    """
    provider = settings.CLOUD_STORAGE_PROVIDER.lower()

    match provider:
        case "stub" | "local":
            return LocalCloudStorageStub()
        case "s3":
            # TODO: Implementar quando AWS for escolhida
            # from src.infrastructure.storage.aws_s3_storage import AwsS3Storage
            # return AwsS3Storage()
            raise NotImplementedError("AWS S3 storage ainda não configurado.")
        case "azure":
            # TODO: Implementar quando Azure for escolhida
            # from src.infrastructure.storage.azure_blob_storage import AzureBlobStorage
            # return AzureBlobStorage()
            raise NotImplementedError("Azure Blob storage ainda não configurado.")
        case "gcp":
            # TODO: Implementar quando GCP for escolhido
            raise NotImplementedError("GCP Cloud Storage ainda não configurado.")
        case _:
            raise ValueError(f"Provider de cloud desconhecido: {provider}")
