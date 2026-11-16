"""Render one JSONL bundle of ready-to-send prompts per (variant, track).

A bundle record is self-contained: system prompt, user prompt, the JSON schema
to constrain decoding with, and the book/batch identifiers. Ground truth is
deliberately **not** included — bundles travel to a benchmark node, and the
node should never see the answers.

    cd backend
    python -m scripts.prompt_eval.build_bundles --variants V00,V07 --track clean
    python -m scripts.prompt_eval.build_bundles --stage 1 --track ocr
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.prompt_eval import common

STAGE_VARIANTS = {
    1: ("V00", "V01", "V02", "V03", "V04", "V05", "V06"),
    2: ("V00", "V07", "V08", "V09", "V10", "V11", "V12"),
}


def wrapper_schema(batch_schema: dict) -> dict:
    """JSON schema for the evidence arm: ``{fields: {...}, evidence: {...}}``.

    ``fields`` keeps the production value shape so scoring can unwrap it and
    compare like for like; ``evidence`` is free-form because it is analysed,
    never validated field by field.
    """
    properties = batch_schema.get("properties", {})
    field_props = {}
    for name, spec in properties.items():
        if name == "custom_fields":
            continue
        field_props[name] = spec if spec.get("type") == "object" else {"type": ["string", "null"]}
    return {
        "type": "object",
        "properties": {
            "fields": {"type": "object", "properties": field_props},
            "evidence": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "quote": {"type": ["string", "null"]},
                        "page": {"type": ["integer", "null"]},
                    },
                },
            },
        },
        "required": ["fields"],
    }


def resolve_variants(args) -> list[str]:
    from app.services.prompt_profiles import PROMPT_PROFILES

    if args.stage:
        ids = list(STAGE_VARIANTS.get(args.stage, ()))
        if args.stage == 3:
            stage3 = common.EVAL_ROOT / "stage3.json"
            if not stage3.is_file():
                raise SystemExit(
                    "stage3.json missing — run `python -m scripts.prompt_eval.compare --emit-stage3` first."
                )
            return [entry["id"] for entry in json.loads(stage3.read_text(encoding="utf-8"))["variants"]]
        return [v for v in ids if v in PROMPT_PROFILES]

    if args.variants:
        ids = [v.strip() for v in args.variants.split(",") if v.strip()]
    else:
        ids = list(PROMPT_PROFILES)
    unknown = [v for v in ids if v not in PROMPT_PROFILES]
    if unknown:
        raise SystemExit(f"Unknown profile(s): {unknown}. Known: {sorted(PROMPT_PROFILES)}")
    return ids


def build_for_variant(variant: str, track: str, books: list[common.Book], out_path: Path) -> int:
    from app.schemas.metadata import BATCH_FIELD_ORDER, METADATA_BATCHES
    from app.services.prompt_profiles import get_profile
    from app.services.prompts import render_extraction_prompt, render_system_prompt

    profile = get_profile(variant)
    written = 0
    with out_path.open("w", encoding="utf-8") as handle:
        for book in books:
            corpus = common.load_corpus(track, book)
            if not corpus:
                continue
            pages = common.page_records(corpus)
            system_prompt = render_system_prompt(book.language, profile=variant)
            for batch_name in BATCH_FIELD_ORDER:
                text = common.routed_text(pages, batch_name)
                if not text.strip():
                    continue
                batch_schema = METADATA_BATCHES[batch_name].model_json_schema()
                record = {
                    "key": f"{variant}|{track}|{book.sample_id}|{batch_name}",
                    "variant": variant,
                    "track": track,
                    "book": book.slug,
                    "sample_id": book.sample_id,
                    "language": book.language,
                    "batch": batch_name,
                    "output_mode": profile.output_mode,
                    "system_prompt": system_prompt,
                    "prompt": render_extraction_prompt(
                        batch_name=batch_name,
                        ocr_text=text,
                        language=book.language,
                        page_count=len(pages),
                        profile=variant,
                    ),
                    "schema": wrapper_schema(batch_schema)
                    if profile.output_mode == "wrapped_evidence"
                    else batch_schema,
                    "config": common.RUN_CONFIG,
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants", default="", help="Comma-separated profile ids")
    parser.add_argument("--stage", type=int, choices=[1, 2, 3], default=None)
    parser.add_argument("--track", default="clean", choices=common.TRACKS)
    parser.add_argument("--langs", default="")
    parser.add_argument("--books", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, default=common.BUNDLE_ROOT)
    args = parser.parse_args()

    languages = [c.strip() for c in args.langs.split(",") if c.strip()] or None
    slugs = [s.strip() for s in args.books.split(",") if s.strip()] or None
    books = common.discover_books(languages=languages, slugs=slugs)
    if args.limit:
        books = books[: args.limit]

    variants = resolve_variants(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for variant in variants:
        out_path = args.output_dir / f"{variant}.{args.track}.jsonl"
        written = build_for_variant(variant, args.track, books, out_path)
        total += written
        print(f"  {variant:4s} {args.track:5s} {written:5d} record(s) -> {out_path}", flush=True)
    print(f"\n{total} bundle record(s) across {len(variants)} variant(s)")
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())
