"""Tests for the extraction_validator module."""

from __future__ import annotations

import pytest

from app.services.extraction_validator import (
    OverallEvaluation,
    bootstrap_ci,
    evaluate_book,
    evaluate_field,
    paired_delta_ci,
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

    def test_ignore_fields_excluded_from_scoring(self):
        # A field whose ground truth is model prefill must not be scored, or
        # the model would be credited for reproducing its own output.
        expected = {"title": "A", "printer": "Leader Press"}
        predicted = {"title": "A", "printer": "Leader Press", "isbn": "unexpected"}
        evaln = evaluate_book("test", expected, predicted, expected.keys(), ignore_fields={"printer"})

        assert [r.field_name for r in evaln.field_results] == ["title"]
        assert evaln.tp() == 1
        # `printer` is skipped entirely, so the predicted value is neither TP nor FP.
        assert evaln.fp() == 0
        assert evaln.fn() == 0


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


class TestFuzzyAndValueMetrics:
    def test_free_text_tolerates_one_bad_character(self):
        r = evaluate_field("title", "ఆత్మచరిత్రము", "ఆత్మచరితము")
        assert not r.normalized_match
        assert r.fuzzy_match
        assert r.value_correct

    def test_identifiers_must_match_exactly(self):
        # A one-digit ISBN difference is a wrong answer, not a typo.
        r = evaluate_field("isbn", "978-81-234-5678-9", "978-81-234-5678-8")
        assert not r.fuzzy_match
        assert not r.value_correct

    def test_truncated_year_is_not_fuzzy(self):
        r = evaluate_field("publication_date", "1933", "193")
        assert not r.fuzzy_match
        assert not r.value_correct

    def test_page_count_is_exact_only(self):
        r = evaluate_field("pages", "248", "240")
        assert not r.fuzzy_match

    def test_near_identical_long_name_is_fuzzy(self):
        r = evaluate_field("author", "రాయసం వెంకట శివుడు", "రాయసం వెంకట శివుడు,")
        assert r.fuzzy_match


class TestMaskScoring:
    def test_unroutable_fields_are_excluded(self):
        expected = {"title": "A", "printer": "Leader Press"}
        predicted = {"title": "A"}
        evaln = evaluate_book(
            "a",
            expected,
            predicted,
            ["title", "printer"],
            mask={"title": "visible", "printer": "unroutable"},
        )
        # printer is not a recall miss: it was never in the routed text.
        assert evaln.fn() == 0
        assert len(evaln.unroutable_results) == 1
        assert [r.field_name for r in evaln.scored_results] == ["title"]

    def test_not_in_scan_fields_are_excluded(self):
        expected = {"title": "A", "genre": "autobiography"}
        evaln = evaluate_book(
            "a",
            expected,
            {"title": "A"},
            ["title", "genre"],
            mask={"title": "visible", "genre": "not_in_scan"},
        )
        assert evaln.fn() == 0
        assert evaln.mask_counts()["not_in_scan"] == 1

    def test_absent_field_value_is_a_hallucination(self):
        evaln = evaluate_book(
            "a",
            {"title": "A"},
            {"title": "A", "isbn": "invented"},
            ["title", "isbn"],
            mask={"title": "visible", "isbn": "absent"},
        )
        assert evaln.hallucination_count() == 1
        assert evaln.correct_absent_count() == 0
        assert evaln.absent_count() == 1

    def test_mask_counts_report_every_bucket(self):
        evaln = evaluate_book(
            "a",
            {"title": "A"},
            {},
            ["title"],
            mask={"title": "visible"},
        )
        assert evaln.mask_counts() == {"visible": 1}


class TestValueAggregates:
    def _overall(self):
        # Two books: one perfect, one with a present-but-wrong author and a
        # spurious ISBN.
        a = evaluate_book(
            "tel/a",
            {"title": "A", "author": "B"},
            {"title": "A", "author": "B"},
            ["title", "author", "isbn"],
            mask={"title": "visible", "author": "visible", "isbn": "absent"},
        )
        b = evaluate_book(
            "tel/b",
            {"title": "X", "author": "Y"},
            {"title": "X", "author": "Z", "isbn": "spurious"},
            ["title", "author", "isbn"],
            mask={"title": "visible", "author": "visible", "isbn": "absent"},
        )
        return OverallEvaluation(books=[a, b])

    def test_field_level_accuracy_counts_values_not_presence(self):
        overall = self._overall()
        assert overall.field_level_accuracy() == pytest.approx(3 / 4)

    def test_value_precision_penalises_wrong_and_spurious(self):
        overall = self._overall()
        assert overall.value_micro_precision() == pytest.approx(3 / 5)

    def test_hallucination_rate_uses_absent_fields(self):
        overall = self._overall()
        # One spurious ISBN over two absent ISBN slots.
        assert overall.hallucination_rate() == pytest.approx(0.5)

    def test_missing_field_detection_accuracy(self):
        overall = self._overall()
        assert overall.missing_field_detection_accuracy() == pytest.approx(0.5)

    def test_per_language_splits_by_sample_prefix(self):
        overall = self._overall()
        assert set(overall.per_language()) == {"tel"}

    def test_report_is_serialisable(self):
        import json

        payload = self._overall().to_report()
        assert json.loads(json.dumps(payload))["overall"]["books"] == 2


class TestUncertainty:
    def test_bootstrap_collapses_with_one_unit(self):
        stats = bootstrap_ci([0.5])
        assert stats["n"] == 1
        assert stats["lo"] == stats["hi"] == 0.5

    def test_bootstrap_is_deterministic(self):
        values = [0.1, 0.4, 0.9, 0.2, 0.6]
        assert bootstrap_ci(values) == bootstrap_ci(values)

    def test_paired_delta_detects_a_win(self):
        baseline = {"tel/a": 0.2, "tel/b": 0.3, "tel/c": 0.25, "tel/d": 0.4}
        variant = {"tel/a": 0.6, "tel/b": 0.7, "tel/c": 0.65, "tel/d": 0.8}
        result = paired_delta_ci(baseline, variant)
        assert result["verdict"] == "better"
        assert result["lo"] > 0

    def test_paired_delta_detects_a_loss(self):
        baseline = {"tel/a": 0.6, "tel/b": 0.7, "tel/c": 0.65, "tel/d": 0.8}
        variant = {"tel/a": 0.2, "tel/b": 0.3, "tel/c": 0.25, "tel/d": 0.4}
        assert paired_delta_ci(baseline, variant)["verdict"] == "worse"

    def test_paired_delta_is_inconclusive_on_identical_runs(self):
        values = {"tel/a": 0.5, "tel/b": 0.6, "tel/c": 0.55}
        assert paired_delta_ci(values, dict(values))["verdict"] == "inconclusive"

    def test_paired_delta_needs_two_books(self):
        assert paired_delta_ci({"tel/a": 0.1}, {"tel/a": 0.9})["verdict"] == "insufficient-data"
