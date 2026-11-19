"""Symmetric encryption for secrets stored at rest (e.g. the SMTP password).

The key is derived from ``ENCRYPTION_SECRET`` (falling back to the JWT secret)
via SHA-256, so a single configured secret can protect both. Ciphertext is
Fernet (AES-128-CBC + HMAC), URL-safe, and self-authenticating.

This is a thin wrapper: callers store only the ciphertext and never the
plaintext. Decryption failures raise ``SecretBoxError`` so callers can decide
how to surface them without leaking details.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class SecretBoxError(Exception):
    """Encryption/decryption could not be completed."""


def _fernet() -> Fernet:
    secret = settings.encryption_secret or settings.jwt_secret_key
    if not secret:
        raise SecretBoxError("No encryption secret configured")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    if plaintext == "":
        return ""
    try:
        return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")
    except SecretBoxError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SecretBoxError("Failed to encrypt secret") from exc


def decrypt(ciphertext: str | None) -> str:
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretBoxError("Secret cannot be decrypted (wrong key or corrupt data)") from exc
    except SecretBoxError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SecretBoxError("Failed to decrypt secret") from exc