from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.core.config import settings
from app.services import ocr_line_model


class _FakeModel:
    def __init__(self, texts):
        self.texts = texts
        self.calls: list[tuple[int, str]] = []

    def transcribe(self, crops, tokenizer, decode="ctc"):
        self.calls.append((len(crops), decode))
        return self.texts


def _image() -> Image.Image:
    return Image.new("RGB", (100, 60), "white")


def test_resolve_model_name_uses_fallback_when_finetune_missing(monkeypatch, tmp_path):
    fallback = tmp_path / "base"
    fallback.mkdir()
    monkeypatch.setattr(settings, "ocr_line_model_name", str(tmp_path / "missing"))
    monkeypatch.setattr(settings, "ocr_line_model_fallback_name", str(fallback))

    assert ocr_line_model._resolve_model_name() == str(fallback)


def test_resolve_model_name_keeps_present_finetune(monkeypatch, tmp_path):
    finetuned = tmp_path / "finetuned"
    finetuned.mkdir()
    monkeypatch.setattr(settings, "ocr_line_model_name", str(finetuned))
    monkeypatch.setattr(settings, "ocr_line_model_fallback_name", str(tmp_path / "base"))

    assert ocr_line_model._resolve_model_name() == str(finetuned)


def test_run_line_ocr_contract(monkeypatch):
    boxes = [
        {"bbox": {"x": 1, "y": 2, "w": 30, "h": 10}, "block_num": 1, "line_num": 1},
        {"bbox": {"x": 1, "y": 20, "w": 40, "h": 10}, "block_num": 1, "line_num": 2},
    ]
    fake = _FakeModel(["  first   line ", "second line"])
    monkeypatch.setattr(ocr_line_model, "_line_boxes", lambda img: boxes)
    monkeypatch.setattr(ocr_line_model, "_load_model", lambda: (fake, object()))
    monkeypatch.setattr(settings, "ocr_line_model_confidence", 42.0)
    monkeypatch.setattr(settings, "ocr_line_model_decode", "ctc")

    result = ocr_line_model.run_line_ocr(_image(), Path("/fake/page.png"), "tel")

    assert result["engine"] == "line_model"
    assert result["full_text"] == "first line second line"
    assert result["word_count"] == 2
    assert result["avg_confidence"] == 42.0
    assert result["psm"] == 6
    assert result["psm_label"] == "line_model"
    assert result["words"][0]["bbox"] == boxes[0]["bbox"]
    assert result["words"][0]["confidence"] == 42.0
    assert result["words"][0]["block_num"] == 1
    assert result["words"][0]["word_num"] == 0
    assert fake.calls == [(2, "ctc")]


class _ConfiguredFakeModel(_FakeModel):
    class config:
        image_height = 64
        max_image_width = 256

    def __init__(self):
        super().__init__([])
        self.sizes: list[tuple[int, int]] = []

    def transcribe(self, crops, tokenizer, decode="ctc"):
        self.calls.append((len(crops), decode))
        self.sizes = [crop.size for crop in crops]
        return [f"piece{i}" for i in range(len(crops))]


def test_run_line_ocr_splits_over_wide_crops(monkeypatch):
    # 20 px tall -> 80 px max width at image_height=64/max_image_width=256.
    boxes = [{"bbox": {"x": 0, "y": 0, "w": 1200, "h": 20}, "block_num": 1, "line_num": 1}]
    fake = _ConfiguredFakeModel()
    monkeypatch.setattr(ocr_line_model, "_line_boxes", lambda img: boxes)
    monkeypatch.setattr(ocr_line_model, "_load_model", lambda: (fake, object()))
    monkeypatch.setattr(settings, "ocr_line_model_decode", "ctc")

    result = ocr_line_model.run_line_ocr(Image.new("RGB", (1200, 40), "white"), Path("/fake/page.png"), "tel")

    assert len(fake.sizes) > 1
    assert all(width <= 80 for width, _ in fake.sizes)
    assert all(height == 20 for _, height in fake.sizes)
    assert result["word_count"] == 1
    assert result["words"][0]["text"].startswith("piece0")
    assert result["words"][0]["text"].endswith(f"piece{len(fake.sizes) - 1}")


