from __future__ import annotations

import json
import logging
from typing import Callable

import httpx
import instructor
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


class LlmService:
    def __init__(self, ollama_url: str | None = None):
        self._ollama_url = ollama_url or settings.ollama_url
        self._client: instructor.AsyncInstructor | None = None
        self._http_client: httpx.AsyncClient | None = None

    @property
    def client(self) -> instructor.AsyncInstructor:
        if self._client is None:
            self._client = instructor.from_openai(
                openai.AsyncOpenAI(
                    base_url=f"{self._ollama_url}/v1",
                    api_key="ollama",
                ),
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

    async def extract_batch(
        self,
        ocr_text: str,
        batch_name: str,
        batch_schema: type[BaseModel],
        model: str = "airavata",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        language: str = "tel",
        page_count: int = 1,
        system_prompt_override: str | None = None,
        extraction_prompt_override: str | None = None,
    ) -> tuple[BaseModel, str, dict]:
        system_prompt = render_system_prompt(language, override=system_prompt_override)
        extraction_prompt = render_extraction_prompt(
            batch_name=batch_name,
            ocr_text=ocr_text,
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
                timeout=httpx.Timeout(300.0, connect=30.0),
            )

            raw_response_text = result.model_dump_json()
            usage_stats = {"status": "success"}

        except instructor.exceptions.InstructorRetryException as e:
            logger.warning("Instructor retry exhausted for batch '%s': %s", batch_name, e)
            last_response = e.last_completion
            if last_response and hasattr(last_response, "choices") and last_response.choices:
                raw_response_text = last_response.choices[0].message.content or ""
            result = _fallback_parse(raw_response_text, batch_schema)
            usage_stats = {"status": "fallback", "error": str(e)}

        except (httpx.TimeoutException, openai.APITimeoutError) as e:
            logger.error("Timeout for batch '%s': %s", batch_name, e)
            result = _empty_batch(batch_schema)
            usage_stats = {"status": "timeout", "error": str(e)}

        except Exception as e:
            logger.error("LLM call failed for batch '%s': %s", batch_name, e)
            raw_response_text = str(e)
            result = _empty_batch(batch_schema)
            usage_stats = {"status": "error", "error": str(e)}

        return result, raw_response_text, usage_stats

    async def run_full_extraction(
        self,
        ocr_text: str,
        model: str = "airavata",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        language: str = "tel",
        page_count: int = 1,
        system_prompt_override: str | None = None,
        extraction_prompt_override: str | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
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
                progress_callback(i + 1, total_batches, batch_name)

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


llm_service = LlmService()
