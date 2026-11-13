#!/usr/bin/env python3
"""Enrich ground-truth scaffolds with authoritative metadata.

For each ``ground_truth/{lang}/{slug}/expected_metadata.json`` this pulls
bibliographic fields from two open, human-curated sources and merges them in:

  1. Wikisource Index page header (``Proofreadpage_index_template``) — the
     proofreading project's header carries title/author/translator/editor/
     illustrator/publisher/place/year/type. Only Telugu Wikisource has this set up.
  2. Internet Archive item metadata (``archive.org/metadata/<id>``) — the DLI/IA
     books expose title/creator/date/publisher/language/pages.

Every value is written as ``prefilled_needs_verification``; nothing here is final
ground truth until a human checks it against the scanned title/copyright pages.

Usage:
    cd backend
    uv run python -m scripts.enrich_ground_truth                 # all books
    uv run python -m scripts.enrich_ground_truth --lang tel
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.schemas.metadata import ALL_METADATA_FIELDS

FIELD_NAMES = [f.field_name for f in ALL_METADATA_FIELDS]
USER_AGENT = (
    "IndicBookMetadataExtractor-GT-PoC/0.1 (https://github.com/Agamya-Samuel/indic-book-metadata-extractor-v2) httpx"
)
GT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth"

# Wikisource Proofreadpage_index_template field labels -> schema fields.
TE_LABELS = {
    "శీర్షిక": "title",
    "రచయిత": "author",
    "అనువాదకులు": "translator",
    "ఎడిటర్": "editor",
    "సంపాదకుడు": "editor",
    "చిత్రకర్త": "illustrators",
    "ప్రచురణకర్త": "publisher",
    "చిరునామా": "place_of_publication",
    "సంవత్సరం": "publication_date",
    "రకం": "form_of_creative_work",
    "సంపుటి": "volume",
    "ఆధారము": "based_on",
    "ఆధారం": "based_on",
    "భాష": "language",
    "ISBN": "isbn",
}
HI_LABELS = {
    "शीर्षक": "title",
    "लेखक": "author",
    "अनुवादक": "translator",
    "संपादक": "editor",
    "चित्रकार": "illustrators",
    "प्रकाशक": "publisher",
    "स्थान": "place_of_publication",
    "पता": "place_of_publication",
    "वर्ष": "publication_date",
    "साल": "publication_date",
    "प्रकार": "form_of_creative_work",
    "खंड": "volume",
    "भाग": "volume",
    "आधार": "based_on",
    "स्रोत": "based_on",
    "भाषा": "language",
    "ISBN": "isbn",
}
EN_LABELS = {
    "title": "title",
    "author": "author",
    "translator": "translator",
    "editor": "editor",
    "illustrator": "illustrators",
    "publisher": "publisher",
    "place": "place_of_publication",
    "address": "place_of_publication",
    "year": "publication_date",
    "date": "publication_date",
    "type": "form_of_creative_work",
    "volume": "volume",
    "source": "based_on",
    "isbn": "isbn",
    "language": "language",
}
LANG_LABEL = {"tel": "Telugu", "te": "Telugu", "hin": "Hindi", "hi": "Hindi"}

# Commons category substrings -> schema field values (conservative, curated).
GENRE_HINTS = {
    "autobiograph": "autobiography",
    "memoir": "memoir",
    "biograph": "biography",
    "novel": "novel",
    "poetry": "poetry",
    "poems": "poetry",
    "dictionary": "dictionary",
    "encyclopedia": "encyclopedia",
    "drama": "drama",
    "play": "drama",
    "essay": "essay",
    "short stories": "short stories",
    "proverb": "proverbs",
}


_NAMESPACE_RE = re.compile(r"^(రచయిత|వర్గం|మూస|పుట|సూచిక|Author|Category|File|Index|Template|Page)\s*:")


def _clean_value(value: str) -> str | None:
    value = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", value)  # [[a|b]] -> b
    value = _NAMESPACE_RE.sub("", value.strip())  # drop [[రచయిత:Name]] namespace
    value = re.sub(r"<[^>]+>", " ", html.unescape(value))
    value = re.sub(r"\{\{[^}]*\}\}", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" |")
    if value.lower() in {"-", "n/a", "na", "none", "null", "unknown"}:
        return None
    return value or None


def _is_placeholder(value: str, slug: str) -> bool:
    """True if a prefilled value is really just a filename/DLI id, not real metadata."""
    v = value.strip()
    if v.lower() in {"-", "n/a", "na", "none", "null", "unknown"}:
        return True
    if v in {slug, slug.replace("_", " ")} or v.lower().endswith(".pdf") or v.startswith("File:"):
        return True
    if re.match(r"^\d{4}\.\d+[.\-]", v):  # DLI id like 2015.328360.Andhra...
        return True
    return bool(_NAMESPACE_RE.match(v))


def parse_index_header(wikitext: str) -> dict[str, str]:
    """Extract schema field -> value from a Proofreadpage index wikitext header."""
    out: dict[str, str] = {}
    for line in wikitext.splitlines():
        m = re.match(r"\s*\|\s*([^=]+?)\s*=(.*)$", line)
        if not m:
            continue
        label, raw = m.group(1).strip(), m.group(2).strip()
        field = TE_LABELS.get(label) or HI_LABELS.get(label) or EN_LABELS.get(label.lower())
        if not field:
            continue
        value = _clean_value(raw)
        if value:
            out[field] = value
    return out


def fetch_index_header(client: httpx.Client, index_url: str) -> dict[str, str]:
    parts = urllib.parse.urlsplit(index_url)
    host, title = parts.netloc, urllib.parse.unquote(parts.path.removeprefix("/wiki/"))
    data = client.get(
        f"https://{host}/w/api.php",
        params={
            "action": "query",
            "titles": title,
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
            "formatversion": "2",
        },
    ).json()
    pages = data.get("query", {}).get("pages", [])
    if not pages or "revisions" not in pages[0]:
        return {}
    return parse_index_header(pages[0]["revisions"][0]["slots"]["main"]["content"])


def ia_identifier(provenance: dict, slug: str) -> str | None:
    for key in ("credit", "download_url"):
        url = provenance.get(key)
        if not url:
            continue
        for marker in ("/items/", "/details/"):
            if marker in url:
                return url.split(marker, 1)[1].split("/", 1)[0]
    m = re.match(r"^(\d{4}\.\d+)\.", slug)  # DLI slug -> in.ernet.dli.<id>
    if m:
        return f"in.ernet.dli.{m.group(1)}"
    return None


def fetch_ia_metadata(client: httpx.Client, ident: str) -> dict[str, str]:
    data = client.get(f"https://archive.org/metadata/{ident}").json()
    meta = data.get("metadata", {})
    out: dict[str, str] = {}

    def put(field: str, raw: object) -> None:
        if raw is None:
            return
        if isinstance(raw, list):
            raw = ", ".join(str(x) for x in raw)
        val = _clean_value(str(raw))
        if val:
            out[field] = val

    put("title", meta.get("title"))
    put("author", meta.get("creator"))
    put("publication_date", meta.get("date") or meta.get("year"))
    put("subject", meta.get("subject"))
    put("sponsor", meta.get("sponsor"))
    put("publisher", meta.get("publisher"))
    desc = str(meta.get("description", ""))
    pub = re.search(r"dc\.publisher:\s*([^<\n]+)", desc)
    if pub:
        out["publisher"] = _clean_value(pub.group(1)) or out.get("publisher", "")
    pages = re.search(r"dc\.description\.totalpages:\s*(\d+)", desc)
    if pages:
        out["pages"] = pages.group(1)
    elif meta.get("imagecount"):
        out["pages"] = str(meta["imagecount"])
    lang = str(meta.get("language", "")).strip()
    if lang in LANG_LABEL:
        out["language"] = LANG_LABEL[lang]
    return out


def fetch_commons_categories(client: httpx.Client, commons_title: str | None) -> dict[str, str]:
    """Derive genre / subject / language hints from a Commons file's categories."""
    if not commons_title:
        return {}
    data = client.get(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query",
            "titles": commons_title,
            "prop": "imageinfo",
            "iiprop": "extmetadata",
            "iiextmetadatafilter": "Categories",
            "format": "json",
            "formatversion": "2",
        },
    ).json()
    pages = data.get("query", {}).get("pages", [])
    if not pages or "imageinfo" not in pages[0]:
        return {}
    raw = pages[0]["imageinfo"][0].get("extmetadata", {}).get("Categories", {}).get("value", "")
    cats = [c.strip() for c in str(raw).split("|") if c.strip()]
    out: dict[str, str] = {}
    genres: list[str] = []
    for cat in cats:
        low = cat.lower()
        for hint, genre in GENRE_HINTS.items():
            if hint in low and genre not in genres:
                genres.append(genre)
        for lang in ("telugu", "hindi"):
            if lang in low and low.endswith("language books"):
                out.setdefault("language", lang.capitalize())
    if genres:
        out["genre"] = ", ".join(genres)
    return out


