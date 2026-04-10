"""Presentation — Pydantic schemas for request/response validation."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ==========================================
# Auth Schemas
# ==========================================

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="E-mail do usuário")
    password: str = Field(..., min_length=6, description="Senha do usuário")

    model_config = {"json_schema_extra": {"example": {"email": "admin@ged.local", "password": "senha123"}}}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ==========================================
# User Schemas
# ==========================================

class UserRoleEnum(str):
    OPERADOR = "OPERADOR"
    GESTOR = "GESTOR"
    ADMINISTRADOR = "ADMINISTRADOR"


class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=300)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Mínimo 8 caracteres")
    role: str = Field(..., pattern="^(OPERADOR|GESTOR|ADMINISTRADOR)$")
    department: str = Field(..., min_length=2, max_length=200)


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: str
    department: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ==========================================
# Document Schemas
# ==========================================

class DocumentTypeEnum(str):
    CONTRATO = "CONTRATO"
    PRONTUARIO = "PRONTUARIO"
    LAUDO = "LAUDO"
    OFICIO = "OFICIO"
    RECIBO = "RECIBO"
    DECLARACAO = "DECLARACAO"
    RELATORIO = "RELATORIO"
    OUTRO = "OUTRO"


class FileFormatEnum(str):
    JBIG2 = "JBIG2"
    JPG = "JPG"
    PDF = "PDF"
    PNG = "PNG"
    TIFF = "TIFF"


class UploadDocumentRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=500, description="Título do documento")
    document_type: str = Field(
        ...,
        pattern="^(CONTRATO|PRONTUARIO|LAUDO|OFICIO|RECIBO|DECLARACAO|RELATORIO|OUTRO)$",
        description="Tipo do documento",
    )
    owner_name: str = Field(..., min_length=2, max_length=300, description="Nome do proprietário")
    owner_cpf: Optional[str] = Field(None, description="CPF do proprietário (armazenado criptografado)")
    owner_record_number: Optional[str] = Field(None, max_length=100, description="Número do prontuário/processo")
    document_date: Optional[date] = Field(None, description="Data do documento físico")
    is_confidential: bool = Field(False, description="Marcar como confidencial")
    tags: Optional[List[str]] = Field(default=None, max_length=20, description="Tags para busca")
    retention_until: Optional[date] = Field(None, description="Prazo de retenção legal")
    extra_metadata: Optional[dict] = Field(None, description="Metadados adicionais flexíveis")

    @field_validator("owner_cpf")
    @classmethod
    def validate_cpf_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) != 11:
            raise ValueError("CPF deve conter 11 dígitos numéricos.")
        return v


class DocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    document_type: str
    file_format: str
    storage_type: str
    owner_name: str
    owner_record_number: Optional[str] = None
    document_date: Optional[date] = None
    is_confidential: bool
    status: str
    file_size_bytes: int
    page_count: int
    tags: List[str] = []
    retention_until: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class UpdateDocumentRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=500)
    tags: Optional[List[str]] = None
    is_confidential: Optional[bool] = None
    retention_until: Optional[date] = None
    extra_metadata: Optional[dict] = None


class DeleteDocumentRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="Motivo da exclusão")


# ==========================================
# Audit Schemas
# ==========================================

class AuditLogResponse(BaseModel):
    id: uuid.UUID
    action: str
    user_email: str
    user_role: str
    ip_address: str
    timestamp: datetime
    document_id: Optional[uuid.UUID] = None
    document_title: Optional[str] = None
    success: bool
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class AuditListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ==========================================
# Response Generics
# ==========================================

class MessageResponse(BaseModel):
    message: str
    success: bool = True
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    status_code: int
