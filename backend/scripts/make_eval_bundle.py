"""Build an offline accuracy bundle for remote Ollama scoring.

Renders the real per-batch extraction prompts + JSON schemas for one
ground-truth book from its Wikisource page text, so a stdlib-only script
can run them on a remote node (no backend install there).

Usage:
    python -m scripts.make_eval_bundle \
        --book tests/fixtures/ground_truth/tel/2015.373190.Athma-Charitramu \
        --batches core_identity,publication \
        --output /tmp/bundle_athma.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.schemas.metadata import METADATA_BATCHES  # noqa: E402
from app.services.batch_routing import (  # noqa: E402
    PageText,
    assemble_ocr_text,
    select_pages_for_batch,
)
from app.services.prompts import render_extraction_prompt, render_system_prompt  # noqa: E402

MAX_OCR_CHARS = 2500


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book", required=True, type=Path)
    ap.add_argument("--batches", default="core_identity,publication")
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    meta = json.loads((args.book / "expected_metadata.json").read_text(encoding="utf-8"))
    expected = meta.get("expected_metadata", meta)
    language = meta.get("language") or args.book.parent.name
    ws = json.loads((args.book / "wikisource_gt.json").read_text(encoding="utf-8"))
    raw_pages = ws.get("pages") or []
    pages = [
        PageText(page_number=i + 1, text=p.get("text") or "")
        for i, p in enumerate(raw_pages)
        if (p.get("text") or "").strip()
    ]
    if not pages:
        print("No page text found in wikisource_gt.json", file=sys.stderr)
        return 1

    batch_names = [b.strip() for b in args.batches.split(",") if b.strip()]
    batches = []
    for name in batch_names:
        selected = select_pages_for_batch(pages, name)
        text = assemble_ocr_text(selected, MAX_OCR_CHARS)
        batches.append(
            {
                "name": name,
                "text_chars": len(text),
                "pages": len(selected),
                "prompt": render_extraction_prompt(
                    batch_name=name,
                    ocr_text=text,
                    language=language,
                    page_count=len(selected),
                ),
                "schema": METADATA_BATCHES[name].model_json_schema(),
            }
        )

    bundle = {
        "book": args.book.name,
        "language": language,
        "num_pages": len(pages),
        "system_prompt": render_system_prompt(language),
        "expected": expected,
        "batches": batches,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Bundle -> {args.output} ({len(batches)} batches, {len(pages)} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
