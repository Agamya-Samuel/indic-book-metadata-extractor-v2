"""Prompt rendering for the 49-field extraction pipeline.

The prompt text itself lives in :mod:`app.services.prompt_profiles` so that
experiments (``plans/018-prompt-optimization.md``) and production share one
source of truth. This module keeps the public API that callers already use and
defaults to :data:`prompt_profiles.DEFAULT_PROMPT_PROFILE`, which is the
current production prompt pair.

Pass ``profile="V07"`` (or any registered id) to render an arm under test; pass
``override="..."`` to render a user-supplied template from the LLM-config step,
which keeps precedence over any profile.
"""

from __future__ import annotations

from jinja2 import Template

from app.schemas.metadata import (  # re-exported: scripts import it from here
    FIELD_DISPLAY_NAMES,
    METADATA_BATCHES,
)
from app.services.prompt_profiles import (
    BASELINE_PROFILE_ID,
    DEFAULT_PROMPT_PROFILE,
    FIELD_GUIDANCE,
    SECTION_PRIORITY,
    SYNTHETIC_FEW_SHOT,
    field_context,
    get_profile,
    select_few_shot,
)

LANGUAGE_NAMES: dict[str, str] = {
    "tel": "Telugu",
    "hin": "Hindi",
    "eng": "English",
}

# Retained as module attributes for callers/tests that reference them directly.
# They are compiled from the baseline profile's templates.
SYSTEM_PROMPT_TEMPLATE = Template(get_profile(BASELINE_PROFILE_ID).system_template)
FEW_SHOT_EXAMPLES: dict[str, str] = SYNTHETIC_FEW_SHOT
EXTRACTION_PROMPT_TEMPLATE = Template(get_profile(BASELINE_PROFILE_ID).extraction_template)


def get_language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


def render_system_prompt(
    language: str,
    override: str | None = None,
    profile: str | None = None,
) -> str:
    """Render the system turn.

    ``override`` wins over ``profile``; ``profile`` wins over the default
    profile. The three-way precedence keeps the existing custom-prompt path
    working while experiments select an arm by id.
    """
    if override:
        return override
    active = get_profile(profile)
    return Template(active.system_template).render(
        language_name=get_language_name(language),
        section_priority=SECTION_PRIORITY,
    )


def render_extraction_prompt(
    batch_name: str,
    ocr_text: str,
    language: str,
    page_count: int = 1,
    override: str | None = None,
    include_few_shot: bool = True,
    profile: str | None = None,
) -> str:
    if override:
        template = Template(override)
    else:
        template = Template(get_profile(profile).extraction_template)

    batch_cls = METADATA_BATCHES.get(batch_name)
    if batch_cls is None:
        raise ValueError(f"Unknown batch: {batch_name}")

    fields = []
    for field_name, field_info in batch_cls.model_fields.items():
        if field_name == "custom_fields":
            continue
        fields.append(
            {
                "name": field_name,
                "description": FIELD_DISPLAY_NAMES.get(field_name, field_name),
            }
        )

    active = get_profile(profile)
    if include_few_shot:
        few_shot = select_few_shot(active.few_shot, language, batch_name)
    else:
        few_shot = ""

    return template.render(
        language_name=get_language_name(language),
        fields=field_context(fields),
        ocr_text=ocr_text,
        page_count=page_count,
        few_shot_examples=few_shot,
        section_priority=SECTION_PRIORITY,
    )


def get_batch_field_names(batch_name: str) -> list[str]:
    batch_cls = METADATA_BATCHES.get(batch_name)
    if batch_cls is None:
        raise ValueError(f"Unknown batch: {batch_name}")
    return [f for f in batch_cls.model_fields if f != "custom_fields"]


__all__ = [
    "DEFAULT_PROMPT_PROFILE",
    "EXTRACTION_PROMPT_TEMPLATE",
    "FIELD_DISPLAY_NAMES",
    "FIELD_GUIDANCE",
    "FEW_SHOT_EXAMPLES",
    "LANGUAGE_NAMES",
    "SYSTEM_PROMPT_TEMPLATE",
    "get_batch_field_names",
    "get_language_name",
    "render_extraction_prompt",
    "render_system_prompt",
]
