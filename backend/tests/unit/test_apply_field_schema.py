"""Tests for the ground-truth field-schema conformance script."""

from __future__ import annotations

import json

from app.schemas.metadata import ALL_METADATA_FIELDS
from scripts.apply_field_schema import normalize_dict

CANON = [f.field_name for f in ALL_METADATA_FIELDS]


def test_normalize_adds_missing_and_drops_extra() -> None:
    d = {"title": "A", "not_a_field": "junk"}

    out, missing, extra = normalize_dict(d, None)

    assert list(out)[0] == CANON[0]
    assert out["title"] == "A"
    assert "not_a_field" not in out
    assert "title" not in missing
    assert missing == [f for f in CANON if f != "title"]
    assert extra == ["not_a_field"]


def test_normalize_uses_default_for_missing() -> None:
    out, _, _ = normalize_dict({}, "empty_needs_annotation")

    assert len(out) == len(CANON)
    assert all(v == "empty_needs_annotation" for v in out.values())


def test_normalize_is_idempotent() -> None:
    once, _, _ = normalize_dict({"title": "A", "author": "B"}, None)
    twice, missing, extra = normalize_dict(once, None)

    assert once == twice
    assert missing == []
    assert extra == []


def test_write_normalizes_a_deviating_book(tmp_path) -> None:
    from scripts.apply_field_schema import main  # noqa: PLC0415

    book = tmp_path / "tel" / "b"
    book.mkdir(parents=True)
    gt = book / "expected_metadata.json"
    gt.write_text(
        json.dumps({"expected_metadata": {"title": "A", "junk": 1}, "field_status": {}, "field_source": {}}),
        encoding="utf-8",
    )

    import sys  # noqa: PLC0415

    argv = sys.argv
    sys.argv = ["apply", "--root", str(tmp_path), "--write"]
    try:
        rc = main()
    finally:
        sys.argv = argv

    assert rc == 0
    env = json.loads(gt.read_text(encoding="utf-8"))
    assert set(env["expected_metadata"]) == set(CANON)
    assert env["expected_metadata"]["title"] == "A"
    assert set(env["field_source"]) == set(CANON)
    assert set(env["field_status"]) == set(CANON)
