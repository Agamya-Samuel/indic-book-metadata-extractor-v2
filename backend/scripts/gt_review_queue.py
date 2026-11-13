#!/usr/bin/env python3
"""Emit a review queue of the model-prefilled ground-truth values.

The 41 ``prefilled_llm_unverified`` books hold values read from the scan by
``node_gt_fill.py``/``merge_node_fill.py``. This lists every such value (book,
field, value, script, the pages the model saw, the model) as a CSV a human can
work through to promote a book back to ``verified``.

Usage:
    cd backend
    uv run python -m scripts.gt_review_queue            # -> reports/gt-review-queue.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from app.schemas.metadata import ALL_METADATA_FIELDS

CANON = [f.field_name for f in ALL_METADATA_FIELDS]
GT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth"
OUT = Path(__file__).resolve().parents[1] / "reports" / "gt-review-queue.csv"


def script_of(text: str) -> str:
    if any("\u0c00" <= c <= "\u0c7f" for c in text):
        return "telugu"
    if any("\u0900" <= c <= "\u097f" for c in text):
        return "devanagari"
    if any("a" <= c.lower() <= "z" for c in text):
        return "latin"
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=GT_ROOT)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    rows = []
    for gt in sorted(args.root.glob("*/*/expected_metadata.json")):
        env = json.loads(gt.read_text(encoding="utf-8"))
        em = env.get("expected_metadata", {})
        src = env.get("field_source", {}) or {}
        pages = (env.get("node_fill") or {}).get("pages_used")
        pages_s = " ".join(str(p) for p in pages) if pages else ""
        for f in CANON:
            v = em.get(f)
            if src.get(f) == "node_llm_extraction" and v not in (None, "", [], {}):
                rows.append(
                    {
                        "lang": gt.parent.parent.name,
                        "book": gt.parent.name,
                        "field": f,
                        "value": str(v),
                        "script": script_of(str(v)),
                        "pages_seen": pages_s,
                    }
                )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["lang", "book", "field", "value", "script", "pages_seen"])
        w.writeheader()
        w.writerows(rows)

    books = len({r["book"] for r in rows})
    print(f"wrote {args.out} ({len(rows)} values across {books} books)")
    return 0


if __name__ == "__main__":
    sys.exit(main())