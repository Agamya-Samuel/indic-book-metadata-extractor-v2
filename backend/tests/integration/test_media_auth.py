"""Signed media URLs survive access-token expiry and stay resource-scoped."""

from __future__ import annotations

import uuid
from datetime import timedelta

from app.core import media_tokens


class TestSignedMedia:
    async def test_thumbnail_requires_a_session_or_token(self, client, make_book_with_pages, anon_client):
        book = await make_book_with_pages([1])
        response = await anon_client.get(f"/api/books/{book['id']}/pages/1/thumbnail")
        assert response.status_code == 401

    async def test_thumbnail_token_works_without_cookies(self, client, make_book_with_pages, anon_client):
        book = await make_book_with_pages([1])
        detail = await client.get(f"/api/books/{book['id']}")
        assert detail.status_code == 200
        token = detail.json()["thumbnail_token"]

        response = await anon_client.get(f"/api/books/{book['id']}/pages/1/thumbnail?token={token}")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/")

    async def test_thumbnail_token_is_book_scoped(self, client, make_book_with_pages, anon_client):
        first = await make_book_with_pages([1])
        second = await make_book_with_pages([1])
        detail = await client.get(f"/api/books/{first['id']}")
        token = detail.json()["thumbnail_token"]

        response = await anon_client.get(f"/api/books/{second['id']}/pages/1/thumbnail?token={token}")
        assert response.status_code == 401

    async def test_page_image_url_from_the_api_works_without_cookies(self, client, make_book_with_pages, anon_client):
        book = await make_book_with_pages([1])
        pages = await client.get(f"/api/books/{book['id']}/pages")
        image_url = pages.json()["items"][0]["image_url"]
        assert "token=" in image_url

        response = await anon_client.get(image_url)
        assert response.status_code == 200

    async def test_page_token_does_not_open_another_page(self, client, make_book_with_pages, anon_client):
        book = await make_book_with_pages([1, 2])
        pages = (await client.get(f"/api/books/{book['id']}/pages")).json()["items"]
        first_url = pages[0]["image_url"]
        second_id = pages[1]["id"]
        token = first_url.split("token=", 1)[1]

        response = await anon_client.get(f"/api/pages/{second_id}/image?token={token}")
        assert response.status_code == 401

    async def test_access_token_is_not_a_media_token(self, anon_client):
        response = await anon_client.get(f"/api/pages/{uuid.uuid4()}/image?token=not-a-media-token")
        assert response.status_code == 401


class TestMediaTokenExpiry:
    def test_expired_token_is_rejected(self, monkeypatch):
        monkeypatch.setattr(media_tokens, "MEDIA_TOKEN_TTL", timedelta(seconds=-1))
        token = media_tokens.issue_media_token("page", "abc")

        assert media_tokens.verify_media_token(token, "page", "abc") is False

    def test_valid_token_is_accepted(self):
        token = media_tokens.issue_media_token("page", "abc")

        assert media_tokens.verify_media_token(token, "page", "abc") is True
        assert media_tokens.verify_media_token(token, "page", "other") is False
        assert media_tokens.verify_media_token(token, "thumbnail", "abc") is False
