from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import instructor
from instructor.core import InstructorRetryException
import pytest

from app.schemas.metadata import (
    METADATA_BATCHES,
    BATCH_FIELD_ORDER,
    CoreIdentityBatch,
    FullMetadata,
)
from app.services.llm_service import LLMService, _empty_batch, _fallback_parse


class TestEmptyBatch:
    def test_returns_all_none(self):
        result = _empty_batch(CoreIdentityBatch)
        assert isinstance(result, CoreIdentityBatch)
        data = result.model_dump()
        assert all(v is None for v in data.values())


class TestFallbackParse:
    def test_valid_json_in_text(self):
        raw = 'Some text {"title": "My Book", "author": "Test"} more text'
        result = _fallback_parse(raw, CoreIdentityBatch)
        assert isinstance(result, CoreIdentityBatch)
        assert result.title == "My Book"
        assert result.author == "Test"

    def test_no_json(self):
        raw = "No JSON here at all"
        result = _fallback_parse(raw, CoreIdentityBatch)
        assert isinstance(result, CoreIdentityBatch)
        assert result.title is None

    def test_invalid_json(self):
        raw = '{"title": "unclosed'
        result = _fallback_parse(raw, CoreIdentityBatch)
        assert isinstance(result, CoreIdentityBatch)
        assert result.title is None

    def test_empty_string(self):
        result = _fallback_parse("", CoreIdentityBatch)
        assert isinstance(result, CoreIdentityBatch)
        assert result.title is None


def _setup_service_with_mock_client(service, mock_client):
    service._client = mock_client


class TestLLMServiceExtractBatch:
    @pytest.fixture
    def service(self):
        return LLMService(ollama_url="http://fake-ollama:11434")

    async def test_extract_batch_success(self, service):
        mock_result = CoreIdentityBatch(title="Test Title", author="Test Author")
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_result
        _setup_service_with_mock_client(service, mock_client)

        result, raw, usage = await service.extract_batch(
            ocr_text="some text",
            batch_name="core_identity",
            batch_schema=CoreIdentityBatch,
        )

        assert isinstance(result, CoreIdentityBatch)
        assert usage["status"] == "success"
        assert "title" in raw

    async def test_extract_batch_timeout(self, service):
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = httpx.TimeoutException("timeout")
        _setup_service_with_mock_client(service, mock_client)

        result, raw, usage = await service.extract_batch(
            ocr_text="some text",
            batch_name="core_identity",
            batch_schema=CoreIdentityBatch,
        )

        assert isinstance(result, CoreIdentityBatch)
        assert usage["status"] == "timeout"
        assert result.title is None

    async def test_extract_batch_generic_error(self, service):
        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = Exception("boom")
        _setup_service_with_mock_client(service, mock_client)

        result, raw, usage = await service.extract_batch(
            ocr_text="some text",
            batch_name="core_identity",
            batch_schema=CoreIdentityBatch,
        )

        assert isinstance(result, CoreIdentityBatch)
        assert usage["status"] == "error"

    async def test_extract_batch_instructor_retry(self, service):
        mock_result = CoreIdentityBatch(title="Fallback")
        last_completion = MagicMock()
        last_completion.choices = [MagicMock(message=MagicMock(content='{"title": "Fallback"}'))]

        mock_client = AsyncMock()
        mock_client.chat.completions.create.side_effect = InstructorRetryException(
          "retry exhausted", last_completion=last_completion, messages=[], n_attempts=3, total_usage=[]
        )
        _setup_service_with_mock_client(service, mock_client)

        result, raw, usage = await service.extract_batch(
            ocr_text="some text",
            batch_name="core_identity",
            batch_schema=CoreIdentityBatch,
        )

        assert isinstance(result, CoreIdentityBatch)
        assert usage["status"] == "fallback"


class TestLLMServiceFullExtraction:
    @pytest.fixture
    def service(self):
        return LLMService(ollama_url="http://fake-ollama:11434")

    async def test_merges_all_batches(self, service):
        async def mock_extract(ocr_text, batch_name, batch_schema, **kwargs):
            model = batch_schema()
            data = model.model_dump()
            first_field = next(k for k in data if data[k] is None)
            setattr(model, first_field, f"extracted_{batch_name}")
            return model, '{"mock": true}', {"status": "success"}

        with patch.object(service, "extract_batch", side_effect=mock_extract):
            metadata, batch_results = await service.run_full_extraction(ocr_text="test text")

        assert isinstance(metadata, FullMetadata)
        assert len(batch_results) == len(BATCH_FIELD_ORDER)

    async def test_progress_callback(self, service):
        calls = []

        async def mock_extract(ocr_text, batch_name, batch_schema, **kwargs):
            return batch_schema(), '{}', {"status": "success"}

        async def on_progress(current, total, batch_name):
            calls.append((current, total, batch_name))

        with patch.object(service, "extract_batch", side_effect=mock_extract):
            await service.run_full_extraction(
                ocr_text="test text",
                progress_callback=on_progress,
            )

        assert len(calls) == len(BATCH_FIELD_ORDER)
        assert calls[0][2] == BATCH_FIELD_ORDER[0]
        assert calls[-1][0] == len(BATCH_FIELD_ORDER)
        assert calls[-1][1] == len(BATCH_FIELD_ORDER)


class TestLLMServiceListModels:
    async def test_success(self):
        service = LLMService(ollama_url="http://fake-ollama:11434")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "qwen2.5", "size": 4294967296, "details": {"parameter_size": "7B"}},
                {"name": "llama2", "size": None, "details": {}},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        service._http_client = mock_http

        models = await service.list_available_models()

        assert len(models) == 2
        assert models[0]["name"] == "qwen2.5"
        assert models[0]["size_gb"] == 4.0
        assert models[1]["size_gb"] is None

    async def test_error_returns_empty(self):
        service = LLMService(ollama_url="http://fake-ollama:11434")
        mock_http = AsyncMock()
        mock_http.get.side_effect = Exception("connection failed")
        service._http_client = mock_http

        models = await service.list_available_models()
        assert models == []


class TestLLMServiceClose:
    async def test_close_cleans_up(self):
        service = LLMService()
        mock_http = AsyncMock()
        service._http_client = mock_http

        await service.close()
        mock_http.aclose.assert_called_once()
        assert service._http_client is None

    async def test_close_no_client(self):
        service = LLMService()
        await service.close()
        assert service._http_client is None
