"""Bulk CSV import: admin-only, UTF-8, and guarded against bad input."""

from __future__ import annotations

import io


def _csv(body: bytes, name: str = "books.csv"):
    return {"file": (name, io.BytesIO(body), "text/csv")}


class TestBulkImport:
    async def test_requires_admin(self, client):
        response = await client.post("/api/bulk/import", files=_csv(b"book_id\n"))
        assert response.status_code == 403

    async def test_rejects_non_utf8(self, admin_client):
        response = await admin_client.post("/api/bulk/import", files=_csv(b"book_id\n\xff\xfe\n"))
        assert response.status_code == 400
        assert "UTF-8" in response.json()["detail"]

    async def test_requires_book_id_column(self, admin_client):
        response = await admin_client.post("/api/bulk/import", files=_csv(b"title\nSome book\n"))
        assert response.status_code == 400

    async def test_merges_metadata(self, admin_client, make_book):
        book = await make_book()
        body = f"book_id,title,author\n{book['id']},Imported title,Nobody\n".encode()

        response = await admin_client.post("/api/bulk/import", files=_csv(body))

        assert response.status_code == 200
        data = response.json()
        assert data["books_updated"] == 1
        assert data["fields_changed"] >= 1

        metadata = await admin_client.get(f"/api/books/{book['id']}/metadata")
        fields = metadata.json()["fields"]
        assert fields["author"] == "Nobody"

        detail = await admin_client.get(f"/api/books/{book['id']}")
        assert detail.json()["title"] == "Imported title"
