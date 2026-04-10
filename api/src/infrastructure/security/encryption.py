"""
Infrastructure — AES-256 Encryption for LGPD compliance.

CPF e outros dados pessoais sensíveis são criptografados em repouso.
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.settings import get_settings

settings = get_settings()


class EncryptionService:
    """
    Serviço de criptografia AES-256-GCM para dados sensíveis (CPF, etc.).

    AES-GCM: modo autenticado — detecta adulteração dos dados cifrados.
    Nonce único por operação: garante que textos iguais geram cifras diferentes.
    """

    def __init__(self):
        raw_key = settings.ENCRYPTION_KEY
        if not raw_key:
            # Em dev, gerar chave automaticamente (não persistente)
            self._key = os.urandom(32)
        else:
            self._key = base64.b64decode(raw_key)
            if len(self._key) != 32:
                raise ValueError("ENCRYPTION_KEY deve ser uma chave base64 de 32 bytes.")

    def encrypt(self, plaintext: str) -> str:
        """
        Criptografa texto com AES-256-GCM.
        Retorna: base64(nonce || ciphertext_com_tag)
        """
        aesgcm = AESGCM(self._key)
        nonce = os.urandom(12)  # 96-bit nonce para GCM
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # Concatenar nonce + ciphertext para armazenamento
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode("utf-8")

    def decrypt(self, ciphertext_b64: str) -> str:
        """
        Descriptografa um valor cifrado com AES-256-GCM.
        Lança excepção se o dado for adulterado (GCM authentication tag).
        """
        combined = base64.b64decode(ciphertext_b64)
        nonce = combined[:12]
        ciphertext = combined[12:]
        aesgcm = AESGCM(self._key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

    def encrypt_cpf(self, cpf: str) -> str:
        """Normaliza (remove formatação) e criptografa CPF."""
        # Remover pontos, traços e espaços
        normalized = "".join(c for c in cpf if c.isdigit())
        if len(normalized) != 11:
            raise ValueError(f"CPF inválido: deve ter 11 dígitos. Recebido: {len(normalized)}")
        return self.encrypt(normalized)

    def decrypt_cpf(self, encrypted_cpf: str) -> str:
        """Descriptografa CPF. Usar apenas quando necessário e com auditoria."""
        return self.decrypt(encrypted_cpf)

    @staticmethod
    def generate_key() -> str:
        """Gera uma nova chave AES-256 em base64. Use para configurar ENCRYPTION_KEY."""
        key = os.urandom(32)
        return base64.b64encode(key).decode("utf-8")
