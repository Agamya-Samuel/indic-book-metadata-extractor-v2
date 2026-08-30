"""Tests for the extraction_validator module."""

from __future__ import annotations

import pytest

from app.services.extraction_validator import (
    BookEvaluation,
    OverallEvaluation,
    evaluate_book,
    evaluate_field,
)


class TestEvaluateField:
    def test_exact_match(self):
        r = evaluate_field("title", "Bharat", "Bharat")
        assert r.exact_match
        assert r.normalized_match
        assert r.token_f1 == 1.0

    def test_normalized_match_with_case_diff(self):
        r = evaluate_field("title", "BHARAT", "bharat")
        assert not r.exact_match
        assert r.normalized_match

    def test_partial_token_overlap(self):
        r = evaluate_field("author", "Ram Sharma", "Ram")
        assert not r.exact_match
        assert r.token_f1 == pytest.approx(2 / 3, rel=1e-2)

    def test_missing_expected(self):
        r = evaluate_field("publisher", None, "Foo")
        assert r.expected_present is False
        assert r.predicted_present is True
        assert not r.exact_match

    def test_missing_predicted(self):
        r = evaluate_field("pages", "248", None)
        assert r.expected_present is True
        assert r.predicted_present is False
        assert r.token_f1 == 0.0

    def test_placeholder_predicted_treated_as_absent(self):
        r = evaluate_field("isbn", "978-x", "n/a")
        assert r.predicted_present is False

    def test_empty_strings_treated_as_absent(self):
        r = evaluate_field("isbn", "978-x", "")
        assert r.predicted_present is False


class TestEvaluateBook:
    def test_basic_counts(self):
        expected = {"title": "A", "author": "B", "isbn": "978-x", "pages": "100"}
        predicted = {"title": "A", "author": "B", "isbn": "wrong", "pages": "100"}
        evaln = evaluate_book("test", expected, predicted, expected.keys())

        # TP: title, author, pages (all present in both). isbn: predicted
        # is present, expected is present — counts as TP at the presence
        # level even though the value is wrong. This is what the
        # micro-precision/recall track.
        assert evaln.tp() == 4
        assert evaln.fp() == 0
        assert evaln.fn() == 0
        assert evaln.exact_match_rate() == pytest.approx(3 / 4)

    def test_empty_expected(self):
        evaln = evaluate_book("test", {}, {}, ["title", "author"])
        assert evaln.tp() == 0
        assert evaln.fp() == 0
        assert evaln.fn() == 0
        assert evaln.mean_token_f1() == 0.0


class TestOverallEvaluation:
    def test_micro_metrics(self):
        expected_a = {"title": "A", "author": "B"}
        predicted_a = {"title": "A", "author": "B"}
        evaln_a = evaluate_book("a", expected_a, predicted_a, expected_a.keys())

        expected_b = {"title": "X", "author": "Y"}
        predicted_b = {"title": "X", "author": "Z"}  # author wrong but present
        evaln_b = evaluate_book("b", expected_b, predicted_b, expected_b.keys())

        overall = OverallEvaluation(books=[evaln_a, evaln_b])
        # TP at presence level: title(a) title(b) author(a) author(b) = 4
        assert overall.total_tp() == 4
        assert overall.total_fp() == 0
        assert overall.total_fn() == 0
        assert overall.micro_precision() == 1.0
        assert overall.micro_recall() == 1.0
        # token F1: book A perfect, book B has 0% author F1
        assert overall.macro_token_f1() > 0.5

    def test_per_field_f1_token_level(self):
        # Per-field F1 as exposed is the presence-level metric (precision/recall
        # at the field-has-value level), not the token-overlap metric. The
        # token overlap is on FieldResult.token_f1. Here we test that the
        # author field is "present in both" so its presence F1 is 1.0 even
        # though the values differ — correctness-by-value is separate.
        expected = {"title": "A", "author": "B"}
        predicted = {"title": "A", "author": "WRONG"}
        evaln = evaluate_book("a", expected, predicted, expected.keys())
        overall = OverallEvaluation(books=[evaln])
        per_field = overall.per_field_f1()
        assert per_field["title"]["f1"] == 1.0
        # presence-level: both predicted and expected have author; P=R=1
        assert per_field["author"]["f1"] == 1.0
        # but the token F1 on the field result itself is 0
        author_result = next(r for r in evaln.field_results if r.field_name == "author")
        assert author_result.token_f1 == 0.0

    def test_field_present_but_wrong_counts_as_fp_zero_fn(self):
        """If expected is empty but we predicted a value, that's an FP, not a FN."""
        expected = {"title": "A"}
        predicted = {"title": "A", "author": "Hallucinated"}
        evaln = evaluate_book("a", expected, predicted, ["title", "author"])
        overall = OverallEvaluation(books=[evaln])
        assert overall.total_fp() == 1
        assert overall.total_fn() == 0
