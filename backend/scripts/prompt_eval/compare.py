"""Compare scored variants: leaderboard, paired CIs, regression flags, Stage-3 pick.

A variant is only called better when the paired bootstrap interval of
``variant - baseline`` excludes zero. Pointing at the biggest number in a table
is how prompt tuning produces regressions in the other language.

    cd backend
    python -m scripts.prompt_eval.compare --track clean
    python -m scripts.prompt_eval.compare --track ocr --emit-stage3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.prompt_eval import common

BASELINE = "V00"
PRIMARY_METRIC = "field_level_accuracy"
SYSTEM_ARMS = ("V01", "V02", "V03", "V04", "V05", "V06")
EXTRACTION_ARMS = ("V07", "V08", "V09", "V10", "V11", "V12")


def _series(report: dict, metric: str) -> dict[str, float]:
    series = {}
    for book in report.get("books", []):
        if metric == "field_level_accuracy":
            series[book["sample_id"]] = float(book["field_level_accuracy"])
        elif metric == "presence_f1":
            tp, fp, fn = book["tp"], book["fp"], book["fn"]
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            series[book["sample_id"]] = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        elif metric == "hallucination_rate":
            absent = book.get("absent_fields") or 0
            series[book["sample_id"]] = (book["hallucinations"] / absent) if absent else 0.0
        else:
            series[book["sample_id"]] = float(book.get(metric, 0.0))
    return series


def _language_series(report: dict, metric: str, language: str) -> dict[str, float]:
    return {
        sample_id: value for sample_id, value in _series(report, metric).items() if sample_id.split("/")[0] == language
    }


def _languages(reports: dict[str, dict]) -> list[str]:
    found = set()
    for report in reports.values():
        found.update(report.get("per_language", {}).keys())
    return sorted(found)


def load_reports(report_dir: Path, track: str) -> dict[str, dict]:
    reports = {}
    for path in sorted(report_dir.glob(f"*.{track}.json")):
        if path.name == "registry.json":
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        reports[report["variant"]] = report
    return reports


def build_leaderboard(reports: dict[str, dict]) -> dict:
    from app.services.extraction_validator import paired_delta_ci

    languages = _languages(reports)
    baseline = reports.get(BASELINE)
    rows = []

    for variant, report in sorted(reports.items()):
        overall = report["overall"]
        row = {
            "variant": variant,
            "label": report.get("label"),
            "books": overall.get("books"),
            "field_level_accuracy": overall["field_level_accuracy"],
            "presence_f1": overall["micro_f1"],
            "value_f1": overall["value_f1"],
            "hallucination_rate": overall["hallucination_rate"],
            "missing_field_accuracy": overall["missing_field_detection_accuracy"],
            "json_valid_rate": report["validity"]["json_valid_rate"],
            "schema_compliance_rate": report["validity"]["schema_compliance_rate"],
            "tokens_out_mean": report["cost"]["tokens_out_mean"],
            "wall_s_mean": report["cost"]["wall_s_mean"],
            "per_language": {
                language: report["per_language"].get(language, {}).get("field_level_accuracy") for language in languages
            },
            "delta": None,
            "regressions": [],
        }

        if baseline and variant != BASELINE:
            delta = paired_delta_ci(
                _series(baseline, PRIMARY_METRIC),
                _series(report, PRIMARY_METRIC),
            )
            row["delta"] = delta
            for language in languages:
                language_delta = paired_delta_ci(
                    _language_series(baseline, PRIMARY_METRIC, language),
                    _language_series(report, PRIMARY_METRIC, language),
                )
                if language_delta["verdict"] == "worse":
                    row["regressions"].append(
                        {
                            "language": language,
                            "delta": language_delta,
                        }
                    )
        rows.append(row)

    rows.sort(key=lambda r: (-(r["field_level_accuracy"] or 0), r["variant"]))
    return {"track": next(iter(reports.values()))["track"] if reports else None, "languages": languages, "rows": rows}


def to_markdown(leaderboard: dict) -> str:
    languages = leaderboard["languages"]
    header = (
        "| Variant | Label | Books | Field acc | Presence F1 | Value F1 | Halluc | Missing-det | JSON | "
        + " | ".join(f"{language} acc" for language in languages)
        + " | Δ vs V00 (acc) | Verdict | Regressions |"
    )
    divider = "|" + "---|" * (11 + len(languages) + 3)
    lines = [header, divider]
    for row in leaderboard["rows"]:
        delta = row["delta"]
        delta_text = "—" if delta is None else f"{delta['mean_delta']:+.3f} [{delta['lo']:+.3f}, {delta['hi']:+.3f}]"
        verdict = "baseline" if delta is None else delta["verdict"]
        regressions = ", ".join(item["language"] for item in row["regressions"]) or "—"
        language_cells = " | ".join(
            "—" if row["per_language"].get(language) is None else f"{row['per_language'][language]:.3f}"
            for language in languages
        )
        lines.append(
            f"| {row['variant']} | {row['label']} | {row['books']} | {row['field_level_accuracy']:.3f} | "
            f"{row['presence_f1']:.3f} | {row['value_f1']:.3f} | {row['hallucination_rate']:.3f} | "
            f"{row['missing_field_accuracy']:.3f} | {row['json_valid_rate']:.2f} | {language_cells} | "
            f"{delta_text} | {verdict} | {regressions} |"
        )
    return "\n".join(lines)


def emit_stage3(leaderboard: dict, out_path: Path) -> dict:
    """Pick the Stage-3 combinations by rule: rank arms, then pair the leaders.

    Combos: best system × best extraction, best system × runner-up extraction,
    runner-up system × best extraction. Deterministic ties broken by id.
    """
    rows = {row["variant"]: row for row in leaderboard["rows"]}

    def ranked(ids):
        present = [rows[i] for i in ids if i in rows]
        return sorted(
            present,
            key=lambda r: (
                -(r["field_level_accuracy"] or 0),
                r["hallucination_rate"],
                r["variant"],
            ),
        )

    systems = ranked(SYSTEM_ARMS)
    extractions = ranked(EXTRACTION_ARMS)
    if not systems or not extractions:
        raise SystemExit("Stage-3 selection needs Stage 1 (system arms) and Stage 2 (extraction arms) reports first.")

    pairs = [
        (systems[0]["variant"], extractions[0]["variant"]),
        (systems[0]["variant"], extractions[1]["variant"] if len(extractions) > 1 else extractions[0]["variant"]),
        (systems[1]["variant"] if len(systems) > 1 else systems[0]["variant"], extractions[0]["variant"]),
    ]
    variants = [
        {
            "id": f"V{13 + index}",
            "system": system,
            "extraction": extraction,
            "rule": "ranked by field-level accuracy, ties broken by lower hallucination rate then id",
        }
        for index, (system, extraction) in enumerate(pairs)
    ]

    # Deduplicate identical pairs while keeping ids contiguous.
    seen = set()
    unique = []
    for variant in variants:
        pair = (variant["system"], variant["extraction"])
        if pair in seen:
            continue
        seen.add(pair)
        unique.append(variant)
    for index, variant in enumerate(unique):
        variant["id"] = f"V{13 + index}"

    payload = {
        "generated_at": common.now_iso(),
        "track": leaderboard["track"],
        "baseline": BASELINE,
        "ranked_systems": [r["variant"] for r in systems],
        "ranked_extractions": [r["variant"] for r in extractions],
        "variants": unique,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track", default="clean", choices=common.TRACKS)
    parser.add_argument("--report-dir", type=Path, default=common.REPORT_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Markdown output (default: reports/prompt-eval/leaderboard.<track>.md)",
    )
    parser.add_argument("--emit-stage3", action="store_true")
    args = parser.parse_args()

    reports = load_reports(args.report_dir, args.track)
    if not reports:
        print(f"No reports for track '{args.track}' in {args.report_dir}")
        return 1

    leaderboard = build_leaderboard(reports)
    markdown = to_markdown(leaderboard)
    out_path = args.output or (args.report_dir / f"leaderboard.{args.track}.md")
    out_path.write_text(markdown + "\n", encoding="utf-8")

    print(markdown)
    print(f"\nleaderboard -> {out_path}")

    if args.emit_stage3:
        payload = emit_stage3(leaderboard, common.EVAL_ROOT / "stage3.json")
        print(f"stage3 -> {common.EVAL_ROOT / 'stage3.json'}")
        for variant in payload["variants"]:
            print(f"  {variant['id']} = {variant['system']} × {variant['extraction']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
