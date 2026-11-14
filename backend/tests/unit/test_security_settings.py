"""Production-start security checks."""

from __future__ import annotations

import logging

import pytest

from app.core.config import settings
from app.main import _validate_security_settings


def test_short_jwt_secret_is_refused_outside_debug(monkeypatch):
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "jwt_secret_key", "too-short")

    with pytest.raises(RuntimeError, match="32"):
        _validate_security_settings()


def test_short_jwt_secret_is_allowed_in_debug(monkeypatch):
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "jwt_secret_key", "too-short")
    monkeypatch.setattr(settings, "cors_origins", "http://localhost:3000")

    _validate_security_settings()


def test_wildcard_cors_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "jwt_secret_key", "x" * 64)
    monkeypatch.setattr(settings, "cors_origins", "*")

    with caplog.at_level(logging.WARNING):
        _validate_security_settings()

    assert any("CORS_ORIGINS" in record.message for record in caplog.records)