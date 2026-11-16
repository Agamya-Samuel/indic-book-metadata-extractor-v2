from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


from app.core.config import settings
from app.services.ocr_service import (
    LANGUAGE_MAP,
    _build_config,
    _get_tesseract_lang,
    _reroute_dominant_script_page,
    _reroute_latin_page,
    _script_shares,
    run_ocr,
)


class TestGetTesseractLang:
    def test_telugu(self):
        assert _get_tesseract_lang("tel") == "tel+eng"

    def test_hindi(self):
        assert _get_tesseract_lang("hin") == "hin+eng"

    def test_unknown_passthrough(self):
        assert _get_tesseract_lang("xyz_unknown") == "xyz_unknown"

    def test_language_map_contents(self):
        assert "tel" in LANGUAGE_MAP
        assert "hin" in LANGUAGE_MAP
        assert "eng" in LANGUAGE_MAP
        # Only 3 supported languages
        for code in ("tel", "hin", "eng"):
            assert code in LANGUAGE_MAP, f"missing language: {code}"
            # All non-eng codes pair with English
            if code != "eng":
                assert "eng" in LANGUAGE_MAP[code]


class TestBuildConfig:
    def test_includes_tessdata_dir(self, monkeypatch):
        monkeypatch.setattr(settings, "tesseract_tessdata_dir", "/tmp/custom tessdata")

        config = _build_config(3, "tel")

        assert '--tessdata-dir "/tmp/custom tessdata"' in config
        assert "--psm 3" in config

    def test_omits_tessdata_dir_when_unset(self, monkeypatch):
        monkeypatch.setattr(settings, "tesseract_tessdata_dir", "")

        config = _build_config(3, "tel")

        assert "--tessdata-dir" not in config


class TestScriptRouting:
    def test_script_shares(self):
        assert _script_shares("Hello world")["latin"] == 1.0
        assert _script_shares("నమస్తే")["telugu"] == 1.0
        assert _script_shares("नमस्ते")["devanagari"] == 1.0
        assert _script_shares("") == {"latin": 0.0, "telugu": 0.0, "devanagari": 0.0}

    @patch("app.services.ocr_service.Image")
    @patch("app.services.ocr_service._run_ocr_with_img")
    def test_latin_line_output_reroutes_to_tesseract(self, mock_tesseract, mock_image_cls):
        mock_image_cls.open.return_value = MagicMock()
        mock_tesseract.return_value = {
            "engine": "tesseract",
            "words": [],
            "full_text": "This is a longer English copyright page with enough text.",
        }
        data = {
            "engine": "line_model",
            "words": [],
            "full_text": "short English cover",
        }

        result = _reroute_latin_page(data, Path("/fake/page.png"), "tel", 0)

        assert result["engine"] == "tesseract"
        assert result["route_reason"] == "latin_page_reroute"
        mock_tesseract.assert_called_once()

    @patch("app.services.ocr_service.Image")
    @patch("app.services.ocr_service._run_ocr_with_img")
    def test_telugu_line_output_is_not_rerouted(self, mock_tesseract, mock_image_cls):
        data = {"engine": "line_model", "words": [], "full_text": "నమస్తే ప్రపంచం"}

        result = _reroute_latin_page(data, Path("/fake/page.png"), "tel", 0)

        assert result is data
        mock_tesseract.assert_not_called()
        mock_image_cls.open.assert_not_called()

    @patch("app.services.ocr_service.Image")
    @patch("app.services.ocr_service._run_ocr_with_img")
    def test_short_tesseract_result_is_discarded(self, mock_tesseract, mock_image_cls):
        mock_image_cls.open.return_value = MagicMock()
        mock_tesseract.return_value = {"engine": "tesseract", "words": [], "full_text": "tiny"}
        data = {
            "engine": "line_model",
            "words": [],
            "full_text": "A long English page returned by the line model.",
        }

        result = _reroute_latin_page(data, Path("/fake/page.png"), "tel", 0)

        assert result is data

    @patch("app.services.ocr_service.Image")
    @patch("app.services.ocr_service._run_ocr_with_img")
    def test_hindi_dominant_page_drops_eng(self, mock_tesseract, mock_image_cls):
        mock_image_cls.open.return_value = MagicMock()
        alt = {
            "engine": "tesseract",
            "tesseract_lang": "hin",
            "words": [],
            "full_text": "नमस्ते " * 20,
        }
        mock_tesseract.return_value = alt
        data = {
            "engine": "tesseract",
            "tesseract_lang": "hin+eng",
            "words": [],
            "full_text": "नमस्ते " * 20,
        }

        result = _reroute_dominant_script_page(data, Path("/fake/page.png"), "hin", 0)

        assert result["tesseract_lang"] == "hin"
        assert result["route_reason"] == "dominant_script_reroute"

    @patch("app.services.ocr_service.Image")
    @patch("app.services.ocr_service._run_ocr_with_img")
    def test_telugu_dominant_page_drops_eng(self, mock_tesseract, mock_image_cls):
        mock_image_cls.open.return_value = MagicMock()
        mock_tesseract.return_value = {
            "engine": "tesseract",
            "tesseract_lang": "tel",
            "words": [],
            "full_text": "నమస్తే " * 20,
        }
        data = {
            "engine": "tesseract",
            "tesseract_lang": "tel+eng",
            "words": [],
            "full_text": "నమస్తే " * 20,
        }

        result = _reroute_dominant_script_page(data, Path("/fake/page.png"), "tel", 0)

        assert result["tesseract_lang"] == "tel"
        assert result["route_reason"] == "dominant_script_reroute"

    @patch("app.services.ocr_service.Image")
    @patch("app.services.ocr_service._run_ocr_with_img")
    def test_latin_hindi_page_keeps_combined_model(self, mock_tesseract, mock_image_cls):
        data = {
            "engine": "tesseract",
            "tesseract_lang": "hin+eng",
            "words": [],
            "full_text": "Publisher: Rajkamal Prakashan, New Delhi",
        }

        result = _reroute_dominant_script_page(data, Path("/fake/page.png"), "hin", 0)

        assert result is data
        mock_tesseract.assert_not_called()

    @patch("app.services.ocr_service.Image")
    @patch("app.services.ocr_service._run_ocr_with_img")
    def test_routing_disabled(self, mock_tesseract, mock_image_cls, monkeypatch):
        monkeypatch.setattr(settings, "ocr_script_routing", False)
        data = {"engine": "line_model", "words": [], "full_text": "English cover"}

        result = _reroute_latin_page(data, Path("/fake/page.png"), "tel", 0)

        assert result is data
        mock_tesseract.assert_not_called()


