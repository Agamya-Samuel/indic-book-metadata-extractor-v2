#!/usr/bin/env python3
"""Build page-level OCR ground truth for a Commons book from Wikisource proofreading.

For a ground-truth book directory (``original.pdf`` + ``provenance.json``), this
resolves the book's Wikisource *Index* page, enumerates its ``Page:`` records with
their proofreading levels, validates that the local PDF is byte-identical to the
Commons file, and emits an aligned manifest of verified page text.

Wikisource ``Page:`` titles are ``<file name>/<n>`` where ``n`` is the page number
*inside the PDF*, so alignment is positional — but only if the local PDF is the
same file Commons serves. That is checked by SHA1, never assumed.

Notes on per-wiki configuration, both learned the hard way:

* ``Index:``/``Page:`` namespace IDs are **not** the documentation defaults
  (102/104). Telugu Wikisource has Index=106, Page=104; Hindi Wikisource has
  Index=252, Page=250 because its 104/106 are already taken. IDs are resolved
  from ``siteinfo`` at runtime.
* Commons ``globalusage`` is an unreliable way to find a book's index page: it
  reports nothing for every Hindi book even though the index pages exist. The
  index is therefore located by searching the target wiki, with the provenance
  links used only as a hint.

Usage:
    cd backend
    uv run python -m scripts.fetch_wikisource_gt \\
        --book-dir tests/fixtures/ground_truth/tel/2015.373190.Athma-Charitramu

    # enumerate levels only, do not download page text
    uv run python -m scripts.fetch_wikisource_gt --book-dir ... --max-text 0
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import httpx

USER_AGENT = (
    "IndicBookMetadataExtractor-OCRStudy/0.1 "
    "(https://github.com/Agamya-Samuel/indic-book-metadata-extractor-v2) httpx"
)
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# Proofreading levels that count as human-verified text.
VERIFIED_LEVELS = {"3", "4"}
# pageprops key carrying the proofreading level. The API's documented name is
# "proofread-page-quality", but the value is actually exposed under this
# underscore form; both are accepted below.
QUALITY_PROP = "proofread_page_quality_level"

# Templates that only set a style (font size, spacing) and carry no text.
DROP_TEMPLATES = {
    "p",
    "fs100",
    "fs110",
    "fs125",
    "fs150",
    "fs200",
    "rule",
    "gap",
    "nop",
    "clear",
    "rh",
    "rh/",
    "running header",
}
# Templates whose unnamed arguments are the visible text.
UNWRAP_TEMPLATES = {
    "larger",
    "smaller",
    "x-larger",
    "xx-larger",
    "xxx-larger",
    "center",
    "left",
    "right",
    "c",
    "sc",
    "asc",
    "u",
    "underline",
    "nowrap",
}
LEVEL_LABEL = {
    "0": "no text",
    "1": "not proofread",
    "2": "problematic",
    "3": "proofread",
    "4": "validated",
}


def _api_get(api: str, client: httpx.Client, params: dict, delay: float) -> dict:
    """GET an API endpoint with maxlag/429 backoff (mirrors fetch_commons_ground_truth)."""
    merged = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
    last_error: Exception | None = None
    for attempt in range(6):
        resp = client.get(api, params=merged)
        if resp.status_code in (429, 500, 502, 503, 504):
            last_error = RuntimeError(f"HTTP {resp.status_code}")
            time.sleep(delay * 3 * (attempt + 1))
            continue
        resp.raise_for_status()
        data = resp.json()
        error = data.get("error")
        if error:
            if error.get("code") == "maxlag":
                last_error = RuntimeError("maxlag")
                time.sleep(delay * 3 * (attempt + 1))
                continue
            raise RuntimeError(f"API error {error.get('code')}: {error.get('info')}")
        time.sleep(delay)
        return data
    raise RuntimeError(f"API retries exhausted ({last_error}): {params.get('list') or params.get('prop')}")


def resolve_namespaces(api: str, client: httpx.Client, delay: float) -> dict[str, int]:
    """Map canonical namespace names ('Index', 'Page') to their IDs on this wiki."""
    data = _api_get(api, client, {"action": "query", "meta": "siteinfo", "siprop": "namespaces"}, delay)
    found: dict[str, int] = {}
    for ns_id, meta in data["query"]["namespaces"].items():
        canonical = meta.get("canonical") or ""
        if canonical in ("Index", "Page"):
            found[canonical] = int(ns_id)
    missing = {"Index", "Page"} - set(found)
    if missing:
        raise RuntimeError(f"wiki does not expose namespaces: {sorted(missing)}")
    return found


def find_index_page(
    api: str,
    client: httpx.Client,
    index_ns: int,
    file_title: str,
    hint_urls: list[str],
    delay: float,
) -> str | None:
    """Locate the book's Index page on the target wiki."""
    stem = re.sub(r"^File:", "", file_title)
    stem = re.sub(r"\.pdf$", "", stem, flags=re.IGNORECASE)

    # 1. Index pages named exactly after the file (the common case).
    data = _api_get(
        api,
        client,
        {
            "action": "query",
            "list": "allpages",
            "apnamespace": str(index_ns),
            "apprefix": stem,
            "aplimit": "10",
        },
        delay,
    )
    if data["query"]["allpages"]:
        return data["query"]["allpages"][0]["title"]

    # 2. Fall back to search inside the Index namespace.
    data = _api_get(
        api,
        client,
        {
            "action": "query",
            "list": "search",
            "srsearch": stem,
            "srnamespace": str(index_ns),
            "srlimit": "5",
        },
        delay,
    )
    hits = [h["title"] for h in data["query"]["search"]]
    if hits:
        return hits[0]

    # 3. Last resort: a provenance URL recorded by the Commons fetcher.
    for url in hint_urls:
        tail = httpx.URL(url).path.rstrip("/").rsplit("/", 1)[-1]
        if tail:
            return httpx.URL(url).params.get("title") or tail
    return None


