"""End-to-end accuracy harness.

Discovers all ``backend/tests/fixtures/samples/*/clean/expected_metadata.json``
fixtures, runs the full pipeline on the matching sample PDF, compares
predicted vs expected metadata, and writes a report.

Usage:
    cd backend
    python -m scripts.evaluate_extraction
    python -m scripts.evaluate_extraction --output reports/accuracy.json

The report includes:
  * per-book TP/FP/FN counts
  * per-book mean token F1, exact-match rate, normalized-match rate
  * overall micro precision/recall/F1
  * per-field F1 across all books

This is the source of truth for "did we hit 0.85 F1?" and what
chat2's "delivery goal" hinges on.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.metadata import ALL_METADATA_FIELDS
from app.services.extraction_validator import (
    BookEvaluation,
    OverallEvaluation,
    evaluate_book,
)

logger = logging.getLogger(__name__)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "samples"
GT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth"
GT_ROOT = FIXTURE_ROOT.parent / "ground_truth"


def discover_samples(quality: str = "clean") -> list[dict]:
    """Find all expected_metadata.json fixtures with PDFs present."""
    samples: list[dict] = []
    if not FIXTURE_ROOT.exists():
        return samples
    for lang_dir in sorted(FIXTURE_ROOT.iterdir()):
        if not lang_dir.is_dir():
            continue
        q_dir = lang_dir / quality
        if not q_dir.exists():
            continue
        expected_path = q_dir / "expected_metadata.json"
        if not expected_path.exists():
            continue
        # Pick the first available PDF.
        pdf_path = None
        for candidate in ("sample.pdf", f"sample_{lang_dir.name}_{quality}.pdf"):
            p = q_dir / candidate
            if p.exists():
                pdf_path = p
                break
        if pdf_path is None:
            pdfs = list(q_dir.glob("*.pdf"))
            if pdfs:
                pdf_path = pdfs[0]
        if pdf_path is None:
            logger.info("Skipping %s (no PDF present)", q_dir)
            continue
        samples.append(
            {
                "sample_id": f"{lang_dir.name}/{quality}",
                "pdf_path": str(pdf_path),
                "expected_path": str(expected_path),
            }
        )
    return samples


def discover_ground_truth(root: Path | None = None, only_verified: bool = True) -> list[dict]:
    """Find per-book ground truth under ``ground_truth/{lang}/{slug}/``.

    Unlike :func:`discover_samples`, which supports a single book per
    ``{lang}/{quality}/`` directory, this layout keeps one directory per
    book so the Commons corpus can grow without restructuring.

    Only books with ``verification_status == "verified"`` are scored by
    default: Commons-prefilled metadata is a scaffold, not ground truth.
    A bare expectation dict (no envelope) is treated as already verified.
    """
    root = root or GT_ROOT
    samples: list[dict] = []
    if not root.exists():
        return samples
    for lang_dir in sorted(root.iterdir()):
        if not lang_dir.is_dir():
            continue
        for book_dir in sorted(lang_dir.iterdir()):
            if not book_dir.is_dir():
                continue
            expected_path = book_dir / "expected_metadata.json"
            if not expected_path.exists():
                logger.info("Skipping %s (no expected_metadata.json)", book_dir)
                continue
            if only_verified:
                try:
                    envelope = json.loads(expected_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    logger.warning("Skipping %s (unreadable GT: %s)", expected_path, exc)
                    continue
                status = envelope.get("verification_status") if isinstance(envelope, dict) else None
                if status is not None and status != "verified":
                    logger.info("Skipping %s (verification_status=%s)", book_dir.name, status)
                    continue
            pdf_path = book_dir / "original.pdf"
            if not pdf_path.exists():
                pdfs = sorted(book_dir.glob("*.pdf"))
                pdf_path = pdfs[0] if pdfs else None
            if pdf_path is None:
                logger.info("Skipping %s (no PDF present)", book_dir)
                continue
            samples.append(
                {
                    "sample_id": f"{lang_dir.name}/{book_dir.name}",
                    "pdf_path": str(pdf_path),
                    "expected_path": str(expected_path),
                }
            )
    return samples


def load_expected(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if "expected_metadata" in data:
        return data["expected_metadata"]
    return data


def run_pipeline_on_pdf(pdf_path: str, model: str = "qwen2.5", max_pages: int = 20, language: str = "tel") -> dict:
    """Run the full pipeline (preprocess + OCR + LLM extraction) on a PDF.

    This is a thin wrapper around the existing services. It uses
    ``PDFService`` to render pages, the OCR service to read them, and
    the LLM service to extract metadata. The predicted dict is what
    gets compared against ground truth.

    In offline / dev environments where Ollama or the database is not
    reachable, this function returns a stub dict so the harness can
    still be invoked for testing the diff logic.
    """
    try:
        # Lazy imports so unit tests that only need the validator can
        # import this module without pulling the OCR / LLM stack.
        from app.services.llm_service import LLMService
        from app.services.pdf_service import get_page_count, render_full_page
    except Exception as e:  # noqa: BLE001 - degrade to stub when the stack is absent
        logger.warning("Pipeline services unavailable: %s", e)
        return {"_stub": "pipeline_unavailable", "_error": str(e)}

    try:
        import asyncio
        import tempfile

        from app.services.batch_routing import PageText
        from app.services.llm_service import LLMService
        from app.services.ocr_service import run_ocr

        async def _run() -> dict:
            pdf = Path(pdf_path)
            total = get_page_count(pdf)
            tmpdir = Path(tempfile.mkdtemp(prefix="gteval_"))
            ocr_texts: list[PageText] = []
            for pageno in range(1, min(total, max_pages) + 1):
                img = tmpdir / f"p{pageno:04d}.png"
                render_full_page(pdf, pageno, img)
                data = run_ocr(img, language, page_position=pageno - 1)
                if data.get("full_text"):
                    ocr_texts.append(PageText(page_number=pageno, text=data["full_text"]))

            llm = LLMService()
            metadata, _, _ = await llm.run_hybrid_full_extraction(
                ocr_text="", pages=ocr_texts, language=language, model=model
            )
            return metadata.model_dump()

        return asyncio.run(_run())
    except Exception as e:  # noqa: BLE001 - report any pipeline failure as a stub result
        logger.error("Pipeline run failed: %s", e)
        return {"_stub": "pipeline_error", "_error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quality",
        default="clean",
        help="Fixture quality subdir to evaluate (default: clean)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to write the JSON report (default: stdout summary)",
    )
    parser.add_argument(
        "--stub",
        action="store_true",
        help="Use stub predictions (for testing the diff logic without running the pipeline)",
    )
    parser.add_argument(
        "--ground-truth",
        nargs="?",
        const=str(GT_ROOT),
        default=None,
        metavar="DIR",
        help=(
            "Score the per-book Commons corpus under ground_truth/{lang}/{slug}/ "
            f"instead of fixtures/samples (default dir: {GT_ROOT})"
        ),
    )
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help="With --ground-truth, also include books whose metadata is still an unverified scaffold",
    )
    parser.add_argument("--model", default="qwen2.5", help="Ollama model for extraction (default qwen2.5)")
    parser.add_argument("--limit", type=int, default=0, help="Max books to score (0 = all)")
    parser.add_argument("--pages", type=int, default=12, help="Max pages to render/OCR per book (default 12)")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.ground_truth:
        samples = discover_ground_truth(
            Path(args.ground_truth),
            only_verified=not args.include_unverified,
        )
    else:
        samples = discover_samples(quality=args.quality)
    if args.limit:
        samples = samples[: args.limit]
    if not samples:
        if args.ground_truth:
            print(
                "No verified ground-truth books with PDFs found. "
                "Verify a book (verification_status=verified) or pass --include-unverified.",
                file=sys.stderr,
            )
        else:
            print("No samples with PDFs found. Add PDFs to fixtures or run --stub.", file=sys.stderr)
        return 1

    print(f"Found {len(samples)} samples with PDFs:")
    for s in samples:
        print(f"  - {s['sample_id']}")

    all_field_names = [f.field_name for f in ALL_METADATA_FIELDS]
    book_evals: list[BookEvaluation] = []

    for sample in samples:
        print(f"\n=== {sample['sample_id']} ===")
        expected = load_expected(sample["expected_path"])
        if args.stub:
            # Predict everything correctly for half the fields, miss the rest.
            predicted = {k: v for k, v in expected.items() if k in all_field_names}
        else:
            t0 = time.time()
            env = json.loads(Path(sample["expected_path"]).read_text(encoding="utf-8"))
            book_lang = env.get("language", "tel") if isinstance(env, dict) else "tel"
            predicted = run_pipeline_on_pdf(
                sample["pdf_path"], model=args.model, max_pages=args.pages, language=book_lang
            )
            dt = time.time() - t0
            print(f"Pipeline took {dt:.1f}s")

        evaln = evaluate_book(
            sample_id=sample["sample_id"],
            expected=expected,
            predicted=predicted,
            all_fields=all_field_names,
        )
        book_evals.append(evaln)

        print(
            f"  TP={evaln.tp()} FP={evaln.fp()} FN={evaln.fn()}  "
            f"mean_token_f1={evaln.mean_token_f1():.3f}  "
            f"exact={evaln.exact_match_rate():.3f}  "
            f"normalized={evaln.normalized_match_rate():.3f}"
        )

    overall = OverallEvaluation(books=book_evals)

    print("\n=== OVERALL ===")
    print(f"  Micro precision:  {overall.micro_precision():.3f}")
    print(f"  Micro recall:     {overall.micro_recall():.3f}")
    print(f"  Micro F1:         {overall.micro_f1():.3f}")
    print(f"  Macro token F1:   {overall.macro_token_f1():.3f}")

    per_field = overall.per_field_f1()
    print("\n=== Per-field F1 (sorted) ===")
    for name, m in sorted(per_field.items(), key=lambda kv: -kv[1]["f1"]):
        print(f"  {name:35s} P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1']:.2f}  (n={m['support']})")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "samples": [s["sample_id"] for s in samples],
            "overall": {
                "micro_precision": overall.micro_precision(),
                "micro_recall": overall.micro_recall(),
                "micro_f1": overall.micro_f1(),
                "macro_token_f1": overall.macro_token_f1(),
            },
            "per_field": per_field,
            "books": [
                {
                    "sample_id": b.sample_id,
                    "tp": b.tp(),
                    "fp": b.fp(),
                    "fn": b.fn(),
                    "mean_token_f1": b.mean_token_f1(),
                    "exact_match_rate": b.exact_match_rate(),
                    "normalized_match_rate": b.normalized_match_rate(),
                    "field_results": [asdict(r) for r in b.field_results],
                }
                for b in book_evals
            ],
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nReport written to {args.output}")

    # Exit code: 0 if overall F1 >= threshold, else 1 (for CI gating).
    if overall.micro_f1() < 0.5:
        print("\nFAIL: overall F1 below 0.5 threshold", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
