#!/usr/bin/env python3
"""Standalone test script for the LLM extraction pipeline.

Usage:
    # Full extraction with default Airavata model
    python scripts/test_llm_extraction.py --language tel

    # Test with a specific OCR text file
    python scripts/test_llm_extraction.py --ocr-text sample_ocr.txt --language tel

    # Test a single batch only
    python scripts/test_llm_extraction.py --batch-only core_identity --language tel

    # Dry run (render prompts without calling Ollama)
    python scripts/test_llm_extraction.py --dry-run --language tel
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.metadata import (
    BATCH_FIELD_ORDER,
    METADATA_BATCHES,
    FullMetadata,
)
from app.services.llm_service import LlmService
from app.services.prompts import (
    get_batch_field_names,
    render_extraction_prompt,
    render_system_prompt,
)

SAMPLE_TELUGU_OCR = """శ్రీ వేంకటేశ్వర పబ్లికేషన్స్
ప్రచురణకర్త: శ్రీ వేంకటేశ్వర పబ్లికేషన్స్, హైదరాబాదు
మొదటి ముద్రణ: 2015
రచయిత: విశ్వనాథ సత్యనారాయణ
పుస్తకం: వేయిపడగలు
భాష: తెలుగు
పుటలు: 312
ధర: రూ. 250/-
ISBN: 978-81-1234-567-8
అంకితం: నా తల్లిదండ్రులకు
ముందుమాట: డా. సి. నారాయణరెడ్డి
సంపాదకుడు: డా. కె. విశ్వనాథం
ప్రచురణ స్థలము: హైదరాబాదు, తెలంగాణ
ముద్రణాలయం: శ్రీ లక్ష్మీ ప్రెస్, హైదరాబాదు
ప్రతి సంపుటి ధర రూ. 250/-"""

SAMPLE_HINDI_OCR = """श्री गणेश पब्लिकेशन्स
प्रकाशक: श्री गणेश पब्लिकेशन्स, नई दिल्ली
प्रथम संस्करण: 2018
लेखक: प्रेमचंद
पुस्तक: गोदान
भाषा: हिंदी
पृष्ठ: 280
मूल्य: रु. 200/-
ISBN: 978-81-9876-543-2
अर्पण: मेरे माता-पिता को
प्रकाशन स्थान: नई दिल्ली, भारत"""


async def run_dry_run(language: str):
    print(f"\n{'='*60}")
    print(f"DRY RUN — Rendering prompts for language: {language}")
    print(f"{'='*60}\n")

    system_prompt = render_system_prompt(language)
    print(f"--- SYSTEM PROMPT ---\n{system_prompt}\n")

    for batch_name in BATCH_FIELD_ORDER:
        field_names = get_batch_field_names(batch_name)
        extraction_prompt = render_extraction_prompt(
            batch_name=batch_name,
            ocr_text=SAMPLE_TELUGU_OCR if language == "tel" else SAMPLE_HINDI_OCR,
            language=language,
            page_count=1,
        )
        print(f"--- EXTRACTION PROMPT: {batch_name} ---")
        print(f"Fields: {', '.join(field_names)}")
        print(f"\n{extraction_prompt}\n")

    print("DRY RUN COMPLETE — no LLM calls made.")


async def run_single_batch(
    batch_name: str,
    language: str,
    model: str,
    temperature: float,
    max_tokens: int,
    ocr_text: str,
):
    print(f"\n{'='*60}")
    print(f"SINGLE BATCH TEST: {batch_name}")
    print(f"Model: {model} | Language: {language} | Temperature: {temperature}")
    print(f"{'='*60}\n")

    batch_schema = METADATA_BATCHES.get(batch_name)
    if batch_schema is None:
        print(f"ERROR: Unknown batch '{batch_name}'")
        print(f"Available batches: {', '.join(BATCH_FIELD_ORDER)}")
        sys.exit(1)

    field_names = get_batch_field_names(batch_name)
    print(f"Fields to extract: {', '.join(field_names)}\n")

    llm = LlmService()
    start = time.time()

    result, raw_response, usage = await llm.extract_batch(
        ocr_text=ocr_text,
        batch_name=batch_name,
        batch_schema=batch_schema,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        language=language,
        page_count=1,
    )

    elapsed = time.time() - start
    await llm.close()

    print(f"Status: {usage.get('status', 'unknown')}")
    print(f"Time: {elapsed:.1f}s")
    print(f"\nExtracted fields:")
    for fn in field_names:
        value = getattr(result, fn, None)
        status_icon = "OK" if value else "--"
        print(f"  [{status_icon}] {fn}: {value!r}")

    if usage.get("error"):
        print(f"\nError: {usage['error']}")

    print(f"\nRaw response:\n{raw_response[:500]}...")

    return usage.get("status") == "success"


async def run_full_extraction(
    language: str,
    model: str,
    temperature: float,
    max_tokens: int,
    ocr_text: str,
):
    print(f"\n{'='*60}")
    print(f"FULL EXTRACTION TEST")
    print(f"Model: {model} | Language: {language} | Temperature: {temperature}")
    print(f"Batches: {len(BATCH_FIELD_ORDER)}")
    print(f"OCR text length: {len(ocr_text)} chars")
    print(f"{'='*60}\n")

    llm = LlmService()
    start = time.time()

    def on_progress(current: int, total: int, batch_name: str):
        pct = round((current / total) * 100, 1)
        print(f"  [{pct:5.1f}%] Completed batch '{batch_name}' ({current}/{total})")

    metadata, batch_results = await llm.run_full_extraction(
        ocr_text=ocr_text,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        language=language,
        page_count=1,
        progress_callback=on_progress,
    )

    elapsed = time.time() - start
    await llm.close()

    print(f"\n{'='*60}")
    print(f"EXTRACTION COMPLETE in {elapsed:.1f}s")
    print(f"{'='*60}\n")

    print("Batch summary:")
    for br in batch_results:
        status = br["usage"].get("status", "unknown")
        parsed = br.get("parsed_fields", {})
        non_null = sum(1 for v in parsed.values() if v is not None)
        total_fields = len(parsed)
        print(
            f"  {br['batch_name']:25s} | {status:10s} | {non_null}/{total_fields} fields extracted"
        )

    print(f"\nFull metadata JSON:")
    print(json.dumps(metadata.model_dump(), indent=2, ensure_ascii=False))

    success_count = sum(
        1 for br in batch_results if br["usage"].get("status") == "success"
    )
    failed_count = len(batch_results) - success_count

    print(f"\nResult: {success_count}/{len(batch_results)} batches succeeded")
    if failed_count:
        print(f"WARNING: {failed_count} batches failed")

    return failed_count == 0


def main():
    parser = argparse.ArgumentParser(
        description="Test LLM extraction pipeline for Indic Book Metadata Extractor"
    )
    parser.add_argument(
        "--ocr-text",
        type=str,
        default=None,
        help="Path to file containing OCR text (uses built-in sample if not provided)",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="tel",
        choices=["tel", "hin"],
        help="Language of the OCR text (default: tel)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="airavata",
        help="Ollama model name (default: airavata)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="LLM temperature (default: 0.3)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2048,
        help="Max tokens per LLM call (default: 2048)",
    )
    parser.add_argument(
        "--batch-only",
        type=str,
        default=None,
        help="Test only a single batch (e.g., core_identity)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render prompts without calling Ollama",
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        default="http://localhost:11434",
        help="Ollama API URL (default: http://localhost:11434)",
    )

    args = parser.parse_args()

    if args.ocr_text:
        ocr_text = Path(args.ocr_text).read_text(encoding="utf-8")
    elif args.language == "tel":
        ocr_text = SAMPLE_TELUGU_OCR
    else:
        ocr_text = SAMPLE_HINDI_OCR

    if args.dry_run:
        asyncio.run(run_dry_run(args.language))
        sys.exit(0)

    from app.services.llm_service import LlmService as _LlmService
    import app.services.llm_service as _mod

    _mod.llm_service = _LlmService(ollama_url=args.ollama_url)

    if args.batch_only:
        success = asyncio.run(
            run_single_batch(
                batch_name=args.batch_only,
                language=args.language,
                model=args.model,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                ocr_text=ocr_text,
            )
        )
    else:
        success = asyncio.run(
            run_full_extraction(
                language=args.language,
                model=args.model,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                ocr_text=ocr_text,
            )
        )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
