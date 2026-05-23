"""
OCR accuracy batch test script.

Tests OCR accuracy across multiple PDFs with different preprocessing configurations.
Reports per-page and per-PDF statistics.

Usage:
    python scripts/test_ocr_accuracy.py --pdf-dir path/to/pdfs/ [--base-url http://localhost:8000] [--pages 3]

Requires the full Docker stack to be running.
"""

import argparse
import json
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx is required: uv add httpx")
    sys.exit(1)

BASE_URL = "http://localhost:8000/api"

PREPROCESSING_CONFIGS = {
    "default": {
        "grayscale": True,
        "brightness": 0,
        "contrast": 0,
        "binarization": None,
        "adaptive_block_size": 11,
        "adaptive_c": 2,
        "deskew": True,
        "denoise": False,
        "denoise_strength": 10,
    },
    "grayscale_only": {
        "grayscale": True,
        "brightness": 0,
        "contrast": 0,
        "binarization": None,
        "adaptive_block_size": 11,
        "adaptive_c": 2,
        "deskew": False,
        "denoise": False,
        "denoise_strength": 10,
    },
    "otsu_binarize": {
        "grayscale": True,
        "brightness": 0,
        "contrast": 0,
        "binarization": "otsu",
        "adaptive_block_size": 11,
        "adaptive_c": 2,
        "deskew": True,
        "denoise": False,
        "denoise_strength": 10,
    },
    "adaptive_binarize": {
        "grayscale": True,
        "brightness": 0,
        "contrast": 0,
        "binarization": "adaptive",
        "adaptive_block_size": 11,
        "adaptive_c": 2,
        "deskew": True,
        "denoise": False,
        "denoise_strength": 10,
    },
    "denoise_deskew": {
        "grayscale": True,
        "brightness": 0,
        "contrast": 0,
        "binarization": None,
        "adaptive_block_size": 11,
        "adaptive_c": 2,
        "deskew": True,
        "denoise": True,
        "denoise_strength": 10,
    },
}


def wait_for_server(client: httpx.Client, timeout: int = 30) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = client.get(f"{BASE_URL.replace('/api', '')}/health")
            if r.status_code == 200:
                return True
        except httpx.ConnectError:
            pass
        time.sleep(1)
    return False


def test_pdf(
    client: httpx.Client,
    pdf_path: Path,
    pages_to_test: int,
    config_name: str,
    config: dict,
) -> dict:
    with open(pdf_path, "rb") as f:
        r = client.post(
            f"{BASE_URL}/books/upload",
            files={"file": (pdf_path.name, f, "application/pdf")},
            data={"language": "tel"},
        )

    if r.status_code != 201:
        return {"pdf": pdf_path.name, "config": config_name, "error": f"Upload failed: {r.status_code}"}

    book_id = r.json()["id"]

    r = client.get(f"{BASE_URL}/books/{book_id}")
    book_data = r.json()
    total_pages = book_data.get("total_pages") or pages_to_test
    pages_to_select = list(range(1, min(total_pages + 1, pages_to_test + 1)))

    r = client.post(
        f"{BASE_URL}/books/{book_id}/pages",
        json={"selected_pages": pages_to_select},
    )
    if r.status_code != 200:
        return {"pdf": pdf_path.name, "config": config_name, "error": f"Select pages failed: {r.status_code}"}

    r = client.get(f"{BASE_URL}/books/{book_id}/pages")
    pages = r.json()

    for page in pages:
        client.put(
            f"{BASE_URL}/pages/{page['id']}/preprocessing",
            json=config,
        )

    r = client.post(f"{BASE_URL}/books/{book_id}/run-ocr")
    if r.status_code != 201:
        return {"pdf": pdf_path.name, "config": config_name, "error": f"OCR start failed: {r.status_code}"}

    job_id = r.json()["id"]

    start = time.time()
    timeout = 300
    while time.time() - start < timeout:
        r = client.get(f"{BASE_URL}/books/{book_id}/jobs")
        jobs = r.json()
        current = next((j for j in jobs if j["id"] == job_id), None)
        if current and current["status"] == "completed":
            break
        if current and current["status"] == "failed":
            return {
                "pdf": pdf_path.name,
                "config": config_name,
                "error": f"OCR failed: {current.get('error_log', 'unknown')}",
            }
        time.sleep(3)
    else:
        return {"pdf": pdf_path.name, "config": config_name, "error": "OCR timed out"}

    page_results = []
    for page in pages:
        r = client.get(f"{BASE_URL}/pages/{page['id']}/ocr")
        if r.status_code == 200:
            ocr = r.json()
            boxes = ocr.get("bounding_boxes") or []
            word_count = len(boxes)
            avg_conf = ocr.get("confidence")
            detected_lang = ocr.get("language_detected")
            text_len = len(ocr.get("raw_text") or "")

            if boxes:
                box_confs = [b.get("confidence", 0) for b in boxes if "confidence" in b]
                word_avg_conf = sum(box_confs) / len(box_confs) if box_confs else 0
            else:
                word_avg_conf = 0

            page_results.append({
                "page_number": page["page_number"],
                "word_count": word_count,
                "text_length": text_len,
                "avg_confidence": avg_conf,
                "word_avg_confidence": round(word_avg_conf, 1),
                "detected_language": detected_lang,
            })

    return {
        "pdf": pdf_path.name,
        "config": config_name,
        "pages": page_results,
        "avg_confidence": round(
            sum(p["avg_confidence"] or 0 for p in page_results) / max(len(page_results), 1), 1
        ),
        "avg_word_confidence": round(
            sum(p["word_avg_confidence"] for p in page_results) / max(len(page_results), 1), 1
        ),
        "total_words": sum(p["word_count"] for p in page_results),
    }


