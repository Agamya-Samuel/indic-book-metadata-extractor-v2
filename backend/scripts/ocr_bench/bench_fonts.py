#!/usr/bin/env python3
"""Isolate typeface and scan-quality effects from language-model effects.

Renders the *same* verified passage with several Indic typefaces at 300 DPI,
then applies controlled degradations (blur, low contrast, low resolution,
noise/rotation). Every image is OCR'd with the language's Tesseract model, so
the CER difference is attributable to glyph style or image quality — not to a
different book, layout, or ground-truth convention.

Telugu text comes from a Wikisource-verified page; Hindi text from the
IndicVisionBench OCR bundle. Both are normalized, body-text passages.

Usage:
    TESSDATA_PREFIX=/tmp/ocr-eval/tessdata_fast \
      backend/.venv/bin/python backend/scripts/ocr_bench/bench_fonts.py \
        --lang tel --fonts-dir /tmp/ocr-eval/fonts/tel --out report.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

import cv2
import fitz
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_lang_config import cer, norm, ocr_page, script_counts, telugu_pages, wer  # noqa: E402

HIN_BUNDLE = Path("/tmp/hin_bundle")


def pick_telugu_text() -> str:
    pages = telugu_pages(3, 3)
    best = max(pages, key=lambda p: (len(p["ref"]), script_counts(p["ref"])["telugu_share"]))
    return best["ref"][:1400]


def pick_hindi_text() -> str:
    manifest = HIN_BUNDLE / "manifest.jsonl"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    row = max(rows[:5], key=lambda r: len(r["ref"]))
    return norm(row["ref"])[:1400]


def render_page(
    text: str,
    font_path: Path,
    out: Path,
    fontsize: float = 11.5,
    text_width: float = 487,
) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_font(fontname="body", fontfile=str(font_path))
    rect = fitz.Rect(54, 54, 54 + text_width, 842 - 54)
    leftover = page.insert_textbox(
        rect,
        text,
        fontname="body",
        fontsize=fontsize,
        lineheight=1.55,
        align=fitz.TEXT_ALIGN_LEFT,
    )
    if leftover < 0:
        raise ValueError(f"text does not fit for {font_path.name}: {leftover}")
    page.get_pixmap(dpi=300).save(str(out))
    doc.close()


def degrade(img: np.ndarray, mode: str) -> np.ndarray:
    if mode == "clean":
        return img
    if mode == "blur":
        return cv2.GaussianBlur(img, (5, 5), 1.0)
    if mode == "low_contrast":
        # Faded ink on aged paper: compress 0-255 into 95-235.
        return np.clip(img.astype(np.float32) * 0.55 + 95, 0, 255).astype(np.uint8)
    if mode == "low_res":
        small = cv2.resize(img, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        return cv2.resize(small, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_CUBIC)
    if mode == "noise_skew":
        noisy = np.clip(
            img.astype(np.float32) + np.random.default_rng(7).normal(0, 18, img.shape),
            0,
            255,
        ).astype(np.uint8)
        h, w = noisy.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), 1.5, 1.0)
        return cv2.warpAffine(noisy, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    raise ValueError(mode)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=["tel", "hin"], required=True)
    ap.add_argument("--fonts-dir", type=Path, required=True)
    ap.add_argument("--fontsize", type=float, default=11.5)
    ap.add_argument("--degradations", default="clean")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if not os.environ.get("TESSDATA_PREFIX"):
        print("ERROR: set TESSDATA_PREFIX to a tessdata dir.", file=sys.stderr)
        return 2

    text = pick_telugu_text() if args.lang == "tel" else pick_hindi_text()
    print(f"{args.lang}: {len(text)} chars reference", file=sys.stderr)
    # Telugu text uses "tel"; Hindi "hin". Never combine with eng.
    ocr_lang = "tel" if args.lang == "tel" else "hin"
    fonts = sorted(args.fonts_dir.glob("*.ttf")) + sorted(args.fonts_dir.glob("*.otf"))
    if not fonts:
        print("No fonts found.", file=sys.stderr)
        return 1
    degradations = [d.strip() for d in args.degradations.split(",") if d.strip()]

    tmpdir = Path(tempfile.mkdtemp(prefix="ocr_font_bench_"))
    rows: list[dict] = []
    for font in fonts:
        base = tmpdir / f"{font.stem}.png"
        try:
            render_page(text, font, base, fontsize=args.fontsize)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {font.name}: {exc}", file=sys.stderr)
            continue
        for mode in degradations:
            image = cv2.imread(str(base), cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue
            processed = degrade(image, mode)
            if mode == "clean":
                path = base
            else:
                path = tmpdir / f"{font.stem}__{mode}.png"
                cv2.imwrite(str(path), processed)
            pred, conf = ocr_page(path, ocr_lang, 3)
            row = {
                "font": font.stem,
                "degradation": mode,
                "cer": round(cer(pred, text), 4),
                "wer": round(wer(pred, text), 4),
                "conf": round(conf, 1),
                "chars": len(pred),
                **script_counts(pred),
                "sample": pred[:180],
            }
            rows.append(row)
            print(
                f"  {font.stem:32s} {mode:12s} CER={row['cer']:.3f} WER={row['wer']:.3f} "
                f"conf={row['conf']:.1f} tel={row['telugu_share']:.2f} dev={row['devanagari_share']:.2f}",
                file=sys.stderr,
            )

    summary = []
    for mode in degradations:
        sel = [r for r in rows if r["degradation"] == mode]
        if not sel:
            continue
        cers = sorted(r["cer"] for r in sel)
        summary.append(
            {
                "degradation": mode,
                "fonts": len(sel),
                "median_cer": round(statistics.median(cers), 4),
                "min_cer": round(min(cers), 4),
                "max_cer": round(max(cers), 4),
                "mean_cer": round(statistics.mean(cers), 4),
            }
        )

    print("\nSUMMARY")
    for s in summary:
        print(
            f"  {s['degradation']:12s} n={s['fonts']} medCER={s['median_cer']:.3f} "
            f"range={s['min_cer']:.3f}-{s['max_cer']:.3f}"
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {"lang": args.lang, "fontsize": args.fontsize, "summary": summary, "rows": rows},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"report: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
