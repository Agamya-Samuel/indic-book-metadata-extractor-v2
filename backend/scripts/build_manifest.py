#!/usr/bin/env python3
"""Rebuild the frozen ground-truth manifest from the per-book envelopes.

The manifest is the dataset index: one row per book under
``ground_truth/{lang}/{slug}/``. It is *derived*, never hand-maintained, so it
stays consistent with the books on disk:

  * ``verification_status`` is read from the book's own ``expected_metadata.json``
    (the fetch scripts append ``unverified`` at download time and are never
    revisited, so the old manifest drifted from the files);
  * field density, OCR-text availability and license come from the envelope and
    the sibling ``wikisource_gt.json``/``provenance.json``;
  * a frozen, work-disjoint, language-stratified ``split`` is assigned
    deterministically (hash of the work key), so re-running is a no-op.

Usage:
    cd backend
    uv run python -m scripts.build_manifest             # rewrite manifest + split freeze
    uv run python -m scripts.build_manifest --no-hash   # skip PDF sha256 (faster)
    uv run python -m scripts.build_manifest --check     # fail if the manifest would change
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.metadata import ALL_METADATA_FIELDS

FIELD_NAMES = [f.field_name for f in ALL_METADATA_FIELDS]
GT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth"
MANIFEST_VERSION = "v1.0"
DEV_RATIO = 0.30
# Shortest normalized title (in chars) that may serve as a work-group prefix.
MIN_WORK_PREFIX = 8


def base_title(slug: str, label: str | None) -> str:
    """Normalized title used to group editions/volumes of the same work."""
    src = label or slug
    return re.sub(r"[^0-9a-z\u0900-\u097f\u0c00-\u0c7f]+", "", unicodedata.normalize("NFKC", src).lower())


def assign_work_keys(rows: list[dict]) -> None:
    """Group editions/volumes of a work by prefix, so no group spans the split.

    A book joins an existing group when its normalized title *extends* that
    group's title (e.g. ``...రత్నమాల`` vs ``...రత్నమాల, ద్వితీయ సంపుటము``),
    independent of the language of the volume marker.
    """
    seen: list[str] = []
    for r in sorted(rows, key=lambda r: len(r["_base"])):
        base = r["_base"]
        parent = next((k for k in seen if len(k) >= MIN_WORK_PREFIX and base.startswith(k)), None)
        r["work_key"] = parent or base
        if parent is None:
            seen.append(base)


def book_year(envelope: dict) -> int | None:
    raw = envelope.get("expected_metadata", {}).get("publication_date")
    if not raw:
        return None
    m = re.search(r"(1[5-9]\d{2}|20\d{2})", str(raw))
    return int(m.group(1)) if m else None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_row(book_dir: Path, lang: str, with_hash: bool) -> dict:
    envelope = json.loads((book_dir / "expected_metadata.json").read_text(encoding="utf-8"))
    em = envelope.get("expected_metadata", {})

    pdf = book_dir / "original.pdf"
    if not pdf.exists():
        pdfs = sorted(book_dir.glob("*.pdf"))
        pdf = pdfs[0] if pdfs else None

    provenance: dict = {}
    prov_path = book_dir / "provenance.json"
    if prov_path.exists():
        provenance = json.loads(prov_path.read_text(encoding="utf-8"))

    ocr_pages = 0
    wsg = book_dir / "wikisource_gt.json"
    if wsg.exists():
        ocr_pages = len(json.loads(wsg.read_text(encoding="utf-8")).get("pages", []))

    present = [f for f in FIELD_NAMES if em.get(f) not in (None, "", [], {})]
    year = book_year(envelope)
    verification = envelope.get("verification") or {}

    return {
        "manifest_version": MANIFEST_VERSION,
        "slug": book_dir.name,
        "lang": lang,
        "_base": base_title(book_dir.name, em.get("label")),
        "work_key": None,  # assigned by assign_work_keys()
        "source": "commons" if provenance else "wikisource",
        "category": envelope.get("source_category") or provenance.get("source_category"),
        "commons_title": provenance.get("commons_title"),
        "license": provenance.get("license_short"),
        "publication_date": em.get("publication_date"),
        "year": year,
        "era": None if year is None else ("pre1900" if year < 1900 else "modern"),
        "pdf": str(pdf) if pdf else None,
        "pdf_size_bytes": pdf.stat().st_size if pdf and pdf.exists() else None,
        "pdf_sha256": sha256_file(pdf) if (with_hash and pdf and pdf.exists()) else None,
        "gt": str(book_dir / "expected_metadata.json"),
        "ocr_gt": ocr_pages > 0,
        "ocr_pages": ocr_pages,
        "field_density": len(present),
        "field_density_ratio": round(len(present) / len(FIELD_NAMES), 3),
        "verification_status": envelope.get("verification_status") or "unverified",
        "scan_confirmed": verification.get("scan_confirmed"),
        "split": None,  # assigned by assign_splits()
    }


def assign_splits(rows: list[dict]) -> None:
    """Deterministic, work-disjoint, language-stratified dev/test assignment."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        groups.setdefault((r["lang"], r["work_key"]), []).append(r)

    by_lang: dict[str, list[tuple[str, list[dict]]]] = {}
    for (lang, wk), members in groups.items():
        by_lang.setdefault(lang, []).append((wk, members))

    for lang, grouplist in by_lang.items():
        grouplist.sort(key=lambda g: hashlib.sha256(f"{lang}/{g[0]}".encode()).hexdigest())
        n_books = sum(len(m) for _, m in grouplist)
        dev_target = round(DEV_RATIO * n_books)
        dev_books = 0
        for _, members in grouplist:
            split = "dev" if dev_books < dev_target else "test"
            for r in members:
                r["split"] = split
            if split == "dev":
                dev_books += len(members)


