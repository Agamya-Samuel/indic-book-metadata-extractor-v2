from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.core.config import settings
from app.services import ocr_service


def _page(tmp_path: Path) -> Path:
    path = tmp_path / "page.png"
    Image.new("RGB", (10, 10), "white").save(path)
    return path


def test_telugu_uses_line_model_when_enabled(monkeypatch, tmp_path):
    image = _page(tmp_path)
    monkeypatch.setattr(settings, "ocr_tel_engine", "line_model")
    sentinel = {"engine": "line_model", "words": [], "full_text": ""}

    with (
        patch.object(ocr_service.ocr_line_model, "run_line_ocr", return_value=sentinel) as line_model,
        patch.object(ocr_service, "_run_ocr_with_img") as tesseract,
    ):
        result = ocr_service.run_ocr(image, "tel")

    assert result == sentinel
    line_model.assert_called_once()
    tesseract.assert_not_called()


def test_hindi_never_uses_line_model(monkeypatch, tmp_path):
    image = _page(tmp_path)
    monkeypatch.setattr(settings, "ocr_tel_engine", "line_model")
    sentinel = {"engine": "tesseract", "words": [], "full_text": ""}

    with (
        patch.object(ocr_service.ocr_line_model, "run_line_ocr") as line_model,
        patch.object(ocr_service, "_run_ocr_with_img", return_value=sentinel) as tesseract,
    ):
        result = ocr_service.run_ocr(image, "hin")

    assert result["engine"] == "tesseract"
    line_model.assert_not_called()
    tesseract.assert_called_once()


def test_default_engine_is_tesseract(monkeypatch, tmp_path):
    image = _page(tmp_path)
    monkeypatch.setattr(settings, "ocr_tel_engine", "tesseract")
    sentinel = {"engine": "tesseract", "words": [], "full_text": ""}

    with (
        patch.object(ocr_service.ocr_line_model, "run_line_ocr") as line_model,
        patch.object(ocr_service, "_run_ocr_with_img", return_value=sentinel) as tesseract,
    ):
        ocr_service.run_ocr(image, "tel")

    line_model.assert_not_called()
    tesseract.assert_called_once()


def test_line_model_failure_falls_back_to_tesseract(monkeypatch, tmp_path):
    image = _page(tmp_path)
    monkeypatch.setattr(settings, "ocr_tel_engine", "line_model")
    sentinel = {"engine": "tesseract", "words": [], "full_text": ""}

    with (
        patch.object(ocr_service.ocr_line_model, "run_line_ocr", side_effect=RuntimeError("weights missing")),
        patch.object(ocr_service, "_run_ocr_with_img", return_value=sentinel) as tesseract,
    ):
        result = ocr_service.run_ocr(image, "tel")

    assert result["engine"] == "tesseract"
    assert "RuntimeError: weights missing" in result["engine_fallback_reason"]
    tesseract.assert_called_once()
