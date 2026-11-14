"""Score node_acc.py JSONL output against a book's ground truth (provisional).

Merges the per-batch `parsed` objects into one predicted dict and scores it
with the shared validator. Ground truth is unverified — treat as provisional.

Usage:
    python -m scripts.score_acc --jsonl /tmp/acc_qwen35_4b.jsonl \
        --book tests/fixtures/ground_truth/tel/2015.373190.Athma-Charitramu
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", required=True, type=Path)
    ap.add_argument("--book", required=True, type=Path)
    args = ap.parse_args()

    env = json.loads((args.book / "expected_metadata.json").read_text(encoding="utf-8"))
    expected = env.get("expected_metadata", env)
    sid = f"{env.get('language', '?')}/{args.book.name}"

    merged: dict = {}
    records = 0
    models: set[str] = set()
    for line in args.jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        records += 1
        if rec.get("model"):
            models.add(rec["model"])
        for key, value in (rec.get("parsed") or {}).items():
            if value not in (None, ""):
                merged[key] = value

    ev = evaluate_book(sample_id=sid, expected=expected, predicted=merged, all_fields=ALL_FIELDS)
    absent = sum(1 for r in ev.field_results if not r.expected_present)
    halluc = sum(1 for r in ev.field_results if r.predicted_present and not r.expected_present)

    print(f"model(s)={sorted(models)} records={records} merged_non_null={len(merged)}")
    print(
        f"  TP={ev.tp()} FP={ev.fp()} FN={ev.fn()}  mean_token_f1={ev.mean_token_f1():.3f}  "
        f"exact={ev.exact_match_rate():.3f} normalized={ev.normalized_match_rate():.3f}  "
        f"hallucinations={halluc}/{absent}"
    )
    print("  per-field (present on either side):")
    for r in ev.field_results:
        if r.expected_present or r.predicted_present:
            print(
                f"    {r.field_name:22s} exp={str(r.expected)[:26]:26s} "
                f"pred={str(r.predicted)[:30]:30s} f1={r.token_f1}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