def build(gt_root: Path, with_hash: bool) -> tuple[list[dict], dict]:
    rows = [
        build_row(gt.parent, gt.parent.parent.name, with_hash)
        for gt in sorted(gt_root.glob("*/*/expected_metadata.json"))
    ]
    rows.sort(key=lambda r: (r["lang"], r["slug"]))
    assign_work_keys(rows)
    assign_splits(rows)

    counts: dict[str, dict[str, int]] = {}
    for r in rows:
        counts.setdefault(r["lang"], {"dev": 0, "test": 0})[r["split"]] += 1
    freeze = {
        "split_version": MANIFEST_VERSION,
        "dev_ratio": DEV_RATIO,
        "rule": "sha256(work_key) within language stratum; work-groups are disjoint",
        "counts": counts,
        "dev": sorted(r["slug"] for r in rows if r["split"] == "dev"),
        "test": sorted(r["slug"] for r in rows if r["split"] == "test"),
    }
    return rows, freeze


def render(rows: list[dict]) -> str:
    return "".join(
        json.dumps({k: v for k, v in r.items() if not k.startswith("_")}, ensure_ascii=False) + "\n"
        for r in rows
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=GT_ROOT)
    ap.add_argument("--no-hash", action="store_true", help="skip PDF sha256")
    ap.add_argument("--check", action="store_true", help="exit 1 if the manifest would change")
    args = ap.parse_args()

    rows, freeze = build(args.root, not args.no_hash)
    manifest_text = render(rows)
    manifest_path = args.root / "manifest.jsonl"
    split_path = args.root / "splits" / f"gt-split-{MANIFEST_VERSION}.json"

    if args.check:
        current = manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else ""
        if current != manifest_text:
            print(f"manifest is stale: {manifest_path} would change", file=sys.stderr)
            return 1
        print(f"manifest is current ({len(rows)} books)")
        return 0

    manifest_path.write_text(manifest_text, encoding="utf-8")
    split_path.parent.mkdir(parents=True, exist_ok=True)
    freeze["created_at"] = datetime.now(UTC).isoformat()
    split_path.write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {len(rows)} rows -> {manifest_path}")
    print(f"wrote split freeze -> {split_path}")
    for lang, c in sorted(freeze["counts"].items()):
        print(f"  {lang}: dev={c['dev']} test={c['test']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
