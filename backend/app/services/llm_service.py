from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Awaitable, Callable

import httpx
import instructor
import newrelic.agent
from instructor.core import InstructorRetryException
import openai
from pydantic import BaseModel

from app.core.config import settings
from app.schemas.metadata import (
    METADATA_BATCHES,
    BATCH_FIELD_ORDER,
    FullMetadata,
)
from app.services.batch_routing import (
    PageText,
    assemble_ocr_text,
    select_pages_for_batch,
)
from app.services.extractors import ExtractedField
from app.services.extractors.hybrid import (
    NON_LLM_FIELDS,
    run_hybrid_extraction,
)
from app.schemas.metadata import FIELD_TO_BATCH
from app.services.prompts import (
    render_system_prompt,
    render_extraction_prompt,
)

logger = logging.getLogger(__name__)


class CircuitBreakerOpen(Exception):
    """Raised when the LLM circuit breaker is open (service unavailable)."""
    pass


class LLMService:
    # Circuit breaker configuration
    FAILURE_THRESHOLD: int = 3
    COOLDOWN_SECONDS: float = 60.0

    # Context window management for Ollama models (num_ctx=8192 in Modelfile).
    # With max_tokens=512 reserved for output, that leaves ~7680 tokens for input.
    # Indic script tokenizes at roughly 2-4 chars/token (BPE splits Unicode
    # code-point fragments), so 2500 chars of Telugu/Devanagari text fits
    # comfortably with the system prompt + extraction template + output budget.
    # We deliberately cap per-batch text to 2500 to keep the model focused on
    # the routed page region rather than letting later pages dominate.
    MAX_OCR_CHARS: int = 2500  # per-batch budget under num_ctx=8192
    MAX_PARALLEL_BATCHES: int = 2  # safe for CPU Ollama; raise if GPU

    def __init__(self, ollama_url: str | None = None):
        self._ollama_url = ollama_url or settings.ollama_url
        self._client: instructor.AsyncInstructor | None = None
        self._http_client: httpx.AsyncClient | None = None
        # Circuit breaker state
        self._consecutive_failures: int = 0
        self._circuit_opened_at: float | None = None

    @property
    def client(self) -> instructor.AsyncInstructor:
        if self._client is None:
            self._client = instructor.from_openai(
                openai.AsyncOpenAI(
                    base_url=f"{self._ollama_url}/v1",
                    api_key="ollama",
                ),
                mode=instructor.Mode.MD_JSON,
            )
        return self._client

    @property
    def http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self._ollama_url,
                timeout=httpx.Timeout(30.0),
            )
        return self._http_client

    @newrelic.agent.function_trace(name="LLM: Extract Batch", group="Custom")
    async def extract_batch(
        self,
        ocr_text: str,
        batch_name: str,
        batch_schema: type[BaseModel],
        model: str = "qwen2.5",
        temperature: float = 0.3,
        max_tokens: int = 256,
        language: str = "tel",
        page_count: int = 1,
        system_prompt_override: str | None = None,
        extraction_prompt_override: str | None = None,
    ) -> tuple[BaseModel, str, dict, str]:
        """Run one batch.

        Returns ``(result, raw_response, usage, extraction_prompt)`` where
        ``extraction_prompt`` is the exact prompt sent to the LLM so the
        persist step can store an honest audit trail.
        """
        # Check circuit breaker before attempting LLM call
        self._check_circuit_breaker()

        newrelic.agent.add_custom_attribute("batch_name", batch_name)
        newrelic.agent.add_custom_attribute("model", model)
        newrelic.agent.add_custom_attribute("language", language)

        # Truncate OCR text to fit within context window
        truncated_text = ocr_text[: self.MAX_OCR_CHARS]
        if len(ocr_text) > self.MAX_OCR_CHARS:
            logger.info(
                "Truncated OCR text from %d to %d chars for batch '%s'",
                len(ocr_text),
                len(truncated_text),
                batch_name,
            )

        system_prompt = render_system_prompt(language, override=system_prompt_override)
        extraction_prompt = render_extraction_prompt(
            batch_name=batch_name,
            ocr_text=truncated_text,
            language=language,
            page_count=page_count,
            override=extraction_prompt_override,
        )

        raw_response_text = ""
        usage_stats: dict = {}

        try:
            result = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": extraction_prompt},
                ],
                response_model=batch_schema,
                temperature=temperature,
                max_tokens=max_tokens,
                max_retries=2,
                timeout=1200.0,
            )

            raw_response_text = result.model_dump_json()
            # Distinguish "LLM succeeded but returned nothing useful" from
            # "LLM succeeded and returned real values". The former almost
            # always means context truncation; the UI / job status must
            # surface this so users know the batch produced zero evidence.
            if all(v is None for v in result.model_dump().values()):
                usage_stats = {"status": "empty_response"}
            else:
                usage_stats = {"status": "success"}
            self._record_success()

        except InstructorRetryException as e:
            logger.warning("Instructor retry exhausted for batch '%s': %s", batch_name, e)
            last_response = e.last_completion
            if last_response and hasattr(last_response, "choices") and last_response.choices:
                raw_response_text = last_response.choices[0].message.content or ""
            result = _fallback_parse(raw_response_text, batch_schema)
            if all(v is None for v in result.model_dump().values()):
                usage_stats = {"status": "empty_response", "error": str(e)}
            else:
                usage_stats = {"status": "fallback", "error": str(e)}
            self._record_success()  # fallback is still a response

        except (httpx.TimeoutException, openai.APITimeoutError) as e:
            logger.error("Timeout for batch '%s': %s", batch_name, e)
            result = _empty_batch(batch_schema)
            usage_stats = {"status": "timeout", "error": str(e)}
            self._record_failure()

        except Exception as e:
            logger.error("LLM call failed for batch '%s': %s", batch_name, e)
            raw_response_text = str(e)
            result = _empty_batch(batch_schema)
            usage_stats = {"status": "error", "error": str(e)}
            self._record_failure()

        return result, raw_response_text, usage_stats, extraction_prompt

    @newrelic.agent.function_trace(name="LLM: Run Full Extraction", group="Custom")
    async def run_full_extraction(
        self,
        ocr_text: str,
        model: str = "qwen2.5",
        temperature: float = 0.3,
        max_tokens: int = 256,
        language: str = "tel",
        page_count: int = 1,
        system_prompt_override: str | None = None,
        extraction_prompt_override: str | None = None,
        progress_callback: Callable[[int, int, str], Awaitable[None]] | None = None,
        pages: list[PageText] | None = None,
    ) -> tuple[FullMetadata, list[dict]]:
        """Run all 8 metadata extraction batches and merge the results.

        When ``pages`` is provided, each batch sees the page subset most
        likely to contain its fields (see ``batch_routing.BATCH_PAGE_SLICES``)
        instead of the first 1500 chars of the full OCR blob. Batches run
        in parallel via ``asyncio.gather`` with a concurrency cap to keep
        CPU Ollama from thrashing.

        ``ocr_text`` is retained as a fallback so callers that pass a
        pre-joined string (e.g. tests) still work.
        """
        merged_data: dict = {}
        batch_results: list[dict] = []
        total_batches = len(BATCH_FIELD_ORDER)
        errors: list[str] = []

        async def _run_one(batch_name: str) -> tuple[str, BaseModel, str, dict, str]:
            batch_schema = METADATA_BATCHES[batch_name]
            if pages:
                selected = select_pages_for_batch(pages, batch_name)
                batch_text = assemble_ocr_text(selected, self.MAX_OCR_CHARS)
                batch_page_count = len(selected)
            else:
                batch_text = ocr_text
                batch_page_count = page_count

            result, raw_response, usage, prompt = await self.extract_batch(
                ocr_text=batch_text,
                batch_name=batch_name,
                batch_schema=batch_schema,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                language=language,
                page_count=batch_page_count,
                system_prompt_override=system_prompt_override,
                extraction_prompt_override=extraction_prompt_override,
            )
            return batch_name, result, raw_response, usage, prompt

        # Run batches in parallel with a concurrency cap. Sequential when
        # pages is None (legacy callers / tests) to preserve behavior.
        if pages:
            semaphore = asyncio.Semaphore(self.MAX_PARALLEL_BATCHES)

            async def _guarded(name: str) -> tuple[str, BaseModel, str, dict, str]:
                async with semaphore:
                    return await _run_one(name)

            in_flight = [
                asyncio.create_task(_guarded(name)) for name in BATCH_FIELD_ORDER
            ]
            completed = 0
            for fut in asyncio.as_completed(in_flight):
                batch_name, result, raw_response, usage, prompt = await fut
                completed += 1

                batch_data = result.model_dump(exclude_none=False)
                for key, value in batch_data.items():
                    if value is not None:
                        merged_data[key] = value

                batch_results.append(
                    {
                        "batch_name": batch_name,
                        "raw_response": raw_response,
                        "parsed_fields": batch_data,
                        "usage": usage,
                        "prompt": prompt,
                        "model": model,
                    }
                )

                if usage.get("status") != "success":
                    errors.append(
                        f"Batch '{batch_name}': {usage.get('status')} - {usage.get('error', 'unknown')}"
                    )

                if progress_callback:
                    await progress_callback(completed, total_batches, batch_name)
        else:
            for i, batch_name in enumerate(BATCH_FIELD_ORDER):
                bn, result, raw_response, usage, prompt = await _run_one(batch_name)

                batch_data = result.model_dump(exclude_none=False)
                for key, value in batch_data.items():
                    if value is not None:
                        merged_data[key] = value

                batch_results.append(
                    {
                        "batch_name": bn,
                        "raw_response": raw_response,
                        "parsed_fields": batch_data,
                        "usage": usage,
                        "prompt": prompt,
                        "model": model,
                    }
                )

                if usage.get("status") != "success":
                    errors.append(
                        f"Batch '{bn}': {usage.get('status')} - {usage.get('error', 'unknown')}"
                    )

                if progress_callback:
                    await progress_callback(i + 1, total_batches, bn)

        if errors:
            logger.warning("LLM extraction completed with errors: %s", errors)

        metadata = FullMetadata(**merged_data)
        return metadata, batch_results

    @newrelic.agent.function_trace(name="LLM: Run Hybrid Extraction", group="Custom")
    async def run_hybrid_full_extraction(
        self,
        ocr_text: str,
        model: str = "qwen2.5",
        temperature: float = 0.3,
        max_tokens: int = 256,
        language: str = "tel",
        page_count: int = 1,
        system_prompt_override: str | None = None,
        extraction_prompt_override: str | None = None,
        progress_callback: Callable[[int, int, str], Awaitable[None]] | None = None,
        pages: list[PageText] | None = None,
    ) -> tuple[FullMetadata, list[dict], dict[str, "ExtractedField"]]:
        """Hybrid extraction: cheap extractors first, LLM only for gaps.

        This is the production entry point. The 5 high-confidence fields
        (isbn, pages, publication_date, publisher, language) are resolved
        by regex/dictionary with no LLM call. The LLM is then asked only
        for the remaining ~47 fields, broken into the 8 batches as before
        but with the cheap-extractor values pre-populated so they can't be
        overwritten by hallucinated LLM output.

        Returns ``(metadata, batch_results, evidence)`` where ``evidence``
        is a ``field_name -> ExtractedField`` map carrying confidence,
        method, and source page info for every populated field.
        """
        target_fields = list(FullMetadata.model_fields.keys())
        if "custom_fields" in target_fields:
            target_fields.remove("custom_fields")

        # Build the (page_num, text) tuple list that the cheap extractors
        # expect. This is just the OCR text per page.
        page_tuples: list[tuple[int, str]] = []
        if pages:
            page_tuples = [(p.page_number, p.text) for p in pages]
        elif ocr_text:
            # Fall back to a single synthetic page if the caller didn't
            # pass per-page text. Cheap extractors still work on the blob.
            page_tuples = [(1, ocr_text)]

        batch_results: list[dict] = []

        # LLM-fill callback: only the gaps reach the LLM. We use the
        # same batch-based approach as before, but restricted to batches
        # that contain unresolved fields.
        async def _llm_fill(gaps: set[str]) -> dict[str, ExtractedField]:
            # Map gaps → which batches we still need to call.
            needed_batches: set[str] = set()
            for field_name in gaps:
                needed_batches.add(FIELD_TO_BATCH.get(field_name, "physical_extra"))

            llm_results: dict[str, ExtractedField] = {}
            if not needed_batches:
                return llm_results

            total_needed = len(needed_batches)
            semaphore = asyncio.Semaphore(self.MAX_PARALLEL_BATCHES)

            async def _guarded(bn: str):
                async with semaphore:
                    try:
                        return await self._run_one_batch_for_hybrid(
                            batch_name=bn,
                            ocr_text=ocr_text,
                            pages=pages,
                            model=model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            language=language,
                            page_count=page_count,
                            system_prompt_override=system_prompt_override,
                            extraction_prompt_override=extraction_prompt_override,
                            gap_fields={f for f in gaps if FIELD_TO_BATCH.get(f) == bn},
                        )
                    except Exception as e:
                        return e

            in_flight = [
                asyncio.create_task(_guarded(bn)) for bn in needed_batches
            ]
            completed = 0
            for fut in asyncio.as_completed(in_flight):
                outcome = await fut
                completed += 1
                if isinstance(outcome, Exception):
                    logger.error("Hybrid LLM batch failed: %s", outcome)
                    batch_results.append(
                        {
                            "batch_name": "<failed>",
                            "raw_response": "",
                            "parsed_fields": {},
                            "usage": {"status": "error", "error": str(outcome)},
                            "prompt": "",
                            "model": model,
                        }
                    )
                    if progress_callback:
                        await progress_callback(completed, total_needed, "<failed>")
                    continue
                batch_name, parsed, raw_response, usage, prompt = outcome
                batch_results.append(
                    {
                        "batch_name": batch_name,
                        "raw_response": raw_response,
                        "parsed_fields": parsed,
                        "usage": usage,
                        "prompt": prompt,
                        "model": model,
                    }
                )
                for field_name, value in parsed.items():
                    if value is not None and field_name in gaps:
                        llm_results[field_name] = ExtractedField(
                            field_name=field_name,
                            value=value,
                            confidence=0.6,  # baseline LLM confidence
                            method="llm",
                            source_page_number=None,
                            source_text_snippet=None,
                        )
                if progress_callback:
                    await progress_callback(completed, total_needed, batch_name)

            return llm_results

        results = await run_hybrid_extraction(
            full_text=ocr_text,
            pages=page_tuples,
            llm_fill_remaining=_llm_fill,
            target_fields=target_fields,
        )

        merged_data = {fn: ef.value for fn, ef in results.items() if ef.value is not None}
        metadata = FullMetadata(**merged_data)
        return metadata, batch_results, results

    async def _run_one_batch_for_hybrid(
        self,
        batch_name: str,
        ocr_text: str,
        pages: list[PageText] | None,
        model: str,
        temperature: float,
        max_tokens: int,
        language: str,
        page_count: int,
        system_prompt_override: str | None,
        extraction_prompt_override: str | None,
        gap_fields: set[str],
    ) -> tuple[str, dict, str, dict, str]:
        """Run one LLM batch and return only the gap fields it covers.

        Returns ``(batch_name, parsed_filtered, raw_response, usage, prompt)``.
        """
        batch_schema = METADATA_BATCHES[batch_name]
        if pages:
            selected = select_pages_for_batch(pages, batch_name)
            batch_text = assemble_ocr_text(selected, self.MAX_OCR_CHARS)
            batch_page_count = len(selected)
        else:
            batch_text = ocr_text
            batch_page_count = page_count

        result, raw_response, usage, prompt = await self.extract_batch(
            ocr_text=batch_text,
            batch_name=batch_name,
            batch_schema=batch_schema,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            language=language,
            page_count=batch_page_count,
            system_prompt_override=system_prompt_override,
            extraction_prompt_override=extraction_prompt_override,
        )
        # Filter to only the fields that are actually gaps, so we don't
        # accidentally clobber cheap-extractor values downstream.
        parsed_all = result.model_dump(exclude_none=False)
        parsed_filtered = {k: v for k, v in parsed_all.items() if k in gap_fields and v is not None}
        return batch_name, parsed_filtered, raw_response, usage, prompt

    async def list_available_models(self) -> list[dict]:
        try:
            resp = await self.http_client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                name = m.get("name", "")
                size_bytes = m.get("size", 0)
                models.append(
                    {
                        "name": name,
                        "size_gb": round(size_bytes / (1024**3), 2) if size_bytes else None,
                        "parameter_count": m.get("details", {}).get(
                            "parameter_size", None
                        ),
                    }
                )
            return models
        except Exception as e:
            logger.error("Failed to list models: %s", e)
            return []

    async def pull_model(self, model_name: str) -> bool:
        try:
            resp = await self.http_client.post(
                "/api/pull",
                json={"name": model_name, "stream": False},
                timeout=httpx.Timeout(600.0),
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("Failed to pull model '%s': %s", model_name, e)
            return False

    async def close(self):
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        if self._client:
            self._client = None

    # ------------------------------------------------------------------
    # Circuit breaker methods
    # ------------------------------------------------------------------
    def _check_circuit_breaker(self) -> None:
        """Raise CircuitBreakerOpen if the circuit is open and cooldown hasn't elapsed."""
        if self._consecutive_failures >= self.FAILURE_THRESHOLD:
            if self._circuit_opened_at is not None:
                elapsed = time.monotonic() - self._circuit_opened_at
                if elapsed < self.COOLDOWN_SECONDS:
                    raise CircuitBreakerOpen(
                        f"LLM service circuit breaker open. "
                        f"{self.COOLDOWN_SECONDS - elapsed:.0f}s until retry."
                    )
                else:
                    # Cooldown elapsed — allow a half-open attempt
                    logger.info("Circuit breaker cooldown elapsed, allowing half-open attempt.")
                    self._consecutive_failures = 0
                    self._circuit_opened_at = None

    def _record_success(self) -> None:
        """Reset failure counter on successful call."""
        self._consecutive_failures = 0
        self._circuit_opened_at = None

    def _record_failure(self) -> None:
        """Increment failure counter; open circuit if threshold exceeded."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.FAILURE_THRESHOLD:
            self._circuit_opened_at = time.monotonic()
            logger.warning(
                "Circuit breaker OPEN after %d consecutive failures. "
                "Cooldown: %.0fs.",
                self._consecutive_failures,
                self.COOLDOWN_SECONDS,
            )


def _empty_batch(batch_schema: type[BaseModel]) -> BaseModel:
    return batch_schema()


def _fallback_parse(raw_text: str, batch_schema: type[BaseModel]) -> BaseModel:
    """Best-effort parse of free-form LLM output.

    Walks the string with :class:`json.JSONDecoder.raw_decode` to grab the
    first valid JSON object that validates against the schema. This
    handles cases like ``{"a": 1}\\n{"b": 2}`` where naive
    ``find('{')``/``rfind('}')`` slicing picks up invalid fragments.
    """
    if not raw_text:
        return _empty_batch(batch_schema)

    decoder = json.JSONDecoder()
    cursor = 0
    last_error: Exception | None = None
    while True:
        start = raw_text.find("{", cursor)
        if start == -1:
            break
        try:
            obj, end = decoder.raw_decode(raw_text[start:])
        except json.JSONDecodeError as exc:
            last_error = exc
            cursor = start + 1
            continue
        try:
            return batch_schema(**obj)
        except Exception as exc:
            last_error = exc
            cursor = start + end
            continue
    if last_error is not None:
        logger.warning("Fallback parse failed: %s", last_error)
    return _empty_batch(batch_schema)


llm_service = LLMService()
