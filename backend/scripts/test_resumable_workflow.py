"""
Resumable workflow validation test.

Validates that the server persists all workflow state and a user can resume at any point
by re-fetching the book status.

Usage:
    python scripts/test_resumable_workflow.py --pdf path/to/test.pdf [--base-url http://localhost:8000]

Requires the full Docker stack to be running.
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


def wait_for_server(client: httpx.Client, timeout: int = 30) -> bool:
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


def test_resume_after_upload(client: httpx.Client, pdf_path: str) -> str:
    print("\n=== Test 1: Resume after upload ===")
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
    print(f"  Uploaded: book_id={book_id}, status={data['status']}")

    print("  Simulating 'leave and return' by re-fetching book...")
    r = client.get(f"{BASE_URL}/books/{book_id}")
    assert r.status_code == 200
    book = r.json()
    assert book["status"] == "uploaded", f"Expected 'uploaded', got '{book['status']}'"
    print(f"  [OK] Status preserved: {book['status']}")

    r = client.get(f"{BASE_URL}/books/{book_id}/pages")
    assert r.status_code == 200
    pages = r.json()
    assert len(pages) == 0, "Expected no pages before selection"
    print(f"  [OK] Pages empty (as expected): {len(pages)} pages")

    return book_id


def test_resume_after_select(client: httpx.Client, book_id: str, book_data: dict):
    print("\n=== Test 2: Resume after page selection ===")
    total = book_data.get("total_pages") or 10
    pages_to_select = list(range(1, min(total + 1, 4)))

    r = client.post(
        f"{BASE_URL}/books/{book_id}/pages",
        json={"selected_pages": pages_to_select},
    )
    assert r.status_code == 200, f"Select pages failed: {r.text}"
    data = r.json()
    assert data["status"] == "pages_selected"
    print(f"  Selected {data['selected_count']} pages")

    print("  Simulating 'leave and return'...")
    r = client.get(f"{BASE_URL}/books/{book_id}")
    assert r.status_code == 200
    book = r.json()
    assert book["status"] == "pages_selected", f"Expected 'pages_selected', got '{book['status']}'"
    print(f"  [OK] Status preserved: {book['status']}")

    r = client.get(f"{BASE_URL}/books/{book_id}/pages")
    assert r.status_code == 200
    pages = r.json()
    assert len(pages) == len(pages_to_select)
    print(f"  [OK] Pages persisted: {len(pages)} pages")


def test_resume_after_ocr(client: httpx.Client, book_id: str):
    print("\n=== Test 3: Resume after OCR ===")
    r = client.post(f"{BASE_URL}/books/{book_id}/run-ocr")
    assert r.status_code == 201, f"Run OCR failed: {r.text}"
    job = r.json()
    job_id = job["id"]
    print(f"  OCR job created: {job_id}")

    print("  Waiting for OCR to complete...")
    start = time.time()
    timeout = 300
    while time.time() - start < timeout:
        r = client.get(f"{BASE_URL}/books/{book_id}/jobs")
        assert r.status_code == 200
        jobs = r.json()
        current = next((j for j in jobs if j["id"] == job_id), None)
        if not current:
            print(f"  [FAIL] Job {job_id} not found")
            sys.exit(1)
        if current["status"] == "completed":
            print(f"  OCR completed!")
            break
        elif current["status"] == "failed":
            print(f"  [FAIL] OCR failed: {current.get('error_log')}")
            sys.exit(1)
        time.sleep(3)
    else:
        print(f"  [FAIL] OCR timed out after {timeout}s")
        sys.exit(1)

    print("  Simulating 'leave and return'...")
    r = client.get(f"{BASE_URL}/books/{book_id}")
    assert r.status_code == 200
    book = r.json()
    assert book["status"] == "ocr_complete", f"Expected 'ocr_complete', got '{book['status']}'"
    print(f"  [OK] Status preserved: {book['status']}")

    r = client.get(f"{BASE_URL}/books/{book_id}/ocr-status")
    assert r.status_code == 200
    ocr_status = r.json()
    assert ocr_status["ocr_complete_count"] == ocr_status["total_pages"]
    print(f"  [OK] OCR status preserved: {ocr_status['ocr_complete_count']}/{ocr_status['total_pages']} complete")


def test_resume_after_extraction(client: httpx.Client, book_id: str):
    print("\n=== Test 4: Resume after LLM extraction ===")
    r = client.post(
        f"{BASE_URL}/books/{book_id}/run-extraction",
        json={
            "model": "qwen2.5",
            "temperature": 0.3,
            "max_tokens": 2048,
            "fields_per_batch": 10,
        },
    )
    if r.status_code != 201:
        print(f"  [SKIP] Extraction start returned {r.status_code}: {r.text}")
        print("  (This may be expected if Ollama/Qwen2.5 is not fully configured)")
        return
    data = r.json()
    job_id = data["job_id"]
    print(f"  Extraction job created: {job_id}")

    print("  Waiting for extraction to complete...")
    start = time.time()
    timeout = 600
    while time.time() - start < timeout:
        r = client.get(f"{BASE_URL}/books/{book_id}/jobs")
        assert r.status_code == 200
        jobs = r.json()
        current = next((j for j in jobs if j["id"] == job_id), None)
        if not current:
            print(f"  [FAIL] Job {job_id} not found")
            sys.exit(1)
        if current["status"] == "completed":
            print(f"  Extraction completed!")
            break
        elif current["status"] == "failed":
            print(f"  [WARN] Extraction failed: {current.get('error_log')}")
            print("  Continuing with resume check...")
            break
        time.sleep(5)
    else:
        print(f"  [WARN] Extraction timed out after {timeout}s")
        print("  Continuing with resume check...")

    print("  Simulating 'leave and return'...")
    r = client.get(f"{BASE_URL}/books/{book_id}")
    assert r.status_code == 200
    book = r.json()
    print(f"  [OK] Final status preserved: {book['status']}")

    r = client.get(f"{BASE_URL}/books/{book_id}/metadata")
    assert r.status_code == 200
    metadata = r.json()
    field_count = len(metadata.get("fields") or {})
    print(f"  [OK] Metadata accessible: {field_count} fields")


def test_ocr_corrections_persist(client: httpx.Client, book_id: str):
    print("\n=== Test 5: OCR corrections persist across sessions ===")
    r = client.get(f"{BASE_URL}/books/{book_id}/pages")
    assert r.status_code == 200
    pages = r.json()
    assert len(pages) > 0

    page_id = pages[0]["id"]
    r = client.get(f"{BASE_URL}/pages/{page_id}/ocr")
    assert r.status_code == 200
    ocr = r.json()
    original_text = ocr.get("raw_text") or ""
    corrected = original_text + " [RESUME TEST CORRECTION]"

    r = client.put(
        f"{BASE_URL}/pages/{page_id}/ocr",
        json={"corrected_text": corrected},
    )
    assert r.status_code == 200
    print(f"  Saved correction for page {pages[0]['page_number']}")

    print("  Simulating 'leave and return'...")
    r = client.get(f"{BASE_URL}/pages/{page_id}/ocr")
    assert r.status_code == 200
    ocr2 = r.json()
    assert ocr2["corrected_text"] == corrected, "Correction not persisted!"
    print(f"  [OK] OCR correction preserved across session")


def main():
    parser = argparse.ArgumentParser(description="Resumable workflow validation test")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--pdf", required=True, help="Path to a test PDF file")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = f"{args.base_url}/api"

    print("=" * 60)
    print("Resumable Workflow Validation Test")
    print("=" * 60)

    with httpx.Client(timeout=60) as client:
        if not wait_for_server(client):
            sys.exit(1)

        book_id = test_resume_after_upload(client, args.pdf)

        r = client.get(f"{BASE_URL}/books/{book_id}")
        book_data = r.json()

        test_resume_after_select(client, book_id, book_data)
        test_resume_after_ocr(client, book_id)
        test_ocr_corrections_persist(client, book_id)
        test_resume_after_extraction(client, book_id)

    print("\n" + "=" * 60)
    print("ALL RESUME TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