def test_run_line_ocr_keeps_fitting_crops_whole(monkeypatch):
    boxes = [{"bbox": {"x": 0, "y": 0, "w": 30, "h": 10}, "block_num": 1, "line_num": 1}]
    fake = _ConfiguredFakeModel()
    monkeypatch.setattr(ocr_line_model, "_line_boxes", lambda img: boxes)
    monkeypatch.setattr(ocr_line_model, "_load_model", lambda: (fake, object()))

    result = ocr_line_model.run_line_ocr(_image(), Path("/fake/page.png"), "tel")

    assert fake.sizes == [(30, 10)]
    assert result["full_text"] == "piece0"


def test_run_line_ocr_empty_page(monkeypatch):
    monkeypatch.setattr(ocr_line_model, "_line_boxes", lambda img: [])
    monkeypatch.setattr(ocr_line_model, "_load_model", lambda: (_FakeModel([]), object()))

    result = ocr_line_model.run_line_ocr(_image(), Path("/fake/page.png"), "tel")

    assert result["words"] == []
    assert result["full_text"] == ""
    assert result["avg_confidence"] == 0.0


def test_run_line_ocr_drops_blank_lines(monkeypatch):
    boxes = [
        {"bbox": {"x": 1, "y": 2, "w": 30, "h": 10}, "block_num": 1, "line_num": 1},
        {"bbox": {"x": 1, "y": 20, "w": 40, "h": 10}, "block_num": 1, "line_num": 2},
    ]
    monkeypatch.setattr(ocr_line_model, "_line_boxes", lambda img: boxes)
    monkeypatch.setattr(ocr_line_model, "_load_model", lambda: (_FakeModel(["   ", "kept"]), object()))

    result = ocr_line_model.run_line_ocr(_image(), Path("/fake/page.png"), "tel")

    assert result["word_count"] == 1
    assert result["detected_lines"] == 2
    assert result["empty_lines"] == 1
    assert result["words"][0]["text"] == "kept"
    assert result["words"][0]["bbox"] == boxes[1]["bbox"]


def test_run_line_ocr_raises_when_all_detected_lines_are_empty(monkeypatch):
    boxes = [
        {"bbox": {"x": 1, "y": 2, "w": 30, "h": 10}, "block_num": 1, "line_num": 1},
        {"bbox": {"x": 1, "y": 20, "w": 40, "h": 10}, "block_num": 1, "line_num": 2},
    ]
    monkeypatch.setattr(ocr_line_model, "_line_boxes", lambda img: boxes)
    monkeypatch.setattr(ocr_line_model, "_load_model", lambda: (_FakeModel(["", "   "]), object()))

    with pytest.raises(ocr_line_model.LineModelEmptyOutput):
        ocr_line_model.run_line_ocr(_image(), Path("/fake/page.png"), "tel")


def test_line_boxes_group_and_order(monkeypatch):
    data = {
        "text": ["second", "part", "first"],
        "block_num": [1, 1, 1],
        "par_num": [1, 1, 1],
        "line_num": [2, 2, 1],
        "left": [5, 20, 5],
        "top": [30, 30, 10],
        "width": [10, 15, 30],
        "height": [8, 8, 8],
    }
    monkeypatch.setattr(ocr_line_model.pytesseract, "image_to_data", lambda *args, **kwargs: data)

    boxes = ocr_line_model._line_boxes(_image())

    assert [box["line_num"] for box in boxes] == [1, 2]
    assert boxes[0]["bbox"] == {"x": 5, "y": 10, "w": 30, "h": 8}
    assert boxes[1]["bbox"] == {"x": 5, "y": 30, "w": 30, "h": 8}
