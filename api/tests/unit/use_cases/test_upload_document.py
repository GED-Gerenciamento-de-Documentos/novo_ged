"""Tests — Unit tests for UploadDocumentUseCase."""
from __future__ import annotations

import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.documents.upload_document import (
    UploadDocumentInput,
    UploadDocumentUseCase,
)
from src.domain.documents.entities.document import DocumentType, FileFormat
from src.infrastructure.storage.interfaces import StorageObject


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ANONYMOUS_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

SAMPLE_PDF = b"%PDF-1.4 sample content for testing"

def make_input(**kwargs) -> UploadDocumentInput:
    """Factory para criar UploadDocumentInput de testes."""
    defaults = dict(
        title="Laudo Médico de Teste",
        document_type=DocumentType.LAUDO,
        file_format=FileFormat.PDF,
        file_content=SAMPLE_PDF,
        file_name="laudo_teste.pdf",
        owner_name="Maria da Silva",
        uploaded_by_id=ANONYMOUS_USER_ID,
        uploaded_by_email="dev@localhost",
        uploaded_by_role="ADMINISTRADOR",
        ip_address="127.0.0.1",
        user_agent="pytest/test",
    )
    defaults.update(kwargs)
    return UploadDocumentInput(**defaults)


def make_storage_object(file_content: bytes = SAMPLE_PDF) -> StorageObject:
    return StorageObject(
        key="documentos/laudo/test-uuid.pdf",
        content_type="application/pdf",
        size_bytes=len(file_content),
        checksum_sha256=hashlib.sha256(file_content).hexdigest(),
    )


@pytest.fixture
def mock_storage():
    storage = AsyncMock()
    storage.upload.return_value = make_storage_object()
    return storage


@pytest.fixture
def mock_document_repo():
    repo = AsyncMock()
    # save retorna um objeto com id simulado
    saved_doc = MagicMock()
    saved_doc.id.value = uuid.uuid4()
    repo.save.return_value = saved_doc
    return repo


@pytest.fixture
def mock_audit_repo():
    return AsyncMock()


@pytest.fixture
def mock_encryption():
    enc = MagicMock()
    enc.encrypt_cpf.return_value = "encrypted_cpf_value"
    return enc


@pytest.fixture
def use_case(mock_document_repo, mock_audit_repo, mock_storage, mock_encryption):
    return UploadDocumentUseCase(
        document_repository=mock_document_repo,
        audit_repository=mock_audit_repo,
        cloud_storage=mock_storage,
        encryption_service=mock_encryption,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestUploadDocumentUseCase:
    """Testes unitários do caso de uso de upload de documento."""

    @pytest.mark.asyncio
    async def test_upload_pdf_success(self, use_case, mock_storage, mock_document_repo):
        """Upload de PDF válido deve salvar no storage e no repositório."""
        input_data = make_input()

        output = await use_case.execute(input_data)

        # Verifica que storage.upload foi chamado
        mock_storage.upload.assert_called_once()
        call_kwargs = mock_storage.upload.call_args
        assert "laudo" in call_kwargs.kwargs.get("file_key", call_kwargs.args[0] if call_kwargs.args else "")
        assert call_kwargs.kwargs.get("file_content", call_kwargs.args[1] if len(call_kwargs.args) > 1 else b"") == SAMPLE_PDF

        # Verifica que repositório salvou o documento
        mock_document_repo.save.assert_called_once()

        # Verifica saída
        assert output.title == "Laudo Médico de Teste"
        assert output.file_size_bytes == len(SAMPLE_PDF)
        assert output.message == "Documento enviado com sucesso."

    @pytest.mark.asyncio
    async def test_upload_generates_correct_checksum(self, use_case):
        """Upload deve calcular SHA256 corretamente."""
        input_data = make_input(file_content=b"conteudo_unico_para_teste")
        expected_checksum = hashlib.sha256(b"conteudo_unico_para_teste").hexdigest()

        output = await use_case.execute(input_data)

        assert output.checksum_sha256 == expected_checksum

    @pytest.mark.asyncio
    async def test_upload_saves_audit_log(self, use_case, mock_audit_repo):
        """Upload deve registrar log de auditoria com action=UPLOAD."""
        from src.domain.audit.entities.audit_log import AuditAction

        input_data = make_input()
        await use_case.execute(input_data)

        mock_audit_repo.save.assert_called_once()
        saved_audit = mock_audit_repo.save.call_args.args[0]
        assert saved_audit.action == AuditAction.UPLOAD
        assert saved_audit.user_email == "dev@localhost"

    @pytest.mark.asyncio
    async def test_upload_encrypts_cpf_when_provided(self, use_case, mock_encryption, mock_document_repo):
        """CPF fornecido deve ser criptografado antes de persistir."""
        input_data = make_input(owner_cpf="123.456.789-00")

        await use_case.execute(input_data)

        mock_encryption.encrypt_cpf.assert_called_once_with("123.456.789-00")

    @pytest.mark.asyncio
    async def test_upload_without_cpf_skips_encryption(self, use_case, mock_encryption):
        """Sem CPF, encrypt_cpf não deve ser chamado."""
        input_data = make_input(owner_cpf=None)

        await use_case.execute(input_data)

        mock_encryption.encrypt_cpf.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_storage_path_contains_document_type(self, use_case, mock_storage):
        """storage_key gerado deve conter o tipo de documento para organização."""
        input_data = make_input(document_type=DocumentType.EXAME)

        output = await use_case.execute(input_data)

        assert "exame" in output.storage_path.lower()

    @pytest.mark.asyncio
    async def test_upload_storage_failure_propagates_exception(
        self, mock_document_repo, mock_audit_repo, mock_encryption
    ):
        """Se o storage falhar, o use case deve propagar a exceção."""
        failing_storage = AsyncMock()
        failing_storage.upload.side_effect = OSError("Disco cheio")

        use_case_failing = UploadDocumentUseCase(
            document_repository=mock_document_repo,
            audit_repository=mock_audit_repo,
            cloud_storage=failing_storage,
            encryption_service=mock_encryption,
        )

        with pytest.raises(OSError, match="Disco cheio"):
            await use_case_failing.execute(make_input())

        # Não deve ter salvo nada no banco se o storage falhou
        mock_document_repo.save.assert_not_called()
