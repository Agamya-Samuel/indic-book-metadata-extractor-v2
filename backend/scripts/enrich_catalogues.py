#!/usr/bin/env python3
"""Enrich ground-truth scaffolds from two catalogue sources (plans/011, Phase 1).

  * **IA ``dc.*``** — the DLI item description carries publisher / citation
    date / total pages / subject classification, which the metadata API hides
    inside the description HTML.
  * **Pustaka Nidhi** (library.opentelugu.org, CC BY 4.0) — a catalogue of
    Telugu scans on the Internet Archive, keyed by IA identifier, that adds
    **Telugu-script titles** (and fixes a Latin-only ``title``/``label``).

Only empty fields are filled, except the script fix, which replaces a Latin
``title``/``label`` with the native-script form. Every change is recorded as
``field_source`` and flagged ``prefilled_needs_verification``.

Usage:
    cd backend
    uv run python -m scripts.enrich_catalogues                 # all books
    uv run python -m scripts.enrich_catalogues --lang tel
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

import httpx

from app.schemas.metadata import ALL_METADATA_FIELDS

FIELD_NAMES = [f.field_name for f in ALL_METADATA_FIELDS]
GT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth"
USER_AGENT = "IndicBookMetadataExtractor-GT-PoC/0.1 (https://github.com/Agamya-Samuel/indic-book-metadata-extractor-v2)"
PN_PARTS = 4  # catalog-0.json .. catalog-3.json


def parse_dc(description_html: str) -> dict[str, str]:
    """Extract the ``dc.*: value`` pairs embedded in an IA description blob."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", description_html or ""))
    out: dict[str, str] = {}
    for m in re.finditer(r"(dc\.[a-z.]+)\s*:\s*(.*?)(?=\s*dc\.[a-z.]+\s*:|$)", text, re.S):
        out[m.group(1).strip()] = re.sub(r"\s+", " ", m.group(2)).strip(" ;")
    return out


def ia_id(provenance: dict, slug: str) -> str | None:
    for key in ("credit", "download_url"):
        url = provenance.get(key) or ""
        for marker in ("/items/", "/details/", "/download/"):
            if marker in url:
                return url.split(marker, 1)[1].split("/", 1)[0].split("?", 1)[0]
        m = re.search(r"identifier:\s*([A-Za-z0-9._-]+)", url)
        if m:
            return m.group(1)
    m = re.match(r"^(\d{4}\.\d+)\.", slug)
    return f"in.ernet.dli.{m.group(1)}" if m else None


def load_pustaka_nidhi(client: httpx.Client) -> dict[str, dict]:
    """identifier -> record {title_te, title_la, year}."""
    index: dict[str, dict] = {}
    for i in range(PN_PARTS):
        data = client.get(f"https://library.opentelugu.org/data/catalog-{i}.json").json()
        for r in data:
            ident = str(r.get("i", "")).strip()
            if ident:
                index[ident] = {"title_te": r.get("t"), "title_la": r.get("l"), "year": r.get("y")}
    return index


def fetch_ia_dc(client: httpx.Client, ident: str) -> dict[str, str]:
    meta = client.get(f"https://archive.org/metadata/{ident}").json().get("metadata", {})
    dc = parse_dc(str(meta.get("description", "")))
    found: dict[str, str] = {}
    if dc.get("dc.publisher"):
        found["publisher"] = dc["dc.publisher"]
    if dc.get("dc.date.citation"):
        found["publication_date"] = dc["dc.date.citation"]
    if dc.get("dc.description.totalpages"):
        found["pages"] = re.sub(r"\D", "", dc["dc.description.totalpages"])
    subj = dc.get("dc.subject.classification") or dc.get("dc.subject.keywords")
    if subj:
        found["subject"] = subj
    return found


def is_latin(text: str) -> bool:
    return not any("\u0900" <= c <= "\u097f" or "\u0c00" <= c <= "\u0c7f" for c in text)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=GT_ROOT)
    ap.add_argument("--lang", default=None, choices=["tel", "hin"])
    ap.add_argument("--delay", type=float, default=0.2)
    args = ap.parse_args()

    books = sorted(args.root.glob(f"{args.lang or '*'}/**/expected_metadata.json"))
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=120.0, follow_redirects=True) as client:
        print("loading Pustaka Nidhi catalogue…")
        pn = load_pustaka_nidhi(client)
        print(f"  {len(pn)} records")

        tot_fill = tot_script = 0
        touched = 0
        for gt in books:
            env = json.loads(gt.read_text(encoding="utf-8"))
            em = env.setdefault("expected_metadata", {})
            src = env.setdefault("field_source", dict.fromkeys(FIELD_NAMES))
            status = env.setdefault("field_status", {})
            prov_path = gt.parent / "provenance.json"
            prov = json.loads(prov_path.read_text(encoding="utf-8")) if prov_path.exists() else {}
            changed = 0

            # Pustaka Nidhi: native-script title (fills and fixes Latin)
            ident = ia_id(prov, gt.parent.name)
            rec = pn.get(ident) if ident else None
            if rec and rec.get("title_te"):
                te = rec["title_te"].strip()
                if not em.get("title") or is_latin(str(em["title"])):
                    em["title"] = te
                    src["title"] = "pustaka_nidhi"
                    status["title"] = "prefilled_needs_verification"
                    changed += 1
                    tot_script += 1
                if not em.get("label") or is_latin(str(em.get("label"))):
                    em["label"] = te
                    src["label"] = "pustaka_nidhi"
                    status["label"] = "prefilled_needs_verification"
                    changed += 1
                    tot_script += 1
                if not em.get("publication_date") and rec.get("year"):
                    em["publication_date"] = str(rec["year"])
                    src["publication_date"] = "pustaka_nidhi"
                    status["publication_date"] = "prefilled_needs_verification"
                    changed += 1

            # IA dc.* extras
            if ident:
                try:
                    found = fetch_ia_dc(client, ident)
                except Exception:  # noqa: BLE001
                    found = {}
                for f, v in found.items():
                    if v and em.get(f) in (None, "", [], {}):
                        em[f] = v
                        src[f] = "ia_dc"
                        status[f] = "prefilled_needs_verification"
                        changed += 1
                        tot_fill += 1

            if changed:
                touched += 1
                gt.write_text(json.dumps(env, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"  {gt.parent.parent.name}/{gt.parent.name[:44]:44s} +{changed}")

    print(f"\n{touched} books updated · {tot_fill} fields filled · {tot_script} native-script titles/labels")
    return 0


if __name__ == "__main__":
    sys.exit(main())