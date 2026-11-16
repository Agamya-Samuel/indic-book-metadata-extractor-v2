"""Named prompt profiles for the 49-field metadata extraction pipeline.

This module is the experiment surface for ``plans/018-prompt-optimization.md``.
Production calls ``app.services.prompts.render_*`` without a profile id and gets
:data:`BASELINE_PROFILE_ID`, so an experimental prompt can never leak into the
app by accident.

A profile is a *pair* (system prompt, extraction prompt) plus how few-shot
examples are sourced and what shape the reply takes. Everything here renders
with the same Jinja2 context production already supplies, so any profile that
wins is drop-in:

    language_name, fields[{name, description, guidance}], ocr_text,
    page_count, few_shot_examples, section_priority

Templates that ignore the newer keys (``guidance``, ``section_priority``) render
exactly as they would without them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.schemas.metadata import FIELD_DISPLAY_NAMES

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REAL_FEW_SHOT_DIR = BACKEND_ROOT / "prompt_eval" / "fewshot"

BASELINE_PROFILE_ID = "V00"

# The app's default. Change this only when an experiment has won and the change
# is recorded in learnings/025 — the golden tests in test_prompt_profiles.py
# snapshot whatever is set here.
DEFAULT_PROMPT_PROFILE = BASELINE_PROFILE_ID

OUTPUT_MODES = ("batch_schema", "wrapped_evidence")
FEW_SHOT_SOURCES = ("synthetic", "real", "none")


# ---------------------------------------------------------------------------
# Few-shot sources
# ---------------------------------------------------------------------------

# Production's examples, moved here verbatim so V00 reproduces byte-for-byte.
# They are synthetic: invented books, invented publishers and invented ISBNs.
SYNTHETIC_FEW_SHOT: dict[str, str] = {
    "tel": """
Example 1 (Telugu title page + copyright):
Input:
ప్రచురణ సమాచారం
శీర్షిక: భారత స్వాతంత్ర్య సంగ్రామం
ఉపశీర్షిక: ఒక చారిత్రక అధ్యయనం
రచయిత: డా. రామకృష్ణ శర్మ
సంపాదకులు: ప్రొ. సీతారామయ్య
ప్రచురణకర్త: తెలుగు అకాడమీ, హైదరాబాద్
ముద్రణ: శ్రీ వెంకటేశ్వర ప్రింటర్స్, హైదరాబాద్
మొదటి ముద్రణ: 2024
ISBN: 978-81-234-5678-9
పేజీలు: 248
Output:
{"title": "భారత స్వాతంత్ర్య సంగ్రామం", "subtitle": "ఒక చారిత్రక అధ్యయనం", "author": "డా. రామకృష్ణ శర్మ", "editor": "ప్రొ. సీతారామయ్య", "publisher": "తెలుగు అకాడమీ", "place_of_publication": "హైదరాబాద్", "printer": "శ్రీ వెంకటేశ్వర ప్రింటర్స్", "publication_date": "2024", "isbn": "978-81-234-5678-9", "pages": "248", "edition_number": "మొదటి ముద్రణ"}
""",
    "hin": """
Example 1 (Hindi title page + copyright):
Input:
प्रकाशन सूचना
शीर्षक: आधुनिक भारत का इतिहास
उपशीर्षक: स्वतंत्रता से आज तक
लेखक: डॉ. रमेश चंद्र शर्मा
संपादक: प्रो. सुरेश मिश्रा
प्रकाशक: राजकमल प्रकाशन, नई दिल्ली
मुद्रक: नेशनल प्रिंटिंग प्रेस, नोएडा
तीसरा संस्करण: 2023
ISBN: 978-81-267-1234-5
पृष्ठ संख्या: 320
Output:
{"title": "आधुनिक भारत का इतिहास", "subtitle": "स्वतंत्रता से आज तक", "author": "डॉ. रमेश चंद्र शर्मा", "editor": "प्रो. सुरेश मिश्रा", "publisher": "राजकमल प्रकाशन", "place_of_publication": "नई दिल्ली", "printer": "नेशनल प्रिंटिंग प्रेस", "place_of_printing": "नोएडा", "publication_date": "2023", "isbn": "978-81-267-1234-5", "pages": "320", "edition_number": "तीसरा संस्करण"}
""",
    "eng": """
