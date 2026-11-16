"""Score runner output into per-variant reports.

Merges the per-batch predictions for one variant into per-book metadata dicts,
applies the visibility mask, and writes:

* ``reports/prompt-eval/<variant>.<track>.json`` — full metrics + per-field detail
* ``reports/prompt-eval/registry.json`` — one experiment record per (variant, track)

JSON validity is measured here rather than on the node, because schema
compliance needs the pydantic models and the node deliberately has no backend
install. Validity is reported separately from accuracy on purpose: valid JSON
that says nothing useful is not a good result.

Stress cases use sample ids shaped ``<language>/<case>/<slug>`` so the language
prefix still parses; when any such id is present the report also carries a
``per_case`` breakdown.

    cd backend
    python -m scripts.prompt_eval.score_eval --results results/V00.clean.jsonl --track clean
    python -m scripts.prompt_eval.score_eval --results results/stress.jsonl --mask prompt_eval/masks/stress.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.prompt_eval import common


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 3) if denominator else 0.0


def _report_path(path: Path) -> str:
    """Repo-relative when possible so the registry is portable."""
    try:
        return str(path.relative_to(common.BACKEND_ROOT))
    except ValueError:
        return str(path)


def _case_of(sample_id: str) -> str | None:
    parts = sample_id.split("/")
    return parts[1] if len(parts) >= 3 else None


def _base_sample_id(sample_id: str) -> str:
    """``<lang>/<case>/<slug>`` → ``<lang>/<slug>``; anything else is unchanged."""
    parts = sample_id.split("/")
    if len(parts) >= 3:
        return f"{parts[0]}/{parts[-1]}"
    return sample_id


def _merge_records(records: list[dict]) -> tuple[dict[str, dict], dict]:
    """Group by sample id, unwrapping the evidence arm's ``fields`` wrapper."""
    from app.schemas.metadata import METADATA_BATCHES

    per_book: dict[str, dict] = {}
    validity = {
        "records": 0,
        "errors": 0,
        "json_valid": 0,
        "schema_valid": 0,
        "schema_invalid": 0,
        "empty_responses": 0,
    }

    for record in records:
        validity["records"] += 1
        if record.get("error"):
            validity["errors"] += 1
            continue
        if not record.get("json_valid"):
            continue
        validity["json_valid"] += 1

        parsed = record.get("parsed") or {}
        if record.get("output_mode") == "wrapped_evidence":
            parsed = parsed.get("fields") if isinstance(parsed.get("fields"), dict) else {}

        schema = METADATA_BATCHES.get(record["batch"])
        if schema is not None:
            try:
                schema(**parsed)
                validity["schema_valid"] += 1
            except Exception:  # noqa: BLE001 - non-conforming but still usable
                validity["schema_invalid"] += 1

        if not any(value not in (None, "") for value in parsed.values()):
            validity["empty_responses"] += 1

        merged = per_book.setdefault(record["sample_id"], {})
        for field_name, value in parsed.items():
            if value in (None, ""):
                continue
            # First non-empty value wins: batches are field-disjoint by design,
            # so a collision means two batches both answered for one field.
            merged.setdefault(field_name, value)
    return per_book, validity


def _cost(records: list[dict]) -> dict:
    walls = [r["wall_s"] for r in records if r.get("wall_s") is not None]
    tokens_in = [r["prompt_eval_count"] for r in records if r.get("prompt_eval_count")]
    tokens_out = [r["eval_count"] for r in records if r.get("eval_count")]

    def mean(values):
        return round(sum(values) / len(values), 1) if values else 0.0

    return {
        "calls": len(records),
        "wall_s_total": round(sum(walls), 1),
        "wall_s_mean": mean(walls),
        "tokens_in_total": sum(tokens_in),
        "tokens_in_mean": mean(tokens_in),
        "tokens_out_total": sum(tokens_out),
        "tokens_out_mean": mean(tokens_out),
    }


