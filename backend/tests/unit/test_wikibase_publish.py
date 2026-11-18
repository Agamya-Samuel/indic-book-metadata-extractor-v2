"""Tests for the Wikibase publish service."""

from __future__ import annotations

import asyncio

from app.services import wikibase_publish as wp


class FakeClient:
    """In-memory stand-in for WikibaseClient."""

    def __init__(self) -> None:
        self.created: list[dict] = []
        self.edited: list[tuple[str, dict]] = []
        self.labels: dict[str, str] = {}
        self._next = 1

    async def find_by_label(self, label: str, lang: str) -> str | None:
        return self.labels.get(label)

    async def create_item(self, labels, descriptions=None, claims=None) -> str:
        self.created.append({"labels": labels, "descriptions": descriptions, "claims": claims})
        qid = f"Q{100 + self._next}"
        self._next += 1
        for entry in labels.values():
            self.labels[entry["value"]] = qid
        return qid

    async def edit_item(self, item_id: str, data: dict) -> None:
        self.edited.append((item_id, data))


def _run(coro):
    return asyncio.run(coro)


def test_split_values_keeps_commas_in_names():
    assert wp.split_values("A; B | C\nD") == ["A", "B", "C", "D"]
    assert wp.split_values("Kishore, Kumar; Meena") == ["Kishore, Kumar", "Meena"]
    assert wp.split_values(" ") == []


def test_language_tag_maps_iso_to_bcp47():
    assert wp.language_tag("tel") == "te"
    assert wp.language_tag("hin") == "hi"
    assert wp.language_tag("eng") == "en"
    assert wp.language_tag("unknown") == "en"


def test_labels_fall_back_to_title_and_description_is_truncated():
    labels, descriptions = wp.build_labels_and_description(
        {"label": "", "title": "పుస్తకం", "description_work": "x" * 300}, "tel"
    )
    assert labels["te"]["value"] == "పుస్తకం"
    assert len(descriptions["te"]["value"]) == 150

    labels, descriptions = wp.build_labels_and_description({"label": "", "title": ""}, "tel")
    assert labels == {}
    assert descriptions is None


def test_build_claims_maps_datatypes_and_adds_book_and_language():
    client = FakeClient()
    fields = {
        "author": "రచయిత",
        "publisher": "ఆఖరి; మొదటి",
        "title": "పుస్తకం",
        "publication_date": "1998",
        "pages": "242 p.",
        "place_of_printing": "",
    }
    mapping = {
        "P50": "P3",
        "P123": "P6",
        "P1476": "P31",
        "P577": "P18",
        "P1104": "P29",
        "P31": "P2",
        "P407": "P15",
        "Q571": "Q1",
        "Q809": "Q2",
    }
    warnings: list[str] = []
    claims = _run(wp.build_claims(client, fields, "tel", mapping, warnings))

    assert warnings == []
    # Two publishers were split and each resolved to a stub.
    assert len(claims["P6"]) == 2
    assert claims["P31"][0]["mainsnak"]["datavalue"] == {
        "value": {"text": "పుస్తకం", "language": "te"},
        "type": "monolingualtext",
    }
    assert claims["P18"][0]["mainsnak"]["datavalue"]["type"] == "time"
    assert claims["P29"][0]["mainsnak"]["datavalue"]["type"] == "quantity"
    # instance-of book + language of work.
    assert claims["P2"][0]["mainsnak"]["datavalue"]["value"]["id"] == "Q1"
    assert claims["P15"][0]["mainsnak"]["datavalue"]["value"]["id"] == "Q2"


def test_build_claims_warns_on_unparseable_time_and_entity():
    client = FakeClient()
    warnings: list[str] = []
    claims = _run(
        wp.build_claims(
            client,
            {"publication_date": "सन"},
            "hin",
            {"P577": "P18", "P31": "P2", "P407": "P15", "Q571": "Q1", "Q1568": "Q3"},
            warnings,
        )
    )
    assert any("publication_date" in w for w in warnings)
    assert "P18" not in claims


def test_dry_run_skips_entity_resolution():
    client = FakeClient()
    warnings: list[str] = []
    claims = _run(
        wp.build_claims(
            client,
            {"author": "రచయిత"},
            "tel",
            {"P50": "P3", "P31": "P2", "P407": "P15", "Q571": "Q1", "Q809": "Q2"},
            warnings,
            dry_run=True,
        )
    )
    assert client.created == []
    assert any("dry run" in w for w in warnings)
    assert "P3" not in claims


def test_publish_book_creates_then_updates():
    client = FakeClient()
    mapping = {"P50": "P3", "P31": "P2", "P407": "P15", "Q571": "Q1", "Q809": "Q2"}
    book = type("B", (), {"id": "b1", "language": "tel", "wikibase_item_id": None})()
    fields = {"label": "పుస్తకం", "author": "రచయిత"}

    report = _run(wp.publish_book(client, book, fields, mapping))
    assert report.created is True
    assert report.item_id is not None
    # One stub for the author plus the book item itself.
    assert len(client.created) == 2
    assert client.created[-1]["labels"]["te"]["value"] == "పుస్తకం"

    book.wikibase_item_id = report.item_id
    report2 = _run(wp.publish_book(client, book, fields, mapping))
    assert report2.created is False
    assert len(client.edited) == 1
    assert client.edited[0][0] == report.item_id
