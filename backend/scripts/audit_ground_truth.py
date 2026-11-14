"""Mechanical corroboration of the ground-truth scaffolds.

For each book, checks whether each prefilled expected value appears in the
book's proofread Wikisource text. This does NOT replace human verification —
it flags which scaffold values are corroborated by the source and which are
uncheckable (e.g. Latin-script author vs Telugu body).

Usage:
    python -m scripts.audit_ground_truth --output /tmp/gt_audit.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

GT_ROOT = BACKEND / "tests" / "fixtures" / "ground_truth"

# Fields whose values are expected to be findable in the front-matter text.
CHECKABLE = [
    "label",
    "title",
    "subtitle",
    "author",
    "publisher",
    "publisher_telugu",
    "place_of_publication",
    "publication_date",
    "language",
    "original_language",
    "form_of_creative_work",
    "edition_number",
    "volume",
    "pages",
    "isbn",
]

_STRIP = re.compile(r"[\s\u200c\u200d]+")


def norm(s: str) -> str:
    return _STRIP.sub("", unicodedata.normalize("NFC", s or "").lower())


def script_of(s: str) -> str:
    for ch in s or "":
        cp = ord(ch)
        if 0x0C00 <= cp <= 0x0C7F:
            return "tel"
        if 0x0900 <= cp <= 0x097F:
            return "hin"
        if ch.isalpha():
            return "lat"
    return "other"


def book_text(book_dir: Path) -> str:
    ws = book_dir / "wikisource_gt.json"
    if not ws.exists():
        return ""
    data = json.loads(ws.read_text(encoding="utf-8"))
    return "\n".join((p.get("text") or "") for p in data.get("pages", []))


def audit_book(book_dir: Path) -> dict:
    env = json.loads((book_dir / "expected_metadata.json").read_text(encoding="utf-8"))
    expected = env.get("expected_metadata", env)
    text = book_text(book_dir)
    ntext = norm(text)
    fields = {}
    for name in CHECKABLE:
        value = expected.get(name)
        if value in (None, ""):
            fields[name] = {"status": "null"}
            continue
        value = str(value)
        hit = norm(value) in ntext
        status = "corroborated" if hit else "not_found"
        rec = {"status": status, "value": value[:60]}
        if not hit:
            rec["value_script"] = script_of(value)
            rec["text_script"] = script_of(text)
        fields[name] = rec
    corroborated = sum(1 for f in fields.values() if f["status"] == "corroborated")
    not_found = sum(1 for f in fields.values() if f["status"] == "not_found")
    return {
        "book": book_dir.name,
        "language": book_dir.parent.name,
        "verification_status": env.get("verification_status"),
        "chars_of_text": len(text),
        "corroborated": corroborated,
        "not_found": not_found,
        "null": sum(1 for f in fields.values() if f["status"] == "null"),
        "fields": fields,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--languages", default="tel,hin")
    args = ap.parse_args()
    languages = [x.strip() for x in args.languages.split(",") if x.strip()]

    reports = []
    for lang_dir in sorted(GT_ROOT.iterdir()):
        if not lang_dir.is_dir() or (languages and lang_dir.name not in languages):
            continue
        for book_dir in sorted(lang_dir.iterdir()):
            if (book_dir / "expected_metadata.json").exists():
                reports.append(audit_book(book_dir))

    print(f"{'book':50s} {'corrob':>6s} {'not_found':>9s} {'null':>5s}")
    for r in reports:
        print(f"{r['language'] + '/' + r['book']:50s} {r['corroborated']:6d} {r['not_found']:9d} {r['null']:5d}")

    totals = {
        "books": len(reports),
        "corroborated": sum(r["corroborated"] for r in reports),
        "not_found": sum(r["not_found"] for r in reports),
    }
    print(f"\nTotal: {totals}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({"totals": totals, "books": reports}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Report -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
