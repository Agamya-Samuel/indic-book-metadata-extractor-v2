#!/usr/bin/env python3
"""Fetch Wikimedia Commons book PDFs + catalog metadata into per-book ground-truth scaffolds.

PoC tool for plans/002-ground-truth-poc.md. Metadata-only by default; --download fetches PDFs.
Prefill comes from authoritative Commons catalog metadata, but EVERY field is UNVERIFIED and
must be human-checked against the PDF + its Wikisource index before it counts as ground truth.

Usage:
    cd backend
    uv run python -m scripts.fetch_commons_ground_truth --limit 5
    uv run python -m scripts.fetch_commons_ground_truth \
        --category "Category:PDF books in Telugu" --download --limit 10
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.schemas.metadata import ALL_METADATA_FIELDS

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = (
    "IndicBookMetadataExtractor-GT-PoC/0.1 (https://github.com/Agamya-Samuel/indic-book-metadata-extractor-v2) httpx"
)
DEFAULT_CATEGORIES = ["Category:PDF books in Telugu", "Category:Hindi-language books"]
FIELD_NAMES = [f.field_name for f in ALL_METADATA_FIELDS]
LANG_BY_CATEGORY = {"telugu": "tel", "hindi": "hin"}
LANG_LABEL = {"tel": "Telugu", "hin": "Hindi"}


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", html.unescape(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _lang_for(category: str, override: str | None) -> str:
    if override:
        return override
    low = category.lower()
    for key, lang in LANG_BY_CATEGORY.items():
        if key in low:
            return lang
    return "tel"


def _slugify(title: str) -> str:
    name = title.removeprefix("File:")
    name = re.sub(r"\.pdf$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[^\w.-]+", "_", name, flags=re.UNICODE)
    return name.strip("_")[:120] or "book"


def _api_get(client: httpx.Client, params: dict, delay: float) -> dict:
    merged = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
    for attempt in range(5):
        resp = client.get(API, params=merged)
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(delay * 2 * (attempt + 1))
            continue
        resp.raise_for_status()
        data = resp.json()
        err = data.get("error")
        if err:
            if err.get("code") == "maxlag":
                time.sleep(delay * 2 * (attempt + 1))
                continue
            raise RuntimeError(f"API error {err.get('code')}: {err.get('info')}")
        time.sleep(delay)
        return data
    raise RuntimeError(f"API retries exhausted: {params.get('list') or params.get('prop')}")


def category_pdf_files(client: httpx.Client, category: str, delay: float, recurse: bool, depth: int = 2) -> list[str]:
    """Return PDF file titles directly in a category (optionally walking subcategories)."""
    files: list[str] = []
    subcats: list[str] = []
    cmcontinue: str | None = None
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmtype": "file|subcat",
            "cmlimit": "500",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        data = _api_get(client, params, delay)
        for member in data.get("query", {}).get("categorymembers", []):
            title = member.get("title", "")
            if title.startswith("File:") and title.lower().endswith(".pdf"):
                files.append(title)
            elif title.startswith("Category:"):
                subcats.append(title)
        cmcontinue = data.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            break
    if recurse and depth > 0:
        for sub in subcats:
            files.extend(category_pdf_files(client, sub, delay, recurse, depth - 1))
    seen: set[str] = set()
    out: list[str] = []
    for title in files:
        if title not in seen:
            seen.add(title)
            out.append(title)
    return out


def file_info(client: httpx.Client, title: str, delay: float) -> dict:
    params = {
        "action": "query",
        "titles": title,
        "prop": "imageinfo|globalusage",
        "iiprop": "url|size|mime|extmetadata",
        "gulimit": "50",
    }
    data = _api_get(client, params, delay)
    pages = data.get("query", {}).get("pages", [])
    page = pages[0] if pages else {}
    imageinfo = (page.get("imageinfo") or [{}])[0]
    return {"title": title, "imageinfo": imageinfo, "globalusage": page.get("globalusage") or []}


def _wikisource_index_urls(globalusage: list[dict], limit: int = 10) -> list[str]:
    """Wikisource Index/Book pages only.

    ``globalusage`` lists every page transcluding the file, which includes one proofread
    subpage per PDF page (``Page:….pdf/1``, ``/2``, …) — unbounded and useless here.
    Namespace prefixes are localised (Telugu ``సూచిక:``/``పుట:``), so filter structurally:
    proofread subpages are the only entries containing ``/``.
    """
    seen: set[str] = set()
    for usage in globalusage:
        url = usage.get("url")
        wiki = (usage.get("wiki") or "").lower()
        if not url or "wikisource" not in wiki or "/" in (usage.get("title") or ""):
            continue
        seen.add(url)
    return sorted(seen)[:limit]


def prefill(info: dict, lang: str, category: str) -> tuple[dict, dict, dict, str | None]:
    """Map Commons extmetadata to a conservative, all-49-field GT scaffold + provenance."""
    ext = info["imageinfo"].get("extmetadata") or {}

    def g(key: str) -> str | None:
        return _strip_html((ext.get(key) or {}).get("value"))

    expected: dict[str, str | None] = {fn: None for fn in FIELD_NAMES}
    status = {fn: "empty_needs_annotation" for fn in FIELD_NAMES}

    def setf(fn: str, val: str | None) -> None:
        if val:
            expected[fn] = val
            status[fn] = "prefilled_needs_verification"

    title = g("ObjectName")
    setf("author", g("Artist") or g("Author"))
    setf("title", title)
    setf("label", title)
    setf("description_work", g("ImageDescription"))
    setf("language", LANG_LABEL.get(lang))
    setf("original_language", LANG_LABEL.get(lang))

    license_short = g("LicenseShortName")
    wikisource_urls = _wikisource_index_urls(info["globalusage"])
    provenance = {
        "commons_title": info["title"],
        "source_category": category,
        "file_description_url": "https://commons.wikimedia.org/wiki/" + info["title"].replace(" ", "_"),
        "download_url": info["imageinfo"].get("url"),
        "mime": info["imageinfo"].get("mime"),
        "size_bytes": info["imageinfo"].get("size"),
        "license_short": license_short,
        "license_url": g("LicenseUrl"),
        "permission": g("Permission"),
        "credit": g("Credit"),
        "artist_raw": (ext.get("Artist") or {}).get("value"),
        "wikisource_index_urls": wikisource_urls,
        "wikisource_usage_count": len(info["globalusage"]),
        "globalusage_sample": info["globalusage"][:25],
        "retrieved_at": datetime.now(UTC).isoformat(),
    }
    return expected, status, provenance, license_short


def download_pdf(client: httpx.Client, url: str, dest: Path, delay: float) -> None:
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with client.stream("GET", url) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as fh:
            fh.writelines(resp.iter_bytes())
    tmp.replace(dest)
    time.sleep(delay)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--category", action="append", default=None, help="Repeatable; defaults to the two PoC categories"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth",
    )
    parser.add_argument("--limit", type=int, default=5, help="Max books per category (default 5)")
    parser.add_argument("--download", action="store_true", help="Also download PDFs (default: metadata-only)")
    parser.add_argument("--recurse", action="store_true", help="Walk subcategories (useful for Hindi)")
    parser.add_argument("--depth", type=int, default=2, help="Subcategory recursion depth (default 2)")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between API calls (default 0.5)")
    parser.add_argument("--lang", default=None, choices=["tel", "hin"], help="Override language hint")
    parser.add_argument("--overwrite", action="store_true", help="Rewrite existing GT scaffolds")
    args = parser.parse_args()

    categories = args.category or DEFAULT_CATEGORIES
    args.out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60.0, follow_redirects=True) as client:
        for category in categories:
            lang = _lang_for(category, args.lang)
            print(f"== {category} (lang={lang}) ==")
            try:
                files = category_pdf_files(client, category, args.delay, args.recurse, args.depth)
            except Exception as e:  # noqa: BLE001 - report and continue with other categories
                print(f"  ERROR enumerating: {e}", file=sys.stderr)
                continue
            selected = files[: args.limit]
            print(f"  {len(files)} PDFs found; taking {len(selected)}")
            for title in selected:
                slug = _slugify(title)
                book_dir = args.out / lang / slug
                gt_path = book_dir / "expected_metadata.json"
                if gt_path.exists() and not args.overwrite:
                    print(f"  skip (exists): {slug}")
                    continue
                try:
                    info = file_info(client, title, args.delay)
                    expected, status, provenance, license_short = prefill(info, lang, category)
                    if args.download and provenance.get("download_url"):
                        download_pdf(client, provenance["download_url"], book_dir / "original.pdf", args.delay)
                except Exception as e:  # noqa: BLE001 - per-file failures must not abort the batch
                    print(f"  ERROR {title}: {e}", file=sys.stderr)
                    continue
                book_dir.mkdir(parents=True, exist_ok=True)
                gt = {
                    "description": f"{expected.get('title') or slug} — Commons GT scaffold (UNVERIFIED)",
                    "language": lang,
                    "quality": "commons",
                    "source_category": category,
                    "total_pages": None,
                    "recommended_pages": None,
                    "verification_status": "unverified",
                    "expected_metadata": expected,
                    "field_status": status,
                    "notes": (
                        "Prefilled from Commons catalog metadata. EVERY field must be human-verified against "
                        "the PDF + Wikisource index; set verification_status=verified before scoring."
                    ),
                }
                gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")
                (book_dir / "provenance.json").write_text(
                    json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                rows.append(
                    {
                        "slug": slug,
                        "lang": lang,
                        "category": category,
                        "commons_title": title,
                        "license": license_short,
                        "pdf": str(book_dir / "original.pdf") if args.download else None,
                        "gt": str(gt_path),
                        "verification_status": "unverified",
                    }
                )
                print(f"  + {slug} [{license_short}]")

    with open(args.out / "manifest.jsonl", "a", encoding="utf-8") as fh:
        fh.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)

    print(f"\nWrote {len(rows)} GT scaffolds under {args.out}")
    print("NEXT: human-verify every field; only score books with verification_status=verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
