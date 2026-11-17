"""Export endpoints: formats, ownership scoping, and CSV round-trips."""

from __future__ import annotations

import io
import json

TELUGU_LABEL = "పుస్తకం"
HINDI_AUTHOR = "लेखक"


def _pdf_upload(name: str = "book.pdf"):
    return {"file": (name, None, "application/pdf")}


async def _upload_pdf(client, sample_pdf, name: str = "admin.pdf") -> dict:
    response = await client.post(
        "/api/books/upload",
        files={"file": (name, io.BytesIO(sample_pdf.read_bytes()), "application/pdf")},
        data={"language": "tel"},
    )
    assert response.status_code == 201
    return response.json()


async def _with_metadata(client, book_id: str, fields: dict | None = None) -> None:
    response = await client.put(
        f"/api/books/{book_id}/metadata",
        json={"fields": fields or {"label": TELUGU_LABEL, "author": HINDI_AUTHOR}},
    )
    assert response.status_code == 200


class TestSingleBookExport:
    async def test_requires_authentication(self, anon_client, make_book):
        book = await make_book()
        response = await anon_client.get(f"/api/books/{book['id']}/export")
        assert response.status_code == 401

    async def test_owner_downloads_csv(self, client, make_book):
        book = await make_book(status="complete")
        await _with_metadata(client, book["id"])

        response = await client.get(f"/api/books/{book['id']}/export?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment; filename=\"indic-books_book-" in response.headers["content-disposition"]
        assert response.headers["cache-control"] == "no-store"
        assert response.content.startswith(b"\xef\xbb\xbf")
        text = response.content.decode("utf-8-sig")
        assert TELUGU_LABEL in text
        assert HINDI_AUTHOR in text
        header = text.splitlines()[0].split(",")
        assert header[0] == "book_id"
        assert len(header) == 50

    async def test_book_without_metadata_returns_404(self, client, make_book):
        book = await make_book()
        response = await client.get(f"/api/books/{book['id']}/export")
        assert response.status_code == 404

    async def test_foreign_book_returns_404(self, client, admin_client, sample_pdf, test_storage):
        book = await _upload_pdf(admin_client, sample_pdf)
        await _with_metadata(admin_client, book["id"])

        response = await client.get(f"/api/books/{book['id']}/export")
        assert response.status_code == 404

    async def test_include_details_adds_book_columns(self, client, make_book):
        book = await make_book(status="complete")
        await _with_metadata(client, book["id"])

        response = await client.get(
            f"/api/books/{book['id']}/export?format=csv&include_details=true"
        )
        header = response.content.decode("utf-8-sig").splitlines()[0].split(",")
        assert header[:3] == ["book_id", "book_title", "book_language"]
        assert "source_filename" in header


class TestMultiBookExport:
    async def test_exports_only_selected_books(self, client, make_book):
        first = await make_book(status="complete")
        second = await make_book(status="complete")
        await _with_metadata(client, first["id"])
        await _with_metadata(client, second["id"], {"label": "Second book"})

        response = await client.post(
            "/api/export",
            json={"format": "json", "book_ids": [first["id"]]},
        )

        assert response.status_code == 200
        payload = json.loads(response.content)
        assert len(payload) == 1
        assert payload[0]["book_id"] == first["id"]
        assert payload[0]["metadata"]["label"] == TELUGU_LABEL

    async def test_foreign_book_id_returns_404(self, client, admin_client, sample_pdf, test_storage):
        book = await _upload_pdf(admin_client, sample_pdf)
        await _with_metadata(admin_client, book["id"])

        response = await client.post(
            "/api/export",
            json={"format": "csv", "book_ids": [book["id"]]},
        )
        assert response.status_code == 404

    async def test_admin_exports_all_books(
        self, admin_client, client, make_book, sample_pdf, test_storage
    ):
        regular = await make_book(status="complete")
        await _with_metadata(client, regular["id"])

        admin_book = await _upload_pdf(admin_client, sample_pdf)
        await _with_metadata(admin_client, admin_book["id"], {"label": "Admin book"})

        response = await admin_client.post("/api/export", json={"format": "json"})

        assert response.status_code == 200
        payload = json.loads(response.content)
        ids = {item["book_id"] for item in payload}
        assert ids == {regular["id"], admin_book["id"]}

    async def test_jsonl_and_xlsx_formats(self, client, make_book):
        book = await make_book(status="complete")
        await _with_metadata(client, book["id"])

        jsonl = await client.post("/api/export", json={"format": "jsonl"})
        assert jsonl.status_code == 200
        assert jsonl.headers["content-type"].startswith("application/x-ndjson")
        assert len(jsonl.content.decode().strip().splitlines()) == 1

        xlsx = await client.post("/api/export", json={"format": "xlsx"})
        assert xlsx.status_code == 200
        assert "spreadsheetml" in xlsx.headers["content-type"]
        assert xlsx.content[:2] == b"PK"

    async def test_wikibase_and_openrefine_formats(self, client, make_book):
        book = await make_book(status="complete")
        await _with_metadata(client, book["id"])

        wikibase = await client.post("/api/export", json={"format": "wikibase"})
        assert wikibase.status_code == 200
        item = json.loads(wikibase.content)[0]
        assert item["type"] == "item"
        assert item["claims"]["P31"][0]["mainsnak"]["datavalue"]["value"]["id"] == "Q571"

        openrefine = await client.post("/api/export", json={"format": "openrefine"})
        assert openrefine.status_code == 200
        assert not openrefine.content.startswith(b"\xef\xbb\xbf")
        header = openrefine.content.decode("utf-8").splitlines()[0].split(",")
        assert header[:2] == ["book_id", "book_title"]

    async def test_no_matching_books_returns_404(self, client):
        response = await client.post("/api/export", json={"format": "csv"})
        assert response.status_code == 404

    async def test_rejects_empty_book_ids(self, client):
        response = await client.post("/api/export", json={"format": "csv", "book_ids": []})
        assert response.status_code == 422


class TestBulkExportCompatibility:
    async def test_bulk_export_accepts_new_formats(self, admin_client, client, make_book):
        book = await make_book(status="complete")
        await _with_metadata(client, book["id"])

        response = await admin_client.post("/api/bulk/export?format=json")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        payload = json.loads(response.content)
        assert any(item["book_id"] == book["id"] for item in payload)

    async def test_import_prefixed_headers_and_custom_columns(self, admin_client, make_book):
        book = await make_book()
        body = (
            "book_id,book_title,author,custom:notes\n"
            f"{book['id']},Restored title,కవి,పరిశీలన\n"
        ).encode()

        response = await admin_client.post(
            "/api/bulk/import",
            files={"file": ("books.csv", io.BytesIO(body), "text/csv")},
        )

        assert response.status_code == 200
        detail = await admin_client.get(f"/api/books/{book['id']}")
        assert detail.json()["title"] == "Restored title"

        metadata = (await admin_client.get(f"/api/books/{book['id']}/metadata")).json()
        fields = metadata["fields"]
        assert fields["author"] == "కవి"
        assert fields["custom_fields"] == {"notes": "పరిశీలన"}
        assert "book_title" not in fields
        assert "custom:notes" not in fields
