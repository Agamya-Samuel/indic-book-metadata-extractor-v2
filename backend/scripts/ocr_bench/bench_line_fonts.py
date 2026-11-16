#!/usr/bin/env python3
"""Score the Telugu line model on a controlled typeface set.

Consumes the manifest produced by ``bench_fonts.py`` (or the render helper in
the report's reproduction steps). Each page has the same reference passage
rendered with a different typeface, so CER differences are font effects.

Requires the line-model venv (torch + transformers 4.46) and Telugu tessdata
for line-box detection.

Usage:
    TESSDATA_PREFIX=/tmp/ocr-eval/tessdata_fast \
      ~/.cache/ocr-line-venv/bin/python backend/scripts/ocr_bench/bench_line_fonts.py \
        --bundle /tmp/ocr-eval/font_renders/tel --decode joint
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import Levenshtein
import pytesseract
from PIL import Image
from transformers import AutoModel, AutoTokenizer


def norm(s: str) -> str:
    return " ".join(s.split())


def cer(p: str, r: str) -> float:
    return Levenshtein.distance(p, r) / len(r) if r else 0.0


def wer(p: str, r: str) -> float:
    ps, rs = p.split(), r.split()
    if not rs:
        return 0.0
    prev = list(range(len(rs) + 1))
    for i, pw in enumerate(ps, 1):
        cur = [i]
        for j, rw in enumerate(rs, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (pw != rw)))
        prev = cur
    return prev[-1] / len(rs)


def line_boxes(img: Image.Image) -> list[tuple[int, int, int, int]]:
    d = pytesseract.image_to_data(img, lang="tel", config="--psm 6", output_type=pytesseract.Output.DICT)
    groups: dict[tuple[int, int, int], list[int]] = {}
    for i in range(len(d["text"])):
        if not str(d["text"][i]).strip():
            continue
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        x, y, w, h = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
        g = groups.setdefault(key, [10**9, 10**9, 0, 0])
        g[0] = min(g[0], x)
        g[1] = min(g[1], y)
        g[2] = max(g[2], x + w)
        g[3] = max(g[3], y + h)
    return [tuple(b) for b in sorted(groups.values(), key=lambda b: (b[1], b[0])) if b[2] > b[0] and b[3] > b[1]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--decode", default="ctc")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    rows = [
        json.loads(line)
        for line in (args.bundle / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    model = AutoModel.from_pretrained("harsha-desaraju/telugu-ocr-model", trust_remote_code=True).eval()
    tokenizer = AutoTokenizer.from_pretrained("harsha-desaraju/telugu-ocr-model", trust_remote_code=True)

    results = []
    for row in rows:
        img = Image.open(args.bundle / row["image"]).convert("RGB")
        t0 = time.time()
        boxes = line_boxes(img)
        crops = [img.crop(box) for box in boxes]
        texts = model.transcribe(crops, tokenizer, decode=args.decode)
        pred = norm(" ".join(texts))
        ref = norm(row["ref"])
        results.append(
            {
                "id": row["id"],
                "font": row.get("font"),
                "mode": row.get("mode", "clean"),
                "cer": round(cer(pred, ref), 4),
                "wer": round(wer(pred, ref), 4),
                "lines": len(crops),
                "ref_chars": len(ref),
                "pred_chars": len(pred),
                "sec": round(time.time() - t0, 2),
                "pred": pred,
            }
        )
        print(
            f"  {row['id']:38s} {args.decode:5s} CER={results[-1]['cer']:.3f} "
            f"WER={results[-1]['wer']:.3f} lines={len(crops)} {results[-1]['sec']:.1f}s"
        )

    summary = {
        "decode": args.decode,
        "pages": len(results),
        "median_cer": round(statistics.median(r["cer"] for r in results), 4),
        "mean_cer": round(statistics.mean(r["cer"] for r in results), 4),
        "median_wer": round(statistics.median(r["wer"] for r in results), 4),
        "sec_per_page": round(statistics.mean(r["sec"] for r in results), 2),
    }
    print("SUMMARY", json.dumps(summary))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({**summary, "rows": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
