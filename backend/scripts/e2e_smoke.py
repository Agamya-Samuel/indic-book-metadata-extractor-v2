"""
End-to-end smoke test for the Indic Book Metadata Extractor.

Tests the full workflow: upload -> select pages -> preprocess -> OCR -> review -> corrections.

Usage:
    python scripts/e2e_smoke.py [--base-url http://localhost:8000] [--pdf path/to/test.pdf]

Requires the full Docker stack to be running (or local dev servers).
"""

import argparse
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx is required: uv add httpx")
    sys.exit(1)

BASE_URL = "http://localhost:8000/api"


def wait_for_server(client: httpx.Client, timeout: int = 30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = client.get(f"{BASE_URL.replace('/api', '')}/health")
            if r.status_code == 200:
                print("  [OK] Server is up")
                return True
        except httpx.ConnectError:
            pass
        time.sleep(1)
    print("  [FAIL] Server not reachable")
    return False


def step_upload(client: httpx.Client, pdf_path: str) -> str:
    print("\n--- Step 1: Upload PDF ---")
    pdf = Path(pdf_path)
    if not pdf.exists():
        print(f"  [FAIL] PDF not found: {pdf_path}")
        sys.exit(1)

    with open(pdf, "rb") as f:
        r = client.post(
            f"{BASE_URL}/books/upload",
            files={"file": (pdf.name, f, "application/pdf")},
            data={"language": "tel"},
        )

    assert r.status_code == 201, f"Upload failed: {r.status_code} {r.text}"
    data = r.json()
    book_id = data["id"]
    print(f"  [OK] Uploaded: {pdf.name} -> book_id={book_id}, status={data['status']}")
    assert data["status"] == "uploaded"
    return book_id


def step_get_book(client: httpx.Client, book_id: str):
    print("\n--- Step 2: Get Book Details ---")
    r = client.get(f"{BASE_URL}/books/{book_id}")
    assert r.status_code == 200, f"Get book failed: {r.text}"
    data = r.json()
    print(f"  [OK] Book: {data.get('title') or data.get('filename')}, pages={data.get('total_pages')}, status={data['status']}")
    return data


def step_select_pages(client: httpx.Client, book_id: str, book_data: dict):
    print("\n--- Step 3: Select Pages ---")
    total = book_data.get("total_pages") or 10
    pages_to_select = list(range(1, min(total + 1, 4)))

    r = client.post(
        f"{BASE_URL}/books/{book_id}/pages",
        json={"selected_pages": pages_to_select},
    )
    assert r.status_code == 200, f"Select pages failed: {r.text}"
    data = r.json()
    print(f"  [OK] Selected {data['selected_count']} pages, status={data['status']}")
    assert data["status"] == "pages_selected"
    return pages_to_select


def step_list_pages(client: httpx.Client, book_id: str):
    print("\n--- Step 4: List Pages ---")
    r = client.get(f"{BASE_URL}/books/{book_id}/pages")
    assert r.status_code == 200, f"List pages failed: {r.text}"
    pages = r.json()
    print(f"  [OK] {len(pages)} pages returned")
    assert len(pages) > 0
    return pages


def step_preprocess(client: httpx.Client, pages: list):
    print("\n--- Step 5: Preprocess First Page ---")
    page_id = pages[0]["id"]
    config = {
        "grayscale": True,
        "brightness": 0,
        "contrast": 0,
        "binarization": None,
        "adaptive_block_size": 11,
        "adaptive_c": 2,
        "deskew": True,
        "denoise": False,
        "denoise_strength": 10,
    }

    r = client.put(f"{BASE_URL}/pages/{page_id}/preprocessing", json=config)
    assert r.status_code == 200, f"Preprocessing failed: {r.text}"
    data = r.json()
    print(f"  [OK] Preprocessed page_id={data['page_id']}, image_url={data['processed_image_url']}")
    return data


def step_run_ocr(client: httpx.Client, book_id: str):
    print("\n--- Step 6: Run OCR ---")
    r = client.post(f"{BASE_URL}/books/{book_id}/run-ocr")
    assert r.status_code == 201, f"Run OCR failed: {r.text}"
    data = r.json()
    job_id = data["id"]
    print(f"  [OK] OCR job created: job_id={job_id}, status={data['status']}")
    return job_id


def step_poll_job(client: httpx.Client, book_id: str, job_id: str, timeout: int = 300):
    print(f"\n--- Step 7: Poll OCR Job (timeout={timeout}s) ---")
    start = time.time()
    while time.time() - start < timeout:
        r = client.get(f"{BASE_URL}/books/{book_id}/jobs")
        assert r.status_code == 200
        jobs = r.json()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if not job:
            print(f"  [FAIL] Job {job_id} not found")
            sys.exit(1)

        status = job["status"]
        progress = job["progress"]
        print(f"  ... status={status}, progress={progress:.0f}%")

        if status == "completed":
            print(f"  [OK] OCR job completed!")
            return job
        elif status == "failed":
            print(f"  [FAIL] OCR job failed: {job.get('error_log')}")
            sys.exit(1)

        time.sleep(3)

    print(f"  [FAIL] OCR job timed out after {timeout}s")
    sys.exit(1)


def step_ocr_status(client: httpx.Client, book_id: str):
    print("\n--- Step 8: Check OCR Status Summary ---")
    r = client.get(f"{BASE_URL}/books/{book_id}/ocr-status")
    assert r.status_code == 200, f"OCR status failed: {r.text}"
    data = r.json()
    print(f"  [OK] total={data['total_pages']}, complete={data['ocr_complete_count']}, "
          f"pending={data['ocr_pending_count']}, avg_conf={data.get('avg_confidence')}")
    assert data["ocr_complete_count"] == data["total_pages"]
    return data


def step_get_ocr_result(client: httpx.Client, pages: list):
    print("\n--- Step 9: Get OCR Result for First Page ---")
    page_id = pages[0]["id"]
    r = client.get(f"{BASE_URL}/pages/{page_id}/ocr")
    assert r.status_code == 200, f"Get OCR result failed: {r.text}"
    data = r.json()
    boxes_count = len(data.get("bounding_boxes") or [])
    print(f"  [OK] raw_text length={len(data.get('raw_text') or '')}, "
          f"bounding_boxes={boxes_count}, "
          f"confidence={data.get('confidence')}, "
          f"language={data.get('language_detected')}")
    assert data["raw_text"] is not None
    return data


def step_correct_ocr(client: httpx.Client, pages: list, ocr_data: dict):
    print("\n--- Step 10: Save OCR Correction ---")
    page_id = pages[0]["id"]
    corrected = (ocr_data.get("raw_text") or "") + " [TEST CORRECTION]"

    r = client.put(f"{BASE_URL}/pages/{page_id}/ocr", json={"corrected_text": corrected})
    assert r.status_code == 200, f"Correction failed: {r.text}"
    data = r.json()
    print(f"  [OK] Saved correction, corrected_text ends with: ...{data['corrected_text'][-30:]}")
    assert data["corrected_text"] == corrected
    return data


def main():
    parser = argparse.ArgumentParser(description="E2E smoke test")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--pdf", required=True, help="Path to a test PDF file")
    parser.add_argument("--timeout", type=int, default=300, help="OCR job timeout in seconds")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = f"{args.base_url}/api"

    print("=" * 60)
    print("Indic Book Metadata Extractor - E2E Smoke Test")
    print("=" * 60)

    with httpx.Client(timeout=60) as client:
        if not wait_for_server(client):
            sys.exit(1)

        book_id = step_upload(client, args.pdf)
        book_data = step_get_book(client, book_id)
        step_select_pages(client, book_id, book_data)
        pages = step_list_pages(client, book_id)
        step_preprocess(client, pages)
        job_id = step_run_ocr(client, book_id)
        step_poll_job(client, book_id, job_id, timeout=args.timeout)
        step_ocr_status(client, book_id)
        ocr_data = step_get_ocr_result(client, pages)
        step_correct_ocr(client, pages, ocr_data)

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
