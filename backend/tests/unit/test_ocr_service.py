from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from app.services.ocr_service import (
    LANGUAGE_MAP,
    _get_tesseract_lang,
    detect_language,
    run_ocr,
)


class TestGetTesseractLang:
    def test_telugu(self):
        assert _get_tesseract_lang("tel") == "tel+eng"

    def test_hindi(self):
        assert _get_tesseract_lang("hin") == "hin+eng"

    def test_unknown_passthrough(self):
        assert _get_tesseract_lang("tam") == "tam"

    def test_language_map_contents(self):
        assert "tel" in LANGUAGE_MAP
        assert "hin" in LANGUAGE_MAP


def _mock_tesseract_data(words):
    n = len(words)
    data = {
        "text": [w["text"] for w in words],
        "conf": [str(w["conf"]) for w in words],
        "left": [w.get("left", 10) for w in words],
        "top": [w.get("top", 20) for w in words],
        "width": [w.get("width", 50) for w in words],
        "height": [w.get("height", 15) for w in words],
        "block_num": [w.get("block_num", 1) for w in words],
        "line_num": [w.get("line_num", 1) for w in words],
        "word_num": [w.get("word_num", i + 1) for i, w in enumerate(words)],
    }
    return data


class TestRunOcr:
    @patch("app.services.ocr_service.pytesseract")
    @patch("app.services.ocr_service.Image")
    def test_structure(self, mock_image_cls, mock_pyt):
        mock_img = MagicMock()
        mock_image_cls.open.return_value = mock_img

        mock_pyt.Output.DICT = "dict"
        mock_pyt.image_to_data.return_value = _mock_tesseract_data([
            {"text": "Hello", "conf": 95},
            {"text": "World", "conf": 88},
        ])

        result = run_ocr(Path("/fake/image.png"), "tel")

        assert "words" in result
        assert "full_text" in result
        assert "avg_confidence" in result
        assert "word_count" in result
        assert result["word_count"] == 2
        assert "Hello" in result["full_text"]
        assert "World" in result["full_text"]

    @patch("app.services.ocr_service.pytesseract")
    @patch("app.services.ocr_service.Image")
    def test_filters_empty_and_negative_conf(self, mock_image_cls, mock_pyt):
        mock_img = MagicMock()
        mock_image_cls.open.return_value = mock_img

        mock_pyt.Output.DICT = "dict"
        mock_pyt.image_to_data.return_value = _mock_tesseract_data([
            {"text": "Keep", "conf": 90},
            {"text": "", "conf": 80},
            {"text": "Also", "conf": -1},
            {"text": "  ", "conf": 70},
        ])

        result = run_ocr(Path("/fake/image.png"), "tel")
        assert result["word_count"] == 1
        assert result["full_text"] == "Keep"

    @patch("app.services.ocr_service.pytesseract")
    @patch("app.services.ocr_service.Image")
    def test_avg_confidence(self, mock_image_cls, mock_pyt):
        mock_img = MagicMock()
        mock_image_cls.open.return_value = mock_img

        mock_pyt.Output.DICT = "dict"
        mock_pyt.image_to_data.return_value = _mock_tesseract_data([
            {"text": "A", "conf": 80},
            {"text": "B", "conf": 100},
        ])

        result = run_ocr(Path("/fake/image.png"), "tel")
        assert result["avg_confidence"] == 90.0

    @patch("app.services.ocr_service.pytesseract")
    @patch("app.services.ocr_service.Image")
    def test_no_words(self, mock_image_cls, mock_pyt):
        mock_img = MagicMock()
        mock_image_cls.open.return_value = mock_img

        mock_pyt.Output.DICT = "dict"
        mock_pyt.image_to_data.return_value = _mock_tesseract_data([
            {"text": "", "conf": -1},
        ])

        result = run_ocr(Path("/fake/image.png"), "tel")
        assert result["word_count"] == 0
        assert result["avg_confidence"] == 0.0
        assert result["full_text"] == ""

    @patch("app.services.ocr_service.pytesseract")
    @patch("app.services.ocr_service.Image")
    def test_bounding_box_structure(self, mock_image_cls, mock_pyt):
        mock_img = MagicMock()
        mock_image_cls.open.return_value = mock_img

        mock_pyt.Output.DICT = "dict"
        mock_pyt.image_to_data.return_value = _mock_tesseract_data([
            {"text": "Word", "conf": 90, "left": 10, "top": 20, "width": 50, "height": 15, "block_num": 1, "line_num": 1},
        ])

        result = run_ocr(Path("/fake/image.png"), "tel")
        word = result["words"][0]
        assert "bbox" in word
        assert word["bbox"]["x"] == 10
        assert word["bbox"]["y"] == 20
        assert word["bbox"]["w"] == 50
        assert word["bbox"]["h"] == 15


class TestDetectLanguage:
    @patch("app.services.ocr_service.pytesseract")
    @patch("app.services.ocr_service.Image")
    def test_returns_higher_confidence_lang(self, mock_image_cls, mock_pyt):
        mock_img = MagicMock()
        mock_image_cls.open.return_value = mock_img

        call_count = [0]
        confidences = {"tel": [95, 85, 90], "hin": [50, 40, 60]}

        def fake_ocr(img, lang, output_type, config):
            lang_code = lang.split("+")[0]
            call_count[0] += 1
            confs = confidences.get(lang_code, [0])
            return {
                "text": ["w"] * len(confs),
                "conf": [str(c) for c in confs],
            }

        mock_pyt.Output.DICT = "dict"
        mock_pyt.image_to_data.side_effect = fake_ocr

        result = detect_language(Path("/fake/image.png"))
        assert result == "tel"

    @patch("app.services.ocr_service.pytesseract")
    @patch("app.services.ocr_service.Image")
    def test_handles_exception(self, mock_image_cls, mock_pyt):
        mock_img = MagicMock()
        mock_image_cls.open.return_value = mock_img

        mock_pyt.Output.DICT = "dict"

        def fake_ocr(img, lang, output_type, config):
            lang_code = lang.split("+")[0]
            if lang_code == "tel":
                return {"text": ["w"], "conf": ["90"]}
            raise RuntimeError("OCR failed")

        mock_pyt.image_to_data.side_effect = fake_ocr

        result = detect_language(Path("/fake/image.png"))
        assert result == "tel"
