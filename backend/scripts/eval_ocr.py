#!/usr/bin/env python3
"""Measure OCR-stage error against Wikisource verified page text.

For each Telugu book with a ``wikisource_gt.json`` (human-verified pages), render the
same PDF pages, run the pipeline OCR (``app.services.ocr_service.run_ocr``), and compute
Character/Word Error Rate against the verified text. This measures the OCR half of the
pipeline without needing an LLM.

Requires Telugu tessdata: set ``TESSDATA_PREFIX`` to a dir containing ``tel.traineddata``
and ``eng.traineddata``.

Usage:
    cd backend
    TESSDATA_PREFIX=/tmp/tessdata uv run python -m scripts.eval_ocr --limit 3 --pages 4
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF
import Levenshtein

from app.services.ocr_service import run_ocr
from app.services.preprocessing import run_pipeline

GT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth"


def norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def wer(pred: str, ref: str) -> float:
    """Token-level Levenshtein / reference length."""
    p, r = pred.split(), ref.split()
    if not r:
        return 0.0
    prev = list(range(len(r) + 1))
    for i, pw in enumerate(p, 1):
        cur = [i]
        for j, rw in enumerate(r, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (pw != rw)))
        prev = cur
    return prev[-1] / len(r)


def cer(pred: str, ref: str) -> float:
    return Levenshtein.distance(pred, ref) / len(ref) if ref else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=3, help="Max books (default 3)")
    ap.add_argument("--pages", type=int, default=4, help="Max pages per book (default 4)")
    ap.add_argument("--root", type=Path, default=GT_ROOT)
    ap.add_argument("--out", type=Path, default=None, help="Write JSON report here")
    ap.add_argument(
        "--preprocess",
        choices=["none", "sauvola", "adaptive", "otsu"],
        default="none",
        help="Binarization to apply before OCR (default none)",
    )
    ap.add_argument("--denoise", action="store_true", help="Denoise before OCR")
    ap.add_argument("--dpi", type=int, default=300, help="Render DPI (default 300)")
    args = ap.parse_args()

    if not os.environ.get("TESSDATA_PREFIX"):
        print("WARNING: TESSDATA_PREFIX not set; Telugu tessdata may be missing.", file=sys.stderr)

    books = [p for p in sorted(args.root.glob("tel/*/wikisource_gt.json"))]
    books = [p for p in books if json.loads(p.read_text(encoding="utf-8")).get("pages")]
    print(f"OCR eval on {min(args.limit, len(books))} of {len(books)} Telugu books with verified text\n")

    report: list[dict] = []
    for gt_path in books[: args.limit]:
        book_dir = gt_path.parent
        pdf_path = book_dir / "original.pdf"
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        if not pdf_path.exists():
            continue
        doc = fitz.open(pdf_path)
        rows: list[dict] = []
        for entry in gt["pages"][: args.pages]:
            if entry.get("markup_residue"):
                continue
            ref = norm(entry["text"])
            if len(ref) < 30:  # near-empty title/cover pages fake enormous CER
                continue
            page_no = entry["page"]
            pix = doc[page_no - 1].get_pixmap(dpi=args.dpi)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                pix.save(tmp.name)
                ocr_input = Path(tmp.name)
                if args.preprocess != "none" or args.denoise:
                    ocr_input = Path(tmp.name + ".pp.png")
                    run_pipeline(
                        Path(tmp.name),
                        {
                            "binarization": None if args.preprocess == "none" else args.preprocess,
                            "denoise": args.denoise,
                            "upscale_to_300dpi": False,  # already rendered at 300 dpi
                        },
                        ocr_input,
                    )
                out = run_ocr(ocr_input, "tel", page_position=page_no - 1)
            os.unlink(tmp.name)
            if ocr_input != Path(tmp.name):
                os.unlink(ocr_input)
            pred = norm(out.get("full_text") or "")
            rows.append(
                {
                    "page": page_no,
                    "cer": round(cer(pred, ref), 4),
                    "wer": round(wer(pred, ref), 4),
                    "ref_chars": len(ref),
                }
            )
        doc.close()
        if not rows:
            continue
        mean_cer = sum(r["cer"] for r in rows) / len(rows)
        mean_wer = sum(r["wer"] for r in rows) / len(rows)
        report.append({"book": book_dir.name, "pages": len(rows), "cer": round(mean_cer, 4), "wer": round(mean_wer, 4)})
        print(f"  {book_dir.name[:48]:48s} pages={len(rows):2d}  CER={mean_cer:.3f}  WER={mean_wer:.3f}")

    if report:
        cers = sorted(r["cer"] for r in report)
        wers = sorted(r["wer"] for r in report)
        mid = len(report) // 2
        print(
            f"\nOVERALL  mean CER={sum(cers) / len(cers):.3f}  median CER={cers[mid]:.3f}  "
            f"median WER={wers[mid]:.3f}  ({len(report)} books)"
        )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"report: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
