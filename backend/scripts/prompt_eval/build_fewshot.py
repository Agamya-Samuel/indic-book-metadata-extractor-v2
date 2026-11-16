"""Build real, batch-matched few-shot exemplars from held-out ground-truth books.

The production examples in ``prompt_profiles.SYNTHETIC_FEW_SHOT`` are invented
books with invented ISBNs, and the same core-identity-shaped example is
injected into every batch — including batches whose schema does not contain
those keys. This script produces the alternative: real text from real books,
and only the fields that belong to the batch being asked about.

The source books are **held out of scoring** (recorded in
``prompt_eval/manifest.json`` → ``holdout``) so the model cannot be credited
for memorising an exemplar.

    cd backend
    python -m scripts.prompt_eval.build_fewshot --track ocr --per-language 2
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from scripts.prompt_eval import common

EXEMPLAR_INPUT_CHARS = 700
MIN_FIELDS_PER_BATCH = 1


def _batch_values(expected: dict, batch_name: str) -> dict[str, str]:
    from app.schemas.metadata import METADATA_BATCHES

    values = {}
    for field_name in METADATA_BATCHES[batch_name].model_fields:
        if field_name == "custom_fields":
            continue
        raw = expected.get(field_name)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            values[field_name] = text
    return values


def _pick_holdout(
    books: list[common.Book],
    track: str,
    per_language: int,
) -> list[common.Book]:
    """Deterministically choose books with the richest ground truth per language.

    Richest-first (then slug) so the choice is reproducible and the exemplars
    actually have values to show. Only books with corpus text in this track
    qualify.
    """
    by_language: dict[str, list[tuple[int, common.Book]]] = {}
    for book in books:
        if not common.load_corpus(track, book):
            continue
        expected = common.load_expected(book)
        filled = sum(1 for value in expected.values() if value not in (None, ""))
        by_language.setdefault(book.language, []).append((filled, book))

    holdout: list[common.Book] = []
    for language in sorted(by_language):
        ranked = sorted(by_language[language], key=lambda pair: (-pair[0], pair[1].slug))
        holdout.extend(book for _, book in ranked[:per_language])
    return holdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track", default="ocr", choices=common.TRACKS)
    parser.add_argument("--per-language", type=int, default=2)
    parser.add_argument("--langs", default="")
    args = parser.parse_args()

    from app.schemas.metadata import BATCH_FIELD_ORDER

    languages = [c.strip() for c in args.langs.split(",") if c.strip()] or None
    books = common.discover_books(languages=languages)
    holdout = _pick_holdout(books, args.track, args.per_language)
    if not holdout:
        print(f"No book has a {args.track} corpus yet; run build_corpus.py first.")
        return 1

    manifest = common.load_manifest()
    manifest["holdout"] = sorted(b.sample_id for b in holdout)
    manifest.setdefault("fewshot", {})["track"] = args.track
    common.save_manifest(manifest)

    by_language: dict[str, list[common.Book]] = {}
    for book in holdout:
        by_language.setdefault(book.language, []).append(book)

    written = 0
    for language, lang_books in sorted(by_language.items()):
        for batch_name in BATCH_FIELD_ORDER:
            best: tuple[int, common.Book, dict[str, str]] | None = None
            for book in lang_books:
                values = _batch_values(common.load_expected(book), batch_name)
                if len(values) < MIN_FIELDS_PER_BATCH:
                    continue
                if best is None or len(values) > best[0]:
                    best = (len(values), book, values)
            if best is None:
                continue

            _, book, values = best
            corpus = common.load_corpus(args.track, book) or {}
            pages = common.page_records(corpus)
            snippet = common.routed_text(pages, batch_name)[:EXEMPLAR_INPUT_CHARS].strip()
            example = (
                f"Example ({language}, {best[1].slug.replace('_', ' ')}):\n"
                f"Input:\n{snippet}\n"
                f"Output:\n{json.dumps(values, ensure_ascii=False)}\n"
            )
            out = common.FEWSHOT_ROOT / language / f"{batch_name}.txt"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(example, encoding="utf-8")
            written += 1
            print(f"  {language}/{batch_name}: {len(values)} field(s) from {book.slug}")

    counts = Counter(book.language for book in holdout)
    print(f"\nwrote {written} exemplar file(s) under {common.FEWSHOT_ROOT}")
    print(f"holdout (excluded from scoring): {dict(counts)} -> {manifest['holdout']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
