"""Tests for the prompt profile registry (plans/018).

The baseline hashes pin the production prompt text: an accidental edit to
either template should fail here and force a deliberate update, because every
recorded accuracy number is only comparable to prompts that did not move.
"""

from __future__ import annotations

import hashlib

import pytest

from app.schemas.metadata import BATCH_FIELD_ORDER, FIELD_TO_BATCH, FullMetadata
from app.services.prompt_profiles import (
    BASELINE_PROFILE_ID,
    DEFAULT_PROMPT_PROFILE,
    EXTRACTION_ARMS,
    FIELD_GUIDANCE,
    OUTPUT_MODES,
    PROMPT_PROFILES,
    SYSTEM_ARMS,
    combination_profile,
    field_context,
    get_profile,
    select_few_shot,
)
from app.services.prompts import render_extraction_prompt, render_system_prompt

# sha256 of the pre-experiment production prompts. Update only with a recorded
# reason — these guard every historical comparison in reports/prompt-eval/.
BASELINE_SYSTEM_SHA = "68f9ebc86b6fb62abfa3df847bc006bb716270c128b9adb887a06687021ce3f0"
BASELINE_EXTRACTION_SHA = "600604e2f62152d16a8ddb172140abc91ac491c703376a54f6f890e4995073ce"


class TestRegistry:
    def test_ids_are_consistent(self):
        for profile_id, profile in PROMPT_PROFILES.items():
            assert profile.id == profile_id

    def test_every_profile_is_valid(self):
        for profile in PROMPT_PROFILES.values():
            assert profile.output_mode in OUTPUT_MODES
            assert profile.system_template.strip()
            assert profile.extraction_template.strip()
            assert profile.techniques

    def test_defaults_point_at_the_baseline(self):
        assert BASELINE_PROFILE_ID == "V00"
        assert DEFAULT_PROMPT_PROFILE == BASELINE_PROFILE_ID
        assert get_profile().id == BASELINE_PROFILE_ID

    def test_unknown_profile_raises(self):
        with pytest.raises(ValueError, match="Unknown prompt profile"):
            get_profile("V99")

    def test_stage_arms_are_registered(self):
        for variant in (*SYSTEM_ARMS, *EXTRACTION_ARMS):
            assert variant in PROMPT_PROFILES

    def test_only_the_evidence_arm_wraps_its_output(self):
        wrapped = [p.id for p in PROMPT_PROFILES.values() if p.output_mode == "wrapped_evidence"]
        assert wrapped == ["V08"]


class TestRendering:
    def test_every_profile_renders_every_batch(self):
        for profile_id in PROMPT_PROFILES:
            for batch_name in BATCH_FIELD_ORDER:
                prompt = render_extraction_prompt(
                    batch_name=batch_name,
                    ocr_text="sample text",
                    language="tel",
                    page_count=2,
                    profile=profile_id,
                )
                assert "sample text" in prompt
                assert len(prompt) > 50

    def test_every_profile_renders_each_language(self):
        for profile_id in PROMPT_PROFILES:
            for language in ("tel", "hin", "eng"):
                assert "Telugu" in render_system_prompt(language, profile=profile_id) or language != "tel"

    def test_override_beats_profile(self):
        assert render_system_prompt("tel", override="custom", profile="V05") == "custom"
        rendered = render_extraction_prompt(
            batch_name="core_identity",
            ocr_text="x",
            language="tel",
            override="custom {{ ocr_text }}",
            profile="V05",
        )
        assert rendered == "custom x"

    def test_few_shot_can_be_disabled(self):
        without = render_extraction_prompt(
            batch_name="core_identity", ocr_text="x", language="tel", include_few_shot=False
        )
        assert "Example 1" not in without

    def test_baseline_system_prompt_is_frozen(self):
        rendered = render_system_prompt("tel")
        assert hashlib.sha256(rendered.encode()).hexdigest() == BASELINE_SYSTEM_SHA

    def test_baseline_extraction_prompt_is_frozen(self):
        rendered = render_extraction_prompt(
            batch_name="core_identity", ocr_text="OCR TEXT", language="tel", page_count=3
        )
        assert hashlib.sha256(rendered.encode()).hexdigest() == BASELINE_EXTRACTION_SHA

    def test_unknown_batch_raises_for_every_profile(self):
        for profile_id in PROMPT_PROFILES:
            with pytest.raises(ValueError, match="Unknown batch"):
                render_extraction_prompt(
                    batch_name="nope", ocr_text="x", language="tel", profile=profile_id
                )


