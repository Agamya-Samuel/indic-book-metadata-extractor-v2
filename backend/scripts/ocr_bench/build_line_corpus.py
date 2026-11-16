#!/usr/bin/env python3
"""Build a book-level-split Telugu line-crop corpus from verified page text.

Each line is a Tesseract ``--psm 6`` box cropped from the 300-DPI page render.
The page reference is stored on every row; ``align_line_corpus.py`` later aligns
the line model's hypotheses to that reference to recover per-line labels.

Usage:
    TESSDATA_PREFIX=/home/agamya/.cache/tessdata_fast \
      backend/.venv/bin/python backend/scripts/ocr_bench/build_line_corpus.py \
        --out /home/agamya/.cache/telugu-ocr-ft/data --dpi 300
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

GT_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ground_truth"
TELUGU = re.compile(r"[\u0C00-\u0C7F]")
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


def norm(text: str) -> str:
    return " ".join(text.split())


def script_share(text: str) -> float:
    total = sum(1 for ch in text if ch.isalpha())
    tel = len(TELUGU.findall(text))
    return tel / total if total else 0.0


def line_boxes(img: Image.Image) -> list[dict]:
    data = pytesseract.image_to_data(
        img, lang="tel", config="--psm 6", output_type=pytesseract.Output.DICT
    )
    groups: dict[tuple[int, int, int], dict] = {}
    for i, raw in enumerate(data["text"]):
        if not str(raw).strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        box = groups.setdefault(key, {"x": x, "y": y, "right": x + w, "bottom": y + h})
        box["x"] = min(box["x"], x)
        box["y"] = min(box["y"], y)
        box["right"] = max(box["right"], x + w)
        box["bottom"] = max(box["bottom"], y + h)
    ordered = sorted(groups.values(), key=lambda b: (b["y"], b["x"]))
    return [b for b in ordered if b["right"] > b["x"] and b["bottom"] > b["y"]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("/home/agamya/.cache/telugu-ocr-ft/data"))
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--min-ref", type=int, default=60)
    ap.add_argument("--min-telugu", type=float, default=0.55)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    image_root = args.out / "images"
    image_root.mkdir(exist_ok=True)

    gt_paths = sorted(GT_ROOT.glob("tel/*/wikisource_gt.json"))
    all_books = [p.parent.name for p in gt_paths if (p.parent / "original.pdf").exists()]
    # Deterministic book-level split: every fifth book is held out.
    held_out = set(all_books[::5])
    books = []
    pages = []
    rows = []
    manifest_path = args.out / "manifest.jsonl"
    pages_path = args.out / "pages.jsonl"
    manifest_file = manifest_path.open("w", encoding="utf-8")
    pages_file = pages_path.open("w", encoding="utf-8")
    for book_idx, gt_path in enumerate(gt_paths):
        book_dir = gt_path.parent
        pdf = book_dir / "original.pdf"
        if not pdf.exists():
            continue
        data = json.loads(gt_path.read_text(encoding="utf-8"))
        entries = []
        seen: set[str] = set()
        for entry in data.get("pages") or []:
            if entry.get("markup_residue"):
                continue
            ref = norm(entry.get("text") or "")
            if len(ref) < args.min_ref or ref in seen or script_share(ref) < args.min_telugu:
                continue
            page_no = entry.get("page")
            if not isinstance(page_no, int) or page_no < 1:
                continue
            seen.add(ref)
            entries.append((page_no, ref))
        if not entries:
            continue
        books.append(book_dir.name)
        doc = fitz.open(pdf)
        for page_no, ref in entries:
            if page_no > doc.page_count:
                continue
            pix = doc[page_no - 1].get_pixmap(dpi=args.dpi)
            page_img = args.out / "pages" / f"{book_dir.name}__p{page_no}.png"
            page_img.parent.mkdir(parents=True, exist_ok=True)
            pix.save(str(page_img))
            with Image.open(page_img) as opened:
                img = opened.convert("RGB")
                boxes = line_boxes(img)
                for line_idx, box in enumerate(boxes):
                    pad = 4
                    crop = img.crop(
                        (
                            max(0, box["x"] - pad),
                            max(0, box["y"] - pad),
                            min(img.width, box["right"] + pad),
                            min(img.height, box["bottom"] + pad),
                        )
                    )
                    if crop.width < 20 or crop.height < 8:
                        continue
                    # Skip blank crops (scanner borders, rules).
                    if crop.convert("L").getextrema()[0] > 245:
                        continue
                    rel = Path(book_dir.name) / f"p{page_no:04d}" / f"l{line_idx:03d}.png"
                    dest = image_root / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    crop.save(dest)
                    row = {
                        "id": f"{book_dir.name}__p{page_no}__l{line_idx}",
                        "book": book_dir.name,
                        "page": page_no,
                        "line": line_idx,
                        "image": str(Path("images") / rel),
                        "bbox": [box["x"], box["y"], box["right"], box["bottom"]],
                        "page_ref": ref,
                        "split": "test" if book_dir.name in held_out else "train",
                    }
                    rows.append(row)
                    manifest_file.write(json.dumps(row, ensure_ascii=False) + "\n")
                manifest_file.flush()
            page_row = {"book": book_dir.name, "page": page_no, "ref": ref}
            pages.append(page_row)
            pages_file.write(json.dumps(page_row, ensure_ascii=False) + "\n")
            pages_file.flush()
            print(f"{book_dir.name[:40]:40s} p{page_no:<4d} lines={len(boxes)}", file=sys.stderr)
        doc.close()
        # refresh per-book count after processing
        if len(books) % 4 == 0:
            print(f"progress: {len(books)} books, {len(rows)} lines", file=sys.stderr)

    manifest_file.close()
    pages_file.close()
    (args.out / "books.json").write_text(
        json.dumps({"all": books, "test": sorted(held_out)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {len(rows)} lines from {len(books)} books ({len(held_out)} test) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
