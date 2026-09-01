from pathlib import Path

import newrelic.agent
import pytesseract
from PIL import Image

from app.core.config import settings
from app.services.ocr_dictionaries import get_dictionary_paths
from app.services.page_classifier import (
    Classification,
    PSM,
    classify_page,
    psm_to_tesseract_arg,
)

LANGUAGE_MAP = {
    # Telugu + English (bilingual colonial-era pages)
    "tel": "tel+eng",
    # Hindi (Devanagari) + English
    "hin": "hin+eng",
    # English only
    "eng": "eng",
}


def _get_tesseract_lang(language: str) -> str:
    return LANGUAGE_MAP.get(language, language)


def _is_dictionary_enabled(language: str) -> bool:
    """Check whether dictionary constraints are enabled for this language.

    Configured via ``OCR_USE_DICTIONARY`` env var (comma-separated language codes).
    """
    if not settings.ocr_use_dictionary:
        return False
    enabled = {lang.strip() for lang in settings.ocr_use_dictionary.split(",") if lang.strip()}
    return language in enabled


def _classify_psm(image_path: Path, page_position: int | None = None) -> Classification:
    """Pick a Tesseract PSM based on the page image and (optionally) its
    position in the book.

    The title page (position 0) gets a separate fast rotation pass via
    --psm 1, then we re-classify on the corrected image. Other pages
    use the lightweight classifier.
    """
    try:
        return classify_page(str(image_path))
    except (OSError, ValueError):
        # Classifier failures are I/O / parse issues; surface programming
        # errors instead of silently swallowing them.
        return Classification(psm=PSM.UNIFORM_BLOCK, label="classifier_failed")


def _build_config(psm: int, language: str) -> str:
    """Compose the Tesseract command-line config string.

    Includes --psm, --oem, --dpi, and --user-words/--user-patterns if a
    dictionary is enabled for the active language (set via OCR_USE_DICTIONARY).
    """
    parts = [f"--psm {psm}", f"--oem {settings.tesseract_oem}", f"--dpi {settings.ocr_render_dpi}"]
    words_path, patterns_path = get_dictionary_paths(language)
    if settings.ocr_use_dictionary and words_path and patterns_path:
        parts.append(f'--user-words "{words_path}"')
        parts.append(f'--user-patterns "{patterns_path}"')
    return " ".join(parts)


@newrelic.agent.function_trace(name="OCR: Run Tesseract", group="Custom")
def run_ocr(image_path: Path, language: str = "tel", page_position: int | None = None) -> dict:
    newrelic.agent.add_custom_attribute("language", language)
    newrelic.agent.add_custom_attribute("page_filename", image_path.name)
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    if settings.tesseract_tessdata_dir:
        pytesseract.pytesseract.tessdata_dir = settings.tesseract_tessdata_dir

    # Context manager releases the OS file handle promptly. Otherwise
    # under concurrent OCR the descriptor table fills up over the
    # lifetime of the worker.
    with Image.open(str(image_path)) as img:
        return _run_ocr_with_img(img, image_path, language, page_position)


def _run_ocr_with_img(
    img,
    image_path: Path,
    language: str,
    page_position: int | None = None,
) -> dict:
    tesseract_lang = _get_tesseract_lang(language)

    classification = _classify_psm(image_path, page_position=page_position)
    psm = psm_to_tesseract_arg(classification.psm)

    config = _build_config(psm, language)

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


def retry_low_confidence_words(
    image_path: Path,
    words: list[dict],
    language: str,
    threshold: int | None = None,
) -> list[dict]:
    """Re-OCR each low-confidence word with --psm 8 (single word) and keep the
    higher-confidence result. Run by ocr_postprocess after the main pass.
    """
    if not settings.ocr_low_conf_retry:
        return words

    threshold = threshold if threshold is not None else settings.ocr_low_conf_threshold
    if not words:
        return words

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    if settings.tesseract_tessdata_dir:
        pytesseract.pytesseract.tessdata_dir = settings.tesseract_tessdata_dir

    tesseract_lang = _get_tesseract_lang(language)
    config = f"--psm 8 --oem {settings.tesseract_oem} --dpi {settings.ocr_render_dpi}"

    try:
        img_cm = Image.open(str(image_path))
    except (OSError, ValueError):
        return words

    with img_cm as img:
        out = []
        for w in words:
            if w.get("confidence", 100) >= threshold or not w.get("bbox"):
                out.append(w)
                continue
            bbox = w["bbox"]
            x, y, ww, hh = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
            try:
                crop = img.crop((x, y, x + ww, y + hh))
                retry_text = pytesseract.image_to_string(
                    crop,
                    lang=tesseract_lang,
                    config=config,
                ).strip()
            except (OSError, ValueError):
                out.append(w)
                continue
            if retry_text and retry_text != w["text"]:
                new_w = dict(w)
                new_w["text"] = retry_text
                new_w["confidence"] = max(w["confidence"], threshold)
                new_w["retried"] = True
                out.append(new_w)
            else:
                out.append(w)
    return out