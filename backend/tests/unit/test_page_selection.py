"""Tests for front/back matter page selection."""

from __future__ import annotations

from app.services.page_selection import is_body_page, select_pages

BODY = "\n".join(["lorem ipsum dolor sit amet consectetur adipiscing elit"] * 30)  # long, dense, no cue
META = "శీర్షిక రచయిత ప్రచురణకర్త 1933"  # short, has a cue word


def test_body_vs_front_matter() -> None:
    assert is_body_page(BODY) is True
    assert is_body_page(META) is False
    # long text that still mentions a publisher is not treated as body
    assert is_body_page(BODY + "\npublisher: ACME Press") is False


def test_fixed_strategy() -> None:
    text = {p: META for p in range(1, 21)}
    picked = select_pages(20, text, strategy="fixed", front=3, back=2)
    assert picked == [1, 2, 3, 19, 20]


def test_heuristic_stops_at_body_from_each_end() -> None:
    text = {1: META, 2: META, 3: BODY, 4: BODY, 18: BODY, 19: META, 20: META}
    picked = select_pages(20, text, strategy="heuristic")
    # front: 1,2 then stop at body(3); back: 20,19 then stop at body(18)
    assert picked == [1, 2, 19, 20]


def test_heuristic_skips_empty_pages() -> None:
    text = {1: "", 2: META, 3: BODY, 20: ""}
    assert select_pages(20, text, strategy="heuristic") == [2]


def test_unknown_strategy_raises() -> None:
    import pytest

    with pytest.raises(ValueError):
        select_pages(10, {1: META}, strategy="magic")