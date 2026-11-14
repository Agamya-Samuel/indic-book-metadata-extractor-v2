"""Public liveness endpoint and the security headers on API responses."""

from __future__ import annotations


async def test_liveness_is_public_and_uncached(anon_client) -> None:
    response = await anon_client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_api_responses_carry_security_headers(client) -> None:
    response = await client.get("/api/notifications/unread-count")

    assert response.status_code == 200
    assert response.headers["strict-transport-security"].startswith("max-age=")
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
