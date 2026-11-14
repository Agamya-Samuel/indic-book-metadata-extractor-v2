#!/usr/bin/env python3
"""Merge the node OCR+LLM fill into the ground-truth scaffolds.

Reads the JSONL produced by ``node_gt_fill.py`` and writes values into each
book's ``expected_metadata.json`` — by default only into fields that are still
empty, so catalog-sourced values are never overwritten by model output.

Ground-truth integrity: values added here are *model reads of the scan*, not
human-verified truth. They are recorded with ``field_source=node_llm_extraction``
and ``field_status=prefilled_needs_verification``, and the top-level
``verification_status`` is set to ``prefilled_llm_unverified`` so the scoring
harness (which scores only ``verified`` books) will not treat them as gold until
a human reviews and re-verifies the book.

Usage:
    cd backend
    uv run python -m scripts.merge_node_fill --fill /path/node-fill.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.metadata import ALL_METADATA_FIELDS
from app.services.prompts import FIELD_DISPLAY_NAMES

FIELD_NAMES = [f.field_name for f in ALL_METADATA_FIELDS]
GT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth"

_TELUGU = re.compile(r"[\u0c00-\u0c7f]")
_YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")


def plausible(field: str, value: object) -> bool:
    """Reject model outputs that cannot be right, so noise stays out of the GT."""
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a"}:
        return False
    # A value that is just the field's own label (or its translation) is an echo, not data.
    if text.casefold() == FIELD_DISPLAY_NAMES.get(field, field).casefold():
        return False
    if field == "isbn":
        digits = re.sub(r"[^0-9Xx]", "", text)
        if len(digits) not in (10, 13) or len(set(digits)) <= 2:
            return False
    if field in {"inception", "publication_date", "first_published_in"}:
        years = _YEAR.findall(text)
        if not years:
            return False
    if field == "publisher_telugu" and not _TELUGU.search(text):
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fill", type=Path, required=True, help="node-fill.jsonl")
    ap.add_argument("--root", type=Path, default=GT_ROOT)
    ap.add_argument(
        "--overwrite", action="store_true", help="Also replace non-empty values (default: fill empties only)"
    )
    args = ap.parse_args()

    index = {p.parent.name: p for p in args.root.glob("*/*/expected_metadata.json")}
    rows = [json.loads(line) for line in args.fill.read_text(encoding="utf-8").splitlines() if line.strip()]

    books_touched = fields_filled = 0
    for row in rows:
        if "fields" not in row:
            print(f"  skip {row.get('slug')}: {row.get('error', 'no fields')}")
            continue
        gt_path = index.get(row["slug"])
        if gt_path is None:
            print(f"  skip {row['slug']}: no scaffold", file=sys.stderr)
            continue
        data = json.loads(gt_path.read_text(encoding="utf-8"))
        expected = data.setdefault("expected_metadata", {})
        source = data.setdefault("field_source", dict.fromkeys(FIELD_NAMES))
        status = data.setdefault("field_status", {fn: "empty_needs_annotation" for fn in FIELD_NAMES})

        added = 0
        for field in FIELD_NAMES:
            value = row["fields"].get(field)
            if value in (None, "", [], {}):
                continue
            if not plausible(field, value):
                continue
            if not args.overwrite and expected.get(field) not in (None, "", [], {}):
                continue
            if expected.get(field) == value:
                continue
            expected[field] = value
            source[field] = "node_llm_extraction"
            status[field] = "prefilled_needs_verification"
            added += 1

        if added:
            data.setdefault("node_fill", {})
            data["node_fill"] = {
                "model": row.get("model"),
                "pages_used": row.get("pages_used"),
                "ocr_pages": row.get("ocr_pages"),
                "filled_at": row.get("filled_at"),
                "fields_added": added,
            }
            data["verification_status"] = "prefilled_llm_unverified"
            gt_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            books_touched += 1
            fields_filled += added
            print(f"  {row['slug'][:48]:48s} +{added} fields")

    print(f"\n{books_touched} books updated, {fields_filled} fields filled (now prefilled_llm_unverified)")
    print("Human review required before these books count as verified ground truth.")
    print(f"merged at {datetime.now(UTC).isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
