"""Production end-to-end check for the Indic Books app (throwaway data).

Run from the repository root against the deployed host. Reads QA credentials
from reference/oki-qa-accounts (override with E2E_ACCOUNTS) and uploads a local
PDF (override with E2E_PDF), exercising auth, RBAC, the full pipeline, admin
flows and cleanup. It creates one book and one user, then deletes both.

  E2E_BASE_URL, E2E_PDF, E2E_ACCOUNTS, E2E_REPORT are optional overrides.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

BASE = os.environ.get("E2E_BASE_URL", "https://indic-book-metadata-extractor.agamya.us.kg")
PDF = Path(
    os.environ.get(
        "E2E_PDF",
        "backend/storage/uploads/a2db7f01-e1f4-4ed0-9539-0633b6db6763/original.pdf",
    )
)
ACCOUNTS = Path(os.environ.get("E2E_ACCOUNTS", "reference/oki-qa-accounts"))
REPORT = Path(os.environ.get("E2E_REPORT", "/tmp/e2e-report.json"))

results: list[dict] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append({"test": name, "ok": ok, "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


def creds() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in ACCOUNTS.read_text().splitlines():
        if "@" not in line or ":" not in line:
            continue
        email, rest = line.split(":", 1)
        # The notes line starts with the password, followed by prose.
        out[email.strip()] = rest.strip().split()[0]
    return out


def make_client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE,
        timeout=httpx.Timeout(60.0, read=300.0, write=600.0),
        follow_redirects=True,
        trust_env=False,
    )


def csrf(client: httpx.Client) -> str:
    return client.cookies.get("csrf_token", "")


def login(client: httpx.Client, email: str, password: str) -> httpx.Response:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    token = csrf(client)
    if token:
        client.headers["X-CSRF-Token"] = token
    return response


def authed(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    token = csrf(client)
    if token:
        client.headers["X-CSRF-Token"] = token
    return client.request(method, url, **kwargs)


def rows(payload):
    if isinstance(payload, dict):
        return payload.get("items", [])
    return payload if isinstance(payload, list) else []


def wait_job(
    client: httpx.Client,
    book_id: str,
    job_id: str,
    *,
    timeout_s: int,
    allow_cancel_check: bool = False,
) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        response = authed(client, "GET", f"/api/books/{book_id}/jobs")
        if response.status_code == 200:
            for job in rows(response.json()):
                if job["id"] == job_id:
                    last = job
                    if job["status"] in ("completed", "failed", "cancelled"):
                        return job
        time.sleep(4)
    return last


def main() -> int:
    accounts = creds()
    admin_email = next(e for e in accounts if "admin" in e)
    user_email = next(e for e in accounts if "user" in e and "signup" not in e)

    # ── Anonymous ─────────────────────────────────────────────────────────
    anon = make_client()
    record("anon: /api/health is public", anon.get("/api/health").status_code == 200)
    record("anon: models requires auth", anon.get("/api/books/models").status_code == 401)
    record("anon: dashboard requires auth", anon.get("/api/dashboard/summary").status_code == 401)
    record("anon: admin requires auth", anon.get("/api/admin/stats").status_code == 401)
    anon.close()

    # ── User session ──────────────────────────────────────────────────────
    user = make_client()
    response = login(user, user_email, accounts[user_email])
    record("user: login", response.status_code == 200, str(response.status_code))
    me = authed(user, "GET", "/api/auth/me")
    user_id = me.json().get("id") if me.status_code == 200 else None
    record(
        "user: /me approved",
        me.status_code == 200 and me.json().get("account_status") == "approved",
    )
    record("user: dashboard summary", authed(user, "GET", "/api/dashboard/summary").status_code == 200)
    record("user: own books list", authed(user, "GET", "/api/dashboard/books").status_code == 200)
    record("user: own jobs list", authed(user, "GET", "/api/dashboard/jobs").status_code == 200)
    record("user: admin denied", authed(user, "GET", "/api/admin/stats").status_code == 403)
    record("user: notifications", authed(user, "GET", "/api/notifications").status_code == 200)

    # ── Admin session ─────────────────────────────────────────────────────
    admin = make_client()
    response = login(admin, admin_email, accounts[admin_email])
    record("admin: login", response.status_code == 200, str(response.status_code))
    stats = authed(admin, "GET", "/api/admin/stats")
    record("admin: stats", stats.status_code == 200)
    users = authed(admin, "GET", "/api/admin/users?page_size=100")
    record("admin: users list", users.status_code == 200)
    admin_books = authed(admin, "GET", "/api/admin/books?page_size=100")
    record("admin: books list", admin_books.status_code == 200)

    # ── IDOR: another owner's book is invisible ──────────────────────────
    items = admin_books.json().get("items", []) if admin_books.status_code == 200 else []
    foreign = next((b for b in items if b.get("owner_id") != user_id), None)
    if foreign:
        leaked = authed(user, "GET", f"/api/books/{foreign['id']}")
        record("rbac: foreign book returns 404", leaked.status_code == 404, str(leaked.status_code))
        leaked_pages = authed(user, "GET", f"/api/books/{foreign['id']}/pages")
        record(
            "rbac: foreign pages return 404",
            leaked_pages.status_code == 404,
            str(leaked_pages.status_code),
        )
    else:
        record("rbac: foreign book fixture available", False, "no foreign book found")

    # ── Upload ────────────────────────────────────────────────────────────
    if not PDF.exists():
        record("upload: sample PDF exists", False, str(PDF))
        return 1
    with PDF.open("rb") as handle:
        uploaded = authed(
            user,
            "POST",
            "/api/books/upload",
            files={"file": (PDF.name, handle, "application/pdf")},
            data={"language": "hin"},
        )
    record("upload: accepted", uploaded.status_code == 201, str(uploaded.status_code))
    if uploaded.status_code != 201:
        print(uploaded.text[:500])
        return 1
    book = uploaded.json()
    book_id = book["id"]
    record("upload: page count", (book.get("total_pages") or 0) > 0, str(book.get("total_pages")))

    # ── Page selection + duplicate submission ────────────────────────────
    selection = authed(user, "POST", f"/api/books/{book_id}/pages", json={"selected_pages": [1, 2]})
    record("pages: select two", selection.status_code == 200, str(selection.status_code))
    job_id = selection.json().get("job_id") if selection.status_code == 200 else None
    duplicate = authed(user, "POST", f"/api/books/{book_id}/pages", json={"selected_pages": [1, 2]})
    record(
        "pages: duplicate submission is 409",
        duplicate.status_code == 409 and bool(duplicate.headers.get("x-existing-job-id")),
        f"{duplicate.status_code} job={duplicate.headers.get('x-existing-job-id')}",
    )
    job = wait_job(user, book_id, job_id, timeout_s=600)
    record("pages: extraction completed", job.get("status") == "completed", job.get("status", "?"))

    # ── Preprocessing job ────────────────────────────────────────────────
    prep = authed(
        user,
        "POST",
        f"/api/books/{book_id}/preprocessing",
        json={
            "grayscale": True,
            "binarization": None,
            "deskew": True,
            "denoise": False,
            "upscale_to_300dpi": True,
            "remove_borders": True,
            "auto_preprocess": True,
        },
    )
    record("preprocess: job accepted", prep.status_code == 201, str(prep.status_code))
    prep_job = wait_job(user, book_id, prep.json()["id"], timeout_s=600)
    record("preprocess: completed", prep_job.get("status") == "completed", prep_job.get("status", "?"))

    # ── OCR: cancel once, then run to completion ─────────────────────────
    ocr = authed(user, "POST", f"/api/books/{book_id}/run-ocr")
    record("ocr: first run accepted", ocr.status_code == 201, str(ocr.status_code))
    ocr_job_id = ocr.json()["id"]
    time.sleep(4)
    cancelled = authed(user, "POST", f"/api/dashboard/jobs/{ocr_job_id}/cancel")
    record("ocr: cancel accepted", cancelled.status_code == 200, str(cancelled.status_code))
    time.sleep(20)
    after_cancel = wait_job(user, book_id, ocr_job_id, timeout_s=5)
    record(
        "ocr: cancelled job stays cancelled",
        after_cancel.get("status") == "cancelled",
        after_cancel.get("status", "?"),
    )

    rerun = authed(user, "POST", f"/api/books/{book_id}/rerun-ocr")
    record("ocr: re-run accepted", rerun.status_code == 201, str(rerun.status_code))
    ocr_job = wait_job(user, book_id, rerun.json()["job_id"], timeout_s=1800)
    record(
        "ocr: completed after re-run",
        ocr_job.get("status") == "completed",
        f"{ocr_job.get('status')} {str(ocr_job.get('error_log') or '')[:120]}",
    )

    pages = authed(user, "GET", f"/api/books/{book_id}/pages")
    page_rows = rows(pages.json()) if pages.status_code == 200 else []
    record("ocr: pages listed", pages.status_code == 200 and len(page_rows) == 2)
    failed_pages = [p for p in page_rows if p.get("ocr_error")]
    record("ocr: no page-level failures", not failed_pages, f"{len(failed_pages)} flagged")
    if page_rows:
        page_id = page_rows[0]["id"]
        text = authed(user, "GET", f"/api/pages/{page_id}/ocr")
        record("ocr: text available", text.status_code == 200 and bool((text.json() or {}).get("raw_text")))
        correction = authed(
            user,
            "PUT",
            f"/api/pages/{page_id}/ocr",
            json={"corrected_text": "QA correction persisted"},
        )
        record("ocr: correction saved", correction.status_code == 200)
        reread = authed(user, "GET", f"/api/pages/{page_id}/ocr")
        record(
            "ocr: correction read back",
            reread.status_code == 200 and reread.json().get("corrected_text") == "QA correction persisted",
        )

    # ── LLM extraction + duplicate guard ─────────────────────────────────
    payload = {"model": "phi4-mini", "temperature": 0.3, "max_tokens": 512}
    extraction = authed(user, "POST", f"/api/books/{book_id}/run-extraction", json=payload)
    record("llm: run accepted", extraction.status_code == 201, str(extraction.status_code))
    llm_job_id = extraction.json().get("job_id") if extraction.status_code == 201 else None
    duplicate_llm = authed(user, "POST", f"/api/books/{book_id}/run-extraction", json=payload)
    record(
        "llm: duplicate submission is 409",
        duplicate_llm.status_code == 409,
        str(duplicate_llm.status_code),
    )
    llm_job = wait_job(user, book_id, llm_job_id, timeout_s=1800)
    record(
        "llm: finished",
        llm_job.get("status") in ("completed", "failed"),
        f"{llm_job.get('status')} {str(llm_job.get('error_log') or '')[:140]}",
    )

    book_state = authed(user, "GET", f"/api/books/{book_id}")
    status = book_state.json().get("status") if book_state.status_code == 200 else None
    record("llm: book reached awaiting_review", status == "awaiting_review", str(status))

    metadata = authed(user, "GET", f"/api/books/{book_id}/metadata")
    fields = metadata.json().get("fields", {}) if metadata.status_code == 200 else {}
    record("llm: metadata present", bool(fields), f"{len(fields)} fields")
    evidence = authed(user, "GET", f"/api/books/{book_id}/metadata/evidence")
    record("llm: evidence present", evidence.status_code == 200, str(evidence.status_code))

    # ── Re-run extraction from awaiting_review, then cancel ─────────────
    rerun_ext = authed(user, "POST", f"/api/books/{book_id}/run-extraction", json=payload)
    record(
        "llm: re-run from awaiting_review accepted",
        rerun_ext.status_code == 201,
        str(rerun_ext.status_code),
    )
    if rerun_ext.status_code == 201:
        time.sleep(4)
        cancelled_ext = authed(user, "POST", f"/api/dashboard/jobs/{rerun_ext.json()['job_id']}/cancel")
        record("llm: re-run cancel accepted", cancelled_ext.status_code == 200)

    # ── Metadata validation + save + complete ───────────────────────────
    unknown = authed(
        user,
        "PUT",
        f"/api/books/{book_id}/metadata",
        json={"fields": {"not_a_real_field": "x"}},
    )
    record("metadata: unknown field rejected", unknown.status_code == 422, str(unknown.status_code))
    saved = authed(
        user,
        "PUT",
        f"/api/books/{book_id}/metadata",
        json={"fields": {"title": "QA title", "custom_fields": {"qa_note": "checked"}}},
    )
    record("metadata: save accepted", saved.status_code == 200, str(saved.status_code))
    reread_meta = authed(user, "GET", f"/api/books/{book_id}/metadata")
    reread_fields = reread_meta.json().get("fields", {}) if reread_meta.status_code == 200 else {}
    record(
        "metadata: values persisted",
        reread_fields.get("title") == "QA title"
        and (reread_fields.get("custom_fields") or {}).get("qa_note") == "checked",
    )

    completed = authed(user, "POST", f"/api/books/{book_id}/review/complete")
    record("review: complete accepted", completed.status_code == 200, str(completed.status_code))
    final_state = authed(user, "GET", f"/api/books/{book_id}")
    record(
        "review: book complete",
        final_state.status_code == 200 and final_state.json().get("status") == "complete",
        final_state.json().get("status") if final_state.status_code == 200 else "?",
    )

    # ── Notifications ────────────────────────────────────────────────────
    notifications = authed(user, "GET", "/api/notifications?page_size=50")
    notification_rows = rows(notifications.json()) if notifications.status_code == 200 else []
    record("notifications: job events present", len(notification_rows) > 0, f"{len(notification_rows)} rows")
    if notification_rows:
        target = next((r for r in notification_rows if r.get("book_id") == book_id), notification_rows[0])
        read = authed(user, "POST", f"/api/notifications/{target['id']}/read")
        record("notifications: mark read", read.status_code == 200)
    record(
        "notifications: preferences read",
        authed(user, "GET", "/api/notifications/preferences").status_code == 200,
    )

    # ── Admin: user create/delete ────────────────────────────────────────
    created_user = authed(
        admin,
        "POST",
        "/api/admin/users",
        json={
            "email": f"qa-e2e-{int(time.time())}@example.com",
            "display_name": "QA E2E",
            "password": "correct horse battery staple",
            "role": "user",
        },
    )
    record("admin: create user", created_user.status_code == 201, str(created_user.status_code))
    if created_user.status_code == 201:
        deleted_user = authed(admin, "DELETE", f"/api/admin/users/{created_user.json()['id']}")
        record("admin: delete user", deleted_user.status_code == 204, str(deleted_user.status_code))

    admin_jobs = authed(admin, "GET", f"/api/admin/jobs?book_id={book_id}")
    record(
        "admin: global job queue shows the book",
        admin_jobs.status_code == 200 and admin_jobs.json().get("total", 0) > 0,
    )

    # ── Cleanup ──────────────────────────────────────────────────────────
    deleted_book = authed(user, "DELETE", f"/api/books/{book_id}")
    record("cleanup: test book deleted", deleted_book.status_code == 204, str(deleted_book.status_code))
    gone = authed(user, "GET", f"/api/books/{book_id}")
    record("cleanup: book gone", gone.status_code == 404, str(gone.status_code))

    user.close()
    admin.close()

    failed = [r for r in results if not r["ok"]]
    REPORT.write_text(json.dumps(results, indent=2))
    print(f"\n{len(results) - len(failed)}/{len(results)} passed; report: {REPORT}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
