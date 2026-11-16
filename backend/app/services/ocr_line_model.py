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


class LineModelEmptyOutput(RuntimeError):
    """The line model detected lines but transcribed none of them.

    Raised instead of returning empty text, so ``run_ocr`` can fall back to
    Tesseract and record the reason. A genuinely blank page has no line boxes
    and does not raise.
    """


_load_lock = threading.Lock()
_model = None
_tokenizer = None


def _resolve_model_name() -> str:
    """Use the configured local model, or the baked fallback if it is absent.

    A fine-tuned checkpoint lives on the persistent storage volume. On a fresh
    host (or before the artifact is copied) that path may not exist yet; the
    image still contains the base checkpoint, so never fail into Tesseract when
    the fallback is available.
    """
    name = settings.ocr_line_model_name
    if not name.startswith("/") or Path(name).exists():
        return name
    fallback = settings.ocr_line_model_fallback_name
    if fallback and (not fallback.startswith("/") or Path(fallback).exists()):
        logger.warning("Model path %s is missing; falling back to %s", name, fallback)
        return fallback
    return name


def _load_model():
    """Load the model once per process (Celery concurrency is 1)."""
    global _model, _tokenizer
    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer

    with _load_lock:
        if _model is None or _tokenizer is None:
            from transformers import AutoModel, AutoTokenizer

            model_name = _resolve_model_name()
            logger.info("Loading Telugu line OCR model '%s'", model_name)
            tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True,
            )
            model = AutoModel.from_pretrained(
                model_name,
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


def _crop_width_limit(model, crop: Image.Image) -> int | None:
    """Maximum crop width the model can encode at this crop's height.

    The checkpoint scales a line to ``image_height`` and refuses lines wider
    than ``max_image_width`` after that scale (returning ``""``). The limit is
    therefore proportional to the crop's height: ``h * max_image_width /
    image_height``. Test doubles without a config return ``None`` and keep the
    old one-crop-per-line behavior.
    """
    config = getattr(model, "config", None)
    image_height = getattr(config, "image_height", None)
    max_image_width = getattr(config, "max_image_width", None)
    if not image_height or not max_image_width or crop.height <= 0:
        return None
    return int(crop.height * max_image_width / image_height)


def _split_crop(crop: Image.Image, limit: int, overlap: int = 16) -> list[Image.Image]:
    """Split an over-wide crop into overlapping pieces the model can encode."""
    width, height = crop.size
    if limit < 32 or width <= limit:
        return [crop]
    step = max(32, int(limit * 0.92))
    overlap = min(overlap, step - 1)
    pieces: list[Image.Image] = []
    x = 0
    while x < width:
        pieces.append(crop.crop((x, 0, min(width, x + step), height)))
        if x + step >= width:
            break
        x += step - overlap
    return pieces


def run_line_ocr(
    img: Image.Image,
    image_path: Path,
    language: str = "tel",
    page_position: int | None = None,
) -> dict:
    """Run the Telugu line model and return the same contract as ``run_ocr``.

    ``image_path`` and ``page_position`` are accepted for parity with
    ``ocr_service.run_ocr``; the model works on the in-memory image.

    Lines wider than the checkpoint's input limit are split into overlapping
    pieces instead of being silently dropped (the model returns ``""`` for
    them). This matters for wide front-matter/cover lines; normal body lines
    are under the limit and keep the one-crop-per-line path.
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

    pieces: list[Image.Image] = []
    owners: list[int] = []
    for line_idx, crop in enumerate(crops):
        limit = _crop_width_limit(model, crop)
        parts = _split_crop(crop, limit) if limit is not None else [crop]
        if len(parts) > 1:
            logger.debug(
                "Splitting over-wide line %s crop (%dx%d) into %d pieces",
                line_idx,
                crop.width,
                crop.height,
                len(parts),
            )
        pieces.extend(parts)
        owners.extend([line_idx] * len(parts))

    texts: list[str] = []
    if pieces:
        piece_texts = model.transcribe(pieces, tokenizer, decode=settings.ocr_line_model_decode)
        grouped: list[list[str]] = [[] for _ in crops]
        for owner, text in zip(owners, piece_texts):
            normalized = " ".join(str(text).split())
            if normalized:
                grouped[owner].append(normalized)
        texts = [" ".join(parts) for parts in grouped]

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

    if lines and not words:
        raise LineModelEmptyOutput(
            f"line model transcribed none of {len(lines)} detected lines"
        )

    return {
        "words": words,
        "full_text": " ".join(word["text"] for word in words),
        "avg_confidence": confidence if words else 0.0,
        "word_count": len(words),
        "detected_lines": len(lines),
        "empty_lines": len(lines) - len(words),
        "psm": 6,
        "psm_label": "line_model",
        "engine": "line_model",
    }
