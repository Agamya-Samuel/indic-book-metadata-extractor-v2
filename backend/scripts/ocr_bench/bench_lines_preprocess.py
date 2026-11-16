#!/usr/bin/env python3
"""Measure preprocessing effects on the Telugu *line model* (production engine).

The Tesseract preprocessing benchmark (`bench_preprocess.py`) showed that the
old default pipeline rescaled every 300-DPI page 1.5x to 450 DPI and that this
hurt Tesseract (learnings/027). Production Telugu, however, runs
`harsha-desaraju/telugu-ocr-model`, which has no DPI metadata and recognises
line crops. It may prefer the extra pixels — so the fix must be measured on the
engine we actually ship, not inferred from Tesseract.

Variants, same pages, production code path (`ocr_line_model.run_line_ocr`):

  raw_300dpi          — the 300-DPI render, untouched
  pipeline_default    — DEFAULT_PREPROCESSING_CONFIG, source_dpi = OCR_RENDER_DPI
                        (current behaviour: no rescale at 300 DPI)
  legacy_upscale_450  — DEFAULT_PREPROCESSING_CONFIG with source_dpi = 200, i.e.
                        the pre-027 behaviour (1.5x to 450 DPI)

Also records line-crop widths: the model returns "" for crops wider than its
`max_image_width` after scaling to `image_height`, so upscaling can push lines
over a hard limit.

Usage:
    HF_HUB_OFFLINE=1 TESSDATA_PREFIX=/tmp/ocr-eval/tessdata_fast \\
      ~/.cache/ocr-line-venv/bin/python backend/scripts/ocr_bench/bench_lines_preprocess.py \\
        --books 8 --pages 3 --out benchmarks/reports/ocr-lines-preprocess-bench.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

import fitz
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bench_lang_config import cer, norm, telugu_pages, wer  # noqa: E402

from app.services import ocr_line_model  # noqa: E402
from app.services.preprocessing import DEFAULT_PREPROCESSING_CONFIG, run_pipeline  # noqa: E402

VARIANTS = ("raw_300dpi", "pipeline_default", "legacy_upscale_450")


def _max_crop_width(model, img: Image.Image) -> tuple[int, int]:
    """Return (widest line crop, number of crops over the model's width limit).

    The model scales a crop to ``image_height`` before recognition, so a crop is
    rejected once its width exceeds ``height * max_image_width / image_height``.
    """
    boxes = ocr_line_model._line_boxes(img)
    widest = 0
    over = 0
    for box in boxes:
        width = box["bbox"]["w"]
        height = box["bbox"]["h"]
        if width <= 0 or height <= 0:
            continue
        widest = max(widest, width)
        limit = int(height * model.config.max_image_width / model.config.image_height)
        if limit >= 32 and width > limit:
            over += 1
    return widest, over


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--books", type=int, default=8)
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--decode", default="ctc")
    ap.add_argument(
        "--variants",
        default=",".join(VARIANTS),
        help="comma-separated subset of: " + ", ".join(VARIANTS),
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    variants = tuple(v.strip() for v in args.variants.split(",") if v.strip())
    unknown = set(variants) - set(VARIANTS)
    if unknown:
        print(f"ERROR: unknown variants: {sorted(unknown)}", file=sys.stderr)
        return 2

    pages = telugu_pages(args.books, args.pages)
    if not pages:
        return 1

    t0 = time.time()
    model, tokenizer = ocr_line_model._load_model()
    print(f"model loaded in {time.time() - t0:.1f}s (decode={args.decode})", file=sys.stderr)

    tmpdir = Path(tempfile.mkdtemp(prefix="ocr_lines_pp_bench_"))
    rows: list[dict] = []
    for n, item in enumerate(pages, 1):
        doc = fitz.open(item["pdf"])
        pix = doc[item["page"] - 1].get_pixmap(dpi=args.dpi)
        raw = tmpdir / f"{item['id']}.png"
        pix.save(str(raw))
        doc.close()

        for variant in variants:
            image_path = raw
            if variant == "pipeline_default":
                image_path = tmpdir / f"{item['id']}__default.png"
                run_pipeline(raw, DEFAULT_PREPROCESSING_CONFIG, image_path)
            elif variant == "legacy_upscale_450":
                image_path = tmpdir / f"{item['id']}__legacy.png"
                run_pipeline(raw, DEFAULT_PREPROCESSING_CONFIG, image_path, source_dpi=200)

            with Image.open(image_path) as img:
                img = img.convert("RGB")
                widest, over_limit = _max_crop_width(model, img)
                started = time.time()
                out = ocr_line_model.run_line_ocr(img, image_path, "tel")
                elapsed = time.time() - started

            pred = norm(out.get("full_text") or "")
            ref = norm(item["ref"])
            row = {
                "id": item["id"],
                "book": item["book"],
                "page": item["page"],
                "variant": variant,
                "cer": round(cer(pred, ref), 4),
                "wer": round(wer(pred, ref), 4),
                "lines": out.get("word_count", 0),
                "widest_crop": widest,
                "over_limit_lines": over_limit,
                "pred_chars": len(pred),
                "ref_chars": len(ref),
                "sec": round(elapsed, 3),
            }
            rows.append(row)
            print(
                f"[{n}/{len(pages)}] {item['id'][:36]:36s} {variant:19s} "
                f"CER={row['cer']:.3f} WER={row['wer']:.3f} lines={row['lines']} "
                f"widest={widest} over={over_limit} {elapsed:.2f}s",
                file=sys.stderr,
            )

    summary = []
    for variant in variants:
        sel = [r for r in rows if r["variant"] == variant]
        cers = [r["cer"] for r in sel]
        wers = [r["wer"] for r in sel]
        summary.append(
            {
                "variant": variant,
                "pages": len(sel),
                "median_cer": round(statistics.median(cers), 4),
                "mean_cer": round(statistics.mean(cers), 4),
                "median_wer": round(statistics.median(wers), 4),
                "mean_lines": round(statistics.mean(r["lines"] for r in sel), 1),
                "mean_widest_crop": round(statistics.mean(r["widest_crop"] for r in sel)),
                "total_over_limit_lines": sum(r["over_limit_lines"] for r in sel),
                "sec_per_page": round(statistics.mean(r["sec"] for r in sel), 3),
            }
        )

    paired = {}
    if "raw_300dpi" in variants:
        base = {r["id"]: r for r in rows if r["variant"] == "raw_300dpi"}
        for variant in variants:
            if variant == "raw_300dpi":
                continue
            other = {r["id"]: r for r in rows if r["variant"] == variant}
            deltas = [other[i]["cer"] - base[i]["cer"] for i in base if i in other]
            if not deltas:
                continue
            paired[variant] = {
                "mean_delta_cer": round(statistics.mean(deltas), 4),
                "median_delta_cer": round(statistics.median(deltas), 4),
                "pages_worse": sum(1 for d in deltas if d > 1e-9),
                "pages_better": sum(1 for d in deltas if d < -1e-9),
                "pages_equal": sum(1 for d in deltas if abs(d) <= 1e-9),
            }

    print("\nSUMMARY")
    for s in summary:
        print(
            f"  {s['variant']:19s} medCER={s['median_cer']:.3f} meanCER={s['mean_cer']:.3f} "
            f"medWER={s['median_wer']:.3f} lines={s['mean_lines']:.1f} "
            f"widest={s['mean_widest_crop']} over_limit={s['total_over_limit_lines']} "
            f"{s['sec_per_page']:.2f}s/p"
        )
    for variant, p in paired.items():
        print(
            f"  {variant:19s} vs raw: meanΔCER={p['mean_delta_cer']:+.4f} "
            f"medΔCER={p['median_delta_cer']:+.4f} worse={p['pages_worse']} "
            f"better={p['pages_better']} equal={p['pages_equal']}"
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {
                    "engine": "telugu-ocr-model",
                    "decode": args.decode,
                    "dpi": args.dpi,
                    "summary": summary,
                    "paired_vs_raw": paired,
                    "rows": rows,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"report: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
