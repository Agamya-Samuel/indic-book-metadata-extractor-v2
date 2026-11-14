"""Cooperative cancellation stops an in-flight LLM extraction."""

import pytest

from app.core.errors import JobCancelled
from app.services.llm_service import LLMService


@pytest.mark.asyncio
async def test_hybrid_extraction_raises_when_cancelled_before_batching():
    service = LLMService()

    async def cancelled() -> bool:
        return True

    with pytest.raises(JobCancelled):
        await service.run_hybrid_full_extraction(
            ocr_text="some scanned book text",
            pages=[],
            cancel_check=cancelled,
        )

    await service.close()


@pytest.mark.asyncio
async def test_hybrid_extraction_runs_when_not_cancelled(monkeypatch):
    service = LLMService()

    async def not_cancelled() -> bool:
        return False

    async def fake_batch(**kwargs):
        return (
            kwargs["batch_name"],
            {},
            "",
            {"status": "empty_response"},
            "prompt",
        )

    monkeypatch.setattr(service, "_run_one_batch_for_hybrid", fake_batch)

    metadata, _, _ = await service.run_hybrid_full_extraction(
        ocr_text="some scanned book text",
        pages=[],
        cancel_check=not_cancelled,
    )

    assert metadata.model_dump()
    await service.close()
