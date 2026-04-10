"""Tests — Unit tests for Document domain entity."""
from __future__ import annotations

import uuid
from datetime import datetime, date
import pytest

from src.domain.documents.entities.document import (
    CPF,
    Document,
    DocumentId,
    DocumentStatus,
    DocumentType,
    FileFormat,
    StorageType,
)


def make_document(**kwargs) -> Document:
    """Factory helper para criar documentos de teste."""
    defaults = {
        "id": DocumentId.generate(),
        "title": "Contrato de Prestação de Serviços",
        "document_type": DocumentType.CONTRATO,
        "file_format": FileFormat.JPG,
        "storage_type": StorageType.CLOUD,
        "storage_path": "documentos/contrato/test.jpg",
        "owner_name": "João da Silva",
        "uploaded_by_id": uuid.uuid4(),
    }
    defaults.update(kwargs)
    return Document(**defaults)


class TestDocumentEntity:
    """Testes unitários da entidade Document."""

    def test_create_document_with_valid_data(self):
        doc = make_document()
        assert doc.title == "Contrato de Prestação de Serviços"
        assert doc.document_type == DocumentType.CONTRATO
        assert doc.status == DocumentStatus.ACTIVE
        assert doc.is_confidential is False

    def test_document_id_generates_unique_uuid(self):
        id1 = DocumentId.generate()
        id2 = DocumentId.generate()
        assert id1.value != id2.value

    def test_document_id_from_string(self):
        uid = uuid.uuid4()
        doc_id = DocumentId.from_string(str(uid))
        assert doc_id.value == uid

    def test_soft_delete_changes_status(self):
        doc = make_document()
        deleted_by = uuid.uuid4()
        doc.mark_as_deleted(deleted_by)
        assert doc.status == DocumentStatus.DELETED
        assert doc.deleted_at is not None

    def test_cannot_delete_already_deleted_document(self):
        doc = make_document()
        deleted_by = uuid.uuid4()
        doc.mark_as_deleted(deleted_by)
        with pytest.raises(ValueError, match="já foi excluído"):
            doc.mark_as_deleted(deleted_by)

    def test_non_confidential_accessible_by_operador(self):
        doc = make_document(is_confidential=False)
        assert doc.is_accessible_by("OPERADOR") is True

    def test_confidential_not_accessible_by_operador(self):
        doc = make_document(is_confidential=True)
        assert doc.is_accessible_by("OPERADOR") is False

    def test_confidential_accessible_by_gestor(self):
        doc = make_document(is_confidential=True)
        assert doc.is_accessible_by("GESTOR") is True

    def test_confidential_accessible_by_administrador(self):
        doc = make_document(is_confidential=True)
        assert doc.is_accessible_by("ADMINISTRADOR") is True

    def test_update_metadata_changes_fields(self):
        doc = make_document()
        doc.update_metadata(
            title="Novo Título",
            tags=["urgente", "2024"],
            is_confidential=True,
        )
        assert doc.title == "Novo Título"
        assert "urgente" in doc.tags
        assert doc.is_confidential is True

    def test_update_metadata_preserves_unset_fields(self):
        doc = make_document(owner_name="Maria")
        original_type = doc.document_type
        doc.update_metadata(title="Novo Título")
        # document_type não deve mudar
        assert doc.document_type == original_type

    def test_is_from_legacy_when_nfs(self):
        doc = make_document(storage_type=StorageType.LEGACY_NFS)
        assert doc.is_from_legacy() is True

    def test_is_not_from_legacy_when_cloud(self):
        doc = make_document(storage_type=StorageType.CLOUD)
        assert doc.is_from_legacy() is False

    def test_create_new_factory_method(self):
        uploaded_by = uuid.uuid4()
        doc = Document.create_new(
            title="Laudo Médico",
            document_type=DocumentType.LAUDO,
            file_format=FileFormat.PDF,
            storage_path="documentos/laudo/test.pdf",
            storage_type=StorageType.CLOUD,
            owner_name="Ana Lima",
            uploaded_by_id=uploaded_by,
        )
        assert doc.owner_name == "Ana Lima"
        assert doc.uploaded_by_id == uploaded_by
        assert doc.status == DocumentStatus.ACTIVE
        assert doc.id is not None

    def test_mark_for_archival(self):
        doc = make_document()
        doc.mark_for_archival()
        assert doc.status == DocumentStatus.ARCHIVED

    def test_cpf_value_object_never_exposes_plaintext(self):
        cpf = CPF(encrypted_value="encrypted_value_here")
        assert "encrypted_value_here" not in str(cpf)
        assert "***" in str(cpf)

    def test_document_extension_property(self):
        doc = make_document(file_format=FileFormat.JPG)
        assert doc.extension == "jpg"

        doc_jbig2 = make_document(file_format=FileFormat.JBIG2)
        assert doc_jbig2.extension == "jbig2"