Example 1 (English title page + copyright):
Input:
Publication Information
Title: The History of Modern India
Subtitle: From Independence to the Present Day
Author: Dr. Ramesh Chandra Sharma
Editor: Prof. Suresh Mishra
Publisher: National Book Trust, New Delhi
Printer: National Printing Press, Noida
First Edition: 2024
ISBN: 978-81-234-5678-9
Pages: 280
Output:
{"title": "The History of Modern India", "subtitle": "From Independence to the Present Day", "author": "Dr. Ramesh Chandra Sharma", "editor": "Prof. Suresh Mishra", "publisher": "National Book Trust", "place_of_publication": "New Delhi", "printer": "National Printing Press", "place_of_printing": "Noida", "publication_date": "2024", "isbn": "978-81-234-5678-9", "pages": "280", "edition_number": "First Edition"}
""",
}

# Batch groups whose fields are not core-identity shaped. The synthetic example
# above only teaches core-identity keys, so injecting it into these batches is
# part of what V11 (real, batch-matched exemplars) tests against.
CORE_IDENTITY_BATCHES = {"core_identity", "publication", "edition_series"}


def load_real_few_shot(language: str, batch_name: str) -> str:
    """Return held-out real exemplars for this (language, batch), or "".

    Prefers a batch-scoped file, then a language-wide one. Files are built by
    ``scripts/prompt_eval/build_fewshot.py`` from ground-truth books that are
    excluded from scoring (the holdout list is in ``prompt_eval/manifest.json``).
    Missing files degrade to no examples rather than failing the run.
    """
    for candidate in (
        REAL_FEW_SHOT_DIR / language / f"{batch_name}.txt",
        REAL_FEW_SHOT_DIR / f"{language}.txt",
    ):
        if candidate.is_file():
            text = candidate.read_text(encoding="utf-8").strip()
            if text:
                return f"\n{text}\n"
    return ""


def select_few_shot(source: str, language: str, batch_name: str) -> str:
    if source == "none":
        return ""
    if source == "real":
        return load_real_few_shot(language, batch_name)
    return SYNTHETIC_FEW_SHOT.get(language, "")


# ---------------------------------------------------------------------------
# Per-field guidance (used by V10)
# ---------------------------------------------------------------------------

# Deliberately terse: the point is to disambiguate adjacent fields and say what
# to exclude, not to write an essay the model has to parse.
FIELD_GUIDANCE: dict[str, str] = {
    "label": "shortest printed heading of the work; same as the title unless the title carries a subtitle",
    "title": "the main title as printed on the title page, without the subtitle",
    "subtitle": "the subordinate title printed under the main title, if any",
    "author": "the work's author as printed; exclude editors, translators, printers and publishers",
    "description_work": "a printed statement of what the work is about; never compose one yourself",
    "description_edition": "a printed statement about this edition or printing; never compose one",
    "translator": "the person credited with the translation; do not put the original author here",
    "editor": "the person credited with editing; do not put the author here",
    "compiler": "the సంకలనకర్త / संकलनकर्ता credit only",
    "inception": "the year the work was first written, only if the book states it",
    "form_of_creative_work": "the printed form (పుస్తకం, पुस्तक, novel, poetry collection); not your own classification",
    "genre": "genre words printed on the book; do not infer a genre",
    "subject": "printed subject or keyword lines only",
    "original_language": "the language of the original work, only when this book is a translation",
    "edition_or_translation_of": "the work this is an edition or translation of, when named",
    "based_on": "the work this book is based on, when named",
    "inspired_by": "the work said to have inspired this one, when named",
    "volume": "the volume number or volume name as printed",
    "edition_number": "the edition wording as printed (మొదటి ముద్రణ, दूसरा संस्करण); do not convert to digits",
    "publication_date": "the date or year of this printing as printed; prefer the copyright page over the title page",
    "publisher": "the publishing house name only, without its address",
    "place_of_publication": "the city of the publisher only",
    "printer": "the press name only, without its address",
    "place_of_printing": "the city of the press only",
    "language": "the language of the book as printed, or the language of its script",
    "cover_artist": "the cover artwork credit only",
    "cover_page_designer": "the cover design credit only",
    "typesetting_by": "the typesetting credit only",
    "typing_by": "the టైపింగ్ / typing credit only",
    "book_designer": "the interior or book design credit only",
    "distributors": "distributing agencies; never merge these into the publisher",
    "pages": "the page count as printed",
    "dedication": "the అంకితం / समर्पण text",
    "dedication_verbatim": "the dedication exactly as printed, including the names in it",
    "part_of_series": "the series name, when printed",
    "serial_number_in_series": "the number of this volume within the series",
    "part_of_the_set": "the multi-volume set name or number, when printed",
    "illustrators": "the interior illustration credits",
    "isbn": "the ISBN digits as printed, with hyphens when printed",
    "awards": "awards named on the book itself only",
    "context": "printed context or occasion note (సందర్భం) only",
    "publisher_telugu": "the publisher name in Telugu script only; null for a Hindi book",
    "sponsor": "the funding or sponsoring body only",
    "first_published_in": "the journal or venue of first publication only",
    "forewords": "the names of the foreword authors, as printed",
    "abbreviations": "the abbreviation list heading or entries, when printed",
    "authors_in_compilation": "the authors of the individual pieces in a compilation, as printed",
    "opinions_messages": "printed opinions or messages (అభిప్రాయాలు) only",
    "scribes": "the లేఖకులు / scribe credit only",
}

SECTION_PRIORITY = """The pages come from different parts of the book. When the same metadata appears more than once, prefer the source higher in this list:
1. Title page — title, subtitle, author, publisher, place of publication, edition.
2. Copyright page / publication information — publication date, edition, ISBN, printer, copyright holder.
3. Colophon or final pages — printer, place of printing, print run, date of printing.
4. Cover or half-title — title, author, series, cover artist.
5. Body text — dedication, forewords, abbreviations, scribes; use these pages only for their own fields."""


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

# V00 system prompt: byte-identical to the pre-experiment production template.
SYSTEM_BASELINE = """You are an expert bibliographic metadata extractor specializing in {{ language_name }} language books.
You will be given OCR-extracted text from scanned book pages. The text may contain OCR errors — use your knowledge of {{ language_name }} to interpret corrupted words.
Extract the requested metadata fields as accurately as possible from the provided text.
If a field cannot be determined from the text, return null for that field.
Always respond with valid JSON matching the exact schema provided. Do not include any text outside the JSON object."""

SYSTEM_ROLE_TIGHT = """You are a bibliographic cataloguer working from the OCR of a scanned {{ language_name }} book. Your only task is to fill the requested metadata fields for this one book from the supplied page text.

