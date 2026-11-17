"""Serializer tests for the metadata export service."""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from uuid import uuid4

from openpyxl import load_workbook

from app.services import export_service as svc


def _row(**overrides) -> svc.ExportRow:
    fields = {name: "" for name in svc.CANONICAL_FIELDS}
    fields["label"] = "పుస్తకం"
    fields["author"] = "రచయిత"
    values = {
        "book_id": uuid4(),
        "title": "Book title",
        "language": "tel",
        "filename": "/app/storage/books/secret/path/book.pdf",
        "status": "complete",
        "total_pages": 120,
        "uploaded_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "reviewed_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
        "fields": fields,
        "custom_fields": {},
    }
    values.update(overrides)
    return svc.ExportRow(**values)


def _decode_csv(body: bytes) -> list[list[str]]:
    import csv

    text = body.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


class TestCsv:
    def test_has_bom_and_all_columns(self):
        body, media_type, extension = svc.render([_row()], "csv")
        assert body.startswith(b"\xef\xbb\xbf")
        assert media_type == "text/csv; charset=utf-8"
        assert extension == "csv"

        rows = _decode_csv(body)
        assert rows[0] == ["book_id", *svc.CANONICAL_FIELDS]
        assert len(rows[0]) == 50
        assert len(rows[1]) == 50

    def test_preserves_indic_text(self):
        row = _row()
        row.fields["author"] = "రచయిత"
        row.fields["publisher"] = "प्रकाशक"
        body, _, _ = svc.render([row], "csv")
        text = body.decode("utf-8-sig")
        assert "రచయిత" in text
        assert "प्रकाशक" in text

    def test_include_details_adds_prefixed_columns(self):
        body, _, _ = svc.render([_row()], "csv", include_details=True)
        header = _decode_csv(body)[0]
        assert header[:8] == ["book_id", *svc.DETAIL_COLUMNS]
        assert "book_title" in header
        assert "book_language" in header

    def test_empty_values_keep_every_column(self):
        row = _row(fields={name: "" for name in svc.CANONICAL_FIELDS})
        rows = _decode_csv(svc.render([row], "csv")[0])
        assert len(rows[1]) == 50
        assert rows[1][1:] == [""] * 49

    def test_formula_values_are_escaped(self):
        row = _row()
        row.fields["label"] = "=SUM(A1:A2)"
        body, _, _ = svc.render([row], "csv")
        assert "'=SUM(A1:A2)" in body.decode("utf-8-sig")


class TestOpenRefine:
    def test_no_bom_and_identifying_columns(self):
        body, media_type, _ = svc.render([_row()], "openrefine")
        assert not body.startswith(b"\xef\xbb\xbf")
        assert media_type == "text/csv; charset=utf-8"
        header = _decode_csv(body)[0]
        assert header[:4] == ["book_id", "book_title", "book_language", "source_filename"]
        assert "secret/path" not in body.decode("utf-8")
        assert "book.pdf" in body.decode("utf-8")


class TestXlsx:
    def test_headers_freeze_and_filter(self):
        body, media_type, extension = svc.render([_row()], "xlsx")
        assert extension == "xlsx"
        assert "spreadsheetml" in media_type

        workbook = load_workbook(io.BytesIO(body))
        sheet = workbook.active
        assert sheet.freeze_panes == "A2"
        assert sheet.auto_filter.ref == "A1:AX2"
        assert sheet.cell(row=1, column=1).value == "Book ID"
        assert sheet.cell(row=1, column=2).value == svc.FIELD_DISPLAY_NAMES["label"]
        assert sheet.max_column == 50
        assert sheet.cell(row=2, column=2).value == "పుస్తకం"

    def test_include_details_uses_labels(self):
        sheet = load_workbook(io.BytesIO(svc.render([_row()], "xlsx", True)[0])).active
        assert sheet.cell(row=1, column=2).value == "Book title"
        assert sheet.cell(row=1, column=3).value == "Book language"


class TestJson:
    def test_shape_without_details(self):
        row = _row()
        payload = json.loads(svc.render([row], "json")[0].decode("utf-8"))
        assert payload[0]["book_id"] == str(row.book_id)
        assert set(payload[0]["metadata"]) == set(svc.CANONICAL_FIELDS)
        assert "book" not in payload[0]

    def test_include_details_and_unicode(self):
        row = _row()
        body = svc.render([row], "json", include_details=True)[0]
        text = body.decode("utf-8")
        assert "పుస్తకం" in text
        payload = json.loads(text)
        assert payload[0]["book"]["source_filename"] == "book.pdf"
        assert payload[0]["book"]["title"] == "Book title"

    def test_formula_untouched(self):
        row = _row()
        row.fields["label"] = "=SUM(A1:A2)"
        payload = json.loads(svc.render([row], "json")[0].decode("utf-8"))
        assert payload[0]["metadata"]["label"] == "=SUM(A1:A2)"

    def test_custom_fields_are_included(self):
        row = _row(custom_fields={"notes": "అదనపు"})
        body, _, _ = svc.render([row], "csv")
        assert "custom:notes" in _decode_csv(body)[0]
        payload = json.loads(svc.render([row], "json")[0].decode("utf-8"))
        assert payload[0]["custom_fields"] == {"notes": "అదనపు"}


