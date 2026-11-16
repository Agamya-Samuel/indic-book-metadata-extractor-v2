"""Field-level diff and accuracy metrics for the extraction harness.

Compares a predicted metadata dict against a ground-truth dict and
produces per-field metrics:

  * exact_match        — predicted == expected after light normalization
  * normalized_match   — diacritics stripped, case-folded, whitespace collapsed
  * fuzzy_match        — transcription-level match (token F1 or char ratio),
                         applied only to free-text fields; identifiers such as
                         ISBN and page counts must match exactly
  * token_f1           — token-level F1 on whitespace-split tokens
  * present_tp/fp/fn   — whether the field is "present" (non-null/non-empty)

Two scoring tracks exist and must not be confused:

  * **presence** (``tp``/``fp``/``fn``, ``micro_*``, ``per_field_f1``) answers
    "did the model fill the field at all". This is what the historical reports
    (``gt-eval-*``) measured.
  * **value** (``value_*``, ``field_level_accuracy``) answers "is the value
    correct". A field is a value-level true positive only when it is present on
    both sides *and* the values match after normalisation.

Mask semantics (``plans/018`` §2.2): the harness passes a per-field ``mask``
derived from whether the ground-truth value appears in the text the model was
actually given.

  * ``visible``     — in the text: must be extracted, counts in recall
  * ``absent``      — not in the text: must stay null, a value is a hallucination
  * ``unroutable``  — in the book but outside the routed pages: not scored for
                      recall, reported separately as a routing defect
  * ``not_in_scan`` — nowhere in the cached text (usually catalogue-derived)
  * ``script_mismatch`` — ground truth is in a different script from the scan, so
                      presence cannot be checked by string matching
"""

from __future__ import annotations

import difflib
import random
from dataclasses import asdict, dataclass, field
from typing import Iterable

from app.services.extractors import _normalize

# Mask values for a ground-truth field.
MASK_VISIBLE = "visible"
MASK_ABSENT = "absent"
# Ground truth exists but sits outside the pages this batch was given: a routing
# defect, not a prompt defect.
MASK_UNROUTABLE = "unroutable"
# Ground truth exists (often from a catalogue) but appears nowhere in the book
# text we cached: the model could not extract it from this input at all.
MASK_NOT_IN_SCAN = "not_in_scan"
# Ground truth is written in a different script from the scan (e.g. a Latin
# transliteration of a Devanagari title). Presence cannot be verified by string
# matching, so it must not be scored as an OCR miss.
MASK_SCRIPT_MISMATCH = "script_mismatch"

UNSCORED_MASKS = frozenset({MASK_UNROUTABLE, MASK_NOT_IN_SCAN, MASK_SCRIPT_MISMATCH})

# Free-text fields tolerate transcription noise; identifiers do not. A
# truncated year scored as "fuzzy correct" would hide exactly the error this
# harness exists to find.
EXACT_ONLY_FIELDS = frozenset(
    {
        "isbn",
        "pages",
        "publication_date",
        "edition_number",
        "volume",
        "serial_number_in_series",
        "part_of_the_set",
        "inception",
    }
)

FUZZY_TOKEN_F1 = 0.80
FUZZY_CHAR_RATIO = 0.85


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
    fuzzy_match: bool = False
    mask: str | None = None

    @property
    def value_correct(self) -> bool:
        """A field counts as correct at the value level when it fuzzy-matches."""
        return self.expected_present and self.predicted_present and self.fuzzy_match

    @property
    def is_hallucination(self) -> bool:
        """A value emitted where the ground truth (and the text) has none."""
        return self.predicted_present and not self.expected_present


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


def _char_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _fuzzy_match(field_name: str, exp_str: str, pred_str: str, token_f1: float) -> bool:
    """Transcription-level equality for free-text fields.

    Identifiers (ISBN, page counts, years, edition numbers) never get fuzzy
    credit: a truncated year or a one-digit ISBN difference is a wrong answer,
    and character-similarity scoring would report it as correct.
    """
    if _normalize(exp_str) == _normalize(pred_str):
        return True
    if field_name in EXACT_ONLY_FIELDS:
        return False
    if token_f1 >= FUZZY_TOKEN_F1:
        return True
    return _char_ratio(exp_str, pred_str) >= FUZZY_CHAR_RATIO


