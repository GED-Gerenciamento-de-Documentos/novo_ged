"""
Infrastructure — AWS S3 Storage implementation.
"""
from __future__ import annotations

import hashlib
from typing import AsyncGenerator, Optional

import aioboto3
import structlog
from botocore.exceptions import ClientError

from src.infrastructure.storage.interfaces import IStorage, StorageObject
from src.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()

CHUNK_SIZE = 65536  # 64KB


class AwsS3Storage(IStorage):
    """
    Implementação de storage na nuvem usando AWS S3 de forma assíncrona com aioboto3.
    """

    def __init__(self) -> None:
        self.bucket = settings.S3_BUCKET_NAME
        if not self.bucket:
            raise ValueError("S3_BUCKET_NAME não configurado.")
        
        self.session = aioboto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            region_name=settings.AWS_REGION,
        )

    async def upload(
        self,
        file_key: str,
        file_content: bytes,
        content_type: str,
        metadata: Optional[dict] = None,
    ) -> StorageObject:
        checksum = hashlib.sha256(file_content).hexdigest()
        
        # S3 Metadata keys must be lowercase string and values string
        str_metadata = {str(k).lower(): str(v) for k, v in (metadata or {}).items()}

        try:
            async with self.session.client("s3") as s3:
                await s3.put_object(
                    Bucket=self.bucket,
                    Key=file_key,
                    Body=file_content,
                    ContentType=content_type,
                    Metadata=str_metadata,
                )
            
            logger.info("s3_upload_success", key=file_key, size=len(file_content))
            
            return StorageObject(
                key=file_key,
                content_type=content_type,
                size_bytes=len(file_content),
                checksum_sha256=checksum,
                metadata=str_metadata,
            )
        except ClientError as e:
            logger.error("s3_upload_error", key=file_key, error=str(e))
            raise e

    async def download(self, file_key: str) -> bytes:
        try:
            async with self.session.client("s3") as s3:
                response = await s3.get_object(Bucket=self.bucket, Key=file_key)
                return await response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"Arquivo não encontrado no S3: {file_key}")
            logger.error("s3_download_error", key=file_key, error=str(e))
            raise e

    async def stream(self, file_key: str) -> AsyncGenerator[bytes, None]:
        try:
            async with self.session.client("s3") as s3:
                response = await s3.get_object(Bucket=self.bucket, Key=file_key)
                # response["Body"] is an asyncio stream object in aioboto3
                while chunk := await response["Body"].read(CHUNK_SIZE):
                    yield chunk
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"Arquivo não encontrado no S3: {file_key}")
            logger.error("s3_stream_error", key=file_key, error=str(e))
            raise e

    async def delete(self, file_key: str) -> bool:
        try:
            async with self.session.client("s3") as s3:
                await s3.delete_object(Bucket=self.bucket, Key=file_key)
            logger.info("s3_delete_success", key=file_key)
            return True
        except ClientError as e:
            logger.error("s3_delete_error", key=file_key, error=str(e))
            return False

    async def exists(self, file_key: str) -> bool:
        try:
            async with self.session.client("s3") as s3:
                await s3.head_object(Bucket=self.bucket, Key=file_key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise e

    async def get_metadata(self, file_key: str) -> Optional[StorageObject]:
        try:
            async with self.session.client("s3") as s3:
                response = await s3.head_object(Bucket=self.bucket, Key=file_key)
                return StorageObject(
                    key=file_key,
                    content_type=response.get("ContentType", "application/octet-stream"),
                    size_bytes=response.get("ContentLength", 0),
                    metadata=response.get("Metadata", {}),
                )
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return None
            raise e