class TestJsonl:
    def test_one_object_per_line(self):
        rows = [_row(), _row()]
        body, media_type, extension = svc.render(rows, "jsonl")
        assert media_type == "application/x-ndjson"
        assert extension == "jsonl"
        lines = body.decode("utf-8").strip().splitlines()
        assert len(lines) == 2
        assert all(json.loads(line)["book_id"] for line in lines)


class TestWikibase:
    def test_entity_claims(self):
        row = _row()
        row.fields["publication_date"] = "1998"
        row.fields["description_work"] = "A work"
        row.custom_fields = {"notes": "extra"}

        payload = json.loads(svc.render([row], "wikibase")[0].decode("utf-8"))
        item = payload[0]

        assert item["type"] == "item"
        assert item["labels"]["en"]["value"] == "పుస్తకం"
        assert item["descriptions"]["en"]["value"] == "A work"
        assert item["claims"]["P50"][0]["mainsnak"]["datavalue"]["value"] == "రచయిత"

        instance = item["claims"]["P31"][0]["mainsnak"]["datavalue"]
        assert instance["type"] == "wikibase-entityid"
        assert instance["value"]["id"] == "Q571"

        publication = item["claims"]["P577"][0]["mainsnak"]["datavalue"]
        assert publication["type"] == "time"
        assert publication["value"]["time"] == "+1998-00-00T00:00:00Z"
        assert publication["value"]["precision"] == 9

        language = item["claims"]["P407"][0]["mainsnak"]["datavalue"]
        assert language["value"]["id"] == "Q809"

        assert item["custom_fields"] == {"notes": "extra"}

    def test_empty_fields_are_skipped(self):
        row = _row(
            language="xx",
            fields={name: "" for name in svc.CANONICAL_FIELDS},
        )
        item = json.loads(svc.render([row], "wikibase")[0].decode("utf-8"))[0]
        # Only the always-present instance-of claim remains.
        assert set(item["claims"]) == {"P31"}

    def test_monolingual_and_quantity_datatypes(self):
        row = _row()
        row.fields["title"] = "పుస్తకం"
        row.fields["subtitle"] = "ఉపశీర్షిక"
        row.fields["pages"] = "242 p."
        item = json.loads(svc.render([row], "wikibase")[0].decode("utf-8"))[0]

        title = item["claims"]["P1476"][0]["mainsnak"]["datavalue"]
        assert title["type"] == "monolingualtext"
        assert title["value"] == {"text": "పుస్తకం", "language": "te"}

        subtitle = item["claims"]["P1680"][0]["mainsnak"]["datavalue"]
        assert subtitle["value"]["language"] == "te"

        pages = item["claims"]["P1104"][0]["mainsnak"]["datavalue"]
        assert pages["type"] == "quantity"
        assert pages["value"]["amount"] == "+242"

    def test_isbn_length_selects_property(self):
        ten = _row()
        ten.fields["isbn"] = "0-306-40615-2"
        thirteen = _row()
        thirteen.fields["isbn"] = "978-3-16-148410-0"

        ten_item = json.loads(svc.render([ten], "wikibase")[0].decode("utf-8"))[0]
        thirteen_item = json.loads(svc.render([thirteen], "wikibase")[0].decode("utf-8"))[0]

        assert ten_item["claims"]["P957"][0]["mainsnak"]["datavalue"]["value"] == "0-306-40615-2"
        assert thirteen_item["claims"]["P212"][0]["mainsnak"]["datavalue"]["value"] == ("978-3-16-148410-0")


class TestWikibaseTsvValue:
    def test_uses_property_datatype(self):
        assert svc.wikibase_tsv_value("title", "పుస్తకం", "tel") == 'te:"పుస్తకం"'
        assert svc.wikibase_tsv_value("pages", "242 p.", "tel") == "242"
        assert svc.wikibase_tsv_value("publication_date", "1998", "tel") == "+1998-00-00T00:00:00Z/9"
        assert svc.wikibase_tsv_value("author", 'A "B"', "tel") == '"A \\"B\\""'
        assert svc.wikibase_tsv_value("pages", "no number", "tel") is None


class TestWikidataMapping:
    def test_uses_valid_wikidata_properties(self):
        from app.schemas.metadata import FIELD_WIKIDATA

        assert FIELD_WIKIDATA["place_of_printing"] is None
        assert FIELD_WIKIDATA["original_language"] == "P407"
        assert FIELD_WIKIDATA["isbn"] == "P212"
        assert FIELD_WIKIDATA["title"] == "P1476"
        assert FIELD_WIKIDATA["distributors"] == "P750"
