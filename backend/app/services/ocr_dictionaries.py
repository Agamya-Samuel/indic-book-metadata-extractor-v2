"""Tesseract user-words and user-patterns for Indic bibliographic OCR.

Provides ``get_dictionary_paths(language)`` which returns the filesystem
paths to a ``--user-words`` and ``--user-patterns`` file suitable for
passing to Tesseract.  Files ship alongside this module under
``backend/app/services/dictionaries/``.

When ``--oem 0`` (legacy engine) is active these files act as hard
dictionary constraints; with ``--oem 1`` (LSTM) they bias recognition
toward known bibliographic terms without forcing incorrect matches.
"""

from __future__ import annotations

from pathlib import Path

_DICT_DIR = Path(__file__).resolve().parent / "dictionaries"

# Languages that share Devanagari script → use the Hindi dictionary.
_DEVANAGARI_LANGS = {"hin"}

def _resolve_lang(language: str) -> str | None:
    """Map a language code to the dictionary file prefix, or ``None`` if no
    dictionary is available for that script family.

    Currently ships dictionaries for Hindi (Devanagari) and Telugu. Other
    Indic scripts (Tamil, Bengali, etc.) return ``None`` so the OCR service
    does not silently bias them toward English.
    """
    if language in _DEVANAGARI_LANGS:
        return "hin"
    if language == "tel":
        return "tel"
    if language == "eng":
        return "eng"
    return None

def get_dictionary_paths(language: str) -> tuple[Path | None, Path | None]:
    """Return ``(words_path, patterns_path)`` for *language*.

    Returns ``(None, None)`` when no dictionary files exist for the
    requested language (e.g. a script family not yet covered).
    """
    lang = _resolve_lang(language)
    if lang is None:
        return None, None
    words = _DICT_DIR / f"{lang}.words"
    patterns = _DICT_DIR / f"{lang}.patterns"
    if words.is_file() and patterns.is_file():
        return words, patterns
    return None, None
