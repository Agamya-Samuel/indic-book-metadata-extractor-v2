from __future__ import annotations

import uuid

import pytest

from app.models.book import Book
from app.models.job import Job, JobStatus, JobType
from app.models.llm_run import LlmRun
from app.models.metadata import BookMetadata
from app.models.page import Page


class TestGetMetadata:
    async def test_get_metadata_empty(self, client, make_book):
        book = await make_book()
        response = await client.get(f"/api/books/{book['id']}/metadata")
        assert response.status_code == 200
        data = response.json()
        assert data["fields"] == {}

    async def test_get_metadata_after_set(self, client, make_book, db_session):
        book = await make_book()
        book_id = uuid.UUID(book["id"])

        meta = BookMetadata(
            book_id=book_id,
            fields={"title": "Test Title", "author": "Test Author"},
        )
        db_session.add(meta)
        await db_session.commit()

        response = await client.get(f"/api/books/{book['id']}/metadata")
        assert response.status_code == 200
        data = response.json()
        assert data["fields"]["title"] == "Test Title"
        assert data["fields"]["author"] == "Test Author"


class TestUpdateMetadata:
    async def test_update_metadata_creates(self, client, make_book):
        book = await make_book()
        response = await client.put(
            f"/api/books/{book['id']}/metadata",
            json={"fields": {"title": "New Title", "publisher": "Test Pub"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["fields"]["title"] == "New Title"
        assert data["fields"]["publisher"] == "Test Pub"

    async def test_update_metadata_merges(self, client, make_book, db_session):
        book = await make_book()
        book_id = uuid.UUID(book["id"])

        meta = BookMetadata(
            book_id=book_id,
            fields={"title": "Original", "author": "Author"},
        )
        db_session.add(meta)
        await db_session.commit()

        response = await client.put(
            f"/api/books/{book['id']}/metadata",
            json={"fields": {"title": "Updated", "genre": "Fiction"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["fields"]["title"] == "Updated"
        assert data["fields"]["author"] == "Author"
        assert data["fields"]["genre"] == "Fiction"


class TestFieldDefinitions:
    async def test_get_field_definitions(self, client, make_book):
        book = await make_book()
        response = await client.get(f"/api/books/{book['id']}/metadata/fields")
        assert response.status_code == 200
        fields = response.json()
        assert len(fields) > 40
        field_names = [f["field_name"] for f in fields]
        assert "title" in field_names
        assert "author" in field_names
        assert "custom_fields" not in field_names


class TestLlmRuns:
    async def test_get_llm_runs_empty(self, client, make_book):
        book = await make_book()
        response = await client.get(f"/api/books/{book['id']}/llm-runs")
        assert response.status_code == 200
        assert response.json() == []

    async def test_get_llm_runs_with_data(self, client, make_book, db_session):
        book = await make_book()
        book_id = uuid.UUID(book["id"])

        job = Job(
            book_id=book_id,
            job_type=JobType.LLM,
            status=JobStatus.COMPLETED,
            progress=100.0,
        )
        db_session.add(job)
        await db_session.flush()

        run = LlmRun(
            job_id=job.id,
            model="airavata",
            prompt_template="test prompt",
            raw_response='{"title": "Test"}',
            parsed_fields={"title": "Test"},
        )
        db_session.add(run)
        await db_session.commit()

        response = await client.get(f"/api/books/{book['id']}/llm-runs")
        assert response.status_code == 200
        runs = response.json()
        assert len(runs) == 1
        assert runs[0]["model"] == "airavata"
