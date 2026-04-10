"""
Infrastructure — Acesso aos arquivos GED no servidor 192.168.8.53.

Os arquivos estão nas pastas H:\\GED ou J:\\GED do servidor.
Tenta buscar nos caminhos diretos ou UNC Network paths.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import structlog

from src.settings import get_settings

logger = structlog.get_logger()
settings = get_settings()

CHUNK_SIZE = 65536  # 64 KB


class GedFileStorage:
    """
    Lê arquivos JBIG2/JPG do servidor de arquivos GED (192.168.8.53) em modo síncrono.
    """

    def __init__(self):
        self._fallback_unc_host = getattr(settings, "GED_FILE_SERVER_HOST", "192.168.8.53")

    def resolve_file_path(
        self,
        nome_arquivo: Optional[str],
    ) -> Optional[Path]:
        """
        Localiza o arquivo fisicamente tentando diversas combinações comuns de mapeamento no Windows.
        """
        if not nome_arquivo:
            return None

        possiveis_caminhos = [
            f"/mnt/nfs/{nome_arquivo}",
            f"H:\\GED\\{nome_arquivo}",
            f"J:\\GED\\{nome_arquivo}",
            f"\\\\{self._fallback_unc_host}\\GED\\{nome_arquivo}",
            f"\\\\{self._fallback_unc_host}\\H$\\GED\\{nome_arquivo}",
            f"\\\\{self._fallback_unc_host}\\J$\\GED\\{nome_arquivo}"
        ]

        for cam in possiveis_caminhos:
            if os.path.exists(cam):
                return Path(cam)

        return None

    def read_file(
        self,
        nome_arquivo: Optional[str],
    ) -> bytes:
        """Lê o arquivo completo remotamente e retorna bytes síncronamente."""
        file_path = self.resolve_file_path(nome_arquivo)

        if file_path is None:
            raise FileNotFoundError(
                f"Arquivo {nome_arquivo} não encontrado em nenhum mapeamento de rede "
                f"(H:, J: ou UNC {self._fallback_unc_host})"
            )

        logger.info("ged_file_read", path=str(file_path), size_kb=file_path.stat().st_size // 1024)
        with open(file_path, "rb") as f:
            return f.read()

    def file_exists(
        self,
        nome_arquivo: Optional[str],
    ) -> bool:
        """Verifica se o arquivo existe no servidor."""
        return self.resolve_file_path(nome_arquivo) is not None

    @staticmethod
    def detect_format(nome_arquivo: str) -> str:
        """Detecta o formato pelo sufixo do arquivo."""
        ext = Path(nome_arquivo).suffix.lower().lstrip(".")
        return ext  # "jbig2", "jpg", "pdf", etc.

