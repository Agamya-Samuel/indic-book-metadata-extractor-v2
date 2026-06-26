from __future__ import annotations

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

    # Context window management for Ollama models (1024 tokens)
    # Reserve tokens for: system prompt (~200), extraction template (~400), output (~256)
    MAX_OCR_CHARS: int = 1500  # ~375 tokens, safe for 1024 context window

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
        model: str = "airavata",
        temperature: float = 0.3,
        max_tokens: int = 256,
        language: str = "tel",
        page_count: int = 1,
        system_prompt_override: str | None = None,
        extraction_prompt_override: str | None = None,
    ) -> tuple[BaseModel, str, dict]:
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
            usage_stats = {"status": "success"}
            self._record_success()

        except InstructorRetryException as e:
            logger.warning("Instructor retry exhausted for batch '%s': %s", batch_name, e)
            last_response = e.last_completion
            if last_response and hasattr(last_response, "choices") and last_response.choices:
                raw_response_text = last_response.choices[0].message.content or ""
            result = _fallback_parse(raw_response_text, batch_schema)
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

        return result, raw_response_text, usage_stats

    @newrelic.agent.function_trace(name="LLM: Run Full Extraction", group="Custom")
    async def run_full_extraction(
        self,
        ocr_text: str,
        model: str = "airavata",
        temperature: float = 0.3,
        max_tokens: int = 256,
        language: str = "tel",
        page_count: int = 1,
        system_prompt_override: str | None = None,
        extraction_prompt_override: str | None = None,
        progress_callback: Callable[[int, int, str], Awaitable[None]] | None = None,
    ) -> tuple[FullMetadata, list[dict]]:
        merged_data: dict = {}
        batch_results: list[dict] = []
        total_batches = len(BATCH_FIELD_ORDER)
        errors: list[str] = []

        for i, batch_name in enumerate(BATCH_FIELD_ORDER):
            batch_schema = METADATA_BATCHES[batch_name]

            result, raw_response, usage = await self.extract_batch(
                ocr_text=ocr_text,
                batch_name=batch_name,
                batch_schema=batch_schema,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                language=language,
                page_count=page_count,
                system_prompt_override=system_prompt_override,
                extraction_prompt_override=extraction_prompt_override,
            )

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
                }
            )

            if usage.get("status") != "success":
                errors.append(f"Batch '{batch_name}': {usage.get('status')} - {usage.get('error', 'unknown')}")

            if progress_callback:
                await progress_callback(i + 1, total_batches, batch_name)

        if errors:
            logger.warning("LLM extraction completed with errors: %s", errors)

        metadata = FullMetadata(**merged_data)
        return metadata, batch_results

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
    if not raw_text:
        return _empty_batch(batch_schema)

    try:
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = raw_text[start:end]
            parsed = json.loads(json_str)
            return batch_schema(**parsed)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Fallback parse failed: %s", e)

    return _empty_batch(batch_schema)


llm_service = LLMService()
