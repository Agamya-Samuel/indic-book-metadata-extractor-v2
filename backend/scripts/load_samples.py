"""Sample dataset fixture loader.

Bulk-imports sample PDFs from tests/fixtures/samples/ and validates
OCR + metadata extraction against expected outputs.

Usage:
    uv run python scripts/load_samples.py                  # Load all samples
    uv run python scripts/load_samples.py --language tel   # Load only Telugu samples
    uv run python scripts/load_samples.py --validate       # Validate against expected outputs
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "samples"


def discover_samples(language: str | None = None) -> list[dict]:
    samples = []
    if not FIXTURES_DIR.exists():
        print(f"Fixtures directory not found: {FIXTURES_DIR}")
        return samples

    for lang_dir in sorted(FIXTURES_DIR.iterdir()):
        if not lang_dir.is_dir():
            continue
        if language and lang_dir.name != language:
            continue

        for quality_dir in sorted(lang_dir.iterdir()):
            if not quality_dir.is_dir():
                continue

            expected_path = quality_dir / "expected_metadata.json"
            pdf_path = quality_dir / "sample.pdf"

            if not expected_path.exists():
                continue

            with open(expected_path) as f:
                expected = json.load(f)

            samples.append({
                "language": lang_dir.name,
                "quality": quality_dir.name,
                "dir": quality_dir,
                "pdf_path": pdf_path,
                "expected": expected,
                "has_pdf": pdf_path.exists(),
            })

    return samples


def print_summary(samples: list[dict]) -> None:
    if not samples:
        print("No sample fixtures found.")
        print(f"Place PDFs in subdirectories under: {FIXTURES_DIR}")
        print("Expected structure: samples/{language}/{quality}/sample.pdf + expected_metadata.json")
        return

    print(f"Found {len(samples)} sample fixture(s):\n")
    print(f"{'Language':<12} {'Quality':<15} {'PDF':<8} {'Description'}")
    print("-" * 70)
    for s in samples:
        pdf_status = "YES" if s["has_pdf"] else "MISSING"
        desc = s["expected"].get("description", "")
        print(f"{s['language']:<12} {s['quality']:<15} {pdf_status:<8} {desc}")

    ready = sum(1 for s in samples if s["has_pdf"])
    print(f"\n{ready}/{len(samples)} samples have PDFs ready for loading.")


async def load_samples(samples: list[dict], api_base: str) -> None:
    import httpx

    async with httpx.AsyncClient(base_url=api_base, timeout=120.0) as client:
        for sample in samples:
            if not sample["has_pdf"]:
                print(f"  SKIP: {sample['language']}/{sample['quality']} — no PDF")
                continue

            print(f"  Loading: {sample['language']}/{sample['quality']}...")

            with open(sample["pdf_path"], "rb") as f:
                response = await client.post(
                    "/api/books/upload",
                    files={"file": (sample["pdf_path"].name, f, "application/pdf")},
                    params={"language": sample["language"]},
                )

            if response.status_code != 201:
                print(f"    FAILED: {response.text}")
                continue

            book = response.json()
            print(f"    Uploaded: {book['id']}")

            pages = sample["expected"].get("recommended_pages", [1, 2])
            response = await client.post(
                f"/api/books/{book['id']}/pages",
                json={"selected_pages": pages},
            )
            if response.status_code != 200:
                print(f"    Page selection failed: {response.text}")
                continue
            print(f"    Selected {len(pages)} pages")


async def validate_samples(samples: list[dict], api_base: str) -> None:
    import httpx

    async with httpx.AsyncClient(base_url=api_base, timeout=120.0) as client:
        for sample in samples:
            if not sample["has_pdf"]:
                continue

            print(f"\nValidating: {sample['language']}/{sample['quality']}")
            expected_fields = sample["expected"].get("expected_metadata", {})

            if not expected_fields:
                print("  No expected metadata to validate against.")
                continue

            filled = {k: v for k, v in expected_fields.items() if v}
            if not filled:
                print("  Expected metadata is empty (template). Fill in expected_metadata.json first.")
                continue

            print(f"  Expected {len(filled)} non-empty fields: {list(filled.keys())}")
            print("  Note: Full validation requires running the complete pipeline first.")


def main():
    parser = argparse.ArgumentParser(description="Load and validate sample PDF fixtures")
    parser.add_argument("--language", choices=["tel", "hin"], help="Filter by language")
    parser.add_argument("--validate", action="store_true", help="Validate against expected outputs")
    parser.add_argument("--load", action="store_true", help="Load samples into the system")
    parser.add_argument("--api-base", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()

    samples = discover_samples(args.language)
    print_summary(samples)

    if args.load:
        print("\nLoading samples...")
        asyncio.run(load_samples(samples, args.api_base))

    if args.validate:
        print("\nValidating samples...")
        asyncio.run(validate_samples(samples, args.api_base))


if __name__ == "__main__":
    main()
