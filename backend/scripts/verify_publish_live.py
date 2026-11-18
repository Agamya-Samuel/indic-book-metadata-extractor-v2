"""Live verification helper: publish a real metadata fixture to Wikibase.

Run inside the backend image on the compose network::

    python scripts/verify_publish_live.py tests/fixtures/metadata_hindi.json --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import wikibase_publish as wp  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture")
    parser.add_argument("--language", default="hin")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--item-id", default=None, help="Existing item to update")
    args = parser.parse_args()

    fields = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    book = SimpleNamespace(id="verify", language=args.language, wikibase_item_id=args.item_id)

    client = wp.build_client()
    try:
        if not args.dry_run:
            await client.login()
        report = await wp.publish_book(client, book, fields, wp.mapping(), dry_run=args.dry_run)
        print(
            json.dumps(
                {
                    "item_id": report.item_id,
                    "created": report.created,
                    "warnings": report.warnings,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if report.ok or args.dry_run else 1
    finally:
        await client.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
