"""Telugu line OCR using ``harsha-desaraju/telugu-ocr-model``.

Tesseract leaves ~40 % of Telugu characters wrong (median CER 0.40); this line
model measures ~0.16 and is the locked Telugu engine (learnings/020, 021). The
model is loaded lazily and only when ``OCR_TEL_ENGINE=line_model``; Hindi and
English never reach this module. Weights are vendored into the image or a
mounted volume — this module never downloads at runtime.

The model emits no word-level confidences. Each detected line is stored as one
``word`` entry with the line box and a conservative confidence so the review
canvas keeps working without claiming a certainty the engine does not provide.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import pytesseract
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

_load_lock = threading.Lock()
_model = None
_tokenizer = None


def _load_model():
    """Load the model once per process (Celery concurrency is 1)."""
    global _model, _tokenizer
    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer

    with _load_lock:
        if _model is None or _tokenizer is None:
            from transformers import AutoModel, AutoTokenizer

            logger.info("Loading Telugu line OCR model '%s'", settings.ocr_line_model_name)
            tokenizer = AutoTokenizer.from_pretrained(
                settings.ocr_line_model_name,
                trust_remote_code=True,
            )
            model = AutoModel.from_pretrained(
                settings.ocr_line_model_name,
                trust_remote_code=True,
            ).eval()
            _tokenizer = tokenizer
            _model = model

    return _model, _tokenizer


def _line_boxes(img: Image.Image) -> list[dict]:
    """Detect line boxes with Tesseract and order them top-to-bottom."""
    data = pytesseract.image_to_data(
        img,
        lang="tel",
        output_type=pytesseract.Output.DICT,
        config="--psm 6",
    )

    groups: dict[tuple[int, int, int], dict] = {}
    for i in range(len(data["text"])):
        if not str(data["text"][i]).strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        x = data["left"][i]
        y = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]
        box = groups.setdefault(
            key,
            {"x": x, "y": y, "right": x + w, "bottom": y + h},
        )
        box["x"] = min(box["x"], x)
        box["y"] = min(box["y"], y)
        box["right"] = max(box["right"], x + w)
        box["bottom"] = max(box["bottom"], y + h)

    ordered = sorted(groups.items(), key=lambda item: (item[1]["y"], item[1]["x"]))
    return [
        {
            "bbox": {
                "x": box["x"],
                "y": box["y"],
                "w": box["right"] - box["x"],
                "h": box["bottom"] - box["y"],
            },
            "block_num": key[0],
            "line_num": key[2],
        }
        for key, box in ordered
        if box["right"] > box["x"] and box["bottom"] > box["y"]
    ]


def run_line_ocr(
    img: Image.Image,
    image_path: Path,
    language: str = "tel",
    page_position: int | None = None,
) -> dict:
    """Run the Telugu line model and return the same contract as ``run_ocr``.

    ``image_path`` and ``page_position`` are accepted for parity with
    ``ocr_service.run_ocr``; the model works on the in-memory image.
    """
    model, tokenizer = _load_model()
    lines = _line_boxes(img)
    crops = [
        img.crop(
            (
                line["bbox"]["x"],
                line["bbox"]["y"],
                line["bbox"]["x"] + line["bbox"]["w"],
                line["bbox"]["y"] + line["bbox"]["h"],
            )
        )
        for line in lines
    ]

    texts: list[str] = []
    if crops:
        texts = model.transcribe(crops, tokenizer, decode=settings.ocr_line_model_decode)

    confidence = float(settings.ocr_line_model_confidence)
    words: list[dict] = []
    for line, text in zip(lines, texts):
        normalized = " ".join(str(text).split())
        if not normalized:
            continue
        words.append(
            {
                "text": normalized,
                "confidence": confidence,
                "bbox": line["bbox"],
                "block_num": line["block_num"],
                "line_num": line["line_num"],
                "word_num": 0,
            }
        )

    return {
        "words": words,
        "full_text": " ".join(word["text"] for word in words),
        "avg_confidence": confidence if words else 0.0,
        "word_count": len(words),
        "psm": 6,
        "psm_label": "line_model",
        "engine": "line_model",
    }
