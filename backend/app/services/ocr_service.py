from pathlib import Path

import newrelic.agent
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


@newrelic.agent.function_trace(name="OCR: Run Tesseract", group="Custom")
def run_ocr(image_path: Path, language: str = "tel") -> dict:
    newrelic.agent.add_custom_attribute("language", language)
    newrelic.agent.add_custom_attribute("page_filename", image_path.name)
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    img = Image.open(str(image_path))

    tesseract_lang = _get_tesseract_lang(language)

    config = f"--psm 6 --oem 1 --dpi {settings.ocr_render_dpi}"

    data = pytesseract.image_to_data(
        img,
        lang=tesseract_lang,
        output_type=pytesseract.Output.DICT,
        config=config,
    )

    words = []
    text_parts = []
    confidence_sum = 0.0
    confidence_count = 0

    n_entries = len(data["text"])
    for i in range(n_entries):
        text = data["text"][i].strip()
        conf_str = str(data["conf"][i]).strip()
        if conf_str in ("", "-1") or not conf_str.lstrip("-").isdigit():
            continue
        conf = int(conf_str)

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
