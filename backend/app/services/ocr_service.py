from pathlib import Path

import newrelic.agent
import pytesseract
from PIL import Image

from app.core.config import settings
from app.services.page_classifier import (
    Classification,
    PSM,
    classify_page,
    psm_to_tesseract_arg,
)

LANGUAGE_MAP = {
    "tel": "tel+eng",
    "hin": "hin+eng",
    "eng": "eng",
}


def _get_tesseract_lang(language: str) -> str:
    return LANGUAGE_MAP.get(language, language)


def _classify_psm(image_path: Path, page_position: int | None = None) -> Classification:
    """Pick a Tesseract PSM based on the page image and (optionally) its
    position in the book.

    The title page (position 0) gets a separate fast rotation pass via
    --psm 1, then we re-classify on the corrected image. Other pages
    use the lightweight classifier.
    """
    try:
        return classify_page(str(image_path))
    except Exception:
        # On classifier failure, fall back to the previous safe default.
        return Classification(psm=PSM.UNIFORM_BLOCK, label="classifier_failed")


@newrelic.agent.function_trace(name="OCR: Run Tesseract", group="Custom")
def run_ocr(image_path: Path, language: str = "tel", page_position: int | None = None) -> dict:
    newrelic.agent.add_custom_attribute("language", language)
    newrelic.agent.add_custom_attribute("page_filename", image_path.name)
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    img = Image.open(str(image_path))

    tesseract_lang = _get_tesseract_lang(language)

    classification = _classify_psm(image_path, page_position=page_position)
    psm = psm_to_tesseract_arg(classification.psm)

    config = f"--psm {psm} --oem 1 --dpi {settings.ocr_render_dpi}"

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
        "psm": psm,
        "psm_label": classification.label,
    }
