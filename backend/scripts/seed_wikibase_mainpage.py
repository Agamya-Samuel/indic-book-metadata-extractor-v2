"""Apply docker/wikibase/Main_Page.wikitext to the Wikibase.

The Main Page is wiki content, not code, so it lives in the repository as
wikitext and is applied with this script after a fresh install.

    WIKIBASE_API_URL=http://wikibase/w/api.php \
    WIKIBASE_BOT_USERNAME=admin \
    WIKIBASE_BOT_PASSWORD=... \
    python scripts/seed_wikibase_mainpage.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PAGE = ROOT / "docker" / "wikibase" / "Main_Page.wikitext"


def main() -> int:
    api = os.environ.get("WIKIBASE_API_URL", "http://wikibase/w/api.php")
    username = os.environ.get("WIKIBASE_BOT_USERNAME")
    password = os.environ.get("WIKIBASE_BOT_PASSWORD")
    page_path = Path(os.environ.get("WIKIBASE_MAINPAGE", str(DEFAULT_PAGE)))
    title = os.environ.get("WIKIBASE_MAINPAGE_TITLE", "Main Page")

    if not username or not password:
        print("WIKIBASE_BOT_USERNAME and WIKIBASE_BOT_PASSWORD are required", file=sys.stderr)
        return 2
    if not page_path.exists():
        print(f"wikitext not found: {page_path}", file=sys.stderr)
        return 2

    text = page_path.read_text(encoding="utf-8")

    with httpx.Client(timeout=30) as client:
        login_token = client.get(
            api, params={"action": "query", "meta": "tokens", "type": "login", "format": "json"}
        ).json()["query"]["tokens"]["logintoken"]
        result = client.post(
            api,
            data={
                "action": "login",
                "lgname": username,
                "lgpassword": password,
                "lgtoken": login_token,
                "format": "json",
            },
        )
        if result.json().get("login", {}).get("result") != "Success":
            print(f"login failed: {result.text[:200]}", file=sys.stderr)
            return 1

        csrf = client.get(
            api, params={"action": "query", "meta": "tokens", "format": "json"}
        ).json()["query"]["tokens"]["csrftoken"]

        response = client.post(
            api,
            data={
                "action": "edit",
                "title": title,
                "text": text,
                "summary": "Seed the IndicBooks Main Page from the repository",
                "bot": 1,
                "token": csrf,
                "format": "json",
            },
        )
        body = response.json()
        outcome = body.get("edit", {}).get("result") or body.get("error", {}).get("info")
        print(f"{title}: {outcome}")
        return 0 if outcome == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())