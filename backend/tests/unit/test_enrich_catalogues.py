"""Tests for the catalogue-enrichment helpers."""

from __future__ import annotations

from scripts.enrich_catalogues import ia_id, is_latin, parse_dc

DESC = (
    "<p><b>Book Source:</b> Digital Library of India<br/>"
    "dc.contributor.author: Keshwdas dc.date.citation: 1915 "
    "dc.identifier.barcode: 0599 dc.publisher: Hindustani Acadamy, Allahabad "
    "dc.subject.classification: Literature dc.title: Ramchandrika Satik</p>"
)


def test_parse_dc_extracts_fields() -> None:
    dc = parse_dc(DESC)
    assert dc["dc.date.citation"] == "1915"
    assert dc["dc.publisher"] == "Hindustani Acadamy, Allahabad"
    assert dc["dc.subject.classification"] == "Literature"


def test_ia_id_from_urls() -> None:
    assert ia_id({"credit": "https://archive.org/items/in.ernet.dli.2015.1/x.pdf"}, "s") == "in.ernet.dli.2015.1"
    assert ia_id({"credit": "https://archive.org/download/sivapariksha00unse/a.pdf"}, "s") == "sivapariksha00unse"
    assert ia_id({"credit": "Internet Archive identifier: abc123 http://x"}, "s") == "abc123"


def test_ia_id_from_dli_slug() -> None:
    assert ia_id({}, "2015.373190.Athma-Charitramu") == "in.ernet.dli.2015.373190"
    assert ia_id({}, "no-id-here") is None


def test_is_latin() -> None:
    assert is_latin("Rayasam Venkata") is True
    assert is_latin("రాయసం") is False
    assert is_latin("प्रिय प्रवास") is False