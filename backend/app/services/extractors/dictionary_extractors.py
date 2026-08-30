"""Dictionary-based field extractors for language and known publishers.

A small but high-signal whitelist of common Telugu/Hindi/Indian publishers
lets us extract the publisher field with confidence 0.95 without burning
LLM tokens on it.
"""

from __future__ import annotations

from app.services.extractors import ExtractedField, _normalize, _snippet


# Common Indian publishers seen in OKI sample books. Lowercase and
# stripped of diacritics for fuzzy matching.
KNOWN_PUBLISHERS = {
    # Telugu
    "telugu academy": "Telugu Akademi",
    "visalaandhra": "Visalaandhra",
    "visala andhra": "Visalaandhra",
    "emcee": "EMCEE Publishers",
    "emcee publishers": "EMCEE Publishers",
    "pragati": "Pragati Publications",
    "orient longman": "Orient Longman",
    "ravi publications": "Ravi Publications",
    "sri venkateswara": "Sri Venkateswara",
    # Hindi
    "rajkamal": "Rajkamal Prakashan",
    "rajkamal prakashan": "Rajkamal Prakashan",
    "prabhat prakashan": "Prabhat Prakashan",
    "bharatiya jnanpith": "Bharatiya Jnanpith",
    "lokbharti": "Lokbharti Prakashan",
    "geetanjali": "Geetanjali",
    "vani prakashan": "Vani Prakashan",
    # English (Indian)
    "penguin india": "Penguin India",
    "rupa": "Rupa Publications",
    "rupa publications": "Rupa Publications",
    "harper collins india": "HarperCollins India",
    "aleph": "Aleph Book Company",
    "jaico": "Jaico Publishing",
    "westland": "Westland Books",
    "nbt": "National Book Trust",
    "national book trust": "National Book Trust",
    "sahitya akademi": "Sahitya Akademi",
    "sahitya academy": "Sahitya Akademi",
}


# Language detection. We use a small set of script-marker characters;
# a 5-char sample is plenty to distinguish the three supported langs.
LANGUAGE_SIGNATURES = {
    "tel": {
        # Telugu script range U+0C00..U+0C7F
        "range": (0x0C00, 0x0C7F),
        "label": "Telugu",
    },
    "hin": {
        # Devanagari range U+0900..U+097F
        "range": (0x0900, 0x097F),
        "label": "Hindi",
    },
    "eng": {
        # Latin alphabet — we just check there's no Indic script.
        "range": (0x0041, 0x007A),
        "label": "English",
    },
}


def extract_publisher(
    full_text: str,
    pages: list[tuple[int, str]],
) -> ExtractedField | None:
    """Match the full text against a known publisher whitelist."""
    text_norm = _normalize(full_text)
    best_match: tuple[str, str, int | None, str | None] | None = None
    for needle, canonical in KNOWN_PUBLISHERS.items():
        if needle in text_norm:
            # Prefer the longest match so "national book trust" wins over "nbt".
            if best_match is None or len(needle) > len(best_match[0]):
                page_num, snippet = _find_page(pages, canonical)
                # Also try the lowercased form since OCR may have lost case.
                if page_num is None:
                    page_num, snippet = _find_page(pages, needle)
                best_match = (needle, canonical, page_num, snippet)
    if not best_match:
        return None
    _, canonical, page_num, snippet = best_match
    return ExtractedField(
        field_name="publisher",
        value=canonical,
        confidence=0.95,
        method="dictionary",
        source_page_number=page_num,
        source_text_snippet=snippet,
    )


def detect_language(
    full_text: str,
    pages: list[tuple[int, str]],
) -> ExtractedField | None:
    """Detect language by script-marker count in the first 1000 chars.

    Returns the language with the highest script-marker density. Falls
    back to None if no script marker is dominant (e.g. pure punctuation
    or numbers, which shouldn't happen for a real book).
    """
    sample = full_text[:1000]
    if not sample.strip():
        return None
    counts = {"tel": 0, "hin": 0, "eng": 0}
    for ch in sample:
        cp = ord(ch)
        if 0x0C00 <= cp <= 0x0C7F:
            counts["tel"] += 1
        elif 0x0900 <= cp <= 0x097F:
            counts["hin"] += 1
        elif 0x0041 <= cp <= 0x007A or 0x0061 <= cp <= 0x007A:
            counts["eng"] += 1

    if max(counts.values()) == 0:
        return None
    lang = max(counts, key=counts.get)
    label = LANGUAGE_SIGNATURES[lang]["label"]
    return ExtractedField(
        field_name="language",
        value=label,
        confidence=0.95 if counts[lang] > 20 else 0.7,
        method="dictionary",
        source_page_number=None,
        source_text_snippet=None,
    )


def _find_page(
    pages: list[tuple[int, str]],
    needle: str,
) -> tuple[int | None, str | None]:
    needle_norm = _normalize(needle)
    for page_num, text in pages:
        if needle_norm in _normalize(text):
            return page_num, _snippet(text, needle)
    return None, None


REGISTRY = {
    "publisher": extract_publisher,
    "language": detect_language,
}