def _mock_tesseract_data(words):
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
        mock_pyt.image_to_data.return_value = _mock_tesseract_data(
            [
                {"text": "Hello", "conf": 95},
                {"text": "World", "conf": 88},
            ]
        )

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
        mock_pyt.image_to_data.return_value = _mock_tesseract_data(
            [
                {"text": "Keep", "conf": 90},
                {"text": "", "conf": 80},
                {"text": "Also", "conf": -1},
                {"text": "  ", "conf": 70},
            ]
        )

        result = run_ocr(Path("/fake/image.png"), "tel")
        assert result["word_count"] == 1
        assert result["full_text"] == "Keep"

    @patch("app.services.ocr_service.pytesseract")
    @patch("app.services.ocr_service.Image")
    def test_avg_confidence(self, mock_image_cls, mock_pyt):
        mock_img = MagicMock()
        mock_image_cls.open.return_value = mock_img

        mock_pyt.Output.DICT = "dict"
        mock_pyt.image_to_data.return_value = _mock_tesseract_data(
            [
                {"text": "A", "conf": 80},
                {"text": "B", "conf": 100},
            ]
        )

        result = run_ocr(Path("/fake/image.png"), "tel")
        assert result["avg_confidence"] == 90.0

    @patch("app.services.ocr_service.pytesseract")
    @patch("app.services.ocr_service.Image")
    def test_no_words(self, mock_image_cls, mock_pyt):
        mock_img = MagicMock()
        mock_image_cls.open.return_value = mock_img

        mock_pyt.Output.DICT = "dict"
        mock_pyt.image_to_data.return_value = _mock_tesseract_data(
            [
                {"text": "", "conf": -1},
            ]
        )

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
        mock_pyt.image_to_data.return_value = _mock_tesseract_data(
            [
                {
                    "text": "Word",
                    "conf": 90,
                    "left": 10,
                    "top": 20,
                    "width": 50,
                    "height": 15,
                    "block_num": 1,
                    "line_num": 1,
                },
            ]
        )

        result = run_ocr(Path("/fake/image.png"), "tel")
        word = result["words"][0]
        assert "bbox" in word
        assert word["bbox"]["x"] == 10
        assert word["bbox"]["y"] == 20
        assert word["bbox"]["w"] == 50
        assert word["bbox"]["h"] == 15
