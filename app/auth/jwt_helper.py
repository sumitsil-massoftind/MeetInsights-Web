"""
JWT + AES helpers — Python port of src/helper/jwt_helper.ts

createToken: signs access JWT (JWT_SECRET) + refresh JWT (REFRESH_TOKEN_KEY),
then encrypts both with AES-256-CBC (CRYPT_ALGO + JWT_SECRET + ENCRYPTION_IV_KEY).
"""

from __future__ import annotations

import base64
import secrets
import time
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.auth.config import Settings, get_settings


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    access_token_expired: int  # unix seconds
    refresh_token_expired: int  # unix seconds


class JWTHelper:
    """Mirrors jWT_helper from the Node reference implementation."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _aes_key(self) -> bytes:
        key = self.settings.jwt_secret.encode("utf-8")
        if len(key) < 32:
            key = key.ljust(32, b"0")
        return key[:32]

    def _aes_iv(self) -> bytes:
        iv = self.settings.encryption_iv_key.encode("utf-8")
        if len(iv) < 16:
            iv = iv.ljust(16, b"0")
        return iv[:16]

    def encrypt_me(self, value: str) -> str:
        """AES-CBC encrypt → base64 (matches encryptMe in jwt_helper.ts)."""
        padder = padding.PKCS7(128).padder()
        padded = padder.update(value.encode("utf-8")) + padder.finalize()
        cipher = Cipher(
            algorithms.AES(self._aes_key()),
            modes.CBC(self._aes_iv()),
            backend=default_backend(),
        )
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(encrypted).decode("utf-8")

    def decrypt_me(self, encrypted: str) -> str:
        """AES-CBC decrypt from base64."""
        cipher = Cipher(
            algorithms.AES(self._aes_key()),
            modes.CBC(self._aes_iv()),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()
        padded = decryptor.update(base64.b64decode(encrypted)) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded) + unpadder.finalize()
        return data.decode("utf-8")

    def create_token(self, token_details: dict[str, Any], is_short_token: int = 0) -> TokenPair:
        """
        Create encrypted access + refresh tokens.

        Same flow as jwt_helper.createToken:
        1. jwt.sign access with JWT_SECRET
        2. encrypt access
        3. jwt.sign refresh with REFRESH_TOKEN_KEY
        4. encrypt refresh
        """
        settings = self.settings
        algorithm = settings.jwt_algorithm
        expires_in = settings.jwt_expires
        if is_short_token == 1:
            expires_in = settings.jwt_expires

        access_ttl = Settings.parse_ttl_seconds(expires_in)
        refresh_ttl = Settings.parse_ttl_seconds(settings.refresh_token_expire)
        now = int(time.time())

        access_jwt = jwt.encode(
            {**token_details, "iat": now, "exp": now + access_ttl},
            settings.jwt_secret,
            algorithm=algorithm,
        )
        refresh_jwt = jwt.encode(
            {**token_details, "iat": now, "exp": now + refresh_ttl},
            settings.refresh_token_key,
            algorithm=algorithm,
        )
        if isinstance(access_jwt, bytes):
            access_jwt = access_jwt.decode("utf-8")
        if isinstance(refresh_jwt, bytes):
            refresh_jwt = refresh_jwt.decode("utf-8")

        return TokenPair(
            access_token=self.encrypt_me(access_jwt),
            refresh_token=self.encrypt_me(refresh_jwt),
            access_token_expired=now + access_ttl,
            refresh_token_expired=now + refresh_ttl,
        )

    def verify_access_token(self, encrypted_token: str) -> dict[str, Any]:
        plain = self.decrypt_me(encrypted_token)
        return jwt.decode(
            plain,
            self.settings.jwt_secret,
            algorithms=[self.settings.jwt_algorithm],
        )

    def verify_refresh_token(self, encrypted_token: str) -> dict[str, Any]:
        plain = self.decrypt_me(encrypted_token)
        return jwt.decode(
            plain,
            self.settings.refresh_token_key,
            algorithms=[self.settings.jwt_algorithm],
        )


def generate_session_refresh_token() -> str:
    """
    Opaque 64-char hex token for user_sessions.refresh_token.

    Example schema value:
    "67a41ac058dc8353ebad7c5f0ffb6ac2b49b9a3cb346aadc29170f8e989f1ab3"
    """
    return secrets.token_hex(32)
