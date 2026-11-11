"""Tests for per-book ground-truth discovery in ``scripts/evaluate_extraction.py``.

The Commons corpus uses ``ground_truth/{lang}/{slug}/`` (one directory per
book), which the original ``{lang}/{quality}/`` sample discovery cannot
express. These tests pin the discovery contract, including the guarantee
that unverified Commons scaffolds are never scored as ground truth.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.evaluate_extraction import discover_ground_truth

EXPECTED = {"title": "Andhra Mahaniyulu", "author": "Chilukuri Veerabhadra Rao"}


def _make_book(
    root: Path,
    lang: str,
    slug: str,
    *,
    status: str | None = "verified",
    pdf: bool = True,
    pdf_name: str = "original.pdf",
    envelope: bool = True,
    raw: str | None = None,
) -> Path:
    """Create one ``{lang}/{slug}/`` book directory."""
    book = root / lang / slug
    book.mkdir(parents=True)
    gt = book / "expected_metadata.json"
    if raw is not None:
        gt.write_text(raw, encoding="utf-8")
    else:
        payload = (
            {"verification_status": status, "expected_metadata": EXPECTED, "language": lang} if envelope else EXPECTED
        )
        gt.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    if pdf:
        (book / pdf_name).write_bytes(b"%PDF-1.4 stub")
    return book


def test_discovers_verified_book(tmp_path: Path) -> None:
    book = _make_book(tmp_path, "tel", "andhra-mahaniyulu")

    samples = discover_ground_truth(tmp_path)

    assert len(samples) == 1
    assert samples[0]["sample_id"] == "tel/andhra-mahaniyulu"
    assert samples[0]["pdf_path"] == str(book / "original.pdf")
    assert samples[0]["expected_path"] == str(book / "expected_metadata.json")


def test_skips_unverified_by_default(tmp_path: Path) -> None:
    _make_book(tmp_path, "tel", "scaffold-only", status="unverified")

    assert discover_ground_truth(tmp_path) == []


def test_include_unverified_opts_back_in(tmp_path: Path) -> None:
    _make_book(tmp_path, "tel", "scaffold-only", status="unverified")

    samples = discover_ground_truth(tmp_path, only_verified=False)

    assert [s["sample_id"] for s in samples] == ["tel/scaffold-only"]


def test_skips_book_without_pdf(tmp_path: Path) -> None:
    _make_book(tmp_path, "hin", "no-pdf", pdf=False)

    assert discover_ground_truth(tmp_path) == []


def test_bare_expected_dict_counts_as_verified(tmp_path: Path) -> None:
    """A GT file with no envelope has no status to contradict, so it scores."""
    _make_book(tmp_path, "hin", "bare", envelope=False)

    assert [s["sample_id"] for s in discover_ground_truth(tmp_path)] == ["hin/bare"]


def test_falls_back_to_any_pdf_name(tmp_path: Path) -> None:
    """``--download`` writes original.pdf, but a renamed file must still work."""
    book = _make_book(tmp_path, "tel", "renamed", pdf_name="book-scan.pdf")

    samples = discover_ground_truth(tmp_path)

    assert samples[0]["pdf_path"] == str(book / "book-scan.pdf")


def test_skips_invalid_json(tmp_path: Path) -> None:
    _make_book(tmp_path, "tel", "broken", raw="{not valid json")

    assert discover_ground_truth(tmp_path) == []


def test_missing_root_returns_empty(tmp_path: Path) -> None:
    assert discover_ground_truth(tmp_path / "does-not-exist") == []


def test_ignores_files_and_empty_dirs(tmp_path: Path) -> None:
    (tmp_path / "manifest.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "tel").mkdir()
    (tmp_path / "tel" / "stray.txt").write_text("x", encoding="utf-8")

    assert discover_ground_truth(tmp_path) == []


def test_discovers_across_languages_and_status(tmp_path: Path) -> None:
    _make_book(tmp_path, "tel", "book-a")
    _make_book(tmp_path, "tel", "book-b", status="unverified")
    _make_book(tmp_path, "hin", "book-c")
    _make_book(tmp_path, "hin", "book-d", status="verified")

    ids = [s["sample_id"] for s in discover_ground_truth(tmp_path)]

    assert ids == ["hin/book-c", "hin/book-d", "tel/book-a"]
