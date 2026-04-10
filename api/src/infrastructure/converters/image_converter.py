"""
Infrastructure — JBIG2/JPG Image Converter.

Serviço de conversão e streaming de imagens para o viewer GED.
Suporta JBIG2 (via jbig2dec CLI), JPG, PNG, TIFF.
"""
from __future__ import annotations

import asyncio
import io
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import structlog
from PIL import Image

logger = structlog.get_logger()


class ImageFormat:
    JBIG2 = "jbig2"
    JB2 = "jb2"
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"
    TIFF = "tiff"
    TIF = "tif"
    PDF = "pdf"


class ImageConverter:
    """
    Converte e processa imagens de documentos GED.

    JBIG2: formato de compressão de imagens binárias (preto/branco),
    muito usado em scanners de documentos. Requer jbig2dec para decodificação.

    Responsabilidade única: conversão/processamento de imagens.
    """

    JBIG2_EXTENSIONS = {".jbig2", ".jb2"}
    NATIVE_PIL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}

    @staticmethod
    def detect_format(file_path: str) -> str:
        """Detecta o formato pelo sufixo do arquivo."""
        return Path(file_path).suffix.lower().lstrip(".")

    @staticmethod
    def get_content_type(file_extension: str) -> str:
        """Retorna o MIME type correto para o arquivo."""
        mime_map = {
            "jbig2": "image/jbig2",
            "jb2": "image/jbig2",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "tiff": "image/tiff",
            "tif": "image/tiff",
            "pdf": "application/pdf",
        }
        return mime_map.get(file_extension.lower().lstrip("."), "application/octet-stream")

    @staticmethod
    async def is_jbig2dec_available() -> bool:
        """Verifica se o jbig2dec está instalado no sistema."""
        try:
            def _run():
                return subprocess.run(["jbig2dec", "--version"], capture_output=True)
            proc = await asyncio.to_thread(_run)
            return proc.returncode in (0, 1)  # Alguns builds retornam 1 com --version
        except (FileNotFoundError, OSError):
            return False

    @staticmethod
    async def jbig2_to_png(jbig2_content: bytes) -> bytes:
        """
        Converte conteúdo JBIG2 para PNG usando jbig2dec CLI.

        jbig2dec é um decoder open-source para o formato JBIG2.
        Salvamos o arquivo temporariamente e chamamos o CLI.
        """
        with tempfile.NamedTemporaryFile(suffix=".jbig2", delete=False) as input_f:
            input_path = Path(input_f.name)
            input_f.write(jbig2_content)

        output_path = input_path.with_suffix(".png")

        try:
            def _run_jbig2dec():
                return subprocess.run(
                    ["jbig2dec", "-t", "png", "-o", str(output_path), str(input_path)],
                    capture_output=True,
                )

            proc = await asyncio.to_thread(_run_jbig2dec)

            if proc.returncode != 0:
                error_msg = proc.stderr.decode("utf-8", errors="replace")
                logger.error("jbig2dec_failed", returncode=proc.returncode, error=error_msg)
                raise RuntimeError(f"jbig2dec falhou: {error_msg}")

            if not output_path.exists():
                raise RuntimeError("jbig2dec não gerou o arquivo de saída.")

            png_content = output_path.read_bytes()
            logger.info("jbig2_converted", input_size=len(jbig2_content), output_size=len(png_content))
            return png_content

        finally:
            input_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

    @staticmethod
    async def jbig2_to_jpeg(jbig2_content: bytes, quality: int = 85) -> bytes:
        """Converte JBIG2 → PNG via jbig2dec → depois para JPEG via Pillow."""
        png_content = await ImageConverter.jbig2_to_png(jbig2_content)

        img = Image.open(io.BytesIO(png_content))

        # JBIG2 é monocromático (1-bit) — converter para RGB para JPEG
        if img.mode in ("1", "L"):
            img = img.convert("RGB")

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        return output.getvalue()

    @staticmethod
    async def generate_thumbnail(
        file_content: bytes,
        file_format: str,
        max_size: Tuple[int, int] = (400, 400),
    ) -> bytes:
        """
        Gera thumbnail da primeira página do documento.
        Retorna PNG compactado.
        """
        fmt = file_format.lower().lstrip(".")

        # Converter JBIG2 para PNG primeiro
        if fmt in ("jbig2", "jb2"):
            content = await ImageConverter.jbig2_to_png(file_content)
            fmt = "png"
        else:
            content = file_content

        # Abrir com Pillow
        img = Image.open(io.BytesIO(content))

        # Converter modos não suportados
        if img.mode in ("1", "CMYK", "LA"):
            img = img.convert("RGB")
        elif img.mode == "P":
            img = img.convert("RGBA")

        # Gerar thumbnail mantendo proporção
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        output = io.BytesIO()
        img.save(output, format="PNG", optimize=True)
        return output.getvalue()

    @staticmethod
    async def prepare_for_viewer(
        file_content: bytes,
        file_format: str,
        target_format: str = "auto",
    ) -> Tuple[bytes, str]:
        """
        Prepara o arquivo para visualização no navegador.

        Para JBIG2: converte para JPEG (melhor suporte no browser).
        Para outros formatos: retorna como está.

        Returns:
            Tuple[bytes, str]: (conteúdo, content_type)
        """
        fmt = file_format.lower().lstrip(".")

        if fmt in ("jbig2", "jb2"):
            # Browser não suporta JBIG2 nativamente — converter para JPEG
            jpeg_content = await ImageConverter.jbig2_to_jpeg(file_content)
            return jpeg_content, "image/jpeg"

        elif fmt in ("jpg", "jpeg"):
            return file_content, "image/jpeg"

        elif fmt == "png":
            return file_content, "image/png"

        elif fmt in ("tiff", "tif"):
            # Converter TIFF para JPEG (browser suporte limitado a TIFF)
            img = Image.open(io.BytesIO(file_content))
            if img.mode in ("1", "L", "CMYK"):
                img = img.convert("RGB")
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=90)
            return output.getvalue(), "image/jpeg"

        elif fmt == "pdf":
            # PDF retorna diretamente — browser suporta nativamente
            return file_content, "application/pdf"

        else:
            return file_content, "application/octet-stream"
