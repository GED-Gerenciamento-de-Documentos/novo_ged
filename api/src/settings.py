"""Configurações centrais da aplicação GED via Pydantic Settings."""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_NAME: str = "GED API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "ged_user"
    POSTGRES_PASSWORD: str = "ged_secret_password"
    POSTGRES_DB: str = "ged_metadata"
    DATABASE_URL: str = ""

    # Oracle 11g — Banco Legado Gemmius (Read-Only)
    ORACLE_HOST: str = ""
    ORACLE_PORT: int = 1521
    ORACLE_SERVICE_NAME: str = "ORCL"
    ORACLE_USER: str = "ged_readonly"
    ORACLE_PASSWORD: str = ""
    ORACLE_DSN: str = ""

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_URL: str = ""

    def model_post_init(self, __context) -> None:
        """Garante que as URLs sejam construídas se não fornecidas explicitamente."""
        if not self.DATABASE_URL or "localhost" in self.DATABASE_URL:
             self.DATABASE_URL = f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
        if not self.ORACLE_DSN or "localhost" in self.ORACLE_DSN:
            self.ORACLE_DSN = f"{self.ORACLE_HOST}:{self.ORACLE_PORT}/{self.ORACLE_SERVICE_NAME}"
            
        if not self.REDIS_URL or "localhost" in self.REDIS_URL:
            auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
            self.REDIS_URL = f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # JWT
    JWT_SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_MIN_32_CHARS_REQUIRED"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Criptografia (LGPD)
    ENCRYPTION_KEY: str = ""  # Base64 encoded 32-byte key

    # Storage NFS (legado genérico)
    NFS_MOUNT_PATH: str = "/mnt/nfs/documentos"
    NFS_LEGACY_BASE_PATH: str = "/mnt/nfs/documentos/legado"

    # Storage local para desenvolvimento (definir no .env — não commitar!)
    LOCAL_STORAGE_PATH: str = ""  # Ex: C:\Users\nome\Desktop\GED_Uploads


    # Servidor de Arquivos GED (H:\GED e J:\GED)
    GED_FILE_SERVER_HOST: str = ""  # Definir no .env: GED_FILE_SERVER_HOST=...
    GED_MOUNT_PATH_H: str = "/mnt/ged_h"   # Mount local do share H:\GED
    GED_MOUNT_PATH_J: str = "/mnt/ged_j"   # Mount local do share J:\GED
    GED_SMB_USER: str = ""
    GED_SMB_PASSWORD: str = ""
    GED_SMB_DOMAIN: str = ""

    # Storage Cloud
    CLOUD_STORAGE_PROVIDER: str = "stub"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "sa-east-1"
    S3_BUCKET_NAME: str = "ged-documentos"
    AZURE_CONNECTION_STRING: str = ""
    AZURE_CONTAINER_NAME: str = "ged-documentos"

    # Upload
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: str = "jpg,jpeg,jbig2,jb2,pdf,png,tiff,tif"

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: str = "minute"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    CORS_ALLOW_CREDENTIALS: bool = True

    @property
    def CORS_ORIGINS_LIST(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def ALLOWED_EXTENSIONS_LIST(self) -> List[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """Retorna instância singleton das configurações."""
    return Settings()
