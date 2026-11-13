#!/usr/bin/env python3
"""Render verified Wikisource Telugu pages to PNG + a reference manifest.

Produces a small, engine-agnostic OCR test bundle so the benchmark node needs
only OCR engines (no PDFs, no PyMuPDF). Ground truth = human-verified
Wikisource text already aligned in each book's wikisource_gt.json.

Usage:
    backend/.venv/bin/python /tmp/ocr_eval/build_bundle.py [books] [pages_per_book]
"""

import json
import sys
import unicodedata
from pathlib import Path

import fitz

GT = Path("/run/media/agamya/Storage/WikiProjects/OKI/Indic-Book-Metadata-Extractor/backend/tests/fixtures/ground_truth")
OUT = Path("/tmp/ocr_bundle")
BOOKS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
PAGES = int(sys.argv[2]) if len(sys.argv) > 2 else 3
DPI = 300
MIN_REF = 60


def norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    books_used = 0
    candidates = sorted(GT.glob("tel/*/wikisource_gt.json"))
    for gt_path in candidates:
        if books_used >= BOOKS:
            break
        book_dir = gt_path.parent
        pdf = book_dir / "original.pdf"
        if not pdf.exists():
            continue
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        entries = gt.get("pages") or []
        usable = []
        seen = set()
        for e in entries:
            if e.get("markup_residue"):
                continue
            ref = norm(e.get("text") or "")
            if len(ref) < MIN_REF or ref in seen:
                continue
            pno = e.get("page")
            if not isinstance(pno, int) or pno < 1:
                continue
            seen.add(ref)
            usable.append((pno, ref))
        if not usable:
            continue
        # Even spread across the book so title/body/back matter are all represented.
        if len(usable) <= PAGES:
            picks = usable
        else:
            step = (len(usable) - 1) / (PAGES - 1) if PAGES > 1 else 0
            picks = [usable[round(i * step)] for i in range(PAGES)]
        try:
            doc = fitz.open(pdf)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {book_dir.name}: {exc}")
            continue
        picked = 0
        for pno, ref in picks:
            if pno > doc.page_count:
                continue
            img = OUT / f"{book_dir.name}__p{pno}.png"
            if not img.exists():
                doc[pno - 1].get_pixmap(dpi=DPI).save(str(img))
            manifest.append(
                {"id": f"{book_dir.name}__p{pno}", "book": book_dir.name, "page": pno, "image": img.name, "ref": ref}
            )
            picked += 1
        doc.close()
        if picked:
            books_used += 1
            print(f"  + {book_dir.name}: {picked} pages")

    (OUT / "manifest.jsonl").write_text(
        "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in manifest), encoding="utf-8"
    )
    print(f"\nbundle: books={books_used} pages={len(manifest)} -> {OUT}")


if __name__ == "__main__":
    main()