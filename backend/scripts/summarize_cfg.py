"""Summarize node_cfg.py JSONL into per-config accuracy + resource tables.

Uses the repo's own validator and the bundle's `expected` metadata, so numbers
are comparable with learnings/005/006/010/013.

Usage:
  .venv/bin/python -m scripts.summarize_cfg --jsonl /tmp/cfg.jsonl \
      --bundle /tmp/bundle_athma.json --bundle /tmp/bundle_andhra.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.schemas.metadata import ALL_METADATA_FIELDS  # noqa: E402
from app.services.extraction_validator import evaluate_book  # noqa: E402

ALL_FIELDS = [f.field_name for f in ALL_METADATA_FIELDS]


def load_bundles(paths: list[Path]) -> dict:
    out = {}
    for p in paths:
        b = json.loads(Path(p).read_text(encoding="utf-8"))
        out[b["book"]] = b
    return out


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", required=True, type=Path)
    ap.add_argument("--bundle", action="append", default=[], type=Path)
    args = ap.parse_args()

    bundles = load_bundles(args.bundle)
    groups: dict[tuple[str, str], list[dict]] = {}
    for line in args.jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        groups.setdefault((r["tag"], r["book"]), []).append(r)

    header = (
        f"{'tag':14s} {'book':16s} {'jsonOK':>6s} {'wall_s':>7s} {'gen':>5s} "
        f"{'pref':>6s} {'minAvail':>8s} {'P':>5s} {'R':>5s} {'F1':>5s} "
        f"{'tokF1':>5s} {'halluc':>8s} {'nonnull':>7s}"
    )
    print(header)
    print("-" * len(header))
    merged_by: dict[tuple[str, str], dict] = {}
    for (tag, book), recs in sorted(groups.items()):
        merged: dict = {}
        for r in recs:
            for k, v in (r.get("parsed") or {}).items():
                if v not in (None, ""):
                    merged[k] = v
        merged_by[(tag, book)] = merged

        jok = sum(1 for r in recs if r.get("json_valid"))
        wall = round(sum(r.get("wall_s", 0) for r in recs), 1)

        def avg(key):
            vals = [r.get(key) for r in recs if r.get(key)]
            return round(sum(vals) / len(vals), 2) if vals else None

        avails = [r["min_avail_mib"] for r in recs if r.get("min_avail_mib")]
        minav = min(avails) if avails else 0

        b = bundles.get(book)
        if b:
            ev = evaluate_book(
                sample_id=f"{b.get('language')}/{book}",
                expected=b["expected"],
                predicted=merged,
                all_fields=ALL_FIELDS,
            )
            p, r, f1 = prf(ev.tp(), ev.fp(), ev.fn())
            absent = sum(1 for x in ev.field_results if not x.expected_present)
            halluc = sum(
                1 for x in ev.field_results if x.predicted_present and not x.expected_present
            )
            print(
                f"{tag:14s} {book[:16]:16s} {jok:3d}/{len(recs):<2d} {wall:7.1f} "
                f"{str(avg('gen_tok_s')):>5s} {str(avg('prefill_tok_s')):>6s} {minav:8.0f} "
                f"{p:5.2f} {r:5.2f} {f1:5.2f} {ev.mean_token_f1():5.2f} "
                f"{halluc:3d}/{absent:<4d} {len(merged):7d}"
            )
        else:
            print(
                f"{tag:14s} {book[:16]:16s} {jok:3d}/{len(recs):<2d} {wall:7.1f} "
                f"{str(avg('gen_tok_s')):>5s} {str(avg('prefill_tok_s')):>6s} {minav:8.0f} (no bundle)"
            )

    print("\n=== temperature-0 determinism (gem_base vs gem_seed7) ===")
    for book in bundles:
        a = merged_by.get(("gem_base", book))
        c = merged_by.get(("gem_seed7", book))
        if a is None or c is None:
            continue
        diffs = sorted(set(a) ^ set(c)) + sorted(
            k for k in set(a) & set(c) if a[k] != c[k]
        )
        print(f"  {book[:24]:24s} identical={not diffs} differing_fields={diffs or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
