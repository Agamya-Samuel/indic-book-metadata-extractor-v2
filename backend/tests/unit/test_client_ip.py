"""Client-IP resolution for the rate limiter behind Cloudflare and Traefik."""

from __future__ import annotations

from starlette.requests import Request

from app.main import client_ip


def _request(headers: dict[str, str] | None = None, client=("10.0.0.5", 1234)) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [(name.lower().encode(), value.encode()) for name, value in (headers or {}).items()],
        "client": client,
        "scheme": "https",
        "server": ("testserver", 443),
    }
    return Request(scope)


def test_prefers_cloudflare_header() -> None:
    request = _request({"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "10.9.9.9, 172.16.0.1"})
    assert client_ip(request) == "203.0.113.7"


def test_uses_the_last_forwarded_hop_without_cloudflare() -> None:
    request = _request({"X-Forwarded-For": "1.2.3.4, 198.51.100.23"})
    assert client_ip(request) == "198.51.100.23"


def test_client_supplied_first_hop_cannot_choose_the_bucket() -> None:
    request = _request({"X-Forwarded-For": "203.0.113.99, 198.51.100.23"})
    assert client_ip(request) == "198.51.100.23"


def test_falls_back_to_the_socket_peer() -> None:
    assert client_ip(_request()) == "10.0.0.5"


def test_blank_cloudflare_header_falls_through() -> None:
    request = _request({"CF-Connecting-IP": "   ", "X-Forwarded-For": "198.51.100.23"})
    assert client_ip(request) == "198.51.100.23"
