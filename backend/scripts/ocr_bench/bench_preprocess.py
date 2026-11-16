#!/usr/bin/env python3
"""Measure the effect of the pipeline's default preprocessing on OCR.

``page_tasks._insert_page`` attaches ``DEFAULT_PREPROCESSING_CONFIG`` to every
rendered page, and ``ocr_tasks`` runs it before OCR. That config assumes a
200-DPI source and upscales to 300 DPI, but ``pdf_service.render_full_page``
already renders at ``OCR_RENDER_DPI`` (300). The result is a 450-DPI image
passed to Tesseract with ``--dpi 300``.

This compares raw 300-DPI renders with that exact default pipeline and with
its individual operations removed, on the same Wikisource-verified pages.

Usage:
    TESSDATA_PREFIX=/path/to/tessdata_fast \
      backend/.venv/bin/python backend/scripts/ocr_bench/bench_preprocess.py \
        --books 8 --pages 3 --out report.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

import cv2
import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bench_lang_config import cer, ocr_page, telugu_pages, wer  # noqa: E402

from app.services.preprocessing import DEFAULT_PREPROCESSING_CONFIG, run_pipeline  # noqa: E402

VARIANTS: dict[str, dict] = {
    "raw_300dpi": {},
    "pipeline_default": dict(DEFAULT_PREPROCESSING_CONFIG),
    "no_upscale": {**DEFAULT_PREPROCESSING_CONFIG, "upscale_to_300dpi": False},
    "upscale_only": {
        **DEFAULT_PREPROCESSING_CONFIG,
        "deskew": False,
        "remove_borders": False,
    },
    "deskew_borders_no_upscale": {
        **DEFAULT_PREPROCESSING_CONFIG,
        "upscale_to_300dpi": False,
    },
    "grayscale_only": {
        **DEFAULT_PREPROCESSING_CONFIG,
        "upscale_to_300dpi": False,
        "deskew": False,
        "remove_borders": False,
    },
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--books", type=int, default=8)
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--lang", default="tel@3")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if not os.environ.get("TESSDATA_PREFIX"):
        print("ERROR: set TESSDATA_PREFIX to a tessdata dir.", file=sys.stderr)
        return 2

    lang, _, psm = args.lang.partition("@")
    psm = int(psm or 3)
    pages = telugu_pages(args.books, args.pages)
    if not pages:
        return 1

    tmpdir = Path(tempfile.mkdtemp(prefix="ocr_preprocess_bench_"))
    rows: list[dict] = []
    for n, item in enumerate(pages, 1):
        doc = fitz.open(item["pdf"])
        pix = doc[item["page"] - 1].get_pixmap(dpi=args.dpi)
        raw = tmpdir / f"{item['id']}.png"
        pix.save(str(raw))
        doc.close()

        for name, cfg in VARIANTS.items():
            image_path = raw
            elapsed_pp = 0.0
            if cfg:
                image_path = tmpdir / f"{item['id']}__{name}.png"
                t0 = time.time()
                run_pipeline(raw, cfg, image_path)
                elapsed_pp = time.time() - t0
            img = cv2.imread(str(image_path))
            height, width = img.shape[:2] if img is not None else (0, 0)

            t0 = time.time()
            pred, conf = ocr_page(image_path, lang, psm)
            elapsed = time.time() - t0
            row = {
                "id": item["id"],
                "book": item["book"],
                "page": item["page"],
                "variant": name,
                "cer": round(cer(pred, item["ref"]), 4),
                "wer": round(wer(pred, item["ref"]), 4),
                "conf": round(conf, 1),
                "width": width,
                "height": height,
                "preprocess_sec": round(elapsed_pp, 3),
                "ocr_sec": round(elapsed, 3),
            }
            rows.append(row)
            print(
                f"[{n}/{len(pages)}] {item['id'][:40]:40s} {name:24s} "
                f"CER={row['cer']:.3f} WER={row['wer']:.3f} "
                f"{width}x{height} pp={elapsed_pp:.2f}s ocr={elapsed:.2f}s",
                file=sys.stderr,
            )

    summary = []
    for name in VARIANTS:
        sel = [r for r in rows if r["variant"] == name]
        cers = sorted(r["cer"] for r in sel)
        wers = sorted(r["wer"] for r in sel)
        summary.append(
            {
                "variant": name,
                "pages": len(sel),
                "median_cer": round(statistics.median(cers), 4),
                "mean_cer": round(statistics.mean(cers), 4),
                "median_wer": round(statistics.median(wers), 4),
                "mean_conf": round(statistics.mean(r["conf"] for r in sel), 1),
                "mean_width": round(statistics.mean(r["width"] for r in sel)),
                "mean_preprocess_sec": round(statistics.mean(r["preprocess_sec"] for r in sel), 3),
                "mean_ocr_sec": round(statistics.mean(r["ocr_sec"] for r in sel), 3),
            }
        )

    print("\nSUMMARY")
    for s in summary:
        print(
            f"  {s['variant']:26s} medCER={s['median_cer']:.3f} meanCER={s['mean_cer']:.3f} "
            f"medWER={s['median_wer']:.3f} conf={s['mean_conf']:.1f} "
            f"width={s['mean_width']} pp={s['mean_preprocess_sec']:.2f}s ocr={s['mean_ocr_sec']:.2f}s"
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps({"lang": args.lang, "dpi": args.dpi, "summary": summary, "rows": rows}, indent=2),
            encoding="utf-8",
        )
        print(f"report: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
