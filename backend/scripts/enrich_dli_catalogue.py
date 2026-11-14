#!/usr/bin/env python3
"""Fill publisher/date/pages from the DLI Catalogue (plans/011, Phase 2).

The DLI Catalogue is behind Cloudflare; its pages were fetched once through a
real browser session and cached (JSON-encoded HTML) under ``--cache-dir`` as
``dli_tel_1.html`` … ``dli_hin_3.html``. This parses them into a
``barcode -> {year, publisher, pages}`` map and matches our books by the barcode
carried in their Internet Archive ``dc.identifier.barcode``.

Usage:
    cd backend
    uv run python -m scripts.enrich_dli_catalogue --cache-dir /tmp
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from pathlib import Path

import httpx

from scripts.enrich_catalogues import USER_AGENT, parse_dc

GT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth"
PARTS = ["dli_tel_1.html", "dli_tel_2.html", "dli_hin_1.html", "dli_hin_2.html", "dli_hin_3.html"]


def _text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    try:
        raw = json.loads(raw)  # browser saved the string JSON-encoded
    except json.JSONDecodeError:
        pass
    raw = html.unescape(re.sub(r"<[^>]+>", " ", raw)).replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", raw)


def load_catalogue(cache_dir: Path) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    for name in PARTS:
        path = cache_dir / name
        if not path.exists():
            print(f"  missing {path} — skipping", file=sys.stderr)
            continue
        text = _text(path)
        for m in re.finditer(r"(\d+)\.\s+(.*?)\s+Barcode\s+(\d{8,})", text):
            body, barcode = m.group(2), m.group(3)
            meta = body.rsplit(";", 1)[-1]
            ym = re.search(r",\s*(\d{4})\s*,\s*(.*),\s*(\d+)\s*pages", meta)
            if ym:
                entries.setdefault(
                    barcode, {"year": ym.group(1), "publisher": ym.group(2).strip(), "pages": ym.group(3)}
                )
    return entries


def ia_id_from_prov(prov: dict, slug: str) -> str | None:
    for key in ("credit", "download_url"):
        url = prov.get(key) or ""
        for marker in ("/items/", "/details/", "/download/"):
            if marker in url:
                return url.split(marker, 1)[1].split("/", 1)[0].split("?", 1)[0]
        m = re.search(r"identifier:\s*([A-Za-z0-9._-]+)", url)
        if m:
            return m.group(1)
    m = re.match(r"^(\d{4}\.\d+)\.", slug)
    return f"in.ernet.dli.{m.group(1)}" if m else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=GT_ROOT)
    ap.add_argument("--cache-dir", type=Path, default=Path("/tmp"))
    ap.add_argument("--delay", type=float, default=0.2)
    args = ap.parse_args()

    cat = load_catalogue(args.cache_dir)
    print(f"DLI catalogue: {len(cat)} barcode entries")

    books = sorted(args.root.glob("*/*/expected_metadata.json"))
    touched = filled = matched = 0
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=90.0, follow_redirects=True) as client:
        for gt in books:
            prov_path = gt.parent / "provenance.json"
            prov = json.loads(prov_path.read_text(encoding="utf-8")) if prov_path.exists() else {}
            ident = ia_id_from_prov(prov, gt.parent.name)
            if not ident:
                continue
            try:
                meta = client.get(f"https://archive.org/metadata/{ident}").json().get("metadata", {})
                barcode = parse_dc(str(meta.get("description", ""))).get("dc.identifier.barcode")
            except Exception:  # noqa: BLE001
                continue
            rec = cat.get((barcode or "").strip())
            if not barcode or not rec:
                continue
            matched += 1
            env = json.loads(gt.read_text(encoding="utf-8"))
            em = env.setdefault("expected_metadata", {})
            src = env.setdefault("field_source", {})
            status = env.setdefault("field_status", {})
            added = 0
            for field, value in (
                ("publisher", rec.get("publisher")),
                ("publication_date", rec.get("year")),
                ("pages", rec.get("pages")),
            ):
                if value and em.get(field) in (None, "", [], {}):
                    em[field] = value
                    src[field] = "dli_catalogue"
                    status[field] = "prefilled_needs_verification"
                    added += 1
            if added:
                touched += 1
                filled += added
                gt.write_text(json.dumps(env, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"  {gt.parent.parent.name}/{gt.parent.name[:42]:42s} +{added}")
            time.sleep(args.delay)

    print(f"\nmatched {matched} books by barcode · {touched} updated · {filled} fields filled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