def enrich_book(client: httpx.Client, gt_path: Path, delay: float) -> dict[str, str]:
    """Merge Wikidata-free open sources into one book's expected_metadata.json."""
    data = json.loads(gt_path.read_text(encoding="utf-8"))
    expected: dict[str, str | None] = data.get("expected_metadata", {})
    status: dict[str, str] = data.get("field_status", {fn: "empty_needs_annotation" for fn in FIELD_NAMES})
    source: dict[str, str | None] = data.get("field_source", dict.fromkeys(FIELD_NAMES))
    prov_path = gt_path.parent / "provenance.json"
    provenance = json.loads(prov_path.read_text(encoding="utf-8")) if prov_path.exists() else {}

    ia_found: dict[str, str] = {}
    ws_found: dict[str, str] = {}
    commons_found: dict[str, str] = {}
    provenance_used: list[str] = []

    # 1) Internet Archive
    ident = ia_identifier(provenance, gt_path.parent.name)
    if ident:
        try:
            ia_found = fetch_ia_metadata(client, ident)
            provenance_used.append(f"https://archive.org/details/{ident}")
        except Exception as e:  # noqa: BLE001
            print(f"  IA error {ident}: {e}", file=sys.stderr)
        time.sleep(delay)

    # 2) Wikisource index header (overrides IA)
    index_urls = provenance.get("wikisource_index_urls") or []
    if index_urls:
        try:
            ws_found = fetch_index_header(client, index_urls[0])
            provenance_used.append(index_urls[0])
        except Exception as e:  # noqa: BLE001
            print(f"  Wikisource error {index_urls[0]}: {e}", file=sys.stderr)
        time.sleep(delay)

    # 3) Commons categories (genre/subject/language hints, lowest priority)
    try:
        commons_found = fetch_commons_categories(client, provenance.get("commons_title"))
    except Exception as e:  # noqa: BLE001
        print(f"  Commons error {provenance.get('commons_title')}: {e}", file=sys.stderr)
    time.sleep(delay)

    # 4) Merge: fill empty fields, and replace filename/DLI-id placeholders.
    slug = gt_path.parent.name
    changed = 0
    for field in FIELD_NAMES:
        if field in ws_found:
            origin: str | None = "wikisource_index"
        elif field in ia_found:
            origin = "internet_archive"
        elif field in commons_found:
            origin = "commons_category"
        else:
            origin = None
        cur = expected.get(field)
        if origin and (not cur or _is_placeholder(str(cur), slug)):
            expected[field] = ws_found.get(field) or ia_found.get(field) or commons_found.get(field)
            source[field] = origin
            changed += 1
        if expected.get(field):
            status[field] = "prefilled_needs_verification"
        elif status.get(field) != "prefilled_needs_verification":
            status[field] = "empty_needs_annotation"

    # Keep label in sync with title when label was only a filename.
    if (
        expected.get("title")
        and not _is_placeholder(str(expected["title"]), slug)
        and (not expected.get("label") or _is_placeholder(str(expected["label"]), slug))
    ):
        expected["label"] = expected["title"]
        source["label"] = source.get("title") or "derived"

    # Drop junk / filename placeholders that no real source filled.
    for field in FIELD_NAMES:
        raw = expected.get(field)
        if not raw:
            continue
        text = str(raw).strip()
        if text.lower() in {"-", "n/a", "na", "none", "null", "unknown"}:
            expected[field] = None
            source[field] = None
            status[field] = "empty_needs_annotation"
        elif source.get(field) in (None, "") and _is_placeholder(text, slug):
            expected[field] = None
            status[field] = "empty_needs_annotation"

    data["expected_metadata"] = expected
    data["field_status"] = status
    data["field_source"] = source
    data["enrichment"] = {
        "sources": provenance_used,
        "enriched_at": datetime.now(UTC).isoformat(),
        "prefilled_fields": sum(1 for v in expected.values() if v),
    }
    gt_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"changed": changed, "prefilled": data["enrichment"]["prefilled_fields"], "sources": provenance_used}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", default=None, choices=["tel", "hin"], help="Only enrich one language")
    parser.add_argument("--root", type=Path, default=GT_ROOT)
    parser.add_argument("--delay", type=float, default=0.3)
    args = parser.parse_args()

    gt_paths = sorted(args.root.glob(f"{args.lang or '*'}/**/expected_metadata.json"))
    if not gt_paths:
        print(f"No GT scaffolds under {args.root}", file=sys.stderr)
        return 1

    print(f"Enriching {len(gt_paths)} books under {args.root}")
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60.0, follow_redirects=True) as client:
        for gt_path in gt_paths:
            slug = gt_path.parent.name
            try:
                result = enrich_book(client, gt_path, args.delay)
            except Exception as e:  # noqa: BLE001
                print(f"  ERROR {slug}: {e}", file=sys.stderr)
                continue
            print(
                f"  {gt_path.parent.parent.name}/{slug}: +{result['changed']} fields "
                f"({result['prefilled']} prefilled) via {len(result['sources'])} source(s)"
            )

    print("\nDone. All values are prefilled_needs_verification until human-checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