def _summary(evaluations) -> dict:
    from app.services.extraction_validator import OverallEvaluation

    overall = OverallEvaluation(books=evaluations)
    report = overall.to_report()
    return {
        "overall": report["overall"],
        "per_language": report["per_language"],
        "per_field_presence": report["per_field_presence"],
        "per_field_value": report["per_field_value"],
        "books": report["books"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", nargs="+", required=True, type=Path)
    parser.add_argument("--track", default="clean", choices=common.TRACKS)
    parser.add_argument("--mask", default="", help="Mask file (default: prompt_eval/masks/<track>.json)")
    parser.add_argument("--output-dir", type=Path, default=common.REPORT_ROOT)
    parser.add_argument("--suffix", default="", help="Report filename suffix, e.g. 'stress'")
    parser.add_argument("--include-holdout", action="store_true")
    parser.add_argument("--no-mask", action="store_true", help="Score every GT field (unmasked control run)")
    args = parser.parse_args()

    from app.schemas.metadata import ALL_METADATA_FIELDS
    from app.services.extraction_validator import evaluate_book
    from app.services.prompt_profiles import PROMPT_PROFILES, get_profile

    all_fields = [f.field_name for f in ALL_METADATA_FIELDS]
    manifest = common.load_manifest()
    holdout = set() if args.include_holdout else set(manifest.get("holdout") or [])

    if args.no_mask:
        masks: dict = {}
    elif args.mask:
        masks = json.loads(Path(args.mask).read_text(encoding="utf-8")).get("fields", {})
    else:
        masks = common.load_mask(args.track)

    records = []
    for path in args.results:
        with path.open(encoding="utf-8") as handle:
            records.extend(json.loads(line) for line in handle if line.strip())
    if not records:
        print("error: no result records")
        return 2

    by_variant: dict[str, list[dict]] = {}
    for record in records:
        by_variant.setdefault(record["variant"], []).append(record)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    registry_path = args.output_dir / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {"experiments": []}
    suffix = f".{args.suffix}" if args.suffix else ""
    registry["experiments"] = [
        entry
        for entry in registry["experiments"]
        if not (
            entry.get("track") == args.track
            and entry.get("suffix", "") == args.suffix
            and entry.get("variant") in by_variant
        )
    ]

    books_by_id = {book.sample_id: book for book in common.discover_books()}

    for variant in sorted(by_variant):
        variant_records = by_variant[variant]
        per_book, validity = _merge_records(variant_records)

        evaluations = []
        skipped = 0
        for sample_id in sorted(per_book):
            base_id = _base_sample_id(sample_id)
            if base_id in holdout:
                skipped += 1
                continue
            book = books_by_id.get(base_id)
            if book is None:
                continue
            envelope = common.load_envelope(book)
            evaluations.append(
                evaluate_book(
                    sample_id=sample_id,
                    expected=common.load_expected(book),
                    predicted=per_book[sample_id],
                    all_fields=all_fields,
                    ignore_fields=common.ignored_fields(envelope),
                    mask=masks.get(sample_id) or masks.get(base_id),
                )
            )

        summary = _summary(evaluations)
        profile = PROMPT_PROFILES[variant]
        report = {
            "variant": variant,
            "label": profile.label,
            "track": args.track,
            "suffix": args.suffix,
            "techniques": list(profile.techniques),
            "notes": profile.notes,
            "few_shot": profile.few_shot,
            "output_mode": profile.output_mode,
            "generated_at": common.now_iso(),
            "git_sha": common.git_sha(),
            "dataset": {
                "books": len(evaluations),
                "holdout_excluded": skipped,
                "mask": None if args.no_mask else (args.mask or args.track),
                "unscored_masks": summary["overall"]["mask_totals"],
            },
            "validity": {
                **validity,
                "json_valid_rate": _rate(validity["json_valid"], validity["records"] - validity["errors"]),
                "schema_compliance_rate": _rate(validity["schema_valid"], validity["json_valid"]),
            },
            "cost": _cost(variant_records),
            "system_prompt": get_profile(variant).system_template,
            "extraction_prompt": get_profile(variant).extraction_template,
            **summary,
        }

        # Per-case breakdown for stress runs.
        cases = sorted({c for c in (_case_of(e.sample_id) for e in evaluations) if c})
        if cases:
            report["per_case"] = {}
            for case in cases:
                case_evaluations = [e for e in evaluations if _case_of(e.sample_id) == case]
                case_summary = _summary(case_evaluations)["overall"]
                report["per_case"][case] = {
                    "field_level_accuracy": case_summary["field_level_accuracy"],
                    "presence_f1": case_summary["micro_f1"],
                    "hallucination_rate": case_summary["hallucination_rate"],
                    "missing_field_detection_accuracy": case_summary["missing_field_detection_accuracy"],
                    "books": case_summary["books"],
                }

        out_path = args.output_dir / f"{variant}.{args.track}{suffix}.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        registry["experiments"].append(
            {
                "id": f"{variant}.{args.track}{suffix}",
                "variant": variant,
                "label": profile.label,
                "track": args.track,
                "suffix": args.suffix,
                "techniques": list(profile.techniques),
                "model": variant_records[0].get("model"),
                "config": variant_records[0].get("config"),
                "dataset_books": len(evaluations),
                "overall": report["overall"],
                "per_language": report["per_language"],
                "per_case": report.get("per_case"),
                "validity": report["validity"],
                "cost": report["cost"],
                "report": _report_path(out_path),
                "generated_at": report["generated_at"],
            }
        )

        headline = report["overall"]
        print(
            f"{variant:4s} {profile.label:16s} books={len(evaluations):3d} "
            f"acc={headline['field_level_accuracy']:.3f} "
            f"presF1={headline['micro_f1']:.3f} valF1={headline['value_f1']:.3f} "
            f"hall={headline['hallucination_rate']:.3f} "
            f"json={report['validity']['json_valid_rate']:.2f} "
            f"schema={report['validity']['schema_compliance_rate']:.2f}"
        )
        for language, stats in report["per_language"].items():
            print(
                f"       {language}: acc={stats['field_level_accuracy']:.3f} "
                f"valF1={stats['value_f1']:.3f} hall={stats['hallucination_rate']:.3f} "
                f"({stats['books']} books)"
            )
        for case, stats in report.get("per_case", {}).items():
            print(
                f"       {case:22s} acc={stats['field_level_accuracy']:.3f} "
                f"hall={stats['hallucination_rate']:.3f} miss-det={stats['missing_field_detection_accuracy']:.3f}"
            )

    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nreports -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
