#!/usr/bin/env python3
"""Seed ground-truth books from a Wikisource's proofread Index pages.

Enumerates ``Index:`` pages on a wiki, maps each back to its Commons PDF, and writes a
ground-truth book dir (``original.pdf`` + ``expected_metadata.json`` + ``provenance.json``)
with metadata prefilled from the Index header. Then run ``scripts.enrich_ground_truth``
(Internet Archive fill) and ``scripts.fetch_wikisource_gt`` (page-level OCR ground truth).

Usage:
    cd backend
    uv run python -m scripts.fetch_from_wikisource --limit 6
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from pathlib import Path

import httpx

from scripts.enrich_ground_truth import FIELD_NAMES, parse_index_header
from scripts.fetch_commons_ground_truth import USER_AGENT, _slugify, download_pdf, file_info, prefill
from scripts.fetch_wikisource_gt import _api_get, resolve_namespaces

GT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth"


def list_index_pages(api: str, client: httpx.Client, ns_index: int, want: int, delay: float) -> list[str]:
    out: list[str] = []
    cont: dict = {}
    while len(out) < want:
        data = _api_get(
            api,
            client,
            {"action": "query", "list": "allpages", "apnamespace": str(ns_index), "aplimit": "500", **cont},
            delay,
        )
        out.extend(p["title"] for p in data["query"]["allpages"])
        cont = data.get("continue") or {}
        if not cont:
            break
    return out[:want]


def index_header(api: str, client: httpx.Client, title: str, delay: float) -> dict[str, str]:
    data = _api_get(
        api,
        client,
        {"action": "query", "titles": title, "prop": "revisions", "rvprop": "content", "rvslots": "main"},
        delay,
    )
    revs = data["query"]["pages"][0].get("revisions") or []
    return parse_index_header(revs[0]["slots"]["main"]["content"]) if revs else {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wiki", default="te.wikisource.org")
    ap.add_argument("--lang", default="tel", choices=["tel", "hin"])
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--max-size-mb", type=float, default=40.0)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--out", type=Path, default=GT_ROOT)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    api = f"https://{args.wiki}/w/api.php"
    args.out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60.0, follow_redirects=True) as client:
        ns = resolve_namespaces(api, client, args.delay)
        titles = list_index_pages(api, client, ns["Index"], args.limit * 4, args.delay)
        print(f"{args.wiki}: {len(titles)} Index pages; seeding up to {args.limit}")
        for ititle in titles:
            if len(rows) >= args.limit:
                break
            stem = ititle.split(":", 1)[1]
            if not stem.lower().endswith(".pdf"):
                continue
            commons = f"File:{stem}"
            slug = _slugify(commons)
            book_dir = args.out / args.lang / slug
            if (book_dir / "expected_metadata.json").exists() and not args.overwrite:
                continue
            try:
                info = file_info(client, commons, args.delay)
            except Exception as e:  # noqa: BLE001
                print(f"  skip {stem}: {e}", file=sys.stderr)
                continue
            if not info["imageinfo"].get("url"):
                continue
            size_mb = (info["imageinfo"].get("size") or 0) / 1_000_000
            if size_mb > args.max_size_mb:
                print(f"  skip (size {size_mb:.0f}MB): {stem}")
                continue
            expected, status, prov, lic = prefill(info, args.lang, f"Index:{args.wiki}")
            for field, val in index_header(api, client, ititle, args.delay).items():
                if field in FIELD_NAMES and val:
                    expected[field] = val
                    status[field] = "prefilled_needs_verification"
            prov["wikisource_index_urls"] = [
                f"https://{args.wiki}/wiki/" + urllib.parse.quote(ititle.replace(" ", "_"))
            ]
            prov["source_category"] = f"Index:{args.wiki}"
            prov["wiki"] = args.wiki
            book_dir.mkdir(parents=True, exist_ok=True)
            gt = {
                "description": f"{expected.get('title') or slug} — Wikisource GT scaffold (UNVERIFIED)",
                "language": args.lang,
                "quality": "wikisource",
                "source_category": prov["source_category"],
                "total_pages": None,
                "recommended_pages": None,
                "verification_status": "unverified",
                "expected_metadata": expected,
                "field_status": status,
                "notes": "Prefilled from Wikisource Index header + Commons metadata. Verify against the scan; set verification_status=verified before scoring.",
            }
            (book_dir / "expected_metadata.json").write_text(
                json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            (book_dir / "provenance.json").write_text(json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")
            if prov.get("download_url"):
                download_pdf(client, prov["download_url"], book_dir / "original.pdf", args.delay)
            rows.append({"slug": slug, "lang": args.lang, "commons_title": commons, "license": lic, "index": ititle})
            print(f"  + {slug} [{lic}]")

    with open(args.out / "manifest.jsonl", "a", encoding="utf-8") as fh:
        fh.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"\nSeeded {len(rows)} books under {args.out}")
    print("Next: scripts.enrich_ground_truth (IA fill), then scripts.fetch_wikisource_gt per book (OCR GT).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
