"""Freeze the evaluation corpus: one OCR pass and one clean-text pass per book.

The OCR track runs the **same pass production runs** (``ocr_service.process_page_image``:
OCR -> low-confidence retry -> text normalisation) across a wider page window,
drops library/accession pages, and keeps the metadata-bearing front/back pages.
The result is committed, so every prompt variant is scored against identical
bytes and no PDF is ever rendered twice. The clean track reuses the Wikisource
page text that already ships with 17 of the ground-truth books and acts as the
control that separates prompt quality from OCR noise.

Needs the Indic Tesseract packs, so run it on a node or inside the worker
image — not on a laptop with only ``eng`` installed:

    cd backend
    python -m scripts.prompt_eval.build_corpus --track ocr --langs tel,hin
    python -m scripts.prompt_eval.build_corpus --track clean

Why the filtering matters: production OCRs the pages a human selected in the
page-selection step. These scans put library accession slips, stamps and
rotated book-post labels first, so a naive "pages 1..12" window spends its
whole per-page character budget on pages that hold no metadata. Measured on the
frozen corpus, 27 of 71 books had *no* core field findable, and one book's
title page sat at page 13+ while pages 1-9 were library forms.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import tempfile
from pathlib import Path

from scripts.prompt_eval import common

logger = logging.getLogger("prompt_eval.build_corpus")

# Pages that carry no bibliographic metadata: accession slips, library stamps,
# book-post labels. They are common in DLI/Commons scans and are usually rotated
# or typed in Latin, so OCR turns them into noise that crowds out the real
# front matter.
LIBRARY_MARKERS = re.compile(
    r"(accession|access\s*no|catalogue|class\s*no|date\s*of\s*(issue|entry)|"
    r"पुस्तकालय|विद्यापीठ|बनस्थली|ग्रंथालय|పుస్తకాలయ|గ్రంథాలయ|"
    r"इंदिरा गांधी|खोजपूर्ण|सूचीकरण)",
    re.IGNORECASE,
)

# Typed/printed forms are the only Latin-dominant pages that are safe to drop.
# A Latin-dominant page without one of these cues may be an English title page,
# which is exactly what a Latin-transliterated ground truth can match.
FORM_MARKERS = re.compile(
    r"(creativecommons|https?://|accession|access\s*no|book\s*post|"
    r"government\s+of\s+india|publicity\s+material|date\s*of\s*(issue|entry))",
    re.IGNORECASE,
)

# Only genuinely empty pages are noise. Sparse pages are often *the* metadata
# pages: a half-title can be a single line (a 17-character page in the corpus
# was the book's title and was being discarded).
MIN_PAGE_CHARS = 12
# Marker matching is restricted to short pages. "पुस्तकालय" inside a 2 000-
# character body page is running text, not a library slip.
SHORT_PAGE_CHARS = 600
MAX_LATIN_SHARE = 0.85

# Some PDFs declare an oversized page box, so a 300 DPI render lands at 35 MP
# (measured: 4963x7017) and Tesseract spends tens of minutes on that one page —
# three such pages stalled a rebuild for 30+ minutes. Normal pages render at
# 1878x2812 and are untouched by this cap.
MAX_RENDER_PIXELS = 3000


def _cap_image_size(path: Path) -> None:
    """Downscale a pathological render so one page cannot stall the run."""
    from PIL import Image

    with Image.open(path) as img:
        longest = max(img.size)
        if longest <= MAX_RENDER_PIXELS:
            return
        scale = MAX_RENDER_PIXELS / longest
        resized = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
        resized.save(path)


def _latin_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    latin = sum(1 for c in letters if ord(c) < 0x250)
    return latin / len(letters)


def _is_noise_page(text: str, language: str) -> bool:
    stripped = text.strip()
    if len(stripped) < MIN_PAGE_CHARS:
        return True
    if len(stripped) <= SHORT_PAGE_CHARS and LIBRARY_MARKERS.search(stripped):
        return True
    if _latin_share(stripped) > MAX_LATIN_SHARE and FORM_MARKERS.search(stripped):
        return True
    return False


def _page_numbers(total: int, front: int = common.FRONT_PAGES, tail: int = common.TAIL_PAGES) -> list[int]:
    """A wider window than before: metadata can sit well past page 12.

    Batch routing looks at the first pages and the last three, so caching more
    than this costs OCR time without changing what any batch sees. The window is
    filtered afterwards, so its size is about *coverage*, not cost per batch.
    """
    if total <= front + tail:
        return list(range(1, total + 1))
    return sorted(set(list(range(1, front + 1)) + list(range(total - tail + 1, total + 1))))


def _select_pages(pages: list[dict], language: str) -> list[dict]:
    """Drop noise pages, then keep a bounded front band and the colophon band.

    Order is preserved, so a batch's positional slice starts at the first page
    that actually holds front matter instead of at a library slip.
    """
    kept = [p for p in pages if not _is_noise_page(p["text"], language)]
    if not kept:
        return []
    front = kept[: common.FRONT_KEEP]
    tail = [p for p in kept[-common.TAIL_KEEP :] if p not in front]
    return sorted(front + tail, key=lambda p: p["n"])


def _write(track: str, book: common.Book, pages: list[dict], meta: dict) -> dict:
    payload = {
        "book": book.slug,
        "language": book.language,
        "track": track,
        "pages": pages,
        "meta": {**meta, "built_at": common.now_iso(), "git_sha": common.git_sha()},
    }
    canonical = json.dumps(payload["pages"], ensure_ascii=False, sort_keys=True).encode("utf-8")
    payload["sha256"] = common.sha256_bytes(canonical)
    path = common.corpus_path(track, book)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"sha256": payload["sha256"], "pages": len(pages), "chars": sum(len(p["text"]) for p in pages)}


def _cached_meta(path: Path) -> dict:
    cached = json.loads(path.read_text(encoding="utf-8"))
    pages = cached.get("pages") or []
    return {
        "sha256": cached.get("sha256", ""),
        "pages": len(pages),
        "chars": sum(len(p.get("text") or "") for p in pages),
        "cached": True,
    }


def build_clean(book: common.Book, force: bool = False) -> dict | None:
    source = book.directory / "wikisource_gt.json"
    if not source.is_file():
        return None
    path = common.corpus_path("clean", book)
    if path.is_file() and not force:
        return _cached_meta(path)

    raw = json.loads(source.read_text(encoding="utf-8"))
    records = [p for p in (raw.get("pages") or []) if (p.get("text") or "").strip()]
    if not records:
        return None
    records.sort(key=lambda p: int(p.get("page") or 0))
    pages = [
        {"n": int(rec.get("page") or i + 1), "text": (rec.get("text") or "").strip()}
        for i, rec in enumerate(records)
    ]
    meta = _write(
        "clean",
        book,
        pages,
        {
            "source": "wikisource_gt.json",
            "wiki": raw.get("wiki"),
            "index_title": raw.get("index_title"),
            # Verified pages only: the clean track can therefore miss front or
            # back matter that was never proofread. Stated so reports don't
            # over-read clean-track recall.
            "coverage": "proofread pages only",
        },
    )
    return meta


def build_ocr(book: common.Book, force: bool = False, dpi: int | None = None) -> dict | None:
    pdf = book.directory / "original.pdf"
    if not pdf.is_file():
        return None
    path = common.corpus_path("ocr", book)
    if path.is_file() and not force:
        return _cached_meta(path)

    from app.core.config import settings
    from app.services.ocr_service import process_page_image
    from app.services.pdf_service import get_page_count, render_full_page

    total = get_page_count(pdf)
    scanned: list[dict] = []
    with tempfile.TemporaryDirectory(prefix=f"corpus_{book.slug[:12]}_") as tmp:
        for page_number in _page_numbers(total):
            image = Path(tmp) / f"p{page_number:04d}.png"
            render_full_page(pdf, page_number, image, dpi=dpi)
            _cap_image_size(image)
            result = process_page_image(
                image,
                book.language,
                page_position=page_number - 1,
                # The corpus only needs text; the retry pass rewrites word boxes
                # for the review canvas and cannot change raw/cleaned text.
                include_retry=False,
            )
            text = (result.get("cleaned_text") or "").strip()
            if not text:
                continue
            scanned.append(
                {
                    "n": page_number,
                    "text": text,
                    # Kept for diagnostics only; prompts and scoring use `text`,
                    # which is what production stores as cleaned_text.
                    "raw_text": (result.get("raw_text") or "").strip(),
                    "psm": result.get("psm"),
                    "engine": result.get("engine"),
                }
            )

    pages = _select_pages(scanned, book.language)
    if not pages:
        # A rebuild that finds nothing must not leave the previous build's file
        # in place: it would be merged as if it came from this run (and on the
        # first rebuild it still carried the PSM-11 text).
        if force and path.is_file():
            path.unlink()
        logger.warning("%s: no usable pages after filtering (%d scanned)", book.sample_id, len(scanned))
        return None

    try:
        import pytesseract

        tesseract_version = str(pytesseract.get_tesseract_version())
    except Exception:  # noqa: BLE001 - metadata only
        tesseract_version = "unknown"

    meta = _write(
        "ocr",
        book,
        pages,
        {
            "source": "tesseract",
            "text_variant": "cleaned_text",
            "tesseract_version": tesseract_version,
            "pdf_pages": total,
            "pages_scanned": [p["n"] for p in scanned],
            "pages_kept": [p["n"] for p in pages],
            "pages_dropped_as_noise": len(scanned) - len(pages),
            "psm_per_page": {p["n"]: p.get("psm") for p in pages},
            "dpi": dpi or settings.ocr_render_dpi,
            "oem": settings.tesseract_oem,
            "preprocess": {"binarization": settings.ocr_binarization},
            "tel_engine": settings.ocr_tel_engine,
            "postprocess": settings.ocr_postprocess,
            "low_conf_retry": settings.ocr_low_conf_retry,
        },
    )
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track", choices=[*common.TRACKS, "both"], default="both")
    parser.add_argument("--langs", default="", help="Comma-separated language codes (default: all)")
    parser.add_argument("--books", default="", help="Comma-separated book slugs (default: all)")
    parser.add_argument("--limit", type=int, default=0, help="Max books per language (0 = all)")
    parser.add_argument("--force", action="store_true", help="Rebuild books already cached")
    parser.add_argument("--dpi", type=int, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    languages = [c.strip() for c in args.langs.split(",") if c.strip()] or None
    slugs = [s.strip() for s in args.books.split(",") if s.strip()] or None
    tracks = list(common.TRACKS) if args.track == "both" else [args.track]
    books = common.discover_books(languages=languages, slugs=slugs)

    if "ocr" in tracks:
        try:
            import pytesseract

            available = set(pytesseract.get_languages(config=""))
        except Exception as exc:  # noqa: BLE001 - report, don't guess
            print(f"error: cannot query Tesseract languages: {exc}", file=sys.stderr)
            return 2
        missing = [b.language for b in books if b.language not in available]
        if missing:
            print(
                "error: Tesseract lacks the pack(s) for "
                f"{sorted(set(missing))}; installed = {sorted(available)}. "
                "Run this on a test node or in the worker image.",
                file=sys.stderr,
            )
            return 2

    manifest = common.load_manifest()
    counts = {track: 0 for track in tracks}
    per_language: dict[str, int] = {}

    for language in sorted({b.language for b in books}):
        lang_books = [b for b in books if b.language == language]
        if args.limit:
            lang_books = lang_books[: args.limit]
        for book in lang_books:
            for track in tracks:
                builder = build_clean if track == "clean" else build_ocr
                # Only the OCR path takes the dpi argument.
                meta = builder(book, force=args.force, **({"dpi": args.dpi} if track == "ocr" else {}))
                if meta is None:
                    continue
                entry = manifest["books"].setdefault(book.sample_id, {})
                entry["language"] = book.language
                entry["slug"] = book.slug
                entry.setdefault("tracks", {})[track] = meta
                counts[track] += 1
                per_language[language] = per_language.get(language, 0) + 1
                print(
                    f"  {book.sample_id:60s} {track:5s} pages={meta['pages']:3d} chars={meta['chars']}",
                    flush=True,
                )

    common.save_manifest(manifest)
    print(f"\nmanifest -> {common.MANIFEST_PATH}")
    for track, count in counts.items():
        print(f"  {track}: {count} book(s)")
    print(f"  per language: {per_language}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
