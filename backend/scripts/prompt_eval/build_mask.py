"""Derive a per-field visibility mask from the frozen corpus.

Answers one question per ``(book, batch, field)``: *could the model have found
this ground-truth value in the text it was actually given?*

Four outcomes, and the distinction matters more than the number:

``visible``     the value is in the routed text — a null answer is a real
                prompt/recall miss.
``absent``      the ground truth is null — a value here is a hallucination.
``unroutable``  the value is in the book but outside the pages this batch was
                given — a **routing** defect, not a prompt defect.
``not_in_scan`` the value appears nowhere in the cached text (catalogue-derived,
                e.g. genre from a Commons category) — not extractable at all.

The last two are excluded from scoring by
``extraction_validator.UNSCORED_MASKS`` and reported separately, so a prompt is
never punished for something it cannot influence.

The 17 books that carry a human ``verification`` block are used to *calibrate*
this machine-derived mask, not to drive it.

    cd backend
    python -m scripts.prompt_eval.build_mask --track clean
"""

from __future__ import annotations

import argparse
import json
import sys

from scripts.prompt_eval import common

MIN_SUBSTRING_LEN = 3
FUZZY_TOKEN_SHARE = 0.60


def _normalize(text: str) -> str:
    from app.services.extractors import _normalize

    return _normalize(text)


def find_value(value: str, text: str) -> str | None:
    """Return how the value was found (``exact``/``fuzzy``) or ``None``."""
    needle = _normalize(value)
    haystack = _normalize(text)
    if not needle or not haystack:
        return None

    if len(needle) >= MIN_SUBSTRING_LEN:
        if needle in haystack:
            return "exact"
    elif needle in haystack.split():
        # Very short values ("1", "5") must match a whole token, otherwise they
        # match everywhere and every field looks visible.
        return "exact"

    tokens = [t for t in needle.split() if len(t) > 1]
    if tokens:
        share = sum(1 for token in tokens if token in haystack) / len(tokens)
        if share >= FUZZY_TOKEN_SHARE:
            return "fuzzy"

    return None


def mask_book(book: common.Book, track: str) -> dict[str, str] | None:
    from app.schemas.metadata import BATCH_FIELD_ORDER, METADATA_BATCHES
    from app.services.extraction_validator import MASK_SCRIPT_MISMATCH, _dominant_script

    corpus = common.load_corpus(track, book)
    if not corpus:
        return None
    expected = common.load_expected(book)
    pages = common.page_records(corpus)
    full_text = "\n".join(page.text for page in pages)

    masks: dict[str, str] = {}
    for batch_name in BATCH_FIELD_ORDER:
        routed = common.routed_text(pages, batch_name)
        for field_name in METADATA_BATCHES[batch_name].model_fields:
            if field_name == "custom_fields":
                continue
            raw = expected.get(field_name)
            value = "" if raw is None else str(raw).strip()
            if not value:
                masks[field_name] = "absent"
                continue
            if find_value(value, routed) is not None:
                masks[field_name] = "visible"
            elif find_value(value, full_text) is not None:
                masks[field_name] = "unroutable"
            elif (
                book.language in ("hin", "tel")
                and _dominant_script(value) == "lat"
                and _dominant_script(full_text) == book.language
            ):
                # Half of the Hindi core metadata is a Latin transliteration
                # ("Sadhu Aur Vaishya") while the scan is Devanagari. String
                # matching can never confirm it, so it is unverifiable rather
                # than absent — scoring it as a miss blames OCR for a GT format.
                masks[field_name] = MASK_SCRIPT_MISMATCH
            else:
                masks[field_name] = "not_in_scan"
    return masks


def apply_human_labels(book: common.Book, masks: dict[str, str]) -> dict[str, str]:
    """Let a human verification block override the machine mask.

    On OCR text the matcher disagrees with human labels on ~27 % of informative
    fields. Where a person has actually looked at the scan, their verdict wins:
    ``not_in_scan`` and ``empty`` are authoritative. ``scan_confirmed`` is left
    to the matcher, because a confirmed field may still sit outside the pages
    this batch is given — that case is a routing fact, not a visibility one.
    """
    verification = common.load_envelope(book).get("verification")
    if not isinstance(verification, dict):
        return masks
    statuses = verification.get("fields") or {}
    overrides = {"not_in_scan": "not_in_scan", "empty": "absent"}
    for field_name, info in statuses.items():
        status = (info or {}).get("status")
        replacement = overrides.get(status)
        if replacement and field_name in masks:
            masks[field_name] = replacement
    return masks