class TestFieldGuidance:
    def test_every_metadata_field_has_guidance(self):
        fields = [name for name in FullMetadata.model_fields if name != "custom_fields"]
        missing = [name for name in fields if not FIELD_GUIDANCE.get(name)]
        assert missing == []

    def test_guidance_has_no_orphans(self):
        fields = set(FullMetadata.model_fields)
        assert set(FIELD_GUIDANCE) <= fields

    def test_field_context_always_sets_guidance(self):
        context = field_context([{"name": "title", "description": "Title"}])
        assert context[0]["guidance"]
        assert context[0]["name"] == "title"


class TestFewShot:
    def test_synthetic_is_keyed_by_language(self):
        assert select_few_shot("synthetic", "tel", "core_identity").strip()

    def test_none_returns_empty(self):
        assert select_few_shot("none", "tel", "core_identity") == ""

    def test_real_degrades_to_empty_when_missing(self):
        assert select_few_shot("real", "xyz", "core_identity") == ""

    def test_few_shot_is_batch_specific_where_files_exist(self):
        # Files are optional; when present they must differ per batch, which is
        # the whole point of the V11 arm.
        tel_core = select_few_shot("real", "tel", "core_identity")
        tel_rel = select_few_shot("real", "tel", "relationships")
        assert tel_core != tel_rel or tel_core == ""


class TestCombination:
    def test_combines_system_and_extraction(self):
        combo = combination_profile("V03", "V10", profile_id="V13")
        assert combo.id == "V13"
        assert combo.system_template == PROMPT_PROFILES["V03"].system_template
        assert combo.extraction_template == PROMPT_PROFILES["V10"].extraction_template
        assert combo.output_mode == PROMPT_PROFILES["V10"].output_mode
        assert any(t.startswith("system:") for t in combo.techniques)
        assert any(t.startswith("extraction:") for t in combo.techniques)

    def test_inherits_the_evidence_output_mode(self):
        combo = combination_profile("V02", "V08", profile_id="V15")
        assert combo.output_mode == "wrapped_evidence"


class TestFieldBatchCoverage:
    def test_every_field_maps_to_a_batch(self):
        for field_name in FullMetadata.model_fields:
            if field_name == "custom_fields":
                continue
            assert FIELD_TO_BATCH[field_name] in BATCH_FIELD_ORDER


class TestPromptDefaultsApi:
    def test_route_is_registered_ahead_of_the_book_id_route(self):
        # /books/models and /books/prompt-defaults must be declared before
        # /books/{book_id}, or the UUID path parameter shadows them and 422s.
        from app.api.extraction import router

        paths = [route.path for route in router.routes]
        assert "/prompt-defaults" in paths
        assert paths.index("/prompt-defaults") < paths.index("/{book_id}/run-extraction")

    def test_defaults_payload_matches_the_registry(self):
        from app.schemas.metadata import PromptDefaultsResponse

        profile = get_profile()
        payload = PromptDefaultsResponse(
            profile=profile.id,
            system_prompt=profile.system_template,
            extraction_prompt=profile.extraction_template,
            variables=["language_name"],
            batch_field_order=list(BATCH_FIELD_ORDER),
        )
        assert payload.profile == BASELINE_PROFILE_ID
        # The templates must be renderable as served.
        assert "{{ language_name }}" in payload.system_prompt
        assert "{% for field in fields %}" in payload.extraction_prompt
