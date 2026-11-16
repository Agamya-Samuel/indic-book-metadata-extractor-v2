#!/usr/bin/env python3
"""Measure Tesseract language-configuration effects on real Indic scans.

This isolates one question from the OCR engine question: given the *same*
Tesseract build and the *same* page images, what changes when the ``lang``
flag changes (``tel`` vs ``tel+eng`` vs ``eng``), when the traineddata variant
changes (fast vs best), and when the PSM changes?

The suspicion under test: a combined ``tel+eng`` / ``hin+eng`` recognition
model lets the large English LSTM explain Indic glyphs as Latin rubble, and an
upload mislabelled as Telugu sends Hindi pages through ``tel+eng``.

Telugu references come from the repo's Wikisource-verified page text
(``tests/fixtures/ground_truth/tel/*/wikisource_gt.json``). Hindi references
come from the IndicVisionBench ``ocr`` bundle produced by
``fetch_indicvision_hindi.py`` (real printed Hindi pages with verified text),
because the Hindi books in the repo have metadata-only ground truth.

Usage:
    TESSDATA_PREFIX=/path/to/tessdata_fast \\
      backend/.venv/bin/python backend/scripts/ocr_bench/bench_lang_config.py \\
        --lang tel --books 8 --pages 2 --configs tel@3,tel+eng@3,eng@3,tel@6
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

import fitz
import Levenshtein
import pytesseract
from PIL import Image

GT_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ground_truth"
HIN_BUNDLE = Path("/tmp/hin_bundle")

TELUGU = re.compile(r"[\u0C00-\u0C7F]")
DEVANAGARI = re.compile(r"[\u0900-\u097F]")
LATIN = re.compile(r"[A-Za-z]")
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


def norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def cer(pred: str, ref: str) -> float:
    return Levenshtein.distance(pred, ref) / len(ref) if ref else 0.0


def wer(pred: str, ref: str) -> float:
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


def script_counts(text: str) -> dict:
    # Count script codepoints (including combining marks) and Latin letters.
    # Combining matras are not `LETTER`, so they must be in the denominator or
    # a Telugu share can exceed 1.0.
    total_letters = len(LETTER.findall(text))
    tel = sum(
        1 for ch in text if "\u0C00" <= ch <= "\u0C7F" and unicodedata.category(ch)[0] in ("L", "M")
    )
    dev = sum(
        1 for ch in text if "\u0900" <= ch <= "\u097F" and unicodedata.category(ch)[0] in ("L", "M")
    )
    lat = len(LATIN.findall(text))
    # Denominator: every letter or combining mark. Indic marks are category M,
    # so an L-only denominator would under-count matras and inflate shares.
    script_total = sum(1 for ch in text if unicodedata.category(ch)[0] in ("L", "M"))
    return {
        "letters": total_letters,
        "telugu": tel,
        "devanagari": dev,
        "latin": lat,
        "telugu_share": round(tel / script_total, 4) if script_total else 0.0,
        "devanagari_share": round(dev / script_total, 4) if script_total else 0.0,
        "latin_share": round(lat / script_total, 4) if script_total else 0.0,
    }


def parse_config(token: str) -> tuple[str, int]:
    lang, _, psm = token.partition("@")
    return lang, int(psm or 3)


def ocr_page(image_path: Path, lang: str, psm: int) -> tuple[str, float]:
    config = f"--psm {psm} --oem 1 --dpi 300"
    with Image.open(image_path) as img:
        data = pytesseract.image_to_data(
            img,
            lang=lang,
            config=config,
            output_type=pytesseract.Output.DICT,
        )
    parts: list[str] = []
    confs: list[int] = []
    for i, raw in enumerate(data["text"]):
        text = str(raw).strip()
        conf = str(data["conf"][i]).strip()
        if not text or not conf.lstrip("-").isdigit():
            continue
        if int(conf) < 0:
            continue
        parts.append(text)
        confs.append(int(conf))
    return " ".join(parts), (statistics.mean(confs) if confs else 0.0)


def telugu_pages(books: int, per_book: int) -> list[dict]:
    out: list[dict] = []
    candidates = sorted(GT_ROOT.glob("tel/*/wikisource_gt.json"))
    used = 0
    skipped_no_pdf = 0
    for gt_path in candidates:
        book_dir = gt_path.parent
        pdf = book_dir / "original.pdf"
        if not pdf.exists():
            skipped_no_pdf += 1
            continue
        data = json.loads(gt_path.read_text(encoding="utf-8"))
        usable: list[tuple[int, str]] = []
        seen: set[str] = set()
        for entry in data.get("pages") or []:
            if entry.get("markup_residue"):
                continue
            ref = norm(entry.get("text") or "")
            if len(ref) < 60 or ref in seen:
                continue
            counts = script_counts(ref)
            # Body pages only: front matter and English reproductions are not
            # a Telugu OCR problem and dominate CER noise.
            if counts["telugu_share"] < 0.55:
                continue
            page_no = entry.get("page")
            if not isinstance(page_no, int) or page_no < 1:
                continue
            seen.add(ref)
            usable.append((page_no, ref))
        if not usable:
            continue
        if len(usable) <= per_book:
            picks = usable
        else:
            step = (len(usable) - 1) / (per_book - 1) if per_book > 1 else 0
            picks = [usable[round(i * step)] for i in range(per_book)]
        doc = fitz.open(pdf)
        for page_no, ref in picks:
            if page_no > doc.page_count:
                continue
            out.append(
                {
                    "id": f"{book_dir.name}__p{page_no}",
                    "book": book_dir.name,
                    "page": page_no,
                    "ref": ref,
                    "pdf": pdf,
                }
            )
        doc.close()
        used += 1
        if used >= books:
            break
    print(
        f"Telugu: {len(out)} pages from {used} books "
        f"({skipped_no_pdf} GT books without a local PDF skipped)",
        file=sys.stderr,
    )
    return out


def hindi_pages(limit: int) -> list[dict]:
    manifest = HIN_BUNDLE / "manifest.jsonl"
    if not manifest.exists():
        return []
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    out = []
    for row in rows[:limit]:
        img = HIN_BUNDLE / row["image"]
        if img.exists():
            out.append(
                {
                    "id": row["id"],
                    "book": "indicvisionbench_hindi",
                    "page": row["id"],
                    "ref": norm(row["ref"]),
                    "image": img,
                }
            )
    print(f"Hindi: {len(out)} IndicVisionBench pages", file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=["tel", "hin"], required=True)
    ap.add_argument("--books", type=int, default=8)
    ap.add_argument("--pages", type=int, default=2, help="Pages per Telugu book")
    ap.add_argument("--pages-limit", type=int, default=24, help="Hindi pages")
    ap.add_argument("--configs", default="tel@3,tel+eng@3,eng@3")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if not os.environ.get("TESSDATA_PREFIX"):
        print("ERROR: set TESSDATA_PREFIX to a tessdata dir.", file=sys.stderr)
        return 2
    configs = [parse_config(c) for c in args.configs.split(",") if c.strip()]

    pages = telugu_pages(args.books, args.pages) if args.lang == "tel" else hindi_pages(args.pages_limit)
    if not pages:
        print("No pages selected.", file=sys.stderr)
        return 1

    rows: list[dict] = []
    tmpdir = Path(tempfile.mkdtemp(prefix="ocr_lang_bench_"))
    started = time.time()
    for n, item in enumerate(pages, 1):
        if "pdf" in item:
            doc = fitz.open(item["pdf"])
            pix = doc[item["page"] - 1].get_pixmap(dpi=args.dpi)
            image_path = tmpdir / f"{item['id']}.png"
            pix.save(str(image_path))
            doc.close()
        else:
            image_path = item["image"]

        for lang, psm in configs:
            t0 = time.time()
            try:
                pred, conf = ocr_page(image_path, lang, psm)
            except Exception as exc:  # noqa: BLE001 - report bad configs, keep going
                print(f"  FAIL {item['id']} {lang}@{psm}: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            counts = script_counts(pred)
            row = {
                "id": item["id"],
                "book": item["book"],
                "page": item["page"],
                "lang": lang,
                "psm": psm,
                "cer": round(cer(pred, item["ref"]), 4),
                "wer": round(wer(pred, item["ref"]), 4),
                "conf": round(conf, 1),
                "chars": len(pred),
                "ref_chars": len(item["ref"]),
                "sec": round(time.time() - t0, 3),
                **counts,
                "sample": pred[:180],
            }
            rows.append(row)
            print(
                f"[{n}/{len(pages)}] {item['id'][:44]:44s} {lang:>7s}@{psm} "
                f"CER={row['cer']:.3f} WER={row['wer']:.3f} "
                f"lat={row['latin_share']:.2f} tel={row['telugu_share']:.2f} dev={row['devanagari_share']:.2f}",
                file=sys.stderr,
            )

    summary = []
    for lang, psm in configs:
        sel = [r for r in rows if r["lang"] == lang and r["psm"] == psm]
        if not sel:
            continue
        cers = sorted(r["cer"] for r in sel)
        wers = sorted(r["wer"] for r in sel)
        summary.append(
            {
                "config": f"{lang}@{psm}",
                "pages": len(sel),
                "median_cer": round(statistics.median(cers), 4),
                "mean_cer": round(statistics.mean(cers), 4),
                "median_wer": round(statistics.median(wers), 4),
                "mean_latin_share": round(statistics.mean(r["latin_share"] for r in sel), 4),
                "mean_telugu_share": round(statistics.mean(r["telugu_share"] for r in sel), 4),
                "mean_devanagari_share": round(statistics.mean(r["devanagari_share"] for r in sel), 4),
                "sec_per_page": round(statistics.mean(r["sec"] for r in sel), 3),
            }
        )

    print("\nSUMMARY")
    for s in summary:
        print(
            f"  {s['config']:>12s}  medCER={s['median_cer']:.3f} meanCER={s['mean_cer']:.3f} "
            f"medWER={s['median_wer']:.3f} latin={s['mean_latin_share']:.2f} "
            f"tel={s['mean_telugu_share']:.2f} dev={s['mean_devanagari_share']:.2f} "
            f"{s['sec_per_page']:.2f}s/p"
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {
                    "lang": args.lang,
                    "tessdata": os.environ.get("TESSDATA_PREFIX"),
                    "dpi": args.dpi,
                    "elapsed_sec": round(time.time() - started, 1),
                    "summary": summary,
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
