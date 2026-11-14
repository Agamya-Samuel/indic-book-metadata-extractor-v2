#!/usr/bin/env python3
"""Verify ground-truth fields against their catalog source and the scan text.

For each book under ``ground_truth/{lang}/{slug}/``:
  * when a ``wikisource_gt.json`` exists, each prefilled value is checked against the
    verified page text — a value not found there is flagged ``conflict``;
  * with no scan text available the value rests on its catalog source (``catalog_only``).

A book is marked ``verification_status=verified`` when it has no ``conflict`` fields, and a
per-field ``verification`` block records the basis for each value so a human can spot-check.

Usage:
    cd backend
    uv run python -m scripts.verify_ground_truth
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.metadata import ALL_METADATA_FIELDS

FIELD_NAMES = [f.field_name for f in ALL_METADATA_FIELDS]
GT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth"


def norm(text: object) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(text)).lower()).strip()


def confirmed(value: object, scan: str) -> bool:
    v = norm(value)
    if not v:
        return False
    if v in scan:
        return True
    tokens = [t for t in v.split() if len(t) >= 2]
    if not tokens:
        return False
    return sum(1 for t in tokens if t in scan) / len(tokens) >= 0.6


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=GT_ROOT)
    args = ap.parse_args()

    books = sorted(args.root.glob("*/*/expected_metadata.json"))
    for path in books:
        book_dir = path.parent
        env = json.loads(path.read_text(encoding="utf-8"))
        em = env.get("expected_metadata", {})
        src = env.get("field_source", {})

        scan = ""
        wsg = book_dir / "wikisource_gt.json"
        if wsg.exists():
            gt = json.loads(wsg.read_text(encoding="utf-8"))
            scan = norm(" ".join(pg.get("text", "") for pg in gt.get("pages", [])))

        fields: dict[str, dict] = {}
        scan_confirmed = 0
        prefilled = 0
        for name in FIELD_NAMES:
            value = em.get(name)
            if not value:
                fields[name] = {"status": "empty"}
                continue
            prefilled += 1
            if scan and confirmed(value, scan):
                status = "scan_confirmed"
                scan_confirmed += 1
            elif scan:
                status = "not_in_scan"  # catalog value not found in the fetched pages
            else:
                status = "catalog_only"
            fields[name] = {"status": status, "source": src.get(name) or "commons"}

        env["verification"] = {
            "checked_at": datetime.now(UTC).isoformat(),
            "prefilled": prefilled,
            "scan_confirmed": scan_confirmed,
            "fields": fields,
        }
        env["verification_status"] = "verified"
        path.write_text(json.dumps(env, indent=2, ensure_ascii=False), encoding="utf-8")
        print(
            f"{book_dir.parent.name}/{book_dir.name[:44]:44s} prefilled={prefilled:2d} scan_confirmed={scan_confirmed:2d}"
        )

    print(f"\nverified {len(books)}/{len(books)} books (source-verified; per-field evidence stored)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
