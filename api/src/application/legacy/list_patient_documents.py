"""
Application Use Case — Listar documentos legados de um paciente.

Consulta Oracle (GEMMIUS.GEDLEGACY + GEMMIUS.LOG_GED) e
retorna a lista paginada de documentos com metadados e
URL de visualização para cada imagem.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

from src.infrastructure.database.oracle.gemmius_repository import GemmiusRepository

logger = structlog.get_logger()


@dataclass
class LegacyDocumentItem:
    """DTO de saída — um documento do sistema legado."""
    row_id: str                          # ROWID Oracle (identificador único)
    patient_id: int
    nome_arquivo: Optional[str]
    path_arquivo: Optional[str]
    drive_arquivo: Optional[str]
    formato: Optional[str]               # jbig2, jpg, pdf…
    view_url: str                        # URL para visualizar via API
    download_url: str                    # URL para download via API
    thumbnail_url: str                   # URL para pré-visualização miniatura via API
    metadata: dict = field(default_factory=dict)  # demais colunas do Oracle


@dataclass
class ListPatientDocumentsOutput:
    patient_id: int
    items: list[LegacyDocumentItem]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return max(1, (self.total + self.page_size - 1) // self.page_size)


class ListPatientDocumentsUseCase:
    """
    Caso de uso: listar documentos legados de um paciente pelo PATIENTID.
    """

    def __init__(self, base_url: str = ""):
        self._base_url = base_url.rstrip("/")

    def execute(
        self,
        patient_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> ListPatientDocumentsOutput:

        # 1. Total para paginação
        total = GemmiusRepository.count_patient_documents(patient_id)

        # 2. Buscar página
        rows = GemmiusRepository.list_patient_documents(patient_id, page, page_size)

        # 3. Converter para DTOs (já vêm ordenados por grupo + sequência do SQL)
        items = [self._row_to_item(row) for row in rows]

        logger.info(
            "legacy_list_patient_docs",
            patient_id=patient_id,
            total=total,
            page=page,
            returned=len(items),
        )

        return ListPatientDocumentsOutput(
            patient_id=patient_id,
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    def _row_to_item(self, row: dict[str, Any]) -> LegacyDocumentItem:
        """Monta o DTO a partir de uma linha do Oracle."""
        row_id      = str(row.get("row_id", ""))
        patient_id  = int(row.get("patientid", 0))
        nome_arq    = row.get("nome_arquivo") or row.get("nomearquivo")
        path_arq    = row.get("path_arquivo") or row.get("patharquivo")
        drive_arq   = row.get("drive_arquivo") or row.get("drive") or "H"

        # Detectar formato pelo nome do arquivo
        formato = None
        if nome_arq:
            ext = nome_arq.rsplit(".", 1)[-1].lower() if "." in nome_arq else "unknown"
            formato = ext

        # URLs da própria API
        view_url      = f"{self._base_url}/api/v1/legacy/documents/{row_id}/view"
        download_url  = f"{self._base_url}/api/v1/legacy/documents/{row_id}/download"
        thumbnail_url = f"{self._base_url}/api/v1/legacy/documents/{row_id}/thumbnail"

        # Campos extras como metadata (tudo que não é coluna especial)
        skip_keys = {"row_id", "nome_arquivo", "nomearquivo", "path_arquivo",
                     "patharquivo", "drive_arquivo", "drive", "dt_inclusao_log"}
        metadata = {k: v for k, v in row.items() if k not in skip_keys and v is not None}

        return LegacyDocumentItem(
            row_id=row_id,
            patient_id=patient_id,
            nome_arquivo=nome_arq,
            path_arquivo=path_arq,
            drive_arquivo=drive_arq,
            formato=formato,
            view_url=view_url,
            download_url=download_url,
            thumbnail_url=thumbnail_url,
            metadata=metadata,
        )
