#!/usr/bin/env python3
"""Enforce the canonical 49-field schema on the ground-truth scaffolds.

The field list in ``docs/metadata-fields.md`` is derived from
``app/schemas/metadata.py``. This script compares every book's
``expected_metadata`` / ``field_status`` / ``field_source`` against that
canonical set and, in write mode, normalizes them to it: missing keys are
added (null / default status / null source), unknown keys are removed, and
keys are written in canonical batch order.

With ``--check`` it only reports and exits non-zero if any book deviates, so it
can gate CI.

Usage:
    cd backend
    uv run python -m scripts.apply_field_schema --check
    uv run python -m scripts.apply_field_schema --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.schemas.metadata import ALL_METADATA_FIELDS

CANON = [f.field_name for f in ALL_METADATA_FIELDS]
CANON_SET = set(CANON)
GT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth"


def normalize_dict(d: dict, default) -> tuple[dict, list[str], list[str]]:
    missing = [f for f in CANON if f not in d]
    extra = [k for k in d if k not in CANON_SET]
    out = {f: d.get(f, default) for f in CANON}
    return out, missing, extra


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=GT_ROOT)
    ap.add_argument("--write", action="store_true", help="Normalize files in place")
    ap.add_argument("--check", action="store_true", help="Report only (the default)")
    args = ap.parse_args()

    books = sorted(args.root.glob("*/*/expected_metadata.json"))
    deviating = 0
    for gt in books:
        env = json.loads(gt.read_text(encoding="utf-8"))
        em, em_miss, em_extra = normalize_dict(env.get("expected_metadata", {}), None)
        fs, fs_miss, fs_extra = normalize_dict(env.get("field_status", {}) or {}, "empty_needs_annotation")
        src, src_miss, src_extra = normalize_dict(env.get("field_source", {}) or {}, None)

        changed = bool(em_miss or em_extra or fs_miss or fs_extra or src_miss or src_extra)
        if not changed:
            continue
        deviating += 1
        label = f"{gt.parent.parent.name}/{gt.parent.name}"
        print(
            f"  {label[:52]:52s} em(-{len(em_miss)}/+{len(em_extra)}) fs(-{len(fs_miss)}/+{len(fs_extra)}) src(-{len(src_miss)}/+{len(src_extra)})"
        )
        if em_extra or fs_extra or src_extra:
            print(f"      unexpected keys: em={em_extra} fs={fs_extra} src={src_extra}")
        if args.write:
            env["expected_metadata"] = em
            env["field_status"] = fs
            env["field_source"] = src
            gt.write_text(json.dumps(env, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{len(books)} books checked, {deviating} deviated from the 49-field schema")
    if deviating and not args.write:
        print("Re-run with --write to normalize them.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
