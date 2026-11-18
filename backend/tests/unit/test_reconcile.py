"""Tests for the public reconciliation service and Wikibase manifest."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from app.api import reconcile as rc
from app.core.config import settings


def _run(coro):
    return asyncio.run(coro)


def _body(response):
    return json.loads(response.body)


def _request(base: str = "https://app.example.test/"):
    return SimpleNamespace(base_url=base)


def test_reconciliation_query_maps_wbsearchentities(monkeypatch):
    async def fake_request(params):
        assert params["action"] == "wbsearchentities"
        assert params["search"] == "book"
        assert params["language"] == "en"
        return {
            "search": [
                {"id": "Q1", "label": "book", "description": "written work"},
                {"id": "Q2", "label": "booklet", "description": ""},
            ]
        }

    monkeypatch.setattr(rc, "_wb_request", fake_request)
    response = _run(rc.reconcile_query(lang="en", query="book", type="item", limit=10))
    body = _body(response)
    assert body["result"][0] == {
        "id": "Q1",
        "name": "book",
        "description": "written work",
        "type": [{"id": "/item", "name": "Item"}],
        "match": True,
    }
    assert len(body["result"]) == 2


def test_reconciliation_query_empty_returns_empty_result():
    response = _run(rc.reconcile_query(lang="en", query="", type="item", limit=10))
    assert _body(response) == {"result": []}


def test_reconciliation_downstream_error_is_502(monkeypatch):
    import httpx

    async def boom(params):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(rc, "_wb_request", boom)
    response = _run(rc.reconcile_query(lang="en", query="x", type="item", limit=10))
    assert response.status_code == 502
    assert _body(response)["error"] == "wikibase unreachable"


def test_manifest_is_v2_and_points_at_reconciliation(monkeypatch):
    monkeypatch.setattr(settings, "wikibase_public_url", "https://wb.example.test")
    monkeypatch.setattr(rc, "load_property_mapping", lambda: {"P31": "P2"})

    response = _run(rc.wikibase_manifest(_request()))
    manifest = _body(response)

    assert manifest["version"] == "2.0"
    assert manifest["mediawiki"]["api"] == "https://wb.example.test/w/api.php"
    assert manifest["wikibase"]["properties"]["instance_of"] == "P2"
    item = manifest["entity_types"]["item"]
    assert item["reconciliation_endpoint"] == "https://app.example.test/api/reconcile/{lang}/api"
    assert item["mediawiki_api"] == "https://wb.example.test/w/api.php"


def test_manifest_requires_public_url(monkeypatch):
    monkeypatch.setattr(settings, "wikibase_public_url", "")
    response = _run(rc.wikibase_manifest(_request()))
    assert response.status_code == 500


def test_cors_headers_present_on_json():
    response = rc._json({"ok": True})
    assert response.headers["access-control-allow-origin"] == "*"


def test_options_preflight_returns_204():
    response = _run(rc.reconcile_options("en"))
    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "*"
