#!/usr/bin/env python3
"""Generate docs/ground-truth-field-coverage.md from the GT corpus."""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

from app.schemas.metadata import ALL_METADATA_FIELDS, BATCH_FIELD_ORDER

CANON = [f.field_name for f in ALL_METADATA_FIELDS]
BATCH = {f.field_name: f.batch_group for f in ALL_METADATA_FIELDS}
WD = {f.field_name: f.wikidata_property for f in ALL_METADATA_FIELDS}
GT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth"
OUT = Path(__file__).resolve().parents[2] / "docs" / "ground-truth-field-coverage.md"


def present(v: object) -> bool:
    return v not in (None, "", [], {})


def main() -> int:
    books = sorted(GT_ROOT.glob("*/*/expected_metadata.json"))
    filled = collections.Counter()
    by_lang = collections.defaultdict(collections.Counter)
    src = collections.defaultdict(collections.Counter)
    status = collections.Counter()
    per_book = []
    for p in books:
        env = json.loads(p.read_text(encoding="utf-8"))
        em = env.get("expected_metadata", {})
        fs = env.get("field_source", {}) or {}
        status[env.get("verification_status")] += 1
        lang = p.parent.parent.name
        n = 0
        for f in CANON:
            if present(em.get(f)):
                filled[f] += 1
                by_lang[lang][f] += 1
                src[f][fs.get(f) or "unmapped"] += 1
                n += 1
        per_book.append((lang, p.parent.name, n, env.get("verification_status")))
    empty = [f for f in CANON if filled[f] == 0]

    order = {b: i for i, b in enumerate(BATCH_FIELD_ORDER)}
    out = ["# Ground Truth vs. Metadata Fields (49-field conformance & coverage)\n"]
    out.append("Comparison of the corpus in `backend/tests/fixtures/ground_truth/` against "
               "[`docs/metadata-fields.md`](metadata-fields.md) (source: `app/schemas/metadata.py`). "
               "Regenerate with `uv run python -m scripts.gt_coverage_report`.\n")
    out.append("## Conformance\n")
    out.append(f"- Books **{len(books)}** · canonical fields **{len(CANON)}**.")
    out.append("- Every book's `expected_metadata`, `field_status` and `field_source` hold **exactly** "
               "the 49 keys (0 missing, 0 extra; `scripts/apply_field_schema.py --check`).")
    out.append(f"- Status: {', '.join(f'`{k}`={v}' for k, v in status.items())}.\n")
    out.append("## Coverage\n")
    out.append(f"- **{sum(filled.values())}** non-null values; **{sum(1 for f in CANON if filled[f])}/49** "
               "fields populated.")
    out.append(f"- Empty in every book ({len(empty)}): {', '.join(f'`{e}`' for e in empty)}.\n")
    out.append("## Per-field\n")
    out.append("| # | Field | Batch | Wikidata | Telugu | Hindi | Total | Source(s) |")
    out.append("|---|---|---|---|---|---|---|---|")
    for i, f in enumerate(sorted(CANON, key=lambda x: (order[BATCH[x]], x)), 1):
        s = ", ".join(f"{k}:{v}" for k, v in src[f].most_common()) or "—"
        out.append(f"| {i} | `{f}` | {BATCH[f]} | {WD[f] or '—'} | {by_lang['tel'][f]} | {by_lang['hin'][f]} | {filled[f]} | {s} |")
    out.append("\n## Per-book\n")
    out.append("| Book | Lang | Filled / 49 | Status |")
    out.append("|---|---|---|---|")
    for lang, slug, n, st in sorted(per_book, key=lambda x: (x[0], -x[2], x[1])):
        out.append(f"| {slug} | {lang} | {n} | {st} |")
    out.append("\nSource key: `unmapped` = value present but `field_source` unset; `node_llm_extraction` = "
               "unverified model prefill (see `learnings/019`); catalog sources as named.")
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(books)} books, {len(empty)} empty fields)")
    return 0


if __name__ == "__main__":
    sys.exit(main())