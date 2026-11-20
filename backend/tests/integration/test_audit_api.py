"""Audit log API: RBAC, filtering, sorting, pagination, and event coverage."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.audit_log import AuditLog


async def _audit_rows(db_session) -> list[AuditLog]:
    result = await db_session.execute(select(AuditLog))
    return list(result.scalars().all())


async def _actions(db_session) -> set[str]:
    return {row.action for row in await _audit_rows(db_session)}


# ---------------------------------------------------------------------------
# RBAC and routing
# ---------------------------------------------------------------------------


async def test_audit_endpoints_require_admin(anon_client, client, admin_client):
    assert (await anon_client.get("/api/admin/audit-logs")).status_code == 401
    assert (await client.get("/api/admin/audit-logs")).status_code == 403
    assert (await admin_client.get("/api/admin/audit-logs")).status_code == 200

    assert (await client.get("/api/admin/audit-logs/actions")).status_code == 403
    assert (await admin_client.get("/api/admin/audit-logs/actions")).status_code == 200

    some_id = uuid.uuid4()
    assert (await client.get(f"/api/admin/audit-logs/{some_id}")).status_code == 403
    assert (await admin_client.get(f"/api/admin/audit-logs/{some_id}")).status_code == 404


async def test_no_mutation_routes_exist(admin_client):
    for method in ("post", "put", "patch", "delete"):
        response = await getattr(admin_client, method)("/api/admin/audit-logs")
        assert response.status_code == 405, method


async def test_actions_catalogue_shape(admin_client):
    response = await admin_client.get("/api/admin/audit-logs/actions")
    assert response.status_code == 200
    items = response.json()
    assert items
    values = {item["value"] for item in items}
    assert "auth.login" in values
    assert "metadata.updated" in values
    assert "job.failed" in values
    assert all({"value", "category", "label", "critical"} <= set(item) for item in items)


# ---------------------------------------------------------------------------
# Meta-audit and filters
# ---------------------------------------------------------------------------


async def test_viewing_the_log_records_audit_viewed(admin_client, db_session):
    response = await admin_client.get("/api/admin/audit-logs")
    assert response.status_code == 200
    assert "audit.viewed" in await _actions(db_session)


async def test_exclude_meta_hides_audit_viewed(admin_client, db_session):
    await admin_client.get("/api/admin/audit-logs")  # generate a viewed row
    response = await admin_client.get("/api/admin/audit-logs", params={"exclude_meta": "true"})
    assert response.status_code == 200
    actions = {item["action"] for item in response.json()["items"]}
    assert "audit.viewed" not in actions


async def test_filter_by_action_and_category(admin_client, db_session):
    await admin_client.get("/api/admin/audit-logs")

    by_action = await admin_client.get("/api/admin/audit-logs", params={"action": "audit.viewed"})
    assert by_action.status_code == 200
    assert all(item["action"] == "audit.viewed" for item in by_action.json()["items"])
    assert by_action.json()["total"] >= 1

    by_category = await admin_client.get("/api/admin/audit-logs", params={"category": "system"})
    assert by_category.status_code == 200
    assert all(item["category"] == "system" for item in by_category.json()["items"])


async def test_filter_by_result_and_actor_role(admin_client):
    failed = await admin_client.get("/api/admin/audit-logs", params={"result": "failure"})
    assert failed.status_code == 200
    assert all(item["result"] == "failure" for item in failed.json()["items"])

    admins = await admin_client.get("/api/admin/audit-logs", params={"actor_role": "admin"})
    assert admins.status_code == 200
    assert all(item["actor_role"] == "admin" for item in admins.json()["items"])


async def test_search_matches_description_and_actor(admin_client):
    await admin_client.get("/api/admin/audit-logs")
    response = await admin_client.get("/api/admin/audit-logs", params={"q": "audit log"})
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_sort_and_pagination(admin_client):
    first = await admin_client.get("/api/admin/audit-logs", params={"sort": "created_at", "order": "desc"})
    assert first.status_code == 200
    body = first.json()
    assert body["page"] == 1
    assert len(body["items"]) <= body["page_size"]

    second = await admin_client.get(
        "/api/admin/audit-logs",
        params={"sort": "created_at", "order": "desc", "page": 2, "page_size": 1},
    )
    assert second.status_code == 200
    assert second.json()["page"] == 2

    bad_sort = await admin_client.get("/api/admin/audit-logs", params={"sort": "drop table"})
    assert bad_sort.status_code == 422
    bad_order = await admin_client.get("/api/admin/audit-logs", params={"order": "sideways"})
    assert bad_order.status_code == 422


# ---------------------------------------------------------------------------
# Instrumentation coverage
# ---------------------------------------------------------------------------


async def test_login_is_audited(client, create_user, db_session):
    user = await create_user(email="login-audit@example.com")
    response = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "correct horse battery staple"},
    )
    assert response.status_code == 200
    assert "auth.login" in await _actions(db_session)


async def test_failed_login_stores_attempted_email_not_password(client, db_session):
    response = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "sup3r-secret"},
    )
    assert response.status_code == 401

    rows = await _audit_rows(db_session)
    failed = [r for r in rows if r.action == "auth.login_failed"]
    assert failed
    row = failed[-1]
    assert row.details["attempted_email"] == "nobody@example.com"
    assert row.result == "failure"
    assert "sup3r-secret" not in (row.details or {}).__str__()
    assert "sup3r-secret" not in (row.description or "")


async def test_metadata_update_is_audited_with_diff(client, make_book_with_pages, db_session):
    book = await make_book_with_pages(selected_pages=[1])
    book_id = book["id"]

    response = await client.put(
        f"/api/books/{book_id}/metadata",
        json={"fields": {"title": "A New Title", "author": "Someone"}},
    )
    assert response.status_code == 200

    rows = [r for r in await _audit_rows(db_session) if r.action == "metadata.updated"]
    assert rows
    row = rows[-1]
    assert row.resource_type == "book"
    assert row.resource_id == book_id
    assert row.after == {"title": "A New Title", "author": "Someone"}
    assert row.details["changed_field_count"] == 2


async def test_review_completion_is_audited(client, make_book_with_pages, db_session):
    from app.models.metadata import BookMetadata
    from app.services.stage_manager import StageManager

    book = await make_book_with_pages(selected_pages=[1])
    book_id = uuid.UUID(book["id"])
    db_session.add(BookMetadata(book_id=book_id, fields={"title": "T"}))
    # Walk the pipeline to awaiting_review so the review can complete.
    for stage in ("ocr", "llm_extraction"):
        await StageManager.initiate_stage(db_session, book_id, stage)
        await StageManager.start_stage(db_session, book_id, stage)
        await StageManager.complete_stage(db_session, book_id, stage)
    await db_session.commit()

    response = await client.post(f"/api/books/{book_id}/review/complete")
    assert response.status_code == 200
    assert "metadata.review_completed" in await _actions(db_session)


async def test_ocr_correction_is_audited(client, make_book_with_pages, db_session):
    from app.models.ocr_result import OcrResult
    from app.models.page import Page

    book = await make_book_with_pages(selected_pages=[1])
    book_id = uuid.UUID(book["id"])
    page = (await db_session.execute(select(Page).where(Page.book_id == book_id))).scalars().first()
    assert page is not None
    db_session.add(OcrResult(page_id=page.id, raw_text="raw", corrected_text="old"))
    await db_session.commit()

    response = await client.put(f"/api/pages/{page.id}/ocr", json={"corrected_text": "brand new"})
    assert response.status_code == 200

    rows = [r for r in await _audit_rows(db_session) if r.action == "ocr.correction_saved"]
    assert rows
    row = rows[-1]
    assert row.before == {"corrected_text": "old"}
    assert row.after == {"corrected_text": "brand new"}


async def test_book_export_is_audited(client, make_book_with_pages, db_session):
    from app.models.metadata import BookMetadata

    book = await make_book_with_pages(selected_pages=[1])
    book_id = uuid.UUID(book["id"])
    db_session.add(BookMetadata(book_id=book_id, fields={"title": "Export Me"}))
    await db_session.commit()

    response = await client.get(f"/api/books/{book_id}/export")
    assert response.status_code == 200

    rows = [r for r in await _audit_rows(db_session) if r.action == "export.metadata"]
    assert rows
    assert rows[-1].resource_id == str(book_id)
    assert rows[-1].details["row_count"] == 1


async def test_profile_update_is_audited(client):
    response = await client.patch("/api/auth/me", json={"display_name": "Renamed User"})
    assert response.status_code == 200


async def test_admin_user_approval_is_audited(admin_client, create_user, db_session):
    from app.models.user import AccountStatus

    pending = await create_user(
        email="pending-audit@example.com",
        account_status=AccountStatus.PENDING,
    )
    response = await admin_client.post(f"/api/admin/users/{pending.id}/approve")
    assert response.status_code == 200
    assert "user.approved" in await _actions(db_session)


async def test_preprocessing_update_is_audited(client, make_book_with_pages, db_session):
    from app.models.page import Page

    book = await make_book_with_pages(selected_pages=[1])
    book_id = uuid.UUID(book["id"])
    page = (await db_session.execute(select(Page).where(Page.book_id == book_id))).scalars().first()
    assert page is not None

    response = await client.put(
        f"/api/pages/{page.id}/preprocessing",
        json={"grayscale": False, "brightness": 10},
    )
    assert response.status_code == 200
    assert "preprocessing.updated" in await _actions(db_session)


async def test_page_selection_audit_carries_real_job_id(client, make_book_with_pages, db_session):
    book = await make_book_with_pages(selected_pages=[1, 2])
    book_id = book["id"]

    response = await client.post(
        f"/api/books/{book_id}/pages",
        json={"selected_pages": [1, 2]},
    )
    assert response.status_code == 200

    rows = [r for r in await _audit_rows(db_session) if r.action == "pages.selected"]
    assert rows
    job_id = rows[-1].details["job_id"]
    assert job_id != "None"
    uuid.UUID(job_id)  # must parse as a real UUID


async def test_language_noop_is_not_audited(client, make_book_with_pages, db_session):
    book = await make_book_with_pages(selected_pages=[1])
    book_id = book["id"]

    response = await client.patch(
        f"/api/books/{book_id}/language",
        json={"language": book["language"]},
    )
    assert response.status_code == 200
    assert "book.language_changed" not in await _actions(db_session)

    response = await client.patch(
        f"/api/books/{book_id}/language",
        json={"language": "hin"},
    )
    assert response.status_code == 200
    assert "book.language_changed" in await _actions(db_session)


async def test_rejected_retry_is_not_audited_as_success(client, make_book_with_pages, db_session):
    from app.models.book import Book, BookStatus

    book = await make_book_with_pages(selected_pages=[1])
    book_id = uuid.UUID(book["id"])

    # OCR-complete book with pages but no OCR text: run_extraction rejects
    # with 400 "No OCR text", so the retry never started.
    row = await db_session.get(Book, book_id)
    row.status = BookStatus.OCR_COMPLETE
    await db_session.commit()

    response = await client.post(f"/api/books/{book_id}/retry-extraction", json={})
    assert response.status_code == 400

    actions = await _actions(db_session)
    assert "extraction.retried" not in actions
