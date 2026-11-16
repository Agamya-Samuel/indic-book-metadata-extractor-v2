import logging
import unicodedata
from pathlib import Path

import newrelic.agent
import pytesseract
from PIL import Image

from app.core.config import settings
from app.services import ocr_line_model, ocr_postprocess
from app.services.ocr_dictionaries import get_dictionary_paths
from app.services.page_classifier import (
    Classification,
    PSM,
    classify_page,
    psm_to_tesseract_arg,
)

logger = logging.getLogger(__name__)

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


def _use_line_model(language: str) -> bool:
    """Telugu only, and only when the line engine is explicitly selected."""
    return language == "tel" and settings.ocr_tel_engine.strip().lower() == "line_model"


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


def _tessdata_arg() -> str:
    """Tesseract's real custom-model flag (``pytesseract.tessdata_dir`` is inert)."""
    return f'--tessdata-dir "{settings.tesseract_tessdata_dir}"' if settings.tesseract_tessdata_dir else ""


def _build_config(psm: int, language: str) -> str:
    """Compose the Tesseract command-line config string.

    Includes --psm, --oem, --dpi, --tessdata-dir when configured, and
    --user-words/--user-patterns if a dictionary is enabled for the active
    language (set via OCR_USE_DICTIONARY).
    """
    parts = [f"--psm {psm}", f"--oem {settings.tesseract_oem}", f"--dpi {settings.ocr_render_dpi}"]
    if tessdata := _tessdata_arg():
        parts.append(tessdata)
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

    # Context manager releases the OS file handle promptly. Otherwise
    # under concurrent OCR the descriptor table fills up over the
    # lifetime of the worker.
    with Image.open(str(image_path)) as img:
        if _use_line_model(language):
            try:
                result = ocr_line_model.run_line_ocr(img, image_path, language, page_position)
                newrelic.agent.add_custom_attribute("ocr_engine", result.get("engine"))
                return result
            except Exception as exc:  # noqa: BLE001 - a missing/broken model must not fail the page
                logger.warning(
                    "Telugu line OCR failed for %s; falling back to Tesseract",
                    image_path.name,
                    exc_info=True,
                )
                result = _run_ocr_with_img(img, image_path, language, page_position)
                result["engine_fallback_reason"] = f"{type(exc).__name__}: {exc}"
                newrelic.agent.add_custom_attribute("ocr_engine", result.get("engine"))
                return result

        result = _run_ocr_with_img(img, image_path, language, page_position)
        newrelic.agent.add_custom_attribute("ocr_engine", result.get("engine"))
        return result


def _run_ocr_with_img(
    img,
    image_path: Path,
    language: str,
    page_position: int | None = None,
    tesseract_lang: str | None = None,
) -> dict:
    tesseract_lang = tesseract_lang or _get_tesseract_lang(language)

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
        "engine": "tesseract",
        "tesseract_lang": tesseract_lang,
    }


def _script_shares(text: str) -> dict[str, float]:
    """Share of letters/marks in Latin, Telugu, and Devanagari scripts."""
    latin = telugu = devanagari = total = 0
    for ch in text:
        category = unicodedata.category(ch)
        if category[0] not in ("L", "M"):
            continue
        total += 1
        codepoint = ord(ch)
        if ch.isascii() and ch.isalpha():
            latin += 1
        elif 0x0C00 <= codepoint <= 0x0C7F:
            telugu += 1
        elif 0x0900 <= codepoint <= 0x097F:
            devanagari += 1
    if not total:
        return {"latin": 0.0, "telugu": 0.0, "devanagari": 0.0}
    return {
        "latin": latin / total,
        "telugu": telugu / total,
        "devanagari": devanagari / total,
    }


def _reroute_latin_page(
    data: dict,
    image_path: Path,
    language: str,
    page_position: int | None,
) -> dict:
    """Run Tesseract on a Latin-dominated line-model page and keep the result.

    Only fires for the Telugu line model when its output is overwhelmingly
    Latin (front matter, cover, English copyright page). That is exactly where
    the model loses lines and Tesseract's page layout/English model wins.
    """
    if not settings.ocr_script_routing or data.get("engine") != "line_model":
        return data
    if language != "tel":
        return data

    text = data.get("full_text") or ""
    shares = _script_shares(text)
    if shares["latin"] < 0.8 or shares["telugu"] > 0.2:
        return data

    with Image.open(str(image_path)) as img:
        alt = _run_ocr_with_img(img, image_path, language, page_position=page_position)
    alt_text = alt.get("full_text") or ""
    if not alt_text.strip():
        return data
    # Keep Tesseract only when it found at least half as much text; a shorter
    # result usually means the page is not actually Latin prose.
    if len(alt_text) < 0.5 * len(text):
        return data

    logger.info(
        "Re-routed %s to Tesseract (line model Latin share %.2f, %d→%d chars)",
        image_path.name,
        shares["latin"],
        len(text),
        len(alt_text),
    )
    alt["route_reason"] = "latin_page_reroute"
    alt["script_shares"] = _script_shares(alt_text)
    return alt


