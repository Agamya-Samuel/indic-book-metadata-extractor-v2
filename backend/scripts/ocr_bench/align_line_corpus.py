#!/usr/bin/env python3
"""Recover per-line labels by aligning line-model hypotheses to page GT.

The corpus builder stores Tesseract line boxes plus the whole verified page
text. This runs the current Telugu line model on each crop, concatenates the
line hypotheses, aligns that string to the page text, and cuts the page text
back into per-line labels. Low-similarity lines are discarded, so the labels
stay anchored to verified text even when the current model is wrong.

Usage:
    TESSDATA_PREFIX=/home/agamya/.cache/tessdata_fast \
      /home/agamya/.cache/ocr-ft-venv/bin/python \
        backend/scripts/ocr_bench/align_line_corpus.py \
        --data /home/agamya/.cache/telugu-ocr-ft/data
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import Levenshtein
from PIL import Image
from transformers import AutoModel, AutoTokenizer

TELUGU = re.compile(r"[\u0C00-\u0C7F]")
MODEL = "harsha-desaraju/telugu-ocr-model"


def norm(text: str) -> str:
    return " ".join(text.split())


def telugu_share(text: str) -> float:
    letters = sum(1 for ch in text if ch.isalpha())
    return len(TELUGU.findall(text)) / letters if letters else 0.0


def position_map(source: str, target: str) -> list[int]:
    """Map every source boundary to the nearest target boundary."""
    mapping = [0] * (len(source) + 1)
    matcher = difflib.SequenceMatcher(None, source, target, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                mapping[i1 + k] = j1 + k
            mapping[i2] = j2
        elif tag == "replace":
            n = min(i2 - i1, j2 - j1)
            for k in range(n):
                mapping[i1 + k] = j1 + k
            for k in range(n, i2 - i1):
                mapping[i1 + k] = max(j1, j2 - 1)
            mapping[i2] = j2
        elif tag == "delete":
            for k in range(i2 - i1):
                mapping[i1 + k] = j1
            mapping[i2] = j1
        else:  # insert: no source chars, advance the target boundary
            mapping[i1] = j2
    # Fill any gaps left by the block walk.
    for i in range(1, len(mapping)):
        if mapping[i] < mapping[i - 1]:
            mapping[i] = mapping[i - 1]
    return mapping


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("/home/agamya/.cache/telugu-ocr-ft/data"))
    ap.add_argument("--min-similarity", type=float, default=0.40)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    rows = [json.loads(line) for line in (args.data / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["book"], row["page"])].append(row)
    for page_rows in grouped.values():
        page_rows.sort(key=lambda r: r["line"])
    print(f"pages={len(grouped)} lines={len(rows)}; loading model", file=sys.stderr)

    model = AutoModel.from_pretrained(args.model, trust_remote_code=True).eval()
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)

    aligned: list[dict] = []
    for n, ((book, page), page_rows) in enumerate(grouped.items(), 1):
        images = [Image.open(args.data / row["image"]).convert("RGB") for row in page_rows]
        hypotheses = model.transcribe(images, tokenizer, decode="ctc")
        hypotheses = [norm(str(h)) for h in hypotheses]
        ref = norm(page_rows[0]["page_ref"])
        # Build the concatenated hypothesis and each line's character span.
        parts: list[str] = []
        spans: list[tuple[int, int]] = []
        cursor = 0
        for hyp in hypotheses:
            spans.append((cursor, cursor + len(hyp)))
            parts.append(hyp)
            cursor += len(hyp) + 1
        joined = " ".join(parts)
        mapping = position_map(joined, ref)
        for row, hyp, (start, end) in zip(page_rows, hypotheses, spans):
            t0, t1 = mapping[start], mapping[end]
            label = ref[t0:t1].strip()
            if not hyp or len(label) < 3 or telugu_share(label) < 0.5:
                continue
            similarity = Levenshtein.ratio(hyp, label)
            if similarity < args.min_similarity:
                continue
            aligned.append(
                {
                    **row,
                    "hyp": hyp,
                    "label": label,
                    "similarity": round(similarity, 4),
                }
            )
        if n % 20 == 0:
            print(f"  {n}/{len(grouped)} pages, {len(aligned)} accepted lines", file=sys.stderr)

    out = args.out or (args.data / "aligned.jsonl")
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in aligned), encoding="utf-8")
    sims = [r["similarity"] for r in aligned]
    print(
        f"accepted {len(aligned)}/{len(rows)} lines; mean similarity {statistics.mean(sims):.3f} "
        f"median {statistics.median(sims):.3f}; wrote {out}",
        file=sys.stderr,
    )
    by_book: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        by_book[row["book"]][1] += 1
    for row in aligned:
        by_book[row["book"]][0] += 1
    for book, (kept, total) in sorted(by_book.items()):
        print(f"  {book[:48]:48s} {kept:4d}/{total:4d}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
