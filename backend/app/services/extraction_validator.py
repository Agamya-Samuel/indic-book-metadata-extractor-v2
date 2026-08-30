"""Field-level diff and accuracy metrics for the extraction harness.

Compares a predicted metadata dict against a ground-truth dict and
produces per-field metrics:

  * exact_match        — predicted == expected after light normalization
  * normalized_match   — diacritics stripped, case-folded, whitespace collapsed
  * token_f1           — token-level F1 on whitespace-split tokens
  * present_tp/fp/fn   — whether the field is "present" (non-null/non-empty)

The accuracy harness in scripts/evaluate_extraction.py aggregates these
into per-book and overall reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.services.extractors import _normalize


@dataclass
class FieldResult:
    field_name: str
    expected: str | None
    predicted: str | None
    expected_present: bool
    predicted_present: bool
    exact_match: bool
    normalized_match: bool
    token_precision: float
    token_recall: float
    token_f1: float
    script_match: bool | None = None  # True if expected/predicted share the dominant script


def _is_present(v: object) -> bool:
    if v is None:
        return False
    s = str(v).strip()
    if not s:
        return False
    # Treat placeholder strings as absent.
    placeholders = {"n/a", "na", "null", "none", "unknown", "not found", "-", ""}
    return _normalize(s) not in placeholders


def _dominant_script(s: str) -> str:
    """Return the dominant Unicode script of a string.

    Returns "tel" (Telugu), "hin" (Devanagari), "lat" (Latin), or
    "other" if no dominant script. Used to detect when expected and
    predicted are in different scripts (e.g. Telugu vs Latin
    transliteration) so we can flag the comparison as not directly
    comparable.
    """
    if not s:
        return "other"
    counts = {"tel": 0, "hin": 0, "lat": 0}
    for ch in s:
        cp = ord(ch)
        if 0x0C00 <= cp <= 0x0C7F:
            counts["tel"] += 1
        elif 0x0900 <= cp <= 0x097F:
            counts["hin"] += 1
        elif 0x0041 <= cp <= 0x007A or 0x0061 <= cp <= 0x007A:
            counts["lat"] += 1
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else "other"


def _tokens(s: str) -> set[str]:
    return {t for t in _normalize(s).split() if t}


def evaluate_field(field_name: str, expected: object, predicted: object) -> FieldResult:
    exp_present = _is_present(expected)
    pred_present = _is_present(predicted)

    exp_str = str(expected).strip() if expected is not None else ""
    pred_str = str(predicted).strip() if predicted is not None else ""

    exact = exp_present and pred_present and exp_str == pred_str
    norm = exp_present and pred_present and _normalize(exp_str) == _normalize(pred_str)

    # Track whether the two values are even in the same script. If not,
    # strict equality will be False by construction and the per-field F1
    # is uninformative. We surface this as ``script_match`` so the report
    # can highlight the case (and so the team knows to add
    # transliteration or change the LLM output script).
    script_match: bool | None = None
    if exp_present and pred_present:
        script_match = _dominant_script(exp_str) == _dominant_script(pred_str)

    if exp_present and pred_present:
        exp_tokens = _tokens(exp_str)
        pred_tokens = _tokens(pred_str)
        if exp_tokens or pred_tokens:
            inter = exp_tokens & pred_tokens
            precision = len(inter) / len(pred_tokens) if pred_tokens else 0.0
            recall = len(inter) / len(exp_tokens) if exp_tokens else 0.0
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )
        else:
            precision = recall = f1 = 0.0
    else:
        precision = recall = f1 = 0.0

    return FieldResult(
        field_name=field_name,
        expected=exp_str if exp_present else None,
        predicted=pred_str if pred_present else None,
        expected_present=exp_present,
        predicted_present=pred_present,
        exact_match=exact,
        normalized_match=norm,
        token_precision=round(precision, 3),
        token_recall=round(recall, 3),
        token_f1=round(f1, 3),
        script_match=script_match,
    )


@dataclass
class BookEvaluation:
    sample_id: str
    field_results: list[FieldResult] = field(default_factory=list)

    @property
    def expected_fields(self) -> list[str]:
        return [r.field_name for r in self.field_results if r.expected_present]

    @property
    def predicted_fields(self) -> list[str]:
        return [r.field_name for r in self.field_results if r.predicted_present]

    def tp(self) -> int:
        return sum(1 for r in self.field_results if r.expected_present and r.predicted_present)

    def fp(self) -> int:
        return sum(1 for r in self.field_results if r.predicted_present and not r.expected_present)

    def fn(self) -> int:
        return sum(1 for r in self.field_results if r.expected_present and not r.predicted_present)

    def mean_token_f1(self) -> float:
        scored = [r.token_f1 for r in self.field_results if r.expected_present]
        return round(sum(scored) / len(scored), 3) if scored else 0.0

    def exact_match_rate(self) -> float:
        scored = [r for r in self.field_results if r.expected_present]
        if not scored:
            return 0.0
        return round(sum(1 for r in scored if r.exact_match) / len(scored), 3)

    def normalized_match_rate(self) -> float:
        scored = [r for r in self.field_results if r.expected_present]
        if not scored:
            return 0.0
        return round(sum(1 for r in scored if r.normalized_match) / len(scored), 3)


def evaluate_book(
    sample_id: str,
    expected: dict,
    predicted: dict,
    all_fields: Iterable[str],
) -> BookEvaluation:
    """Evaluate one book's predicted metadata against the ground truth."""
    evaln = BookEvaluation(sample_id=sample_id)
    for field_name in all_fields:
        exp = expected.get(field_name)
        pred = predicted.get(field_name)
        evaln.field_results.append(evaluate_field(field_name, exp, pred))
    return evaln


