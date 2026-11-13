#!/usr/bin/env python3
"""POC: pick the front/back page window that holds a book's bibliographic metadata.

Feeding body-text pages into the extraction prompt adds OCR noise, so the
window matters. This compares detectors against a *silver* label (a page is a
metadata page if its OCR text contains a known ground-truth identity value):

  fixed        first 6 + last 2 pages (the current heuristic)
  heuristic    walk from each end, stop at the first body-like page
  llm_text     ask the local model, per page, whether it is bibliographic matter

Run inside the worker image on a GCP node. Usage:
    uv run python /gt_fill/scripts/poc_page_detector.py \
        --gt-root /gt_fill/tests/fixtures/ground_truth --out /gt_fill/poc-detect.jsonl \
        --lang tel --limit 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

import httpx

from app.services.ocr_service import run_ocr
from app.services.pdf_service import get_page_count, render_full_page

IDENTITY_FIELDS = ("label", "title", "author", "publisher", "place_of_publication")
CUE = re.compile(
    r"(ప్రచురణ|ముద్రా|సంవత్సర|ప్రకాశక|प्रकाशक|मुद्र|©|\(c\)|copyright|isbn|press|printed|publisher|registered)",
    re.IGNORECASE,
)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s).lower()).strip()


def is_body(text: str) -> bool:
    """A page that looks like running body content, not front/back matter."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return len(text) > 1200 and len(lines) > 14 and not CUE.search(text)


def silver_pages(page_text: dict[int, str], em: dict) -> set[int]:
    """A page is a metadata page if >=50% of a GT identity value's tokens appear.

    Token overlap (not exact substring) so OCR errors do not blank every label.
    """
    vals = [norm(str(em.get(f))) for f in IDENTITY_FIELDS if em.get(f)]
    vals = [v for v in vals if len(v) >= 4]
    out = set()
    for p, t in page_text.items():
        nt = norm(t)
        for v in vals:
            toks = [x for x in v.split() if len(x) >= 3]
            if toks and sum(1 for x in toks if x in nt) / len(toks) >= 0.5:
                out.add(p)
                break
    return out


def window_pages(total: int, front: list[int], back: list[int]) -> list[int]:
    seen, ordered = set(), []
    for p in front + back:
        if 1 <= p <= total and p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def detect_fixed(total: int, order: list[int]) -> list[int]:
    front = [p for p in order if p <= 6]
    back = [p for p in order if p > total - 2]
    return window_pages(total, front, back)


def detect_heuristic(total: int, order: list[int], page_text: dict[int, str]) -> list[int]:
    picked: list[int] = []
    for p in order:
        t = page_text.get(p, "")
        if is_body(t):
            break
        if t.strip():
            picked.append(p)
    # back matter: walk from the end until a body page
    for p in reversed(order):
        if p in picked:
            continue
        t = page_text.get(p, "")
        if is_body(t):
            break
        if t.strip():
            picked.append(p)
    return sorted(set(picked))


async def llm_judge(client: httpx.AsyncClient, url: str, model: str, pages: dict[int, str]) -> list[int]:
    picked = []
    for p, t in pages.items():
        if not t.strip():
            continue
        q = (
            "You are shown OCR text of ONE page of a scanned book. Answer with a single word, "
            "yes or no: does this page contain the book's bibliographic front/back matter "
            "(title page, author, publisher/printer, copyright, dedication, colophon)?\n\n"
            f"OCR text:\n---\n{t[:1500]}\n---"
        )
        try:
            r = await client.post(
                f"{url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": q}],
                    "stream": False,
                    "think": False,
                    "options": {"num_predict": 4, "temperature": 0},
                },
            )
            ans = (r.json().get("message", {}) or {}).get("content", "").strip().lower()
            if ans.startswith("y"):
                picked.append(p)
        except Exception:  # noqa: BLE001
            pass
    return sorted(picked)


def score(detected: list[int], silver: set[int]) -> dict:
    d, s = set(detected), silver
    hit = len(d & s)
    return {
        "pages": sorted(d),
        "n": len(d),
        "recall": round(hit / len(s), 3) if s else 1.0,
        "precision": round(hit / len(d), 3) if d else 0.0,
    }


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gt-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ollama-url", default="http://ollama:11434")
    ap.add_argument("--model", default="gemma4:e4b")
    ap.add_argument("--front-max", type=int, default=14)
    ap.add_argument("--back-max", type=int, default=6)
    ap.add_argument("--lang", default=None, choices=["tel", "hin"])
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()

    books = sorted(args.gt_root.glob(f"{args.lang or '*'}/**/expected_metadata.json"))[: args.limit]
    rows = []
    async with httpx.AsyncClient(timeout=600.0) as client:
        for gt in books:
            env = json.loads(gt.read_text(encoding="utf-8"))
            em = env.get("expected_metadata", {})
            pdf = gt.parent / "original.pdf"
            total = get_page_count(pdf)
            order = sorted(set(list(range(1, min(total, args.front_max) + 1)) + list(range(max(1, total - args.back_max + 1), total + 1))))
            page_text: dict[int, str] = {}
            with tempfile.TemporaryDirectory(prefix="poc_") as tmp:
                for p in order:
                    img = Path(tmp) / f"p{p:04d}.png"
                    render_full_page(pdf, p, img)
                    page_text[p] = run_ocr(img, "tel" if gt.parent.parent.name == "tel" else "hin", page_position=p - 1).get("full_text", "")
            silver = silver_pages(page_text, em)
            det = {
                "fixed": detect_fixed(total, order),
                "heuristic": detect_heuristic(total, order, page_text),
            }
            if not args.no_llm:
                det["llm_text"] = await llm_judge(client, args.ollama_url, args.model, page_text)
            row = {"book": gt.parent.name, "lang": gt.parent.parent.name, "total": total, "silver": sorted(silver), "detectors": {k: score(v, silver) for k, v in det.items()}}
            rows.append(row)
            print(f"{gt.parent.name[:40]:40s} silver={len(silver)} " + " ".join(f"{k}:r{v['recall']}/p{v['precision']}/n{v['n']}" for k, v in row['detectors'].items()), flush=True)

    args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    for k in rows[0]["detectors"]:
        ms = [r["detectors"][k] for r in rows]
        print(f"MEAN {k:10s} recall={sum(m['recall'] for m in ms)/len(ms):.3f} precision={sum(m['precision'] for m in ms)/len(ms):.3f} pages={sum(m['n'] for m in ms)/len(ms):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))