#!/usr/bin/env python3
"""Download the corpus PDFs on the node from Wikimedia Commons.

Ships nothing heavy: the corpus PDFs are fetched here instead of being
transferred, because the node's egress is far faster than the workstation's
uplink. Each scaffold's ``provenance.json`` carries the Commons file title;
``Special:FilePath`` resolves it (and follows the redirect to the upload URL).

Usage (on the node):
    uv run python /gt_fill/node_fetch_pdfs.py --gt-root /gt_fill/ground_truth
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

USER_AGENT = (
    "IndicBookMetadataExtractor-GT-PoC/0.1 (https://github.com/Agamya-Samuel/indic-book-metadata-extractor-v2) httpx"
)


def commons_filepath(title: str) -> str:
    name = title.removeprefix("File:").replace(" ", "_")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{httpx.URL(name)}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gt-root", type=Path, required=True)
    ap.add_argument("--delay", type=float, default=0.4)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    books = sorted(args.gt_root.glob("*/*/expected_metadata.json"))
    todo = [b for b in books if not (b.parent / "original.pdf").exists()]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)}/{len(books)} book(s) need a PDF", flush=True)

    ok = miss = 0
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=300.0, follow_redirects=True) as client:
        for i, gt in enumerate(todo, 1):
            book_dir = gt.parent
            prov_path = book_dir / "provenance.json"
            title = None
            if prov_path.exists():
                title = json.loads(prov_path.read_text(encoding="utf-8")).get("commons_title")
            dest = book_dir / "original.pdf"
            if not title:
                print(f"[{i}/{len(todo)}] {book_dir.name[:44]:44s} no commons_title -> skip", flush=True)
                miss += 1
                continue
            try:
                r = client.get(commons_filepath(title))
                r.raise_for_status()
                dest.write_bytes(r.content)
                ok += 1
                print(f"[{i}/{len(todo)}] {book_dir.name[:44]:44s} {len(r.content) / 1e6:.1f}MB", flush=True)
            except Exception as e:  # noqa: BLE001 - keep going
                miss += 1
                print(f"[{i}/{len(todo)}] {book_dir.name[:44]:44s} ERROR {str(e)[:80]}", flush=True)
            time.sleep(args.delay)

    print(f"\ndownloaded {ok}, failed {miss}")
    return 0 if miss == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
