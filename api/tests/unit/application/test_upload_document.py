"""Tests — Unit tests for UploadDocumentUseCase."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.documents.upload_document import UploadDocumentInput, UploadDocumentUseCase
from src.domain.documents.entities.document import DocumentType, FileFormat
from src.infrastructure.storage.interfaces import StorageObject


def make_upload_input(**kwargs) -> UploadDocumentInput:
    defaults = {
        "title": "Contrato Teste",
        "document_type": DocumentType.CONTRATO,
        "file_format": FileFormat.JPG,
        "file_content": b"fake_image_content",
        "file_name": "contrato.jpg",
        "owner_name": "João da Silva",
        "uploaded_by_id": uuid.uuid4(),
        "uploaded_by_email": "user@ged.local",
        "uploaded_by_role": "OPERADOR",
        "ip_address": "127.0.0.1",
        "user_agent": "Mozilla/5.0",
        "owner_cpf": None,
        "is_confidential": False,
        "tags": ["teste"],
    }
    defaults.update(kwargs)
    return UploadDocumentInput(**defaults)


@pytest.fixture
def mock_document_repo():
    repo = AsyncMock()
    repo.save = AsyncMock(side_effect=lambda doc: doc)
    return repo


@pytest.fixture
def mock_audit_repo():
    repo = AsyncMock()
    repo.save = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_cloud_storage():
    storage = AsyncMock()
    storage.upload = AsyncMock(
        return_value=StorageObject(
            key="documentos/contrato/test.jpg",
            content_type="image/jpeg",
            size_bytes=1024,
            checksum_sha256="abc123",
        )
    )
    return storage


@pytest.fixture
def mock_encryption():
    enc = MagicMock()
    enc.encrypt_cpf = MagicMock(return_value="encrypted_cpf_value")
    return enc


@pytest.fixture
def use_case(mock_document_repo, mock_audit_repo, mock_cloud_storage, mock_encryption):
    return UploadDocumentUseCase(
        document_repository=mock_document_repo,
        audit_repository=mock_audit_repo,
        cloud_storage=mock_cloud_storage,
        encryption_service=mock_encryption,
    )


class TestUploadDocumentUseCase:
    """Testes unitários do caso de uso de upload."""

    @pytest.mark.asyncio
    async def test_upload_succeeds_with_valid_input(self, use_case, mock_document_repo, mock_cloud_storage):
        input_data = make_upload_input()
        output = await use_case.execute(input_data)

        assert output.title == "Contrato Teste"
        assert output.document_id is not None
        assert output.file_size_bytes == 1024
        mock_cloud_storage.upload.assert_called_once()
        mock_document_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_calculates_sha256_checksum(self, use_case):
        import hashlib
        content = b"document_content_for_test"
        expected_checksum = hashlib.sha256(content).hexdigest()

        input_data = make_upload_input(file_content=content)
        output = await use_case.execute(input_data)
        assert output.checksum_sha256 == expected_checksum

    @pytest.mark.asyncio
    async def test_upload_encrypts_cpf_when_provided(
        self, use_case, mock_encryption, mock_document_repo
    ):
        input_data = make_upload_input(owner_cpf="123.456.789-09")
        await use_case.execute(input_data)
        mock_encryption.encrypt_cpf.assert_called_once_with("123.456.789-09")

    @pytest.mark.asyncio
    async def test_upload_does_not_encrypt_cpf_when_not_provided(
        self, use_case, mock_encryption
    ):
        input_data = make_upload_input(owner_cpf=None)
        await use_case.execute(input_data)
        mock_encryption.encrypt_cpf.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_creates_audit_log(self, use_case, mock_audit_repo):
        input_data = make_upload_input()
        await use_case.execute(input_data)
        mock_audit_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_generates_storage_path_with_document_type(
        self, use_case, mock_cloud_storage
    ):
        input_data = make_upload_input(document_type=DocumentType.PRONTUARIO, file_format=FileFormat.JPG)
        output = await use_case.execute(input_data)
        assert "prontuario" in output.storage_path.lower()

    @pytest.mark.asyncio
    async def test_upload_fails_when_storage_raises_exception(
        self, mock_document_repo, mock_audit_repo, mock_encryption
    ):
        failing_storage = AsyncMock()
        failing_storage.upload = AsyncMock(side_effect=ConnectionError("Storage indisponível"))

        use_case = UploadDocumentUseCase(
            document_repository=mock_document_repo,
            audit_repository=mock_audit_repo,
            cloud_storage=failing_storage,
            encryption_service=mock_encryption,
        )

        with pytest.raises(ConnectionError):
            await use_case.execute(make_upload_input())

        # Documento não deve ser salvo se o storage falhou
        mock_document_repo.save.assert_not_called()
