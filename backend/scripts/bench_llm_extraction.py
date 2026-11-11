"""DB-free LLM extraction benchmark over the ground-truth book corpus.

Runs the real hybrid extraction entry point (LLMService) against real OCR
(or Wikisource) text and scores per-field F1 plus a hallucination rate,
without needing Postgres/Celery. Ollama is required only for real mode.

Usage:
    python -m scripts.bench_llm_extraction --list
    python -m scripts.bench_llm_extraction --model qwen3.5:4b --languages tel --limit 1
    python -m scripts.bench_llm_extraction --fake-llm --languages tel,hin
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.schemas.metadata import ALL_METADATA_FIELDS  # noqa: E402
from app.services.extraction_validator import (  # noqa: E402
    OverallEvaluation,
    evaluate_book,
)

GT_ROOT = BACKEND / "tests" / "fixtures" / "ground_truth"
ALL_FIELDS = [f.field_name for f in ALL_METADATA_FIELDS]


def load_envelope(path: Path) -> tuple[dict, str | None]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "expected_metadata" in data:
        return data["expected_metadata"], data.get("verification_status")
    return data, None


def discover(languages: list[str], needles: list[str], limit: int) -> list[dict]:
    books: list[dict] = []
    for lang_dir in sorted(GT_ROOT.iterdir()):
        if not lang_dir.is_dir() or (languages and lang_dir.name not in languages):
            continue
        for book_dir in sorted(lang_dir.iterdir()):
            exp = book_dir / "expected_metadata.json"
            if not exp.exists():
                continue
            sid = f"{lang_dir.name}/{book_dir.name}"
            if needles and not any(n in sid for n in needles):
                continue
            pdf = book_dir / "original.pdf"
            ws = book_dir / "wikisource_gt.json"
            meta, status = load_envelope(exp)
            books.append(
                {
                    "sample_id": sid,
                    "language": lang_dir.name,
                    "expected": meta,
                    "status": status,
                    "pdf": pdf if pdf.exists() else None,
                    "wikisource": ws if ws.exists() else None,
                }
            )
            if limit and len(books) >= limit:
                return books
    return books


def _collect_strings(obj: object, out: list[str]) -> None:
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_strings(v, out)


def load_wikisource_text(path: Path) -> str:
    obj = json.loads(path.read_text(encoding="utf-8"))
    out: list[str] = []
    _collect_strings(obj, out)
    return "\n".join(s for s in out if s.strip())


def build_pages(book: dict, args: argparse.Namespace) -> list:
    from app.services.batch_routing import PageText

    if args.text_source == "wikisource":
        if not book["wikisource"]:
            raise FileNotFoundError(f"no wikisource_gt.json for {book['sample_id']}")
        return [PageText(page_number=1, text=load_wikisource_text(book["wikisource"]))]

    if not book["pdf"]:
        raise FileNotFoundError(f"no original.pdf for {book['sample_id']}")
    from app.services.ocr_service import run_ocr
    from app.services.pdf_service import PDFService

    images = PDFService().render_pages(Path(book["pdf"]), max_pages=args.pages)
    pages = []
    for i, img in enumerate(images):
        data = run_ocr(Path(img), book["language"], page_position=i)
        pages.append(PageText(page_number=i + 1, text=data.get("full_text") or ""))
    return pages


def predict(book: dict, args: argparse.Namespace) -> tuple[dict, dict]:
    if args.fake_llm:
        return {k: book["expected"].get(k) for k in ALL_FIELDS}, {"mode": "fake"}
    if args.dry_run:
        return {k: None for k in ALL_FIELDS}, {"mode": "dry_run"}

    from app.services.llm_service import LLMService

    pages = build_pages(book, args)
    service = LLMService(ollama_url=args.ollama_url)
    metadata, batch_results, _evidence = asyncio.run(
        service.run_hybrid_full_extraction(
            ocr_text="",
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            language=book["language"],
            page_count=len(pages),
            pages=pages,
        )
    )
    statuses = [b.get("usage", {}).get("status") for b in batch_results]
    return metadata.model_dump(), {"pages": len(pages), "batch_statuses": statuses}


def rss_mb() -> float:
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ollama-url", default=None)
    ap.add_argument("--model", default="qwen2.5")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--languages", default="tel,hin")
    ap.add_argument("--book", action="append", default=[], help="substring filter; repeatable")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pages", type=int, default=8)
    ap.add_argument("--text-source", choices=["ocr", "wikisource"], default="ocr")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fake-llm", action="store_true")
    ap.add_argument("--include-unverified", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    languages = [x.strip() for x in args.languages.split(",") if x.strip()]
    all_books = discover(languages, args.book, args.limit)

    if args.list:
        print(f"{'sample_id':55s} {'lang':4s} {'status':12s} prefilled")
        for b in all_books:
            prefilled = sum(1 for v in b["expected"].values() if v not in (None, ""))
            print(f"{b['sample_id']:55s} {b['language']:4s} {str(b['status']):12s} {prefilled}")
        return 0

    books = all_books
    if not args.include_unverified:
        books = [b for b in books if b["status"] in (None, "verified")]
    if not books:
        print("No books matched. Use --include-unverified to include unverified scaffolds.", file=sys.stderr)
        return 1

    evaluations = []
    rows = []
    for book in books:
        started = time.time()
        try:
            predicted, meta = predict(book, args)
        except Exception as exc:  # noqa: BLE001
            print(f"{book['sample_id']:55s} ERROR: {exc}", file=sys.stderr)
            continue
        wall = time.time() - started
        ev = evaluate_book(
            sample_id=book["sample_id"],
            expected=book["expected"],
            predicted=predicted,
            all_fields=ALL_FIELDS,
        )
        evaluations.append(ev)
        absent = sum(1 for r in ev.field_results if not r.expected_present)
        halluc = sum(1 for r in ev.field_results if r.predicted_present and not r.expected_present)
        rows.append(
            {
                "sample_id": book["sample_id"],
                "language": book["language"],
                "verification_status": book["status"],
                "wall_s": round(wall, 1),
                "tp": ev.tp(),
                "fp": ev.fp(),
                "fn": ev.fn(),
                "mean_token_f1": ev.mean_token_f1(),
                "exact_match_rate": ev.exact_match_rate(),
                "hallucinations": halluc,
                "absent_fields": absent,
                "hallucination_rate": round(halluc / absent, 3) if absent else 0.0,
                "meta": meta,
            }
        )
        print(
            f"{book['sample_id']:55s} F1={ev.mean_token_f1():.3f} "
            f"TP={ev.tp():3d} FP={ev.fp():3d} FN={ev.fn():3d} "
            f"hall={halluc}/{absent} {wall:.0f}s"
        )

    if not evaluations:
        print("No successful evaluations.", file=sys.stderr)
        return 1

    overall = OverallEvaluation(books=evaluations)
    total_hall = sum(r["hallucinations"] for r in rows)
    total_absent = sum(r["absent_fields"] for r in rows)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "text_source": args.text_source,
        "mode": "fake" if args.fake_llm else ("dry_run" if args.dry_run else "real"),
        "books": rows,
        "overall": {
            "micro_precision": overall.micro_precision(),
            "micro_recall": overall.micro_recall(),
            "micro_f1": overall.micro_f1(),
            "macro_token_f1": overall.macro_token_f1(),
            "hallucination_rate": round(total_hall / total_absent, 3) if total_absent else 0.0,
        },
        "per_field": overall.per_field_f1(),
        "peak_rss_mb": round(rss_mb(), 1),
    }

    print("\n=== OVERALL ===")
    print(
        f"  micro F1={overall.micro_f1():.3f}  macro token F1={overall.macro_token_f1():.3f}  "
        f"hallucination_rate={summary['overall']['hallucination_rate']:.3f}  "
        f"peak_rss={summary['peak_rss_mb']:.0f}MB"
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Report -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())