Rules:
- Read the page text and copy what the book itself states.
- Use the page markers ([Page 1], [Page 2], ...) to know where each value came from.
- Return one JSON object with exactly the requested keys and nothing else."""

SYSTEM_STRICT_VERBATIM = """You transcribe bibliographic metadata from OCR text of a {{ language_name }} book. Extraction only.

- Every value you return must be stated in the supplied text.
- Do not use outside knowledge about this book, its author or its publisher.
- Do not complete a partial value, infer a missing date, or rewrite a name into a different form.
- If a value is not stated, return null for that field.
- Return one JSON object with exactly the requested keys and nothing else."""

SYSTEM_OCR_NOISE = """You extract bibliographic metadata from OCR text of a {{ language_name }} book. The OCR is noisy: characters may be misread, spaces inserted inside words, and lines broken mid-phrase.

Repair boundary:
- You MAY repair an obviously corrupted word when the surrounding words make the intended word unambiguous.
- You MAY ignore OCR debris (isolated symbols, broken lines, duplicated fragments).
- You MUST NOT invent a word, name, number, publisher or date that is not visible in the text.
- When a corrupted value cannot be resolved confidently, return null rather than a guess.
- Keep the book's own spelling of names and places; do not translate or transliterate."""

SYSTEM_SCRIPT_AWARE = """You extract bibliographic metadata from OCR text of a {{ language_name }} book.

Script rules:
- Return each value in the script it appears in. Do not transliterate between scripts.
- Read through common confusions instead of copying them: ి/ీ, ె/ే, శ/ష/స, బ/వ (Telugu); ि/ी, श/ष/स, ब/व, ड/ड़ (Devanagari). Choose the reading that forms a real {{ language_name }} word.
- Numerals may be in either script or ASCII digits; return them as printed.
- Keep honorifics and prefixes exactly as printed (ఉదా. డా., ప్రొ., श्री, डॉ.).
- If a value is genuinely absent, return null."""

SYSTEM_CONTEXT_PRIORITY = """You extract bibliographic metadata from OCR text of a {{ language_name }} book.

{{ section_priority }}

Never take a title, author or date from running body text when a title or copyright page states it. Return null when no source states the value."""

