"""Build seeded stress cases from real frozen pages, plus their own masks.

Twelve perturbations of real book text, each testing one failure mode the task
asks about: OCR spelling damage, partial text, a missing title/author block,
several authors/dates/ISBNs at once, information spread across pages, mixed
scripts, duplicated blocks.

Everything is derived deterministically from the frozen corpus, so a case can
be rebuilt byte-identically. Each case writes bundles in the same format
``run_eval.py`` already consumes, plus a ````prompt_eval/masks/stress.json````
recomputed on the *perturbed* text — scoring against the original mask would
punish the model for text we deliberately removed.

Sample ids are ``<language>/<case>/<slug>`` so the language prefix still parses
and the report can group by case.

    cd backend
    python -m scripts.prompt_eval.build_stress --track ocr --variants V00,V13,V14
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from scripts.prompt_eval import common
from scripts.prompt_eval.build_bundles import wrapper_schema
from scripts.prompt_eval.build_mask import find_value

# Indic confusable pairs. Substituting one for the other is exactly the failure
# mode Tesseract produces on these scripts, and it changes meaning rather than
# just appearance.
CONFUSABLES = {
    "tel": [("ి", "ీ"), ("ె", "ే"), ("శ", "ష"), ("ష", "స"), ("బ", "వ"), ("వ", "బ"), ("ు", "ూ")],
    "hin": [("ि", "ी"), ("ु", "ू"), ("श", "ष"), ("ष", "स"), ("ब", "व"), ("व", "ब"), ("ड", "ड़")],
}

CASE_NAMES = (
    "confusables_10",
    "confusables_20",
    "confusables_30",
    "dropped_lines_30",
    "truncated_tail",
    "title_author_removed",
    "injected_second_author",
    "injected_second_date",
    "injected_second_isbn",
    "cross_page_scramble",
    "latin_mixed",
    "duplicated_blocks",
)

INJECTIONS = {
    "injected_second_author": {"tel": "రచయిత: కల్పిత రచయిత", "hin": "लेखक: काल्पनिक लेखक"},
    "injected_second_date": {"tel": "పునర్ముద్రణ: 1999", "hin": "पुनर्मुद्रण: 1999"},
    "injected_second_isbn": {"tel": "ISBN: 978-81-0000-0000-0", "hin": "ISBN: 978-81-0000-0000-0"},
}


def substitute(text: str, language: str, share: float, rng: random.Random) -> str:
    """Corrupt one confusable character in ``share`` of the words.

    Character-level substitution at 30% destroys every field outright, which
    measures nothing. Real OCR damages a minority of words, so the value stays
    recoverable and recall remains meaningful.
    """
    pairs = CONFUSABLES.get(language, [])
    if not pairs:
        return text
    mapping = dict(pairs)
    words = []
    for word in text.split(" "):
        if rng.random() < share:
            for index, char in enumerate(word):
                if char in mapping:
                    word = f"{word[:index]}{mapping[char]}{word[index + 1 :]}"
                    break
        words.append(word)
    return " ".join(words)


def drop_lines(text: str, share: float, rng: random.Random) -> str:
    lines = text.splitlines()
    kept = [line for line in lines if rng.random() >= share]
    return "\n".join(kept) if kept else text


def remove_title_author(pages: list[dict], expected: dict) -> list[dict]:
    """Blank the front page and scrub any line carrying the title or author."""
    needles = [str(expected.get("title") or "").strip(), str(expected.get("author") or "").strip()]
    needles = [n for n in needles if len(n) > 2]
    out = [dict(page) for page in pages]
    for page in out:
        lines = page["text"].splitlines()
        page["text"] = "\n".join(line for line in lines if not any(n in line for n in needles))
    if out:
        out[0]["text"] = ""
    return out


def inject(pages: list[dict], line: str) -> list[dict]:
    """Append a conflicting value to a *body* page, not the front or back matter.

    That is what makes the case a precedence test: the injected value is on a
    lower-ranked source, so a prompt with a good conflict policy should still
    return the ground-truth value.
    """
    out = [dict(page) for page in pages]
    if len(out) > 2:
        target = out[len(out) // 2]
    elif out:
        target = out[-1]
    else:
        return out
    target["text"] = f"{target['text']}\n{line}"
    return out


def duplicate_blocks(pages: list[dict]) -> list[dict]:
    out = []
    for page in pages:
        out.append(dict(page))
        out.append({"n": page["n"], "text": page["text"]})
    return out


def perturb(case: str, pages: list[dict], expected: dict, language: str, seed: int, slug: str = "") -> list[dict]:
    rng = random.Random(f"{seed}:{case}")
    out = [dict(page) for page in pages]

    if case.startswith("confusables_"):
        share = int(case.rsplit("_", 1)[1]) / 100
        for page in out:
            page["text"] = substitute(page["text"], language, share, rng)
    elif case.startswith("dropped_lines_"):
        share = int(case.rsplit("_", 1)[1]) / 100
        for page in out:
            page["text"] = drop_lines(page["text"], share, rng)
    elif case == "truncated_tail":
        for page in out:
            page["text"] = page["text"][: max(20, int(len(page["text"]) * 0.6))]
    elif case == "title_author_removed":
        out = remove_title_author(out, expected)
    elif case in INJECTIONS:
        out = inject(out, INJECTIONS[case][language])
    elif case == "cross_page_scramble":
        texts = [page["text"] for page in out]
        rng.shuffle(texts)
        for page, text in zip(out, texts, strict=False):
            page["text"] = text
    elif case == "latin_mixed":
        # A romanised title line competing with the printed one: does the model
        # switch script or keep the book's own?
        romanised = slug.replace("_", " ").strip() or "Unknown Title"
        for page in out[:1]:
            page["text"] = f"{page['text']}\nTitle: {romanised}\nAuthor: Unknown"
    elif case == "duplicated_blocks":
        out = duplicate_blocks(out)
    return out


def stress_mask(pages: list[dict], expected: dict) -> dict[str, str]:
    """Recompute visibility on the *perturbed* text, not the original.

    A case that removes the title must not still demand it; a case that only
    injects a competing value leaves the original visible, so the model is
    expected to prefer the higher-ranked source.
    """
    from app.schemas.metadata import BATCH_FIELD_ORDER, METADATA_BATCHES

    page_texts = _page_texts(pages)
    full_text = "\n".join(page.text for page in page_texts)
    masks: dict[str, str] = {}
    for batch_name in BATCH_FIELD_ORDER:
        routed = common.routed_text(page_texts, batch_name)
        for field_name in METADATA_BATCHES[batch_name].model_fields:
            if field_name == "custom_fields":
                continue
            raw = expected.get(field_name)
            value = "" if raw is None else str(raw).strip()
            if not value:
                masks[field_name] = "absent"
            elif find_value(value, routed) is not None:
                masks[field_name] = "visible"
            elif find_value(value, full_text) is not None:
                masks[field_name] = "unroutable"
            else:
                masks[field_name] = "not_in_scan"
    return masks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track", default="ocr", choices=common.TRACKS)
    parser.add_argument("--variants", default="V00", help="Comma-separated profile ids")
    parser.add_argument("--cases", default="", help="Comma-separated subset (default: all 12)")
    parser.add_argument("--books", default="", help="Comma-separated book slugs (default: 6 noisiest)")
    parser.add_argument("--langs", default="")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=common.STRESS_ROOT / "stress.jsonl")
    args = parser.parse_args()

    from app.schemas.metadata import BATCH_FIELD_ORDER, METADATA_BATCHES
    from app.services.prompt_profiles import get_profile
    from app.services.prompts import render_extraction_prompt, render_system_prompt

    cases = [c.strip() for c in args.cases.split(",") if c.strip()] or list(CASE_NAMES)
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    languages = [code.strip() for code in args.langs.split(",") if code.strip()] or None

    books = [b for b in common.discover_books(languages=languages) if common.load_corpus(args.track, b)]
    if args.books:
        wanted = {s.strip() for s in args.books.split(",")}
        books = [b for b in books if b.slug in wanted]
    else:
        # "Noisiest" = fewest ground-truth values that survive the visibility
        # mask, i.e. the books whose OCR lost the most metadata.
        base_masks = common.load_mask(args.track)
        ranked = sorted(
            books,
            key=lambda b: sum(1 for m in (base_masks.get(b.sample_id) or {}).values() if m == "visible"),
        )
        books = ranked[:6]

    if not books:
        print(f"No {args.track} corpus available; run build_corpus.py first.")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    masks: dict[str, dict[str, str]] = {}
    written = 0

    with args.output.open("w", encoding="utf-8") as handle:
        for book in books:
            corpus = common.load_corpus(args.track, book) or {}
            base_pages = corpus.get("pages") or []
            expected = common.load_expected(book)
            for case in cases:
                pages = perturb(case, base_pages, expected, book.language, args.seed, slug=book.slug)
                sample_id = f"{book.language}/{case}/{book.slug}"
                masks[sample_id] = stress_mask(pages, expected)

                page_texts = _page_texts(pages)
                for variant in variants:
                    profile = get_profile(variant)
                    system_prompt = render_system_prompt(book.language, profile=variant)
                    for batch_name in BATCH_FIELD_ORDER:
                        text = common.routed_text(page_texts, batch_name)
                        if not text.strip():
                            continue
                        batch_schema = METADATA_BATCHES[batch_name].model_json_schema()
                        handle.write(
                            json.dumps(
                                {
                                    "key": f"{variant}|stress|{case}|{book.sample_id}|{batch_name}",
                                    "variant": variant,
                                    "track": args.track,
                                    "case": case,
                                    "book": book.slug,
                                    "sample_id": sample_id,
                                    "language": book.language,
                                    "batch": batch_name,
                                    "output_mode": profile.output_mode,
                                    "system_prompt": system_prompt,
                                    "prompt": render_extraction_prompt(
                                        batch_name=batch_name,
                                        ocr_text=text,
                                        language=book.language,
                                        page_count=len(page_texts),
                                        profile=variant,
                                    ),
                                    "schema": wrapper_schema(batch_schema)
                                    if profile.output_mode == "wrapped_evidence"
                                    else batch_schema,
                                    "config": common.RUN_CONFIG,
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                        written += 1

    mask_path = common.MASK_ROOT / "stress.json"
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.write_text(
        json.dumps(
            {
                "generated_at": common.now_iso(),
                "track": args.track,
                "seed": args.seed,
                "cases": cases,
                "fields": masks,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"{written} stress record(s) -> {args.output}")
    print(f"mask -> {mask_path}  ({len(masks)} case/book combinations)")
    print(f"cases: {', '.join(cases)}")
    print(f"books: {', '.join(b.slug for b in books)}")
    return 0


def _page_texts(pages: list[dict]):
    from app.services.batch_routing import PageText

    return [PageText(page_number=int(p["n"]), text=p.get("text") or "") for p in pages]


if __name__ == "__main__":
    raise SystemExit(main())
