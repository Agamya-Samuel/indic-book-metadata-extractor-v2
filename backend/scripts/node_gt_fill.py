#!/usr/bin/env python3
"""Node-side OCR+LLM prefill of the scan-embedded ground-truth fields.

Most of the 49 fields (publisher, printer, series, editor, translator,
illustrators, dedication, ...) live only *inside* the book — on the title,
copyright and colophon/back-cover pages — so no catalog source can supply
them. This runner reads those pages with the real pipeline (render -> OCR ->
LLM) and writes one JSON row per book for later merge into the scaffolds.

Two extraction modes:

  * ``focused`` (default): ONE JSON call per book asking for the fields
    catalogs rarely carry. On CPU this is ~8x cheaper than the production
    8-batch hybrid (~19 min/book).
  * ``hybrid``: the production ``run_hybrid_full_extraction`` (8 batches).

The focused path calls Ollama's OpenAI-compatible endpoint directly with
``think: false`` — the production ``instructor`` path does not forward the
think flag here, so a thinking model (gemma4) otherwise spends its whole
budget on the reasoning channel and returns empty content.

Usage (on the node, inside the worker image):
    uv run python /gt_fill/scripts/node_gt_fill.py \
        --gt-root /gt_fill/tests/fixtures/ground_truth \
        --out /gt_fill/node-fill.jsonl --model gemma4:e4b --front 5 --back 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.schemas.metadata import ALL_METADATA_FIELDS
from app.services.batch_routing import PageText
from app.services.llm_service import LLMService
from app.services.ocr_service import run_ocr
from app.services.pdf_service import get_page_count, render_full_page
from app.services.page_selection import select_pages
from app.services.prompts import FIELD_DISPLAY_NAMES

LANG_CODE = {"tel": "tel", "te": "tel", "telugu": "tel", "hin": "hin", "hi": "hin", "hindi": "hin"}
LANG_NAME = {"tel": "Telugu", "hin": "Hindi"}

COMMON_FIELDS = {
    "label",
    "author",
    "title",
    "language",
    "original_language",
    "form_of_creative_work",
    "publication_date",
    "publisher",
    "place_of_publication",
    "pages",
    "description_work",
}
TARGET_FIELDS = [f.field_name for f in ALL_METADATA_FIELDS if f.field_name not in COMMON_FIELDS]

_SYSTEM_PROMPT = (
    "You are an expert bibliographic metadata extractor for scanned Indian-language books. "
    "Read the OCR text and return a single JSON object. Use null for any field not present. "
    "Return the actual value found in the text (a name, place, number or phrase) — never the "
    "field's own label, and never a translation of the label. Return only JSON, with no "
    "explanation or markdown."
)
_FIELD_LIST = "\n".join(f'- "{f}": {FIELD_DISPLAY_NAMES.get(f, f)}' for f in TARGET_FIELDS)


def build_user_prompt(language: str, joined_text: str, page_count: int) -> str:
    return (
        f"Extract these metadata fields from the following {LANG_NAME.get(language, language)} book text "
        f"({page_count} pages of a scanned book). Use your knowledge of the script and OCR error "
        "correction to read imperfect text; use null only when a field is genuinely absent.\n\n"
        f"Fields (JSON keys):\n{_FIELD_LIST}\n\n"
        f"OCR text:\n---\n{joined_text}\n---\n\n"
        "Respond with a JSON object containing exactly these keys."
    )


def parse_json(content: str) -> dict:
    text = content.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in response")
    return json.loads(text[start : end + 1])


async def direct_extract(client: httpx.AsyncClient, url: str, model: str, user: str, max_tokens: int, temperature: float) -> dict:
    """Call Ollama's native /api/chat with think:false.

    The OpenAI-compatible endpoint ignores ``think`` for thinking models here
    (gemma4 keeps a reasoning channel and returns empty content), so the
    native endpoint is used instead.
    """
    r = await client.post(
        f"{url}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": user}],
            "stream": False,
            "think": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        },
    )
    r.raise_for_status()
    content = (r.json().get("message", {}) or {}).get("content") or ""
    return parse_json(content)


def page_plan(total: int, front: int, back: int) -> list[int]:
    head = list(range(1, min(total, front) + 1))
    tail = list(range(max(1, total - back + 1), total + 1))
    seen, ordered = set(), []
    for p in head + tail:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def ocr_pages(pdf: Path, pages: list[int], lang: str) -> tuple[list[PageText], str]:
    texts: list[PageText] = []
    with tempfile.TemporaryDirectory(prefix="gtfill_") as tmp:
        for pageno in pages:
            img = Path(tmp) / f"p{pageno:04d}.png"
            render_full_page(pdf, pageno, img)
            data = run_ocr(img, lang, page_position=pageno - 1)
            if data.get("full_text"):
                texts.append(PageText(page_number=pageno, text=data["full_text"]))
    joined = "\n\n".join(f"[page {p.page_number}]\n{p.text}" for p in texts)
    return texts, joined


async def fill_book(client: httpx.AsyncClient, llm: LLMService, book_dir: Path, args) -> dict:
    envelope = json.loads((book_dir / "expected_metadata.json").read_text(encoding="utf-8"))
    lang = LANG_CODE.get(str(envelope.get("language", "tel")).lower(), "tel")
    pdf = book_dir / "original.pdf"
    total = get_page_count(pdf)
    if args.select == "fixed":
        scan = page_plan(total, args.front, args.back)
    else:
        scan = page_plan(total, args.scan_front, args.scan_back)
    scanned, _ = ocr_pages(pdf, scan, lang)
    text_by_page = {p.page_number: p.text for p in scanned}
    keep = set(select_pages(total, text_by_page, strategy=args.select, front=args.front, back=args.back))
    texts = [p for p in scanned if p.page_number in keep]
    pages = sorted(keep)
    joined = "\n\n".join(f"[page {p.page_number}]\n{p.text}" for p in texts)

    if args.mode == "hybrid":
        metadata, _b, _e = await llm.run_hybrid_full_extraction(
            ocr_text="", pages=texts, language=lang, model=args.model, max_tokens=args.max_tokens
        )
        fields = metadata.model_dump()
    else:
        prompt = build_user_prompt(lang, joined[: args.ocr_chars], len(texts))
        fields = await direct_extract(client, args.ollama_url, args.model, prompt, args.max_tokens, args.temperature)

    return {
        "slug": book_dir.name,
        "lang": lang,
        "model": args.model,
        "mode": args.mode,
        "total_pages": total,
        "pages_used": pages,
        "ocr_pages": len(texts),
        "fields": {k: v for k, v in fields.items() if k != "custom_fields"},
        "filled_at": datetime.now(UTC).isoformat(),
    }


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gt-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="gemma4:e4b")
    ap.add_argument("--mode", choices=["focused", "hybrid"], default="focused")
    ap.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://ollama:11434"))
    ap.add_argument("--front", type=int, default=5)
    ap.add_argument("--back", type=int, default=2)
    ap.add_argument("--select", choices=["fixed", "heuristic"], default="fixed")
    ap.add_argument("--scan-front", type=int, default=12)
    ap.add_argument("--scan-back", type=int, default=5)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--ocr-chars", type=int, default=4000)
    ap.add_argument("--lang", default=None, choices=["tel", "hin"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    books = sorted(args.gt_root.glob(f"{args.lang or '*'}/**/expected_metadata.json"))
    done: set[str] = set()
    if args.out.exists() and not args.overwrite:
        done = {json.loads(line)["slug"] for line in args.out.read_text(encoding="utf-8").splitlines() if line.strip()}
    books = [b for b in books if b.parent.name not in done]
    if args.limit:
        books = books[: args.limit]

    llm = LLMService(ollama_url=args.ollama_url)
    print(f"{len(books)} book(s) to fill (mode={args.mode}, model={args.model}, front={args.front}, back={args.back})", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=1200.0) as client:
        with args.out.open("a", encoding="utf-8") as fh:
            for i, gt in enumerate(books, 1):
                t0 = time.time()
                try:
                    row = await fill_book(client, llm, gt.parent, args)
                except Exception as e:  # noqa: BLE001 - keep going, record the failure
                    row = {"slug": gt.parent.name, "lang": gt.parent.parent.name, "error": str(e)[:300]}
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                filled = len([v for v in row.get("fields", {}).values() if v]) if "fields" in row else 0
                print(f"[{i}/{len(books)}] {gt.parent.name[:44]:44s} pages={row.get('ocr_pages', '-')} filled={filled} {time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