def calibrate(books: list[common.Book], fields: dict[str, dict[str, str]]) -> dict:
    """Compare the machine mask with the human verification blocks.

    ``scan_confirmed`` should be visible or unroutable (present in the book,
    maybe outside this batch's pages). ``not_in_scan`` should be
    ``not_in_scan``. ``empty`` should be ``absent``.
    """
    expected_map = {
        # A human can confirm a value they saw in the scan even when the stored
        # GT is a transliteration of it, so script_mismatch is compatible here too.
        "scan_confirmed": {"visible", "unroutable", "script_mismatch"},
        "not_in_scan": {"not_in_scan", "script_mismatch"},
        "empty": {"absent"},
    }
    total = 0
    agree = 0
    disagreements: list[dict] = []
    books_compared = 0
    by_status: dict[str, dict[str, int]] = {}

    for book in books:
        book_masks = fields.get(book.sample_id)
        if not book_masks:
            # A book with no corpus in this track cannot calibrate anything;
            # counting it would inflate the agreement rate with skipped fields.
            continue
        envelope = common.load_envelope(book)
        verification = envelope.get("verification")
        if not isinstance(verification, dict):
            continue
        statuses = verification.get("fields") or {}
        if not statuses:
            continue
        books_compared += 1
        expected = common.load_expected(book)
        for field_name, info in statuses.items():
            status = (info or {}).get("status")
            allowed = expected_map.get(status)
            actual = book_masks.get(field_name)
            if allowed is None or actual is None:
                continue
            bucket = by_status.setdefault(status, {"n": 0, "agree": 0})
            total += 1
            bucket["n"] += 1
            if actual in allowed:
                agree += 1
                bucket["agree"] += 1
            elif len(disagreements) < 60:
                raw = expected.get(field_name)
                disagreements.append(
                    {
                        "book": book.sample_id,
                        "field": field_name,
                        "verification": status,
                        "mask": actual,
                        "value": ("" if raw is None else str(raw))[:80],
                    }
                )

    per_status = {
        status: {
            "n": counts["n"],
            "agreement": round(counts["agree"] / counts["n"], 3) if counts["n"] else None,
        }
        for status, counts in sorted(by_status.items())
    }
    informative = [s for s in ("scan_confirmed", "not_in_scan") if s in by_status]
    informative_n = sum(by_status[s]["n"] for s in informative)
    informative_agree = sum(by_status[s]["agree"] for s in informative)

    return {
        "books_compared": books_compared,
        "fields_compared": total,
        "agreement": round(agree / total, 3) if total else None,
        # `empty` fields are trivially "absent", so the overall figure is
        # dominated by them. This is the number to trust.
        "informative_agreement": round(informative_agree / informative_n, 3) if informative_n else None,
        "informative_fields": informative_n,
        "by_status": per_status,
        "disagreements": disagreements,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track", default="clean", choices=common.TRACKS)
    parser.add_argument("--langs", default="")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    languages = [c.strip() for c in args.langs.split(",") if c.strip()] or None
    books = common.discover_books(languages=languages)
    if args.limit:
        books = books[: args.limit]

    fields: dict[str, dict[str, str]] = {}
    totals = {"visible": 0, "absent": 0, "unroutable": 0, "not_in_scan": 0}
    skipped = 0

    for book in books:
        masks = mask_book(book, args.track)
        if masks is None:
            skipped += 1
            continue
        masks = apply_human_labels(book, masks)
        fields[book.sample_id] = masks
        for mask in masks.values():
            totals[mask] = totals.get(mask, 0) + 1

    if not fields:
        print(f"No {args.track}-track corpus found. Run build_corpus.py first.", file=sys.stderr)
        return 1

    calibration = calibrate(books, fields)
    scored = totals["visible"] + totals["absent"]
    payload = {
        "generated_at": common.now_iso(),
        "track": args.track,
        "git_sha": common.git_sha(),
        "definition": {
            "visible": "GT value found in the text this batch was given",
            "absent": "GT value is null",
            "unroutable": "GT value is in the book but outside this batch's pages",
            "not_in_scan": "GT value appears nowhere in the cached text",
            "script_mismatch": "GT value is in a different script from the scan, so presence is unverifiable",
        },
        "stats": {
            "books": len(fields),
            "books_without_corpus": skipped,
            "field_masks": totals,
            "scored_fields": scored,
            "unscored_share": round(1 - scored / max(1, sum(totals.values())), 3),
        },
        "calibration": calibration,
        "fields": fields,
    }

    out = common.mask_path(args.track)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"mask -> {out}")
    print(f"  books: {len(fields)} ({skipped} without {args.track} corpus)")
    print(f"  field masks: {totals}")
    print(f"  scored fields: {scored} ({payload['stats']['unscored_share']:.1%} excluded)")
    if calibration["agreement"] is not None:
        print(f"  calibration over {calibration['books_compared']} book(s), {calibration['fields_compared']} fields:")
        print(f"    overall    {calibration['agreement']:.1%}")
        print(
            f"    informative {calibration['informative_agreement']:.1%}"
            f"  (scan_confirmed/not_in_scan only, n={calibration['informative_fields']})"
        )
        for status, stats in calibration["by_status"].items():
            print(f"    {status:16s} n={stats['n']:4d}  agreement={stats['agreement']:.1%}")
    else:
        print("  calibration: no book in this set carries a verification block")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