SYSTEM_NULL_DISCIPLINE = """You extract bibliographic metadata from OCR text of a {{ language_name }} book.

Null rule — this is the only rule that applies:
- Return a value when the text states it, even if the OCR is imperfect but the intended value is unmistakable.
- Return null when the text does not state it.
- Return null when the text is too damaged to identify the value with confidence.
- Never return a plausible guess, a placeholder such as "unknown" or "N/A", or a value taken from a different book.

Return one JSON object with exactly the requested keys and nothing else."""


# V00 extraction prompt: byte-identical to the pre-experiment production template.
EXTRACTION_BASELINE = """Extract the following metadata fields from this {{ language_name }} book text.

Fields to extract:
{% for field in fields %}
- {{ field.name }}: {{ field.description }}
{% endfor %}

{% if few_shot_examples %}{{ few_shot_examples }}
{% endif %}
OCR Text (from {{ page_count }} pages of a scanned book):
---
{{ ocr_text }}
---

Respond with a JSON object containing exactly these fields.
Extract your best reading for every field that appears anywhere in the text — including titles, authors, and publishers even when the OCR is imperfect; use null only when the information is genuinely absent.
Do not include any explanation or text outside the JSON object."""

EXTRACTION_SCHEMA_DRIVEN = """Extract these metadata fields from the {{ language_name }} book text below.

Target object — every key is required, and every value is a string or null:
{
{% for field in fields %}
  "{{ field.name }}": <string|null>{% if not loop.last %},{% endif %}
{% endfor %}
}

Rules:
- Dates, page counts and edition numbers are strings, not numbers.
- Use null when the text does not state the value.
- Return no keys other than the ones listed.

{% if few_shot_examples %}{{ few_shot_examples }}
{% endif %}
OCR Text (from {{ page_count }} pages of a scanned book):
---
{{ ocr_text }}
---

Respond with the JSON object only."""

EXTRACTION_EVIDENCE = """Extract these metadata fields from the {{ language_name }} book text below.

Fields to extract:
{% for field in fields %}
- {{ field.name }}: {{ field.description }}
{% endfor %}

For every field, decide:
- stated — the text states the value: put it in "fields" and also cite it in "evidence".
- not stated or unreadable — use null in "fields" and omit the field from "evidence".

Each "evidence" entry must contain the exact snippet copied from the OCR text and the page number from its [Page N] marker:
  "field_name": {"quote": "<exact snippet>", "page": <number>}

A value with no supporting evidence entry is treated as wrong. Do not paraphrase the quote.

OCR Text (from {{ page_count }} pages of a scanned book):
---
{{ ocr_text }}
---

Respond with exactly this shape and nothing else:
{"fields": {<the requested fields, string|null>}, "evidence": {<one entry per non-null field>}}"""

EXTRACTION_MISSING_EXPLICIT = """Extract these metadata fields from the {{ language_name }} book text below.

Fields to extract:
{% for field in fields %}
- {{ field.name }}: {{ field.description }}
{% endfor %}

Before answering, classify each field using the text alone:
- stated — the text states the value. Return it.
- damaged — the text clearly intends a value but the characters cannot be read. Return null.
- absent — the text never mentions the field. Return null.

Only "stated" produces a value. Do not return a placeholder, a best guess, or a value reconstructed from a similar book.

{% if few_shot_examples %}{{ few_shot_examples }}
{% endif %}
OCR Text (from {{ page_count }} pages of a scanned book):
---
{{ ocr_text }}
---

Respond with a JSON object containing exactly these fields. Do not include any explanation or text outside the JSON object."""

EXTRACTION_FIELD_GUIDANCE = """Extract these metadata fields from the {{ language_name }} book text below.

Fields to extract, with how to read each one:
{% for field in fields %}
- {{ field.name }} ({{ field.description }}): {{ field.guidance }}
{% endfor %}

Use the guidance to decide what belongs in the field and what must be excluded. If the text does not state the value, return null.

{% if few_shot_examples %}{{ few_shot_examples }}
{% endif %}
OCR Text (from {{ page_count }} pages of a scanned book):
---
{{ ocr_text }}
---

Respond with a JSON object containing exactly these fields. Do not include any explanation or text outside the JSON object."""

