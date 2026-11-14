"""Harness-only extraction via Ollama's native endpoint.

``LLMService`` calls Ollama's OpenAI-compatible endpoint, where ``think:false``
is dropped — a thinking model (gemma4) then spends its whole budget on the
reasoning channel and returns empty content, so the evaluation harness scores
nothing. This path calls ``/api/chat`` with ``think:false`` instead, so the
harness can score thinking models too. It is a *test harness* helper: it does
not touch the production extraction path or the database.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import httpx

from app.schemas.metadata import BATCH_FIELD_ORDER
from app.services.prompts import render_extraction_prompt

MAX_PROMPT_CHARS = 3000


def _parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def _ocr_pages(pdf: Path, language: str, max_pages: int) -> list[tuple[int, str]]:
    from app.services.ocr_service import run_ocr
    from app.services.pdf_service import get_page_count, render_full_page

    total = get_page_count(pdf)
    texts: list[tuple[int, str]] = []
    with tempfile.TemporaryDirectory(prefix="native_") as tmp:
        for pageno in range(1, min(total, max_pages) + 1):
            img = Path(tmp) / f"p{pageno:04d}.png"
            render_full_page(pdf, pageno, img)
            text = run_ocr(img, language, page_position=pageno - 1).get("full_text", "")
            if text:
                texts.append((pageno, text))
    return texts


def run_native(
    pdf_path: str,
    model: str = "gemma4:e4b",
    language: str = "tel",
    max_pages: int = 10,
    max_tokens: int = 1024,
    ollama_url: str = "http://ollama:11434",
) -> dict:
    """Extract all batches via /api/chat (think:false); returns a field dict."""
    from app.services.prompts import render_system_prompt

    texts = _ocr_pages(Path(pdf_path), language, max_pages)
    joined = "\n\n".join(f"[page {p}]\n{t}" for p, t in texts)
    system = render_system_prompt(language)
    merged: dict = {}
    with httpx.Client(timeout=1200.0) as client:
        for batch_name in BATCH_FIELD_ORDER:
            prompt = render_extraction_prompt(
                batch_name=batch_name,
                ocr_text=joined[:MAX_PROMPT_CHARS],
                language=language,
                page_count=len(texts),
            )
            try:
                r = client.post(
                    f"{ollama_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                        "stream": False,
                        "think": False,
                        "options": {"num_predict": max_tokens, "temperature": 0},
                    },
                )
                r.raise_for_status()
                data = _parse_json((r.json().get("message", {}) or {}).get("content") or "")
            except Exception:  # noqa: BLE001 - a failed batch just contributes nothing
                data = {}
            for key, value in data.items():
                if value is not None:
                    merged[key] = value
    return merged