def print_summary(results: list[dict]):
    print("\n" + "=" * 80)
    print("OCR ACCURACY SUMMARY")
    print("=" * 80)

    header = f"{'PDF':<30} {'Config':<20} {'Avg Conf':>10} {'Word Conf':>10} {'Words':>8} {'Pages':>6}"
    print(header)
    print("-" * 80)

    for r in results:
        if "error" in r:
            print(f"{r['pdf']:<30} {r['config']:<20} ERROR: {r['error']}")
        else:
            page_count = len(r.get("pages", []))
            print(
                f"{r['pdf']:<30} {r['config']:<20} "
                f"{r['avg_confidence']:>9.1f}% "
                f"{r['avg_word_confidence']:>9.1f}% "
                f"{r['total_words']:>8} "
                f"{page_count:>6}"
            )

    print()

    default_results = [r for r in results if r.get("config") == "default" and "error" not in r]
    if default_results:
        overall_avg = sum(r["avg_confidence"] for r in default_results) / len(default_results)
        overall_word_avg = sum(r["avg_word_confidence"] for r in default_results) / len(default_results)
        print(f"Overall (default config): avg_confidence={overall_avg:.1f}%, word_confidence={overall_word_avg:.1f}%")

    print()

    for r in results:
        if "error" in r or "pages" not in r:
            continue
        print(f"\n--- {r['pdf']} ({r['config']}) ---")
        for p in r["pages"]:
            print(
                f"  Page {p['page_number']:>3}: "
                f"words={p['word_count']:>4}, "
                f"text_len={p['text_length']:>5}, "
                f"conf={p['avg_confidence'] or 'N/A'}, "
                f"word_conf={p['word_avg_confidence']:.1f}%, "
                f"lang={p['detected_language'] or 'N/A'}"
            )


def main():
    parser = argparse.ArgumentParser(description="OCR accuracy batch test")
    parser.add_argument("--pdf-dir", required=True, help="Directory containing test PDFs")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--pages", type=int, default=3, help="Number of pages to test per PDF")
    parser.add_argument(
        "--configs",
        nargs="*",
        default=["default"],
        choices=list(PREPROCESSING_CONFIGS.keys()),
        help="Preprocessing configs to test",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = f"{args.base_url}/api"

    pdf_dir = Path(args.pdf_dir)
    if not pdf_dir.is_dir():
        print(f"Error: {args.pdf_dir} is not a directory")
        sys.exit(1)

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"Error: No PDFs found in {args.pdf_dir}")
        sys.exit(1)

    print(f"Found {len(pdfs)} PDF(s) in {args.pdf_dir}")
    print(f"Testing with configs: {', '.join(args.configs)}")
    print(f"Pages per PDF: {args.pages}")

    results = []

    with httpx.Client(timeout=60) as client:
        if not wait_for_server(client):
            print("Server not reachable")
            sys.exit(1)

        for pdf_path in pdfs:
            for config_name in args.configs:
                config = PREPROCESSING_CONFIGS[config_name]
                print(f"\nTesting {pdf_path.name} with config '{config_name}'...")
                result = test_pdf(client, pdf_path, args.pages, config_name, config)
                results.append(result)
                if "error" in result:
                    print(f"  ERROR: {result['error']}")
                else:
                    print(f"  Done: avg_conf={result['avg_confidence']}%, words={result['total_words']}")

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_summary(results)


if __name__ == "__main__":
    main()