@dataclass
class OverallEvaluation:
    books: list[BookEvaluation]

    def total_tp(self) -> int:
        return sum(b.tp() for b in self.books)

    def total_fp(self) -> int:
        return sum(b.fp() for b in self.books)

    def total_fn(self) -> int:
        return sum(b.fn() for b in self.books)

    def micro_precision(self) -> float:
        tp, fp = self.total_tp(), self.total_fp()
        return round(tp / (tp + fp), 3) if (tp + fp) > 0 else 0.0

    def micro_recall(self) -> float:
        tp, fn = self.total_tp(), self.total_fn()
        return round(tp / (tp + fn), 3) if (tp + fn) > 0 else 0.0

    def micro_f1(self) -> float:
        p, r = self.micro_precision(), self.micro_recall()
        return round(2 * p * r / (p + r), 3) if (p + r) > 0 else 0.0

    def macro_token_f1(self) -> float:
        scores = [b.mean_token_f1() for b in self.books]
        return round(sum(scores) / len(scores), 3) if scores else 0.0

    def per_field_f1(self) -> dict[str, dict[str, float]]:
        """Per-field precision/recall/F1 across all books."""
        per_field: dict[str, dict[str, int]] = {}
        for b in self.books:
            for r in b.field_results:
                if r.field_name not in per_field:
                    per_field[r.field_name] = {"tp": 0, "fp": 0, "fn": 0}
                if r.predicted_present and r.expected_present:
                    per_field[r.field_name]["tp"] += 1
                elif r.predicted_present and not r.expected_present:
                    per_field[r.field_name]["fp"] += 1
                elif r.expected_present and not r.predicted_present:
                    per_field[r.field_name]["fn"] += 1
        out: dict[str, dict[str, float]] = {}
        for name, c in per_field.items():
            tp, fp, fn = c["tp"], c["fp"], c["fn"]
            p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            r_ = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * p * r_ / (p + r_) if (p + r_) > 0 else 0.0
            out[name] = {
                "precision": round(p, 3),
                "recall": round(r_, 3),
                "f1": round(f1, 3),
                "support": tp + fn,
            }
        return out