EXTRACTION_CONFLICT_POLICY = """Extract these metadata fields from the {{ language_name }} book text below.

Fields to extract:
{% for field in fields %}
- {{ field.name }}: {{ field.description }}
{% endfor %}

When the text shows more than one candidate value for a field, resolve it in this order:
1. Prefer the title page for title, subtitle, author, publisher, place of publication.
2. Prefer the copyright page for publication_date, edition_number, isbn, printer.
3. publication_date: prefer the date of THIS printing over the original copyright year; if only a range is printed, return the first year.
4. isbn: return the ISBN of this copy; if several are printed, prefer the one labelled for this binding or edition, otherwise the first 13-digit value.
5. author, editor, translator: when several names are credited, return them in printed order separated by "; ".
6. publisher, distributors, sponsor: publisher is the publishing house, distributors are separate distributing agencies, sponsor is the funding body. Never merge them.
7. If two sources of the same rank disagree and no rule above resolves it, return null.

{% if few_shot_examples %}{{ few_shot_examples }}
{% endif %}
OCR Text (from {{ page_count }} pages of a scanned book):
---
{{ ocr_text }}
---

Respond with a JSON object containing exactly these fields. Do not include any explanation or text outside the JSON object."""


@dataclass(frozen=True)
class PromptProfile:
    id: str
    label: str
    system_template: str
    extraction_template: str
    few_shot: str = "synthetic"
    output_mode: str = "batch_schema"
    techniques: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        if self.output_mode not in OUTPUT_MODES:
            raise ValueError(f"{self.id}: unknown output_mode {self.output_mode!r}")
        if self.few_shot not in FEW_SHOT_SOURCES:
            raise ValueError(f"{self.id}: unknown few_shot source {self.few_shot!r}")


# Stage 1 isolates the system prompt (extraction held at baseline).
# Stage 2 isolates the extraction prompt (system held at baseline).
# V13–V15 are built by combination_profile() once Stage 1/2 results exist.
PROMPT_PROFILES: dict[str, PromptProfile] = {
    "V00": PromptProfile(
        id="V00",
        label="baseline",
        system_template=SYSTEM_BASELINE,
        extraction_template=EXTRACTION_BASELINE,
        few_shot="synthetic",
        techniques=("current-production",),
        notes="Reproduction target. Byte-identical to the pre-experiment prompts.",
    ),
    "V01": PromptProfile(
        id="V01",
        label="role-tight",
        system_template=SYSTEM_ROLE_TIGHT,
        extraction_template=EXTRACTION_BASELINE,
        techniques=("role-based",),
        notes="Narrow single-purpose role; adds page-marker awareness.",
    ),
    "V02": PromptProfile(
        id="V02",
        label="strict-verbatim",
        system_template=SYSTEM_STRICT_VERBATIM,
        extraction_template=EXTRACTION_BASELINE,
        techniques=("extraction-only", "no-outside-knowledge"),
        notes="Forbids inference/completion; tests whether precision rises without recall collapse.",
    ),
    "V03": PromptProfile(
        id="V03",
        label="ocr-noise",
        system_template=SYSTEM_OCR_NOISE,
        extraction_template=EXTRACTION_BASELINE,
        techniques=("noise-aware", "repair-boundary"),
        notes="Separates repairing a garbled word from fabricating a missing one.",
    ),
    "V04": PromptProfile(
        id="V04",
        label="script-aware",
        system_template=SYSTEM_SCRIPT_AWARE,
        extraction_template=EXTRACTION_BASELINE,
        techniques=("multilingual", "script-policy", "confusable-pairs"),
        notes="Telugu/Devanagari confusables; forbids transliteration.",
    ),
    "V05": PromptProfile(
        id="V05",
        label="context-priority",
        system_template=SYSTEM_CONTEXT_PRIORITY,
        extraction_template=EXTRACTION_BASELINE,
        techniques=("context-prioritisation",),
        notes="Section precedence title > copyright > colophon > cover > body. Routing is unchanged.",
    ),
    "V06": PromptProfile(
        id="V06",
        label="null-discipline",
        system_template=SYSTEM_NULL_DISCIPLINE,
        extraction_template=EXTRACTION_BASELINE,
        techniques=("explicit-null", "anti-hallucination"),
        notes="Replaces the two contradictory null thresholds with one calibrated rule.",
    ),
    "V07": PromptProfile(
        id="V07",
        label="schema-driven",
        system_template=SYSTEM_BASELINE,
        extraction_template=EXTRACTION_SCHEMA_DRIVEN,
        techniques=("schema-driven",),
        notes="Typed key list in the prompt; every key required, string|null only.",
    ),
    "V08": PromptProfile(
        id="V08",
        label="evidence-based",
        system_template=SYSTEM_BASELINE,
        extraction_template=EXTRACTION_EVIDENCE,
        output_mode="wrapped_evidence",
        techniques=("evidence-based", "quote-grounding"),
        notes="Values must carry an OCR snippet and page; unwrapped for scoring.",
    ),
    "V09": PromptProfile(
        id="V09",
        label="missing-explicit",
        system_template=SYSTEM_BASELINE,
        extraction_template=EXTRACTION_MISSING_EXPLICIT,
        techniques=("missing-field-handling", "absent-vs-damaged"),
        notes="Distinguishes stated / damaged / absent before emitting null.",
    ),
    "V10": PromptProfile(
        id="V10",
        label="field-guidance",
        system_template=SYSTEM_BASELINE,
        extraction_template=EXTRACTION_FIELD_GUIDANCE,
        techniques=("field-specific-instructions", "per-field-exclusions"),
        notes="Per-field where-to-look/qualifies/excludes guidance for all 49 fields.",
    ),
    "V11": PromptProfile(
        id="V11",
        label="few-shot-real",
        system_template=SYSTEM_BASELINE,
        extraction_template=EXTRACTION_BASELINE,
        few_shot="real",
        techniques=("few-shot", "real-exemplars", "batch-matched"),
        notes="Held-out real GT exemplars, batch-matched. Differs from V00 only in exemplar sourcing.",
    ),
    "V12": PromptProfile(
        id="V12",
        label="conflict-policy",
        system_template=SYSTEM_BASELINE,
        extraction_template=EXTRACTION_CONFLICT_POLICY,
        techniques=("conflict-resolution", "source-precedence"),
        notes="Explicit precedence for multiple dates, ISBNs, publishers and authors.",
    ),
}

