"""Unit tests for the at-rest secret encryption helper."""

from __future__ import annotations

import pytest

from app.core import secret_box
from app.core.config import settings


def test_encrypt_decrypt_round_trip() -> None:
    plaintext = "s3cr3t-smtp-password"
    ciphertext = secret_box.encrypt(plaintext)
    assert ciphertext != plaintext
    assert secret_box.decrypt(ciphertext) == plaintext


def test_empty_password_round_trips_to_empty() -> None:
    assert secret_box.encrypt("") == ""
    assert secret_box.decrypt("") == ""
    assert secret_box.decrypt(None) == ""


def test_decrypt_of_garbage_raises() -> None:
    with pytest.raises(secret_box.SecretBoxError):
        secret_box.decrypt("not-a-valid-fernet-token")


def test_wrong_key_cannot_decrypt(monkeypatch) -> None:
    ciphertext = secret_box.encrypt("top-secret")
    monkeypatch.setattr(settings, "encryption_secret", "a-different-secret")
    with pytest.raises(secret_box.SecretBoxError):
        secret_box.decrypt(ciphertext)