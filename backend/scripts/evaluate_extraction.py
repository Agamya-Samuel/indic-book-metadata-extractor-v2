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
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.metadata import ALL_METADATA_FIELDS
from app.services.extraction_validator import (
    BookEvaluation,
    FieldResult,
    OverallEvaluation,
    evaluate_book,
)

logger = logging.getLogger(__name__)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "samples"


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


def load_expected(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if "expected_metadata" in data:
        return data["expected_metadata"]
    return data


def run_pipeline_on_pdf(pdf_path: str) -> dict:
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
        from app.services.llm_service import LLMService  # noqa: F401
        from app.services.pdf_service import PDFService  # noqa: F401
    except Exception as e:
        logger.warning("Pipeline services unavailable: %s", e)
        return {"_stub": "pipeline_unavailable", "_error": str(e)}

    try:
        import asyncio
        import uuid

        from app.core.database import async_session_factory
        from app.models.book import Book
        from app.models.metadata import BookMetadata
        from app.models.metadata_field_evidence import MetadataFieldEvidence
        from app.models.ocr_result import OcrResult
        from app.models.page import Page
        from app.services.batch_routing import PageText
        from app.services.llm_service import LLMService
        from app.services.ocr_service import run_ocr
        from app.services.pdf_service import PDFService
        from app.services.storage import StorageService
        from sqlalchemy import select

        async def _run() -> dict:
            pdf = Path(pdf_path)
            pdf_service = PDFService()
            image_paths = pdf_service.render_pages(pdf, max_pages=20)
            storage = StorageService()

            async with async_session_factory() as db:
                book = Book(
                    id=uuid.uuid4(),
                    filename=pdf.name,
                    language="tel",
                    total_pages=len(image_paths),
                )
                db.add(book)
                await db.flush()
                page_records = []
                for i, img_path in enumerate(image_paths):
                    rel = storage.relative(img_path)
                    page = Page(
                        book_id=book.id,
                        page_number=i + 1,
                        image_path=rel,
                    )
                    db.add(page)
                    page_records.append((page, img_path))
                await db.commit()

                # OCR each page synchronously. This avoids depending on
                # Celery/Redis being up; the harness is meant to measure
                # what the system actually produces.
                ocr_texts: list[PageText] = []
                for page, img_path in page_records:
                    ocr_data = run_ocr(Path(img_path), "tel", page_position=page.page_number - 1)
                    db.add(
                        OcrResult(
                            page_id=page.id,
                            raw_text=ocr_data.get("full_text"),
                            confidence=ocr_data.get("avg_confidence"),
                            language_detected="tel",
                            bounding_boxes={"words": ocr_data.get("words", [])},
                        )
                    )
                    if ocr_data.get("full_text"):
                        ocr_texts.append(
                            PageText(
                                page_number=page.page_number,
                                text=ocr_data["full_text"],
                            )
                        )
                await db.commit()

                # Run the hybrid LLM extraction synchronously.
                llm = LLMService()
                metadata, _, _ = await llm.run_hybrid_full_extraction(
                    ocr_text="",
                    pages=ocr_texts,
                    language="tel",
                )
                return metadata.model_dump()

        return asyncio.run(_run())
    except Exception as e:
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
        "-v",
        "--verbose",
        action="store_true",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    samples = discover_samples(quality=args.quality)
    if not samples:
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
            predicted = run_pipeline_on_pdf(sample["pdf_path"])
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
        print(
            f"  {name:35s} P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1']:.2f}  (n={m['support']})"
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
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
