from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.metadata import (
    ALL_METADATA_FIELDS,
    BATCH_FIELD_ORDER,
    METADATA_BATCHES,
    FIELD_TO_BATCH,
    CoreIdentityBatch,
    ExtractionRequest,
    FullMetadata,
    MetadataResponse,
    MetadataUpdateRequest,
)
from app.schemas.page import PreprocessingConfig


class TestFullMetadata:
    def test_all_none(self):
        m = FullMetadata()
        data = m.model_dump()
        assert all(v is None for v in data.values())

    def test_partial(self):
        m = FullMetadata(title="My Book", author="Test Author")
        assert m.title == "My Book"
        assert m.author == "Test Author"
        assert m.publisher is None

    def test_all_fields_set(self):
        data = {name: f"value_{name}" for name in FullMetadata.model_fields}
        data["custom_fields"] = {"key": "value"}
        m = FullMetadata(**data)
        assert m.title == "value_title"
        assert m.custom_fields == {"key": "value"}


class TestBatchStructure:
    def test_batch_count(self):
        assert len(METADATA_BATCHES) == 8

    def test_batch_field_order_matches_keys(self):
        assert BATCH_FIELD_ORDER == list(METADATA_BATCHES.keys())

    def test_all_batches_have_fields(self):
        for name, cls in METADATA_BATCHES.items():
            assert len(cls.model_fields) > 0, f"Batch {name} has no fields"


class TestFieldDefinitions:
    def test_count_excludes_custom_fields(self):
        expected = len([f for f in FullMetadata.model_fields if f != "custom_fields"])
        assert len(ALL_METADATA_FIELDS) == expected

    def test_field_to_batch_mapping(self):
        for field_def in ALL_METADATA_FIELDS:
            assert field_def.batch_group in METADATA_BATCHES

    def test_display_names_present(self):
        for field_def in ALL_METADATA_FIELDS:
            assert field_def.display_name is not None
            assert len(field_def.display_name) > 0


class TestExtractionRequest:
    def test_defaults(self):
        req = ExtractionRequest()
        assert req.model == "qwen2.5"
        assert req.temperature == 0.3
        assert req.max_tokens == 512
        assert req.custom_system_prompt is None
        assert req.custom_extraction_prompt is None

    def test_custom_values(self):
        req = ExtractionRequest(
            model="llama2",
            temperature=0.7,
            max_tokens=4096,
            custom_system_prompt="custom",
        )
        assert req.model == "llama2"
        assert req.temperature == 0.7

    def test_invalid_temperature_high(self):
        with pytest.raises(ValidationError):
            ExtractionRequest(temperature=3.0)

    def test_invalid_temperature_low(self):
        with pytest.raises(ValidationError):
            ExtractionRequest(temperature=-0.1)

    def test_invalid_max_tokens_low(self):
        with pytest.raises(ValidationError):
            ExtractionRequest(max_tokens=100)


class TestPreprocessingConfig:
    def test_defaults(self):
        config = PreprocessingConfig()
        assert config.grayscale is True
        assert config.brightness == 0
        assert config.contrast == 0
        assert config.binarization is None
        assert config.deskew is True
        assert config.denoise is False

    def test_otsu_binarization(self):
        config = PreprocessingConfig(binarization="otsu")
        assert config.binarization == "otsu"

    def test_adaptive_binarization(self):
        config = PreprocessingConfig(binarization="adaptive", adaptive_block_size=15, adaptive_c=3)
        assert config.binarization == "adaptive"
        assert config.adaptive_block_size == 15

    def test_invalid_binarization(self):
        with pytest.raises(ValidationError):
            PreprocessingConfig(binarization="invalid")

    def test_brightness_out_of_range(self):
        with pytest.raises(ValidationError):
            PreprocessingConfig(brightness=200)

    def test_denoise_strength_range(self):
        with pytest.raises(ValidationError):
            PreprocessingConfig(denoise=True, denoise_strength=0)
        with pytest.raises(ValidationError):
            PreprocessingConfig(denoise=True, denoise_strength=100)


class TestMetadataResponse:
    def test_create(self):
        import uuid
        resp = MetadataResponse(
            book_id=uuid.uuid4(),
            fields={"title": "Test"},
        )
        assert resp.fields["title"] == "Test"

    def test_empty_fields(self):
        import uuid
        resp = MetadataResponse(
            book_id=uuid.uuid4(),
            fields={},
        )
        assert resp.fields == {}


class TestMetadataUpdateRequest:
    def test_create(self):
        req = MetadataUpdateRequest(fields={"title": "New Title"})
        assert req.fields["title"] == "New Title"