# Ordered so bundles and reports are deterministic.
VARIANT_ORDER: tuple[str, ...] = tuple(PROMPT_PROFILES)

SYSTEM_ARMS: tuple[str, ...] = ("V01", "V02", "V03", "V04", "V05", "V06")
EXTRACTION_ARMS: tuple[str, ...] = ("V07", "V08", "V09", "V10", "V11", "V12")


def get_profile(profile_id: str | None = None) -> PromptProfile:
    """Resolve a profile id, defaulting to the app's configured default."""
    resolved = profile_id or DEFAULT_PROMPT_PROFILE
    try:
        return PROMPT_PROFILES[resolved]
    except KeyError:
        known = ", ".join(PROMPT_PROFILES)
        raise ValueError(f"Unknown prompt profile {resolved!r}. Known profiles: {known}") from None


def combination_profile(
    system_profile_id: str,
    extraction_profile_id: str,
    *,
    profile_id: str,
) -> PromptProfile:
    """Build a Stage-3 combination from two tested arms.

    Kept out of :data:`PROMPT_PROFILES` on purpose: V13–V15 are defined by the
    Stage 1/2 leaderboard, not by guesswork. ``scripts/prompt_eval/compare.py
    --emit-stage3`` writes the choice, and ``build_bundles.py --stage 3`` calls
    this function with it.
    """
    system = get_profile(system_profile_id)
    extraction = get_profile(extraction_profile_id)
    few_shot = extraction.few_shot if extraction.few_shot != "synthetic" else system.few_shot
    return PromptProfile(
        id=profile_id,
        label=f"combo:{system.label}+{extraction.label}",
        system_template=system.system_template,
        extraction_template=extraction.extraction_template,
        few_shot=few_shot,
        output_mode=extraction.output_mode,
        techniques=(
            *(f"system:{t}" for t in system.techniques),
            *(f"extraction:{t}" for t in extraction.techniques),
        ),
        notes=f"Stage-3 combination of {system.id} and {extraction.id}.",
    )


def field_context(fields: list[dict[str, str]]) -> list[dict[str, str]]:
    """Add per-field guidance to the render context.

    ``guidance`` is always present (empty when unknown) so templates can use
    ``{% if field.guidance %}`` without Jinja undefined surprises.
    """
    return [
        {
            "name": field["name"],
            "description": field["description"],
            "guidance": FIELD_GUIDANCE.get(field["name"], ""),
        }
        for field in fields
    ]


def display_name(field_name: str) -> str:
    return FIELD_DISPLAY_NAMES.get(field_name, field_name)