def page_number(title: str) -> int | None:
    match = re.search(r"/(\d+)$", title)
    return int(match.group(1)) if match else None


def fetch_qualities(
    api: str, client: httpx.Client, page_ns: int, file_title: str, delay: float
) -> tuple[list[str], dict[int, str | None]]:
    """Return all ``Page:`` titles for the file and their proofreading level."""
    stem = re.sub(r"^File:", "", file_title)
    titles: list[str] = []
    cont: dict = {}
    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "apnamespace": str(page_ns),
            "apprefix": f"{stem}/",
            "aplimit": "500",
            **cont,
        }
        data = _api_get(api, client, params, delay)
        titles.extend(p["title"] for p in data["query"]["allpages"])
        cont = data.get("continue") or {}
        if not cont:
            break

    qualities: dict[int, str | None] = {}
    for start in range(0, len(titles), 50):
        batch = titles[start : start + 50]
        data = _api_get(
            api,
            client,
            {
                "action": "query",
                "titles": "|".join(batch),
                "prop": "pageprops",
                "ppprop": QUALITY_PROP,
            },
            delay,
        )
        for page in data["query"]["pages"]:
            num = page_number(page.get("title", ""))
            if num is not None:
                props = page.get("pageprops") or {}
                qualities[num] = props.get(QUALITY_PROP) or props.get("proofread-page-quality")
    return titles, qualities


