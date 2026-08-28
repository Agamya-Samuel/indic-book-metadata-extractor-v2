"""Hybrid extraction orchestration.

Runs regex → dictionary → (NER) → LLM in that order, only escalating a
field to the next tier when the previous tier returned None. The LLM is
asked to fill the remaining gaps, not the whole 52 fields.

The orchestrator is intentionally simple — no parallel fan-out here, no
sophisticated merging. The point is to spend LLM tokens only where they
buy accuracy, and to attach provenance to every field that gets filled.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Iterable

from app.services.extractors import ExtractedField
from app.services.extractors.dictionary_extractors import REGISTRY as DICT_REGISTRY
from app.services.extractors.regex_extractors import REGISTRY as REGEX_REGISTRY


# Fields handled by cheap extractors. Everything else is sent to the LLM.
NON_LLM_FIELDS: set[str] = set(REGEX_REGISTRY) | set(DICT_REGISTRY)


async def run_hybrid_extraction(
    full_text: str,
    pages: list[tuple[int, str]],
    llm_fill_remaining: Callable[[set[str]], Awaitable[dict[str, ExtractedField]]],
    target_fields: Iterable[str] | None = None,
) -> dict[str, ExtractedField]:
    """Run the cheap extractors first, then call the LLM for the gaps.

    ``llm_fill_remaining`` is injected so the orchestrator doesn't need
    to know about Instructor/Ollama. It receives the set of field names
    that the cheap extractors couldn't resolve and must return an
    ExtractedField for each.

    ``target_fields`` restricts which fields the orchestrator will even
    try to fill. If None, the union of all known fields is used.
    """
    targets = set(target_fields) if target_fields is not None else None

    results: dict[str, ExtractedField] = {}

    # Tier 1: regex.
    for field_name, fn in REGEX_REGISTRY.items():
        if targets is not None and field_name not in targets:
            continue
        try:
            extracted = fn(full_text, pages)
        except Exception:
            extracted = None
        if extracted is not None:
            results[field_name] = extracted

    # Tier 2: dictionary.
    for field_name, fn in DICT_REGISTRY.items():
        if field_name in results:
            continue
        if targets is not None and field_name not in targets:
            continue
        try:
            extracted = fn(full_text, pages)
        except Exception:
            extracted = None
        if extracted is not None:
            results[field_name] = extracted

    # Tier 3: LLM, only for fields we still don't have.
    if targets is not None:
        gaps = targets - set(results.keys())
        if gaps:
            llm_results = await llm_fill_remaining(gaps)
            for field_name, extracted in llm_results.items():
                existing = results.get(field_name)
                if existing is None or existing.confidence < extracted.confidence:
                    results[field_name] = extracted

    return results