def _reroute_dominant_script_page(
    data: dict,
    image_path: Path,
    language: str,
    page_position: int | None,
) -> dict:
    """Drop the unnecessary ``+eng`` model on a dominant-script Tesseract page.

    Hindi body pages read better with ``hin`` than ``hin+eng`` (0.063 vs 0.081
    median CER), and Telugu Tesseract pages read better with ``tel`` than
    ``tel+eng`` (0.272 vs 0.331 after this reroute). Bilingual/Latin pages stay
    on the combined model because their dominant-script share is low.
    """
    if not settings.ocr_script_routing or data.get("engine") != "tesseract":
        return data

    expected = {"hin": "devanagari", "tel": "telugu"}.get(language)
    target = {"hin": "hin", "tel": "tel"}.get(language)
    if expected is None or target is None or data.get("tesseract_lang") == target:
        return data

    text = data.get("full_text") or ""
    shares = _script_shares(text)
    if shares[expected] < 0.85 or shares["latin"] > 0.15:
        return data

    with Image.open(str(image_path)) as img:
        alt = _run_ocr_with_img(
            img,
            image_path,
            language,
            page_position=page_position,
            tesseract_lang=target,
        )
    alt_text = alt.get("full_text") or ""
    if len(alt_text) < 0.9 * len(text):
        return data

    logger.info(
        "Re-routed %s from combined to %s (dominant %s share %.2f, %d→%d chars)",
        image_path.name,
        target,
        expected,
        shares[expected],
        len(text),
        len(alt_text),
    )
    alt["route_reason"] = "dominant_script_reroute"
    alt["script_shares"] = _script_shares(alt_text)
    return alt


def process_page_image(
    image_path: Path,
    language: str = "tel",
    page_position: int | None = None,
    *,
    include_retry: bool = True,
) -> dict:
    """The full production OCR pass for one page image.

    Single source of truth shared by the OCR worker and the evaluation corpus
    builder. Before this existed the corpus called :func:`run_ocr` directly and
    therefore skipped post-processing, so frozen evaluation text was not what
    production stores — a difference that silently invalidated comparisons.

    ``include_retry=False`` skips :func:`retry_low_confidence_words`. That pass
    rewrites only the per-word boxes the review canvas draws; production's
    ``raw_text``/``cleaned_text`` come from :func:`run_ocr` and are unaffected.
    The corpus builder turns it off because it is expensive (one crop OCR per
    low-confidence word) and provably cannot change the text.

    Returns the ``run_ocr`` dict plus:

    * ``words``       — post-retry word boxes (what the review canvas shows)
    * ``raw_text``    — the text production persists as ``raw_text``
    * ``cleaned_text``— post-normalisation text, what the LLM reads first
    * ``corrections`` — normalisation rules that fired
    """
    data = run_ocr(image_path, language, page_position=page_position)
    try:
        data = _reroute_latin_page(data, image_path, language, page_position)
        data = _reroute_dominant_script_page(data, image_path, language, page_position)
    except Exception:  # noqa: BLE001 - never lose the primary result to a reroute failure
        logger.warning("Page script reroute failed for %s", image_path.name, exc_info=True)
    engine = data.get("engine", "tesseract")
    words = data.get("words") or []

    # The line model emits line-level boxes; re-OCR'ing them with Tesseract
    # would overwrite the model's output.
    if include_retry and settings.ocr_low_conf_retry and engine == "tesseract":
        words = retry_low_confidence_words(
            image_path,
            words,
            language,
            threshold=settings.ocr_low_conf_threshold,
            tesseract_lang=data.get("tesseract_lang"),
        )

    raw_text = data.get("full_text") or ""
    cleaned_text = raw_text
    corrections: list[dict] = []
    if settings.ocr_postprocess:
        cleaned_text, corrections = ocr_postprocess.normalize_text(raw_text, language)

    return {
        **data,
        "words": words,
        "engine": engine,
        "raw_text": raw_text,
        "cleaned_text": cleaned_text,
        "corrections": corrections,
        "script_shares": _script_shares(raw_text),
    }


def retry_low_confidence_words(
    image_path: Path,
    words: list[dict],
    language: str,
    threshold: int | None = None,
    tesseract_lang: str | None = None,
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

    tesseract_lang = tesseract_lang or _get_tesseract_lang(language)
    config = f"--psm 8 --oem {settings.tesseract_oem} --dpi {settings.ocr_render_dpi}"
    if tessdata := _tessdata_arg():
        config = f"{config} {tessdata}"

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
