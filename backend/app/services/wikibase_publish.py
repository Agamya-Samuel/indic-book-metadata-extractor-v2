"""Publish reviewed metadata to the local Wikibase.

The automated path used by ``POST /api/export/wikibase/publish`` and by the
end-to-end tests. It is deliberately idempotent:

* a book that already has ``books.wikibase_item_id`` updates that item;
* entity-valued fields (author, publisher, ...) are resolved to an existing
  item by label, or created once as a stub.

OpenRefine remains the interactive cleaning surface; this module is the
scriptable equivalent and the verification oracle.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.models.book import Book
from app.schemas.metadata import FIELD_CONTRACT
from app.services.export_service import (
    MAX_STRING_LENGTH,
    _entity_datavalue,
    _monolingual_datavalue,
    _quantity_datavalue,
    _string_datavalue,
    _time_datavalue,
    load_property_mapping,
    wikibase_property_id,
)

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# MediaWiki API etiquette for automated writes.
MAX_LAG = 5
EDIT_SUMMARY = "Published from Open Book Map"

LANGUAGE_TAGS = {"tel": "te", "hin": "hi", "eng": "en"}
LANGUAGE_QIDS = {"tel": "Q809", "hin": "Q1568", "eng": "Q1860"}

# Multi-value fields in the source data are separated by semicolons, pipes or
# newlines. Commas are not separators: names and titles contain them.
_SPLIT = (";", "|", "\n")


@dataclass
class PublishReport:
    book_id: str
    item_id: str | None = None
    created: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.item_id is not None


def split_values(value: str) -> list[str]:
    """Split a multi-value cell without breaking names that contain commas."""
    parts = [value]
    for sep in _SPLIT:
        next_parts: list[str] = []
        for part in parts:
            next_parts.extend(part.split(sep))
        parts = next_parts
    return [p.strip() for p in parts if p and p.strip()]


def language_tag(book_language: str) -> str:
    return LANGUAGE_TAGS.get(book_language, "en")


def _labels(text: str, lang: str) -> dict[str, dict[str, str]]:
    labels = {lang: {"language": lang, "value": text}}
    if lang != "en":
        # Mirror the label so the default English UI does not show
        # "No label defined" for an Indic-language item.
        labels["en"] = {"language": "en", "value": text}
    return labels


class WikibaseClient:
    """Minimal MediaWiki API client (login + wbeditentity + search)."""

    def __init__(self, api_url: str, username: str, password: str) -> None:
        self._api = api_url
        self._username = username
        self._password = password
        self._client = httpx.AsyncClient(timeout=_TIMEOUT)
        self._csrf: str | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.get(self._api, params={"format": "json", **params})
        response.raise_for_status()
        return response.json()

    async def _post(self, data: dict[str, Any]) -> dict[str, Any]:
        """POST an API action, honouring maxlag and retrying once on lag."""
        import asyncio

        payload: dict[str, Any] = {"format": "json", "maxlag": MAX_LAG, **data}
        for attempt in range(2):
            response = await self._client.post(self._api, data=payload)
            response.raise_for_status()
            body = response.json()
            if body.get("error", {}).get("code") == "maxlag" and attempt == 0:
                delay = int(response.headers.get("retry-after", MAX_LAG))
                logger.info("wikibase maxlag, retrying in %ss", delay)
                await asyncio.sleep(max(1, delay))
                continue
            return body
        return body

    async def login(self) -> None:
        token = await self._get({"action": "query", "meta": "tokens", "type": "login"})
        login_token = token["query"]["tokens"]["logintoken"]
        result = await self._post(
            {
                "action": "login",
                "lgname": self._username,
                "lgpassword": self._password,
                "lgtoken": login_token,
            }
        )
        if result.get("login", {}).get("result") != "Success":
            raise RuntimeError(f"Wikibase login failed: {result.get('login')}")
        tokens = await self._get({"action": "query", "meta": "tokens"})
        self._csrf = tokens["query"]["tokens"]["csrftoken"]

    async def search(self, query: str, lang: str, limit: int = 10) -> list[dict[str, Any]]:
        payload = await self._get(
            {
                "action": "wbsearchentities",
                "search": query,
                "language": lang,
                "uselang": lang,
                "type": "item",
                "limit": limit,
            }
        )
        return payload.get("search", [])

    async def find_by_label(self, label: str, lang: str) -> str | None:
        for hit in await self.search(label, lang):
            if (hit.get("label") or "").strip() == label.strip():
                return hit["id"]
        return None

    async def last_revid(self, item_id: str) -> int | None:
        """Latest revision id of an item, for edit-conflict detection."""
        payload = await self._get({"action": "wbgetentities", "ids": item_id, "props": "info"})
        info = payload.get("entities", {}).get(item_id, {})
        return info.get("lastrevid")

    async def create_item(
        self,
        labels: dict[str, dict[str, str]],
        descriptions: dict[str, dict[str, str]] | None = None,
        claims: dict[str, list[dict]] | None = None,
    ) -> str:
        data: dict[str, Any] = {"labels": labels}
        if descriptions:
            data["descriptions"] = descriptions
        if claims:
            data["claims"] = claims
        payload = await self._post(
            {
                "action": "wbeditentity",
                "new": "item",
                "data": json.dumps(data, ensure_ascii=False),
                "token": self._csrf,
                "summary": EDIT_SUMMARY,
                "bot": "1",
            }
        )
        if "entity" not in payload:
            raise RuntimeError(f"wbeditentity failed: {payload.get('error')}")
        return payload["entity"]["id"]

    async def edit_item(self, item_id: str, data: dict[str, Any]) -> None:
        """Replace an item's statements, detecting edit conflicts with baserevid."""
        for attempt in range(2):
            base = await self.last_revid(item_id)
            body = {"claims": data.get("claims", {}), **{k: v for k, v in data.items() if k != "claims"}}
            if base is not None:
                body["baserevid"] = base
            payload = await self._post(
                {
                    "action": "wbeditentity",
                    "id": item_id,
                    "data": json.dumps(body, ensure_ascii=False),
                    # This Wikibase (REL1_45) clears claims with `clear`.
                    "clear": 1,
                    "token": self._csrf,
                    "summary": EDIT_SUMMARY,
                    "bot": "1",
                }
            )
            if "entity" in payload:
                return
            if payload.get("error", {}).get("code") == "editconflict" and attempt == 0:
                logger.info("edit conflict on %s, refetching", item_id)
                continue
            raise RuntimeError(f"wbeditentity failed: {payload.get('error')}")