def evaluate_field(
    field_name: str,
    expected: object,
    predicted: object,
    *,
    mask: str | None = None,
) -> FieldResult:
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
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        else:
            precision = recall = f1 = 0.0
    else:
        precision = recall = f1 = 0.0

    fuzzy = exp_present and pred_present and _fuzzy_match(field_name, exp_str, pred_str, f1)

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
        fuzzy_match=fuzzy,
        mask=mask,
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

    @property
    def language(self) -> str | None:
        """Language code from a ``<lang>/<slug>`` sample id, when present."""
        prefix, sep, _ = self.sample_id.partition("/")
        return prefix if sep and len(prefix) == 3 else None

    @property
    def scored_results(self) -> list[FieldResult]:
        """Fields that may be scored: everything except the two unscored masks.

        ``unroutable`` fields exist in the book but outside the pages this batch
        was given; ``not_in_scan`` fields exist in the ground truth but nowhere
        in the text at all (usually catalogue-derived). Scoring either as a
        recall miss would blame the prompt for something the prompt cannot fix,
        so both are excluded from every aggregate and reported separately.
        """
        return [r for r in self.field_results if r.mask not in UNSCORED_MASKS]

    @property
    def unroutable_results(self) -> list[FieldResult]:
        return [r for r in self.field_results if r.mask in UNSCORED_MASKS]

    def tp(self) -> int:
        return sum(1 for r in self.scored_results if r.expected_present and r.predicted_present)

    def fp(self) -> int:
        return sum(1 for r in self.scored_results if r.predicted_present and not r.expected_present)

    def fn(self) -> int:
        return sum(1 for r in self.scored_results if r.expected_present and not r.predicted_present)

    def mean_token_f1(self) -> float:
        scored = [r.token_f1 for r in self.scored_results if r.expected_present]
        return round(sum(scored) / len(scored), 3) if scored else 0.0

    def exact_match_rate(self) -> float:
        scored = [r for r in self.scored_results if r.expected_present]
        if not scored:
            return 0.0
        return round(sum(1 for r in scored if r.exact_match) / len(scored), 3)

    def normalized_match_rate(self) -> float:
        scored = [r for r in self.scored_results if r.expected_present]
        if not scored:
            return 0.0
        return round(sum(1 for r in scored if r.normalized_match) / len(scored), 3)

    # -- value-level (correctness) counts ---------------------------------

    def value_correct_count(self) -> int:
        return sum(1 for r in self.scored_results if r.value_correct)

    def value_expected_count(self) -> int:
        return sum(1 for r in self.scored_results if r.expected_present)

    def absent_count(self) -> int:
        return sum(1 for r in self.scored_results if not r.expected_present)

    def correct_absent_count(self) -> int:
        return sum(1 for r in self.scored_results if not r.expected_present and not r.predicted_present)

    def hallucination_count(self) -> int:
        return sum(1 for r in self.scored_results if r.is_hallucination)

    def mask_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.field_results:
            key = r.mask or "unmasked"
            counts[key] = counts.get(key, 0) + 1
        return counts

    def field_level_accuracy(self) -> float:
        """Share of visible ground-truth fields whose value is correct."""
        expected = self.value_expected_count()
        return round(self.value_correct_count() / expected, 3) if expected else 0.0


