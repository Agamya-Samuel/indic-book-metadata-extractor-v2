"""Role and ownership enforcement across the API."""

from __future__ import annotations

import uuid

from app.models.book import BookStatus


async def test_admin_endpoints_require_role(anon_client, client, admin_client):
    assert (await anon_client.get("/api/admin/stats")).status_code == 401
    assert (await client.get("/api/admin/stats")).status_code == 403
    assert (await admin_client.get("/api/admin/stats")).status_code == 200


async def test_bulk_endpoints_are_admin_only(anon_client, client, admin_client):
    assert (await anon_client.get("/api/bulk/stats")).status_code in (401, 403)
    assert (await client.get("/api/bulk/stats")).status_code == 403
    assert (await admin_client.get("/api/bulk/stats")).status_code == 200


async def test_other_user_cannot_reach_private_book(
    make_book_with_pages, auth_client, create_user, db_session
):
    book = await make_book_with_pages(selected_pages=[1, 2])
    book_id = book["id"]

    other = await create_user(email="other@example.com")
    other_client = await auth_client(other)

    paths = [
        f"/api/books/{book_id}",
        f"/api/books/{book_id}/pages",
        f"/api/books/{book_id}/metadata",
        f"/api/books/{book_id}/jobs",
        f"/api/books/{book_id}/pages/1/thumbnail",
        f"/api/books/{book_id}/detail",
        f"/api/sse/books/{book_id}/events",
    ]
    for path in paths:
        response = await other_client.get(path)
        assert response.status_code == 404, path

    # Page-level endpoints are hidden too.
    from sqlalchemy import select

    from app.models.page import Page

    result = await db_session.execute(
        select(Page).where(Page.book_id == uuid.UUID(book_id))
    )
    page = result.scalars().first()
    assert page is not None
    assert (await other_client.get(f"/api/pages/{page.id}/ocr")).status_code == 404
    assert (await other_client.get(f"/api/pages/{page.id}/image")).status_code == 404


async def test_owner_and_admin_reach_private_book(
    client, admin_client, make_book
):
    book = await make_book()
    assert (await client.get(f"/api/books/{book['id']}")).status_code == 200
    assert (await admin_client.get(f"/api/books/{book['id']}")).status_code == 200


async def test_completed_book_is_still_owner_only(
    make_book_with_pages, auth_client, create_user, db_session
):
    book = await make_book_with_pages(selected_pages=[1, 2])
    # Even a "complete" book is no longer a public catalog entry.
    from app.models.book import Book

    row = await db_session.get(Book, uuid.UUID(book["id"]))
    row.status = BookStatus.AWAITING_REVIEW
    await db_session.commit()

    other = await create_user(email="reader@example.com")
    other_client = await auth_client(other)

    assert (
        await other_client.get(f"/api/books/{book['id']}/detail")
    ).status_code == 404
    assert (await other_client.get(f"/api/books/{book['id']}")).status_code == 404


async def test_library_listing_is_admin_only(anon_client, client, admin_client, make_book):
    # Anonymous callers are rejected outright.
    assert (await anon_client.get("/api/admin/books")).status_code == 401
    # Regular approved users cannot browse the cross-user library.
    assert (await client.get("/api/admin/books")).status_code == 403

    await make_book()
    await make_book(status=BookStatus.AWAITING_REVIEW)

    admin_response = await admin_client.get("/api/admin/books")
    assert admin_response.status_code == 200
    assert admin_response.json()["total"] == 2


async def test_admin_user_crud_and_safety_rules(
    admin_client, create_user, regular_user
):
    listed = await admin_client.get("/api/admin/users")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 2

    created = await admin_client.post(
        "/api/admin/users",
        json={
            "email": "created@example.com",
            "display_name": "Created User",
            "password": "a temporary password",
            "role": "user",
        },
    )
    assert created.status_code == 201
    user_id = created.json()["id"]
    assert created.json()["email_verified_at"] is not None

    detail = await admin_client.get(f"/api/admin/users/{user_id}")
    assert detail.status_code == 200
    assert detail.json()["book_count"] == 0

    updated = await admin_client.patch(
        f"/api/admin/users/{user_id}",
        json={"display_name": "Renamed", "role": "admin"},
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "admin"

    reset = await admin_client.post(
        f"/api/admin/users/{user_id}/reset-password",
        json={"new_password": "another temporary password"},
    )
    assert reset.status_code == 204

    deleted = await admin_client.delete(f"/api/admin/users/{user_id}")
    assert deleted.status_code == 204


async def test_last_admin_protection(admin_client, admin_user):
    demote = await admin_client.patch(
        f"/api/admin/users/{admin_user.id}", json={"role": "user"}
    )
    assert demote.status_code == 400

    deactivate = await admin_client.patch(
        f"/api/admin/users/{admin_user.id}", json={"is_active": False}
    )
    assert deactivate.status_code == 400

    delete = await admin_client.delete(f"/api/admin/users/{admin_user.id}")
    assert delete.status_code == 400


async def test_admin_cannot_demote_self_when_other_admin_exists(
    admin_client, admin_user, create_user
):
    await create_user(email="second-admin@example.com", role="admin")
    demote = await admin_client.patch(
        f"/api/admin/users/{admin_user.id}", json={"role": "user"}
    )
    assert demote.status_code == 400


async def test_user_deletion_blocked_while_owning_books(
    admin_client, make_book, regular_user
):
    await make_book()
    response = await admin_client.delete(f"/api/admin/users/{regular_user.id}")
    assert response.status_code == 409
    assert "owns" in response.json()["detail"].lower()