def clean_page_text(wikitext: str) -> str:
    """Reduce ``Page:`` wikitext to the transcribed body text.

    ProofreadPage wraps a page in ``<noinclude>`` blocks (page-quality banner,
    header/footer templates, references). Those are not part of the scan text and
    must go, or the ground truth would contain markup the OCR never saw.

    Title/front-matter pages are also built almost entirely out of formatting
    templates, so a second pass handles them: templates that only set a CSS class
    (``{{p|fs200}}``) carry no text and are dropped, while templates that wrap
    visible text (``{{larger|AUTOBIOGRAPHY}}``) are unwrapped to their content.
    Unknown templates are left intact on purpose - guessing at an unfamiliar
    template would silently invent or delete ground-truth text.
    """
    text = re.sub(r"<noinclude\s*/>", "", wikitext, flags=re.IGNORECASE)
    text = re.sub(r"<noinclude>.*?</noinclude>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<pagequality[^>]*/>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<references\s*/>", "", text, flags=re.IGNORECASE)

    # Multi-line templates for embedded images carry parameters, not scan text.
    text = re.sub(
        r"\{\{\s*(?:Css image crop|raw image|FI|figure|image|img)\s*\|.*?\}\}",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        # Header/footer templates sit alone on a line ({{rh|...}}, {{running header|...}}).
        if (
            stripped.startswith("{{")
            and stripped.endswith("}}")
            and stripped.count("{{") == stripped.count("}}")
            and re.match(r"\{\{\s*(rh|running header|rh/|header)\s*[|}]", stripped, re.IGNORECASE)
        ):
            continue
        kept.append(stripped)
    text = "\n".join(kept)

    text = _resolve_templates(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"'{2,}", "", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _resolve_templates(text: str, rounds: int = 6) -> str:
    """Drop or unwrap the formatting templates used on Wikisource book pages."""
    innermost = re.compile(r"\{\{([^{}]*)\}\}")
    for _ in range(rounds):
        replaced = False

        def substitute(match: re.Match[str]) -> str:
            nonlocal replaced
            body = match.group(1)
            parts = [p.strip() for p in body.split("|")]
            name = parts[0].strip().lower()
            if name in DROP_TEMPLATES:
                replaced = True
                return ""
            if name in UNWRAP_TEMPLATES:
                positional = [p for p in parts[1:] if "=" not in p]
                if positional:
                    replaced = True
                    return " ".join(positional)
                replaced = True
                return ""
            return match.group(0)

        text = innermost.sub(substitute, text)
        if not replaced:
            break
    return text


def fetch_page_text(api: str, client: httpx.Client, title: str, delay: float) -> str:
    data = _api_get(
        api,
        client,
        {"action": "query", "titles": title, "prop": "revisions", "rvprop": "content", "rvslots": "main"},
        delay,
    )
    page = data["query"]["pages"][0]
    revisions = page.get("revisions") or []
    if not revisions:
        return ""
    content = revisions[0].get("slots", {}).get("main", {}).get("content", "")
    return clean_page_text(content)


def fetch_page_rendered(api: str, client: httpx.Client, title: str, delay: float) -> str:
    """Transcribed text taken from the *rendered* page instead of wikitext.

    Front matter (contents lists, tables, ornaments) is assembled from templates
    whose arguments are not the visible text - a TOC entry is
    ``{{dotted TOC page listing|[[<chapter>|18. నూతన దృక్పథము]]|67}}`` where only
    the display text and the page number are on the scan. Rendering resolves that
    for us; the alternative is reimplementing Wikisource's templates.

    The proofread status banner ProofreadPage injects into every ``Page:`` render
    is removed by its CSS class, since it is a wiki artifact and not scan text.
    """
    data = _api_get(api, client, {"action": "parse", "page": title, "prop": "text"}, delay)
    markup = (data.get("parse") or {}).get("text")
    if not markup:
        return ""
    text = re.sub(r"<style.*?</style>", "", markup, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<div class="prp-page-qualityheader.*?</div>', "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    # Dotted leaders are typographic filler, not characters on the scan.
    text = re.sub(r"(?:\s*\.){4,}\s*", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"(?m)^[ \t]+$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def local_sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def commons_sha1(client: httpx.Client, file_title: str, delay: float) -> tuple[str | None, int | None]:
    data = _api_get(
        COMMONS_API,
        client,
        {"action": "query", "titles": file_title, "prop": "imageinfo", "iiprop": "sha1|size"},
        delay,
    )
    page = data["query"]["pages"][0]
    info = (page.get("imageinfo") or [{}])[0]
    return info.get("sha1"), info.get("size")


def pdf_page_count(path: Path) -> int:
    import fitz  # PyMuPDF, imported lazily so `--help` stays cheap

    with fitz.open(path) as doc:
        return doc.page_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--book-dir", type=Path, required=True, help="Ground-truth book dir (original.pdf + provenance.json)")
    parser.add_argument("--wiki", default=None, help="Override wiki host (default: derived from lang)")
    parser.add_argument("--max-text", type=int, default=40, help="Verified pages whose text to download (default 40)")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between API calls (default 1.0)")
    parser.add_argument("--out", type=Path, default=None, help="Output JSON (default: <book-dir>/wikisource_gt.json)")
    args = parser.parse_args()

    book_dir: Path = args.book_dir
    pdf_path = book_dir / "original.pdf"
    provenance_path = book_dir / "provenance.json"
    if not pdf_path.exists():
        print(f"missing {pdf_path}", file=sys.stderr)
        return 2
    if not provenance_path.exists():
        print(f"missing {provenance_path}", file=sys.stderr)
        return 2

    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    file_title: str = provenance["commons_title"]
    host = (
        args.wiki
        or provenance.get("wiki")
        or ("te.wikisource.org" if "telugu" in provenance.get("source_category", "").lower() else None)
    )
    if not host:
        print("cannot infer wiki host; pass --wiki", file=sys.stderr)
        return 2
    api = f"https://{host}/w/api.php"

    print(f"book      : {book_dir.name}")
    print(f"commons   : {file_title}")
    print(f"wiki      : {host}")

    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60.0, follow_redirects=True) as client:
        ns_ids = resolve_namespaces(api, client, args.delay)
        print(f"namespaces: Index={ns_ids['Index']} Page={ns_ids['Page']}")

        remote_sha, remote_size = commons_sha1(client, file_title, args.delay)
        local = local_sha1(pdf_path)
        pages_in_pdf = pdf_page_count(pdf_path)
        identity = remote_sha == local
        print(f"identity  : local sha1 {local[:12]}… vs commons {str(remote_sha)[:12]}… -> {'MATCH' if identity else 'MISMATCH'}")
        print(f"pdf pages : {pages_in_pdf} (commons size {remote_size} bytes)")

        index_title = find_index_page(
            api, client, ns_ids["Index"], file_title, provenance.get("wikisource_index_urls") or [], args.delay
        )
        if not index_title:
            print("no Index page found on this wiki — no verified GT available", file=sys.stderr)
            return 1
        print(f"index     : {index_title}")

        titles, qualities = fetch_qualities(api, client, ns_ids["Page"], file_title, args.delay)
        verified = sorted(n for n, level in qualities.items() if level in VERIFIED_LEVELS)
        buckets: dict[str, int] = {}
        for level in qualities.values():
            key = level or "unset"
            buckets[key] = buckets.get(key, 0) + 1
        print(f"page recs : {len(titles)} (levels: " + ", ".join(f"{k}={v}" for k, v in sorted(buckets.items())) + ")")
        print(f"verified  : {len(verified)} pages at level 3/4")

        coverage = len(set(qualities) & set(range(1, pages_in_pdf + 1)))
        print(f"coverage  : {coverage}/{pages_in_pdf} PDF pages have a Page: record")
        if identity and coverage < pages_in_pdf:
            # Positional alignment is only sound when every PDF page is represented.
            print("WARNING: local PDF is identical to Commons but some pages lack a Page: record", file=sys.stderr)

        to_fetch = verified[: args.max_text]
        title_prefix = re.sub(r"/\d+$", "", titles[0]) if titles else None
        if to_fetch and not title_prefix:
            print("no Page: titles to derive a prefix from", file=sys.stderr)
            return 1
        texts: list[dict] = []
        for num in to_fetch:
            title = f"{title_prefix}/{num}"
            raw = fetch_page_text(api, client, title, args.delay)
            residue = ("{{" in raw) or ("}}" in raw)
            if residue:
                # Template-heavy page: the wikitext is not the visible text.
                rendered = fetch_page_rendered(api, client, title, args.delay)
                if rendered and "{{" not in rendered and "}}" not in rendered:
                    raw, residue = rendered, False
            if not raw:
                print(f"  page {num}: empty after cleaning, skipped", file=sys.stderr)
                continue
            texts.append(
                {
                    "page": num,
                    "level": int(qualities[num] or 3),
                    "title": title,
                    "text": unicodedata.normalize("NFC", raw),
                    # Unresolved wiki markup means the cleaned text is not a faithful
                    # transcript; the harness must exclude such pages rather than score them.
                    "markup_residue": residue,
                }
            )
        print(f"fetched   : {len(texts)} verified page texts")
        residue = sum(1 for t in texts if t["markup_residue"])
        if residue:
            print(f"residue   : {residue}/{len(texts)} page texts still contain wiki markup (flagged, not silently dropped)")

    payload = {
        "book": book_dir.name,
        "commons_title": file_title,
        "wiki": host,
        "namespaces": ns_ids,
        "index_title": index_title,
        "pdf_pages": pages_in_pdf,
        "identity_verified": identity,
        "local_sha1": local,
        "commons_sha1": remote_sha,
        "level_counts": {k: v for k, v in sorted(buckets.items())},
        "verified_pages": verified,
        "coverage_pages": coverage,
        "pages": texts,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    out_path = args.out or (book_dir / "wikisource_gt.json")
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote     : {out_path}")
    return 0 if identity and verified else 1


if __name__ == "__main__":
    sys.exit(main())
