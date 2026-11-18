"""End-to-end demonstration of the export pipeline against a deployed stack.

Runs the whole chain with real book metadata and prints evidence for each stage:

    extraction status -> single export -> bulk export -> OpenRefine import
    -> QuickStatements batch -> (optional) Wikibase publish

Configure with:

    E2E_BASE_URL        app origin (default https://indic-book-metadata-extractor.nexio.uk)
    E2E_OPENREFINE_URL  OpenRefine origin
    E2E_EMAIL / E2E_PASSWORD  admin account
    E2E_BOOK_ID         book for the single-book export

The publish stage is a dry run unless ``--publish`` is given. It requires the
backend image that contains ``POST /api/wikibase/publish``.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys

import httpx

BASE = os.environ.get("E2E_BASE_URL", "https://indic-book-metadata-extractor.nexio.uk")
OPENREFINE = os.environ.get("E2E_OPENREFINE_URL", "https://indic-book-metadata-extractor-openrefine.nexio.uk")
EMAIL = os.environ.get("E2E_EMAIL", "qa-admin@agamya.us.kg")
PASSWORD = os.environ.get("E2E_PASSWORD", "")
BOOK_ID = os.environ.get("E2E_BOOK_ID", "ee5b0f2d-8ae4-4c49-91ed-251864f5d22a")


def header(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true", help="actually write to Wikibase")
    args = parser.parse_args()

    if not PASSWORD:
        print("E2E_PASSWORD is required", file=sys.stderr)
        return 2

    with httpx.Client(base_url=BASE, timeout=180, follow_redirects=True) as app:
        status = app.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code
        print(f"login: {status}")
        if status != 200:
            return 1
        csrf = app.cookies.get("csrf_token")
        headers = {"X-CSRF-Token": csrf}

        header("1. Extraction status")
        books = app.get("/api/dashboard/books", headers=headers)
        if books.status_code == 200:
            payload = books.json()
            items = payload.get("items", [])
            counts: dict[str, int] = {}
            for book in items:
                counts[book.get("status", "?")] = counts.get(book.get("status", "?"), 0) + 1
            print(f"books: {len(items)}  {counts}")
            for book in items[:8]:
                print(f"  {book.get('language'):4} {book.get('status'):16} {(book.get('title') or '')[:48]}")
        else:
            print(f"  /api/books -> {books.status_code}")

        header("2. Single-book export (OpenRefine CSV)")
        single = app.post("/api/export", json={"format": "openrefine", "book_ids": [BOOK_ID]}, headers=headers)
        print(f"status {single.status_code}, {len(single.content)} bytes")
        rows = list(csv.reader(io.StringIO(single.content.decode("utf-8"))))
        print(f"columns {len(rows[0])}, first data row title: {rows[1][rows[0].index('title')]}")

        header("3. Bulk export (all books, OpenRefine CSV)")
        bulk = app.post("/api/bulk/export?format=openrefine", headers=headers)
        print(f"status {bulk.status_code}, {len(bulk.content)} bytes")
        open("/tmp/e2e_bulk.csv", "wb").write(bulk.content)
        rows = list(csv.reader(io.StringIO(bulk.content.decode("utf-8"))))
        print(f"books {len(rows) - 1}, columns {len(rows[0])}")
        for row in rows[1:]:
            rec = dict(zip(rows[0], row))
            print(f"  {rec.get('book_language'):4} {(rec.get('title') or '')[:45]}")

        header("4. Automatic transfer to OpenRefine")
        with httpx.Client(base_url=OPENREFINE, timeout=300, follow_redirects=True) as refine:
            token = refine.get("/command/core/get-csrf-token").json()["token"]
            with open("/tmp/e2e_bulk.csv", "rb") as handle:
                created = refine.post(
                    "/command/core/create-project-from-upload",
                    params={"csrf_token": token},
                    files={"project-file": ("e2e_bulk.csv", handle, "text/csv")},
                    data={"project-name": "E2E bulk", "csrf_token": token},
                )
            project_id = str(created.url).split("project=")[-1]
            models = refine.get("/command/core/get-models", params={"project": project_id}).json()
            columns = models["columnModel"]["columns"]
            data = refine.get("/command/core/get-rows", params={"project": project_id, "start": 0, "limit": 100}).json()
            print(f"project {project_id}: {len(columns)} columns, {data.get('totalRows')} rows")

        header("5. QuickStatements batch")
        qs = app.post("/api/bulk/export-wikibase", headers=headers)
        print(f"status {qs.status_code}, {len(qs.content)} bytes")
        open("/tmp/e2e_quickstatements.tsv", "wb").write(qs.content)
        lines = qs.content.decode("utf-8").splitlines()
        creates = sum(1 for line in lines if line.strip() == "CREATE")
        print(f"{len(lines)} lines, {creates} CREATE statements")
        for line in lines[:4]:
            print(f"  {line[:100]}")

        header("6. Publish to Wikibase" + ("" if args.publish else " (dry run)"))
        book_ids = [row[0] for row in rows[1:] if row and row[0]] if 'rows' in dir() else None
        published = app.post(
            "/api/wikibase/publish",
            json={"dry_run": not args.publish, "book_ids": book_ids},
            headers=headers,
        )
        print(f"status {published.status_code}")
        if published.status_code == 200:
            body = published.json()
            print(f"books {len(body.get('reports', []))}, with item {body.get('published')}")
            for report in body.get("reports", [])[:4]:
                print(f"  {report['language']:4} {report['item_id'] or '-':6} {(report['title'] or '')[:40]} warnings={len(report['warnings'])}")
        else:
            print(f"  {published.text[:160]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())