# MediaWiki rejects labels longer than 250 characters.
MAX_LABEL_LENGTH = 250


async def resolve_entity(client: WikibaseClient, name: str, lang: str) -> str:
    """Return an item id for ``name``, creating a stub when missing."""
    if len(name) > MAX_LABEL_LENGTH:
        raise ValueError(f"label is longer than {MAX_LABEL_LENGTH} characters")
    existing = await client.find_by_label(name, lang)
    if existing:
        return existing
    return await client.create_item(_labels(name, lang))


def _dedupe(claims: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Drop duplicate statements (e.g. language and original_language)."""
    out: dict[str, list[dict]] = {}
    for prop, statements in claims.items():
        seen: set[str] = set()
        unique: list[dict] = []
        for statement in statements:
            key = json.dumps(statement["mainsnak"]["datavalue"], sort_keys=True, ensure_ascii=False)
            if key not in seen:
                seen.add(key)
                unique.append(statement)
        out[prop] = unique
    return out


def _local_property(spec: dict[str, Any], mapping: dict[str, str]) -> str | None:
    key = spec.get("local_property")
    if not key:
        return None
    return mapping.get(key, key)


def _datavalue(spec: dict[str, Any], value: str, book_language: str) -> dict[str, Any] | None:
    parser = spec.get("parser")
    if parser == "time":
        parsed = _time_datavalue(value)
        return parsed
    if parser == "quantity":
        return _quantity_datavalue(value)
    if parser in ("monolingual", "string", "external-id") or parser is None:
        value = value[:MAX_STRING_LENGTH]
    if parser == "monolingual":
        tag = spec.get("language_tag")
        if tag in (None, "auto"):
            tag = language_tag(book_language)
        return _monolingual_datavalue(value, tag)
    # string, external-id and isbn all carry a plain string datavalue.
    return _string_datavalue(value)


async def build_claims(
    client: WikibaseClient,
    row_fields: dict[str, Any],
    book_language: str,
    mapping: dict[str, str],
    warnings: list[str],
    dry_run: bool = False,
) -> dict[str, list[dict]]:
    claims: dict[str, list[dict]] = {}
    lang = language_tag(book_language)

    for field_name, spec in FIELD_CONTRACT.items():
        prop = _local_property(spec, mapping)
        if not prop:
            continue
        raw = row_fields.get(field_name)
        value = raw.strip() if isinstance(raw, str) else ""
        if not value:
            continue

        if field_name == "isbn":
            isbn_prop = wikibase_property_id("isbn", value, "P212")
            prop = mapping.get(isbn_prop, isbn_prop)
            claims.setdefault(prop, []).append(
                {
                    "mainsnak": {"snaktype": "value", "property": prop, "datavalue": _string_datavalue(value)},
                    "type": "statement",
                    "rank": "normal",
                }
            )
            continue

        if len(value) > MAX_STRING_LENGTH:
            warnings.append(f"{field_name}: truncated to {MAX_STRING_LENGTH} characters")

        if spec.get("parser") == "entity":
            if dry_run:
                warnings.append(f"{field_name}: dry run, entity not resolved")
                continue
            for name in split_values(value):
                try:
                    qid = await resolve_entity(client, name, lang)
                except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                    warnings.append(f"{field_name}: could not resolve {name!r}: {exc}")
                    continue
                claims.setdefault(prop, []).append(
                    {
                        "mainsnak": {"snaktype": "value", "property": prop, "datavalue": _entity_datavalue(qid)},
                        "type": "statement",
                        "rank": "normal",
                    }
                )
            continue

        datavalue = _datavalue(spec, value, book_language)
        if datavalue is None:
            warnings.append(f"{field_name}: could not parse {value!r}")
            continue
        claims.setdefault(prop, []).append(
            {
                "mainsnak": {"snaktype": "value", "property": prop, "datavalue": datavalue},
                "type": "statement",
                "rank": "normal",
            }
        )

    instance_of = mapping.get("P31", "P31")
    book_qid = mapping.get("Q571", "Q571")
    claims.setdefault(instance_of, []).append(
        {
            "mainsnak": {"snaktype": "value", "property": instance_of, "datavalue": _entity_datavalue(book_qid)},
            "type": "statement",
            "rank": "normal",
        }
    )

    lang_qid = LANGUAGE_QIDS.get(book_language)
    if lang_qid:
        prop = mapping.get("P407", "P407")
        claims.setdefault(prop, []).append(
            {
                "mainsnak": {
                    "snaktype": "value",
                    "property": prop,
                    "datavalue": _entity_datavalue(mapping.get(lang_qid, lang_qid)),
                },
                "type": "statement",
                "rank": "normal",
            }
        )

    return _dedupe(claims)


def build_labels_and_description(
    fields: dict[str, Any], book_language: str
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]] | None]:
    lang = language_tag(book_language)
    label = (fields.get("label") or fields.get("title") or "").strip()
    if not label:
        return {}, None
    labels = _labels(label, lang)

    description = (fields.get("description_work") or fields.get("description_edition") or "").strip()
    descriptions = None
    # MediaWiki rejects a label and description that are identical.
    if description and description != label:
        short = description[:150].rstrip()
        descriptions = {lang: {"language": lang, "value": short}}
    return labels, descriptions


async def publish_book(
    client: WikibaseClient,
    book: Book,
    fields: dict[str, Any],
    mapping: dict[str, str],
    dry_run: bool = False,
) -> PublishReport:
    """Create or update the Wikibase item for one book."""
    report = PublishReport(book_id=str(book.id))
    book_language = book.language or "tel"

    claims = await build_claims(client, fields, book_language, mapping, report.warnings, dry_run=dry_run)
    labels, descriptions = build_labels_and_description(fields, book_language)
    if not labels:
        report.warnings.append("no label: field 'label' and 'title' are both empty")
        return report

    if dry_run:
        report.warnings.append("dry run: no changes written")
        return report

    # `clear` replaces the entity's statements, so the labels and descriptions
    # must be included on every update or they are lost.
    data: dict[str, Any] = {"labels": labels, "claims": claims}
    if descriptions:
        data["descriptions"] = descriptions

    if book.wikibase_item_id:
        await client.edit_item(book.wikibase_item_id, data)
        report.item_id = book.wikibase_item_id
        report.created = False
        return report

    report.item_id = await client.create_item(labels, descriptions, claims)
    report.created = True
    return report


def build_client() -> WikibaseClient:
    from app.core.config import settings

    return WikibaseClient(
        settings.wikibase_api_url,
        settings.wikibase_bot_username,
        settings.wikibase_bot_password,
    )


def mapping() -> dict[str, str]:
    return load_property_mapping()
