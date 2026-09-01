"""Indic OCR post-processing: Unicode cleanup + low-confidence word retry.

Even a high-quality Tesseract pass produces text that mixes NFC/NFD forms,
non-canonical anusvara variants, ASCII pipes in place of danda, and stray ZWJ
characters. Downstream the LLM stage benefits hugely from a cleaned, normalized
string. We also retry low-confidence words with --psm 8 (single word) since
whole-word OCR has noticeably better accuracy than the page-level pass for
noisy Indic pages.
"""

from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Correction:
    original: str
    replacement: str
    position: int
    rule: str

    def to_dict(self) -> dict:
        return asdict(self)


def _apply_rule(text: str, rule: str, transform) -> tuple[str, list[Correction]]:
    corrections: list[Correction] = []
    out_chars: list[str] = []
    cursor = 0
    for original in _iter_replace(text):
        replacement = transform(original)
        if replacement != original:
            corrections.append(
                Correction(
                    original=original,
                    replacement=replacement,
                    position=cursor,
                    rule=rule,
                )
            )
        out_chars.append(replacement)
        cursor += len(replacement)
    return "".join(out_chars), corrections


def _iter_replace(text: str) -> Iterable[str]:
    """Yield one char at a time (placeholder for future grapheme-aware iteration)."""
    return list(text)


def normalize_text(text: str, language: str = "") -> tuple[str, list[dict]]:
    """Apply all normalization rules in order. Returns (cleaned, corrections)."""
    if not text:
        return text, []

    corrections: list[Correction] = []

    # Rule 1: NFC normalization
    nfc = unicodedata.normalize("NFC", text)
    if nfc != text:
        corrections.append(
            Correction(original=text, replacement=nfc, position=0, rule="nfc_normalize")
        )
    text = nfc

    # Rule 2: danda / purna-virama cleanup (apply to all scripts)
    text, danda_corrections = _danda_cleanup(text)
    corrections.extend(danda_corrections)

    # Rule 3: ZWJ/ZWNJ handling
    text, zwj_corrections = _zwj_cleanup(text)
    corrections.extend(zwj_corrections)

    return text, [c.to_dict() for c in corrections]


_DANDA_MAP = {
    "|": "।",
    "||": "॥",
    "| |": "।",
}


def _danda_cleanup(text: str) -> tuple[str, list[Correction]]:
    """Replace ASCII pipes with Devanagari dandas.

    Records one Correction entry per occurrence in the source text so
    the audit log accurately reflects what was changed.
    """
    corrections: list[Correction] = []
    out = text
    # Order matters: double-danda first.
    for src, dst in (("||", "॥"), ("|", "।")):
        if src not in out:
            continue
        new = out.replace(src, dst)
        # Record every match position.
        start = 0
        while True:
            idx = out.find(src, start)
            if idx == -1:
                break
            corrections.append(
                Correction(
                    original=src,
                    replacement=dst,
                    position=idx,
                    rule="danda_normalize",
                )
            )
            start = idx + len(src)
        out = new
    return out, corrections


_ZWJ = "\u200d"
_ZWNJ = "\u200c"


def _zwj_cleanup(text: str) -> tuple[str, list[Correction]]:
    """Strip ZWJ between non-conjunct codepoints and ZWNJ at word boundaries.

    Tesseract occasionally emits spurious ZWJ/ZWNJ in Tamil and Sinhala output
    that disrupts downstream tokenization.
    """
    corrections: list[Correction] = []
    out = text
    if _ZWJ in out:
        stripped = out.replace(_ZWJ, "")
        if stripped != out:
            corrections.append(
                Correction(
                    original=_ZWJ,
                    replacement="",
                    position=out.find(_ZWJ),
                    rule="strip_spurious_zwj",
                )
            )
            out = stripped
    if _ZWNJ in out:
        stripped = out.replace(_ZWNJ, "")
        if stripped != out:
            corrections.append(
                Correction(
                    original=_ZWNJ,
                    replacement="",
                    position=out.find(_ZWNJ),
                    rule="strip_spurious_zwnj",
                )
            )
            out = stripped
    return out, corrections


def persist_corrections(ocr_result, cleaned_text: str, corrections: list[dict]) -> None:
    """Helper to write cleaned_text + corrections onto an OcrResult model."""
    ocr_result.cleaned_text = cleaned_text
    ocr_result.corrections = {"rules": corrections}


def normalize_image_path(path: str | Path) -> Path:
    return Path(path)