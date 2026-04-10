"""
Infrastructure — NFS Storage (legado read-only).

Lê documentos JBIG2/JPG do servidor de arquivos NFS montado localmente.
Esta implementação é SOMENTE LEITURA para os documentos legados.
"""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import AsyncGenerator, Optional

import aiofiles
import structlog

from src.infrastructure.storage.interfaces import IStorage, StorageObject
from src.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Mapeamento de extensões para MIME types
MIME_TYPES: dict[str, str] = {
    ".jbig2": "image/jbig2",
    ".jb2": "image/jbig2",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}

CHUNK_SIZE = 65536  # 64KB chunks para streaming


class NfsStorage(IStorage):
    """
    Implementação de storage para servidor NFS legado.

    Monta o caminho do NFS localmente e acessa arquivos diretamente
    via sistema de arquivos. Somente leitura para documentos legados.
    """

    def __init__(self, base_path: Optional[str] = None):
        self._base_path = Path(base_path or settings.NFS_LEGACY_BASE_PATH)

    def _resolve_path(self, file_key: str) -> Path:
        """Resolve o caminho completo e valida que está dentro do base_path (path traversal)."""
        resolved = (self._base_path / file_key).resolve()
        if not str(resolved).startswith(str(self._base_path.resolve())):
            raise PermissionError(
                f"Acesso negado: path fora do diretório base NFS. key={file_key}"
            )
        return resolved

    def _get_content_type(self, file_path: Path) -> str:
        return MIME_TYPES.get(file_path.suffix.lower(), "application/octet-stream")

    async def upload(
        self,
        file_key: str,
        file_content: bytes,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> StorageObject:
        """
        NFS legado é READ-ONLY.
        Novos uploads devem usar CloudStorage.
        """
        raise NotImplementedError(
            "NfsStorage é somente leitura. Use o storage em nuvem para novos uploads."
        )

    async def download(self, file_key: str) -> bytes:
        """Lê o arquivo completo do NFS."""
        file_path = self._resolve_path(file_key)

        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado no NFS: {file_key}")

        logger.info("nfs_download", key=file_key, path=str(file_path))

        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def stream(self, file_key: str) -> AsyncGenerator[bytes, None]:
        """Streaming em chunks para economizar memória em arquivos grandes."""
        file_path = self._resolve_path(file_key)

        if not file_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado no NFS: {file_key}")

        logger.info("nfs_stream", key=file_key, path=str(file_path))

        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(CHUNK_SIZE):
                yield chunk

    async def delete(self, file_key: str) -> bool:
        """NFS legado é read-only — não permite exclusão."""
        raise NotImplementedError(
            "NfsStorage não permite exclusão. Documentos legados são imutáveis."
        )

    async def exists(self, file_key: str) -> bool:
        """Verifica se o arquivo existe no NFS."""
        try:
            file_path = self._resolve_path(file_key)
            return file_path.exists() and file_path.is_file()
        except (PermissionError, OSError):
            return False

    async def get_metadata(self, file_key: str) -> Optional[StorageObject]:
        """Retorna metadados sem ler o arquivo completo."""
        file_path = self._resolve_path(file_key)

        if not file_path.exists():
            return None

        stat = file_path.stat()
        content_type = self._get_content_type(file_path)

        return StorageObject(
            key=file_key,
            content_type=content_type,
            size_bytes=stat.st_size,
            metadata={
                "last_modified": stat.st_mtime,
                "filename": file_path.name,
            },
        )

    async def compute_checksum(self, file_key: str) -> str:
        """Calcula SHA256 do arquivo NFS (pode ser demorado para arquivos grandes)."""
        sha256 = hashlib.sha256()
        async for chunk in self.stream(file_key):
            sha256.update(chunk)
        return sha256.hexdigest()
