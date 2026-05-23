from pathlib import Path

import pytesseract
from PIL import Image

from app.core.config import settings

LANGUAGE_MAP = {
    "tel": "tel+eng",
    "hin": "hin+eng",
    "eng": "eng",
}


def _get_tesseract_lang(language: str) -> str:
    return LANGUAGE_MAP.get(language, language)


def run_ocr(image_path: Path, language: str = "tel") -> dict:
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    img = Image.open(str(image_path))

    tesseract_lang = _get_tesseract_lang(language)

    data = pytesseract.image_to_data(
        img,
        lang=tesseract_lang,
        output_type=pytesseract.Output.DICT,
        config="--psm 6 --oem 3",
    )

    words = []
    text_parts = []
    confidence_sum = 0.0
    confidence_count = 0

    n_entries = len(data["text"])
    for i in range(n_entries):
        text = data["text"][i].strip()
        conf = int(data["conf"][i])

        if conf < 0 or not text:
            continue

        word_entry = {
            "text": text,
            "confidence": conf,
            "bbox": {
                "x": data["left"][i],
                "y": data["top"][i],
                "w": data["width"][i],
                "h": data["height"][i],
            },
            "block_num": data["block_num"][i],
            "line_num": data["line_num"][i],
            "word_num": data["word_num"][i],
        }
        words.append(word_entry)
        text_parts.append(text)
        confidence_sum += conf
        confidence_count += 1

    avg_confidence = round(confidence_sum / confidence_count, 1) if confidence_count > 0 else 0.0
    full_text = " ".join(text_parts)

    return {
        "words": words,
        "full_text": full_text,
        "avg_confidence": avg_confidence,
        "word_count": len(words),
    }


def detect_language(image_path: Path) -> str:
    candidates = {"tel": 0.0, "hin": 0.0}

    for lang in candidates:
        try:
            tesseract_lang = _get_tesseract_lang(lang)
            data = pytesseract.image_to_data(
                Image.open(str(image_path)),
                lang=tesseract_lang,
                output_type=pytesseract.Output.DICT,
                config="--psm 6 --oem 3",
            )
            confs = [int(c) for c in data["conf"] if int(c) >= 0]
            candidates[lang] = sum(confs) / len(confs) if confs else 0.0
        except Exception:
            candidates[lang] = 0.0

    return max(candidates, key=candidates.get)
