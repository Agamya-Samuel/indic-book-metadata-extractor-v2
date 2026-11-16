"""Compare two runs of the same variant to measure determinism.

At temperature 0 with a pinned seed, the same prompt and text should produce the
same values. Anything else is either sampler nondeterminism, a context/cache
change between the runs, or a batch that hit a retry — all of which would make
"the prompt improved accuracy" a claim about noise.

    cd backend
    python -m scripts.prompt_eval.consistency results/V00.a.jsonl results/V00.b.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(paths: list[Path]) -> dict[str, dict]:
    """Map ``variant|sample|batch`` → parsed field dict, keeping the first run."""
    runs: dict[str, dict] = {}
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            variant = record.get("variant")
            sample = record.get("sample_id")
            if variant is None or sample is None:
                continue
            bucket = runs.setdefault(f"{variant}|{sample}", {})
            batch = record["batch"]
            # Keep the first occurrence only, so a resumed file does not count
            # the same call twice.
            bucket.setdefault(batch, record.get("parsed"))
    return runs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--field", default="", help="Restrict to one field name")
    args = parser.parse_args()

    a = _load([args.first])
    b = _load([args.second])
    shared = sorted(set(a) & set(b))
    if not shared:
        print("error: no shared (variant, book) keys — were these the same variant?", flush=True)
        return 2

    compared = agreed = 0
    identical_calls = 0
    total_batches = 0
    differences: list[dict] = []
    missing_batches = 0

    for key in shared:
        batches_a, batches_b = a[key], b[key]
        if set(batches_a) != set(batches_b):
            missing_batches += 1
        for batch in sorted(set(batches_a) & set(batches_b)):
            total_batches += 1
            left = batches_a[batch] or {}
            right = batches_b[batch] or {}
            if left == right:
                identical_calls += 1
            for field_name in sorted(set(left) | set(right)):
                if args.field and field_name != args.field:
                    continue
                compared += 1
                if left.get(field_name) == right.get(field_name):
                    agreed += 1
                elif len(differences) < 50:
                    differences.append(
                        {
                            "book": key.split("|", 1)[1],
                            "batch": batch,
                            "field": field_name,
                            "first": left.get(field_name),
                            "second": right.get(field_name),
                        }
                    )

    agreement = round(agreed / compared, 4) if compared else None
    print(f"books compared:      {len(shared)}")
    print(f"field comparisons:   {compared}")
    print(f"field agreement:     {agreement if agreement is not None else 'n/a'}")
    print(f"identical batch responses: {identical_calls}/{total_batches}")
    if missing_batches:
        print(f"books with differing batch sets: {missing_batches} (a run was incomplete)")

    if differences:
        print("\ndifferences (first 50):")
        for row in differences:
            print(
                f"  {row['book'][:36]:36s} {row['batch']:20s} {row['field']:24s} "
                f"{str(row['first'])[:28]!r} -> {str(row['second'])[:28]!r}"
            )
    elif agreement == 1.0:
        print("\ndeterministic: identical values on every shared field")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