def evaluate_book(
    sample_id: str,
    expected: dict,
    predicted: dict,
    all_fields: Iterable[str],
    ignore_fields: Iterable[str] | None = None,
    mask: dict[str, str] | None = None,
) -> BookEvaluation:
    """Evaluate one book's predicted metadata against the ground truth.

    ``ignore_fields`` names fields that must not be scored — e.g. values the
    ground-truth scaffold flagged ``prefilled_needs_verification`` because they
    came from model prefill rather than a verified source. Excluding them stops
    the model from being scored against its own output (circularity) while the
    rest of the book's fields are still evaluated.

    ``mask`` maps field name → :data:`MASK_VISIBLE` / :data:`MASK_ABSENT` /
    :data:`MASK_UNROUTABLE` (see ``scripts/prompt_eval/build_mask.py``). Fields
    without an entry are scored as before, so existing callers are unaffected.
    """
    skip = set(ignore_fields or ())
    mask = mask or {}
    evaln = BookEvaluation(sample_id=sample_id)
    for field_name in all_fields:
        if field_name in skip:
            continue
        exp = expected.get(field_name)
        pred = predicted.get(field_name)
        evaln.field_results.append(evaluate_field(field_name, exp, pred, mask=mask.get(field_name)))
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

    # -- value-level aggregates -------------------------------------------

    def value_expected_count(self) -> int:
        return sum(b.value_expected_count() for b in self.books)

    def value_correct_count(self) -> int:
        return sum(b.value_correct_count() for b in self.books)

    def field_level_accuracy(self) -> float:
        total = self.value_expected_count()
        return round(self.value_correct_count() / total, 3) if total else 0.0

    def value_micro_precision(self) -> float:
        """TP = present and correct; FP = present but wrong or spurious."""
        correct = self.value_correct_count()
        predicted = sum(1 for b in self.books for r in b.scored_results if r.predicted_present)
        return round(correct / predicted, 3) if predicted else 0.0

    def value_micro_recall(self) -> float:
        return self.field_level_accuracy()

    def value_micro_f1(self) -> float:
        p, r = self.value_micro_precision(), self.value_micro_recall()
        return round(2 * p * r / (p + r), 3) if (p + r) > 0 else 0.0

    def absent_count(self) -> int:
        return sum(b.absent_count() for b in self.books)

    def missing_field_detection_accuracy(self) -> float:
        """Share of text-absent fields correctly left null.

        This is the direct measure of "does it stay quiet when the book does
        not say" — the complement of the hallucination rate.
        """
        absent = self.absent_count()
        correct = sum(b.correct_absent_count() for b in self.books)
        return round(correct / absent, 3) if absent else 0.0

    def hallucination_rate(self) -> float:
        absent = self.absent_count()
        hallucinations = sum(b.hallucination_count() for b in self.books)
        return round(hallucinations / absent, 3) if absent else 0.0

    def unroutable_count(self) -> int:
        return sum(len(b.unroutable_results) for b in self.books)

    def mask_totals(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for book in self.books:
            for key, value in book.mask_counts().items():
                totals[key] = totals.get(key, 0) + value
        return totals

    def per_language(self) -> dict[str, dict[str, float]]:
        """Value-level summary per language code, from the sample-id prefix."""
        buckets: dict[str, list[BookEvaluation]] = {}
        for book in self.books:
            buckets.setdefault(book.language or "unknown", []).append(book)
        out: dict[str, dict[str, float]] = {}
        for language, books in sorted(buckets.items()):
            subset = OverallEvaluation(books=books)
            out[language] = {
                "field_level_accuracy": subset.field_level_accuracy(),
                "presence_f1": subset.micro_f1(),
                "value_f1": subset.value_micro_f1(),
                "hallucination_rate": subset.hallucination_rate(),
                "books": len(books),
            }
        return out

    def per_field_value(self) -> dict[str, dict[str, float]]:
        """Value-level precision/recall/F1 per field (correctness, not presence)."""
        counts: dict[str, dict[str, int]] = {}
        for book in self.books:
            for r in book.scored_results:
                c = counts.setdefault(r.field_name, {"correct": 0, "predicted": 0, "expected": 0})
                if r.expected_present:
                    c["expected"] += 1
                if r.predicted_present:
                    c["predicted"] += 1
                if r.value_correct:
                    c["correct"] += 1
        out: dict[str, dict[str, float]] = {}
        for name, c in counts.items():
            p = c["correct"] / c["predicted"] if c["predicted"] else 0.0
            r_ = c["correct"] / c["expected"] if c["expected"] else 0.0
            f1 = 2 * p * r_ / (p + r_) if (p + r_) > 0 else 0.0
            out[name] = {
                "precision": round(p, 3),
                "recall": round(r_, 3),
                "f1": round(f1, 3),
                "support": c["expected"],
            }
        return out

    def to_report(self) -> dict:
        """Serialisable summary used by ``scripts/prompt_eval/score_eval.py``."""
        return {
            "overall": {
                "micro_precision": self.micro_precision(),
                "micro_recall": self.micro_recall(),
                "micro_f1": self.micro_f1(),
                "macro_token_f1": self.macro_token_f1(),
                "field_level_accuracy": self.field_level_accuracy(),
                "value_f1": self.value_micro_f1(),
                "missing_field_detection_accuracy": self.missing_field_detection_accuracy(),
                "hallucination_rate": self.hallucination_rate(),
                "unroutable_fields": self.unroutable_count(),
                "mask_totals": self.mask_totals(),
                "books": len(self.books),
            },
            "per_language": self.per_language(),
            "per_field_presence": self.per_field_f1(),
            "per_field_value": self.per_field_value(),
            "books": [
                {
                    "sample_id": b.sample_id,
                    "language": b.language,
                    "tp": b.tp(),
                    "fp": b.fp(),
                    "fn": b.fn(),
                    "field_level_accuracy": b.field_level_accuracy(),
                    "mean_token_f1": b.mean_token_f1(),
                    "exact_match_rate": b.exact_match_rate(),
                    "normalized_match_rate": b.normalized_match_rate(),
                    "hallucinations": b.hallucination_count(),
                    # Denominators: paired comparisons recompute per-book rates
                    # and need the counts, not just the aggregate.
                    "absent_fields": b.absent_count(),
                    "correct_absent": b.correct_absent_count(),
                    "value_correct": b.value_correct_count(),
                    "value_expected": b.value_expected_count(),
                    "unroutable": len(b.unroutable_results),
                    "field_results": [asdict(r) for r in b.field_results],
                }
                for b in self.books
            ],
        }

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


# ---------------------------------------------------------------------------
# Uncertainty: a variant only "wins" when its confidence interval excludes zero
# ---------------------------------------------------------------------------

BOOK_METRICS = {
    "field_level_accuracy": lambda b: b.field_level_accuracy(),
    "presence_f1": lambda b: _f1(b.tp(), b.fp(), b.fn()),
    "mean_token_f1": lambda b: b.mean_token_f1(),
    "hallucination_rate": lambda b: b.hallucination_count() / b.absent_count() if b.absent_count() else 0.0,
}


def _f1(tp: int, fp: int, fn: int) -> float:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return 2 * p * r / (p + r) if (p + r) else 0.0


def book_metric_series(books: list[BookEvaluation], metric: str) -> dict[str, float]:
    """Per-book metric values keyed by sample id, for paired comparisons."""
    fn = BOOK_METRICS[metric]
    return {b.sample_id: float(fn(b)) for b in books}


def bootstrap_ci(
    values: list[float],
    *,
    iters: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, float]:
    """Percentile bootstrap over independent units (books).

    With fewer than two units there is nothing to resample; the interval
    collapses to the point estimate and ``n`` says so, which is the honest
    answer rather than a fabricated range.
    """
    if not values:
        return {"mean": 0.0, "lo": 0.0, "hi": 0.0, "n": 0}
    mean = sum(values) / len(values)
    if len(values) < 2:
        return {"mean": round(mean, 4), "lo": round(mean, 4), "hi": round(mean, 4), "n": 1}

    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(iters):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = int((alpha / 2) * iters)
    hi_idx = min(iters - 1, int((1 - alpha / 2) * iters) - 1)
    return {
        "mean": round(mean, 4),
        "lo": round(means[lo_idx], 4),
        "hi": round(means[hi_idx], 4),
        "n": n,
    }


def paired_delta_ci(
    baseline: dict[str, float],
    variant: dict[str, float],
    *,
    iters: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict:
    """Bootstrap CI of ``variant - baseline`` over books present in both.

    Pairing by book controls for how much harder some books are than others,
    which is why it is preferred over comparing two independent aggregates.
    The verdict is deliberately conservative: ``better``/``worse`` only when
    the interval excludes zero, otherwise ``inconclusive``.
    """
    shared = sorted(set(baseline) & set(variant))
    deltas = [variant[k] - baseline[k] for k in shared]
    stats = bootstrap_ci(deltas, iters=iters, seed=seed, alpha=alpha)
    if len(shared) < 2:
        verdict = "insufficient-data"
    elif stats["lo"] > 0:
        verdict = "better"
    elif stats["hi"] < 0:
        verdict = "worse"
    else:
        verdict = "inconclusive"
    return {
        "mean_delta": stats["mean"],
        "lo": stats["lo"],
        "hi": stats["hi"],
        "n": len(shared),
        "verdict": verdict,
        "books_improved": sum(1 for d in deltas if d > 1e-9),
        "books_degraded": sum(1 for d in deltas if d < -1e-9),
        "books_tied": sum(1 for d in deltas if abs(d) <= 1e-9),
    }
