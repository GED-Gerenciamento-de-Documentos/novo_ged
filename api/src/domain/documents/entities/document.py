"""Domain layer — Document entity and value objects."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class DocumentType(str, Enum):
    CONTRATO = "CONTRATO"
    PRONTUARIO = "PRONTUARIO"
    LAUDO = "LAUDO"
    OFICIO = "OFICIO"
    RECIBO = "RECIBO"
    DECLARACAO = "DECLARACAO"
    RELATORIO = "RELATORIO"
    OUTRO = "OUTRO"


class FileFormat(str, Enum):
    JBIG2 = "JBIG2"
    JPG = "JPG"
    PDF = "PDF"
    PNG = "PNG"
    TIFF = "TIFF"


class StorageType(str, Enum):
    LEGACY_NFS = "LEGACY_NFS"    # Servidor NFS legado (leitura)
    CLOUD = "CLOUD"               # Storage em nuvem (novos documentos)


class DocumentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    PENDING_DELETION = "PENDING_DELETION"
    DELETED = "DELETED"


@dataclass(frozen=True)
class CPF:
    """Value Object para CPF — armazenado sempre criptografado."""
    encrypted_value: str

    def __str__(self) -> str:
        return "***.***.***-**"  # Nunca expor o CPF decriptografado em logs

    @classmethod
    def from_encrypted(cls, encrypted: str) -> "CPF":
        return cls(encrypted_value=encrypted)


@dataclass(frozen=True)
class DocumentId:
    """Value Object para identificador do documento."""
    value: uuid.UUID

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def generate(cls) -> "DocumentId":
        return cls(value=uuid.uuid4())

    @classmethod
    def from_string(cls, value: str) -> "DocumentId":
        return cls(value=uuid.UUID(value))


@dataclass
class Document:
    """
    Entidade raiz de agregado — Documento GED.

    Princípio SOLID: Single Responsibility — contém apenas
    a lógica de negócio do domínio documental.
    """

    id: DocumentId
    title: str
    document_type: DocumentType
    file_format: FileFormat
    storage_type: StorageType
    storage_path: str

    # Metadados de identificação
    owner_name: str
    owner_cpf: Optional[CPF] = None
    owner_record_number: Optional[str] = None  # Número do prontuário/processo

    # Metadados de negócio
    document_date: Optional[date] = None
    category_id: Optional[uuid.UUID] = None
    tags: list[str] = field(default_factory=list)

    # Metadados técnicos
    file_size_bytes: int = 0
    page_count: int = 1
    checksum_sha256: Optional[str] = None

    # Controle de acesso
    is_confidential: bool = False

    # Gestão de ciclo de vida
    status: DocumentStatus = DocumentStatus.ACTIVE
    retention_until: Optional[date] = None  # Prazo legal de guarda

    # Auditoria
    uploaded_by_id: Optional[uuid.UUID] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = None

    # Metadados extras flexíveis (para campos específicos por tipo)
    extra_metadata: dict = field(default_factory=dict)

    # ==========================================
    # Regras de negócio do domínio
    # ==========================================

    def mark_as_deleted(self, deleted_by_id: uuid.UUID) -> None:
        """Soft delete — mantém o registro por auditoria."""
        if self.status == DocumentStatus.DELETED:
            raise ValueError("Documento já foi excluído anteriormente.")
        self.status = DocumentStatus.DELETED
        self.deleted_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_for_archival(self) -> None:
        """Marca para arquivamento quando prazo de retenção é atingido."""
        self.status = DocumentStatus.ARCHIVED
        self.updated_at = datetime.utcnow()

    def update_metadata(
        self,
        title: Optional[str] = None,
        tags: Optional[list[str]] = None,
        is_confidential: Optional[bool] = None,
        retention_until: Optional[date] = None,
        extra_metadata: Optional[dict] = None,
    ) -> None:
        """Atualiza metadados permitidos (não altera o arquivo físico)."""
        if title is not None:
            self.title = title
        if tags is not None:
            self.tags = tags
        if is_confidential is not None:
            self.is_confidential = is_confidential
        if retention_until is not None:
            self.retention_until = retention_until
        if extra_metadata is not None:
            self.extra_metadata.update(extra_metadata)
        self.updated_at = datetime.utcnow()

    def is_accessible_by(self, user_role: str) -> bool:
        """
        Verifica se o documento pode ser acessado pelo perfil do usuário.
        Documentos confidenciais só acessíveis por GESTOR e ADMINISTRADOR.
        """
        if not self.is_confidential:
            return True
        return user_role in ("GESTOR", "ADMINISTRADOR")

    def is_active(self) -> bool:
        return self.status == DocumentStatus.ACTIVE

    def is_from_legacy(self) -> bool:
        return self.storage_type == StorageType.LEGACY_NFS

    @property
    def extension(self) -> str:
        return self.file_format.value.lower()

    @classmethod
    def create_new(
        cls,
        title: str,
        document_type: DocumentType,
        file_format: FileFormat,
        storage_path: str,
        storage_type: StorageType,
        owner_name: str,
        uploaded_by_id: uuid.UUID,
        **kwargs,
    ) -> "Document":
        """Factory method — cria novo documento com ID gerado."""
        return cls(
            id=DocumentId.generate(),
            title=title,
            document_type=document_type,
            file_format=file_format,
            storage_type=storage_type,
            storage_path=storage_path,
            owner_name=owner_name,
            uploaded_by_id=uploaded_by_id,
            **kwargs,
        )
