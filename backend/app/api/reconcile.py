"""Public Reconciliation Service API and Wikibase manifest for OpenRefine.

OpenRefine's Wikibase extension requires two things to edit a self-hosted
Wikibase:

1. a **manifest** (v2) describing the instance, and
2. a **reconciliation service** for each editable entity type.

Both are served here so no extra container (SPARQL endpoint, Redis, the
upstream ``openrefine-wikibase`` service) is needed. The service is read-only:
it wraps MediaWiki's ``wbsearchentities`` and never writes.

Endpoints (Reconciliation Service API 1.0)::

    GET  /api/reconcile/                    service descriptor
    GET  /api/reconcile/{lang}/api          query / batch search
    POST /api/reconcile/{lang}/api          batch reconcile, extend
    GET  /api/reconcile/{lang}/view         entity page in the Wikibase
    GET  /api/reconcile/{lang}/preview      minimal HTML preview
    GET  /api/reconcile/manifest.json       Wikibase manifest v2
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from app.core.config import settings
from app.services.export_service import load_property_mapping

logger = logging.getLogger(__name__)

router = APIRouter()

# OpenRefine runs on its own origin, so the browser needs these on every
# response. The service is public and read-only; `*` is safe here.
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

_UPS_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def _json(payload: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status_code, headers=CORS_HEADERS)


def _api_url() -> str:
    return settings.wikibase_api_url


async def _wb_request(params: dict[str, Any]) -> dict[str, Any]:
    """Call the Wikibase API, returning the decoded JSON or raising."""
    async with httpx.AsyncClient(timeout=_UPS_TIMEOUT) as client:
        response = await client.get(_api_url(), params={"format": "json", **params})
        response.raise_for_status()
        return response.json()


def _reconcile_result(entity: dict[str, Any], *, matched: bool) -> dict[str, Any]:
    return {
        "id": entity["id"],
        "name": entity.get("label") or entity["id"],
        "description": entity.get("description") or "",
        "type": [{"id": "/item", "name": "Item"}],
        "match": matched,
    }


@router.get("/")
async def service_descriptor(request: Request) -> JSONResponse:
    """Reconciliation Service API 1.0 service descriptor."""
    base = str(request.base_url).rstrip("/") + "/api/reconcile"
    return _json(
        {
            "versions": ["1.0"],
            "name": "IndicBooks Wikibase reconciliation",
            "view": {"url": base + "/{{lang}}/view?id={{id}}"},
            "preview": {"url": base + "/{{lang}}/preview?id={{id}}"},
        }
    )


@router.get("/manifest.json")
async def wikibase_manifest(request: Request) -> JSONResponse:
    """Wikibase manifest (v2) consumed by OpenRefine's Wikibase extension."""
    public = settings.wikibase_public_url.rstrip("/")
    if not public:
        return _json({"error": "WIKIBASE_PUBLIC_URL is not configured"}, status_code=500)

    mapping = load_property_mapping()
    instance_of = mapping.get("P31", "P31")
    # The application mounts every router under /api.
    base = str(request.base_url).rstrip("/") + "/api/reconcile"

    return _json(
        {
            "version": "2.0",
            "mediawiki": {
                "name": "IndicBooks",
                "root": f"{public}/wiki/",
                "main_page": f"{public}/wiki/Main_Page",
                "api": f"{public}/w/api.php",
            },
            "wikibase": {
                "site_iri": f"{public}/entity/",
                "maxlag": 5,
                "max_edits_per_minute": 60,
                "tag": "openrefine-${version}",
                "properties": {"instance_of": instance_of},
            },
            "oauth": {
                "registration_page": f"{public}/wiki/Special:OAuthConsumerRegistration",
            },
            "entity_types": {
                "item": {
                    "site_iri": f"{public}/entity/",
                    "reconciliation_endpoint": f"{base}/{{lang}}/api",
                    "mediawiki_api": f"{public}/w/api.php",
                }
            },
        }
    )


@router.get("/{lang}/api")
async def reconcile_query(
    lang: str,
    query: str = Query(default=""),
    type: str = Query(default="item", alias="type"),
    limit: int = Query(default=50, ge=1, le=100),
) -> JSONResponse:
    """Reconciliation search over Wikibase entities."""
    if not query:
        return _json({"result": []})

    try:
        payload = await _wb_request(
            {
                "action": "wbsearchentities",
                "search": query,
                "language": lang,
                "uselang": lang,
                "type": type,
                "limit": limit,
            }
        )
    except httpx.HTTPError as exc:
        logger.warning("reconciliation search failed: %s", exc)
        return _json({"error": "wikibase unreachable", "detail": str(exc)}, status_code=502)

    results = [_reconcile_result(item, matched=True) for item in payload.get("search", [])]
    return _json({"result": results})


@router.options("/{lang}/api")
async def reconcile_options(lang: str) -> Response:
    """CORS preflight for the JSON POST endpoint."""
    return Response(status_code=204, headers=CORS_HEADERS)


@router.post("/{lang}/api")
async def reconcile_batch(lang: str, request: Request) -> JSONResponse:
    """Batch reconcile and ``extend`` (Reconciliation Service API 1.0)."""
    try:
        body = await request.json()
    except Exception:
        return _json({"error": "invalid JSON body"}, status_code=400)

    if "extend" in body:
        return _json({"type": [{"id": "/item", "name": "Item"}], "property": []})

    queries = body.get("queries") or []
    results: dict[str, Any] = {}
    for entry in queries:
        qid = entry.get("query") or ""
        try:
            payload = await _wb_request(
                {
                    "action": "wbsearchentities",
                    "search": qid,
                    "language": lang,
                    "uselang": lang,
                    "type": entry.get("type", "item"),
                    "limit": int(entry.get("limit", 50)),
                }
            )
            results[entry.get("qid", qid)] = {
                "result": [_reconcile_result(item, matched=True) for item in payload.get("search", [])]
            }
        except httpx.HTTPError as exc:
            results[entry.get("qid", qid)] = {"error": str(exc)}
    return _json({"results": results})


async def _entity(lang: str, entity_id: str) -> dict[str, Any] | None:
    try:
        payload = await _wb_request({"action": "wbgetentities", "ids": entity_id, "props": "labels|descriptions"})
    except httpx.HTTPError:
        return None
    return payload.get("entities", {}).get(entity_id)


@router.get("/{lang}/view")
async def reconcile_view(lang: str, id: str = Query(...)) -> Response:
    """Human-readable entity page (shown in OpenRefine's preview pane)."""
    entity = await _entity(lang, id)
    if not entity:
        return HTMLResponse("<p>Entity not found.</p>", headers=CORS_HEADERS)
    label = entity.get("labels", {}).get(lang, {}).get("value", id)
    description = entity.get("descriptions", {}).get(lang, {}).get("value", "")
    html = f"<p><strong>{label}</strong> — {description}</p>"
    return HTMLResponse(html, headers=CORS_HEADERS)


@router.get("/{lang}/preview")
async def reconcile_preview(lang: str, id: str = Query(...)) -> Response:
    entity = await _entity(lang, id)
    if not entity:
        return HTMLResponse("<p>Entity not found.</p>", headers=CORS_HEADERS)
    label = entity.get("labels", {}).get(lang, {}).get("value", id)
    return HTMLResponse(f"<p>{label}</p>", headers=CORS_HEADERS)
