"""Tests for the prompt-evaluation harness (plans/018).

These cover the parts that decide whether a result is trustworthy: value
matching for the visibility mask, determinism of the stress perturbations, the
shape of the bundles sent to a node, and the resume logic.
"""

from __future__ import annotations

import json
import random

from scripts.prompt_eval.build_bundles import wrapper_schema
from scripts.prompt_eval.build_mask import find_value
from scripts.prompt_eval.build_stress import drop_lines, perturb, substitute
from scripts.prompt_eval.run_eval import build_payload, load_done
from scripts.prompt_eval.score_eval import _base_sample_id, _case_of


class TestFindValue:
    def test_exact_substring(self):
        assert find_value("ఆంధ్ర పత్రికా ముద్రాలయము", "ప్రచురణకర్త: ఆంధ్ర పత్రికా ముద్రాలయము, మద్రాసు") == "exact"

    def test_normalisation_ignores_case_and_space(self):
        assert find_value("National Book Trust", "publisher:  national  book trust ") == "exact"

    def test_fuzzy_when_tokens_mostly_survive(self):
        assert find_value("రాయసం వెంకట శివుడు", "రాయసము వెంకట శివుడు గుంటూరు") == "fuzzy"

    def test_absent_returns_none(self):
        assert find_value("autobiography", "ప్రచురణకర్త: తెలుగు అకాడమీ") is None

    def test_one_character_value_must_be_a_whole_token(self):
        # "3" inside "1933" must not count as a match for the value "3".
        assert find_value("3", "ప్రచురణ 1933 సంవత్సరం") is None
        assert find_value("3", "సంపుటం 3") == "exact"

    def test_empty_value_never_matches(self):
        assert find_value("", "some text") is None


class TestStressDeterminism:
    def test_substitute_is_seeded(self):
        a = substitute("శ్రీ వెంకటేశ్వర పుస్తకం", "tel", 0.5, random.Random("42:x"))
        b = substitute("శ్రీ వెంకటేశ్వర పుస్తకం", "tel", 0.5, random.Random("42:x"))
        assert a == b

    def test_substitute_only_uses_confusables(self):
        text = "శ్రీ వెంకటేశ్వర"
        out = substitute(text, "tel", 1.0, random.Random(1))
        assert len(out) == len(text)
        assert out != text

    def test_unknown_language_is_unchanged(self):
        assert substitute("text", "xyz", 1.0, random.Random(1)) == "text"

    def test_drop_lines_never_empties_the_text(self):
        assert drop_lines("one\ntwo\nthree", 1.0, random.Random(1)) == "one\ntwo\nthree"

    def test_title_removal_scrubs_the_front_page(self):
        pages = [{"n": 1, "text": "ఆత్మచరిత్రము\nరాయసం వెంకట శివుడు"}, {"n": 2, "text": "body"}]
        expected = {"title": "ఆత్మచరిత్రము", "author": "రాయసం వెంకట శివుడు"}
        out = perturb("title_author_removed", pages, expected, "tel", 42)
        assert out[0]["text"] == ""
        assert "ఆత్మచరిత్రము" not in "".join(p["text"] for p in out)

    def test_injection_lands_on_a_body_page(self):
        pages = [{"n": i, "text": f"page{i}"} for i in range(1, 6)]
        out = perturb("injected_second_date", pages, {}, "tel", 42)
        added = [p["n"] for p in out if "1999" in p["text"]]
        assert added and added[0] not in (1, 5)

    def test_truncation_shortens_every_page(self):
        pages = [{"n": 1, "text": "x" * 100}]
        out = perturb("truncated_tail", pages, {}, "tel", 42)
        assert len(out[0]["text"]) < 100

    def test_original_pages_are_not_mutated(self):
        pages = [{"n": 1, "text": "original"}]
        perturb("duplicated_blocks", pages, {}, "tel", 42)
        assert pages == [{"n": 1, "text": "original"}]


class TestBundleShape:
    def test_wrapper_schema_keeps_the_value_contract(self):
        batch = {"properties": {"title": {"type": "string"}, "pages": {"type": "string"}}}
        schema = wrapper_schema(batch)
        assert set(schema["properties"]) == {"fields", "evidence"}
        assert set(schema["properties"]["fields"]["properties"]) == {"title", "pages"}

    def test_wrapper_schema_allows_null(self):
        schema = wrapper_schema({"properties": {"title": {"type": "string"}}})
        assert schema["properties"]["fields"]["properties"]["title"]["type"] == ["string", "null"]


class TestRunner:
    def test_payload_carries_the_fixed_config(self):
        record = {
            "system_prompt": "sys",
            "prompt": "usr",
            "schema": {"type": "object"},
        }
        config = {
            "model": "gemma4:e4b",
            "num_ctx": 4096,
            "num_predict": 512,
            "temperature": 0.0,
            "seed": 42,
            "repeat_penalty": 1.0,
            "fmt": "schema",
            "think": False,
            "keep_alive": "30m",
            "num_thread": 3,
        }
        payload = build_payload(record, config)
        assert payload["think"] is False
        assert payload["format"] == {"type": "object"}
        assert payload["options"]["temperature"] == 0.0
        assert payload["options"]["num_ctx"] == 4096
        assert [m["role"] for m in payload["messages"]] == ["system", "user"]

    def test_json_mode_drops_the_schema(self):
        record = {"system_prompt": "s", "prompt": "p", "schema": {"type": "object"}}
        payload = build_payload(record, {"model": "m", "fmt": "json"})
        assert payload["format"] == "json"

    def test_resume_skips_completed_keys_and_tolerates_a_bad_line(self, tmp_path):
        path = tmp_path / "out.jsonl"
        path.write_text('{"key": "a|b|c|d"}\nnot json\n', encoding="utf-8")
        assert load_done(path) == {"a|b|c|d"}

    def test_resume_on_missing_file(self, tmp_path):
        assert load_done(tmp_path / "nope.jsonl") == set()


class TestStressSampleIds:
    def test_case_and_base_ids(self):
        assert _case_of("tel/confusables_30/some_book") == "confusables_30"
        assert _case_of("tel/some_book") is None
        assert _base_sample_id("tel/confusables_30/some_book") == "tel/some_book"
        assert _base_sample_id("tel/some_book") == "tel/some_book"


class TestManifestRoundTrip:
    def test_corpus_payload_is_json_serialisable(self, tmp_path):
        from scripts.prompt_eval import common

        payload = {"pages": [{"n": 1, "text": "x"}], "meta": {"built_at": "now"}}
        path = tmp_path / "book.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        assert json.loads(path.read_text(encoding="utf-8"))["pages"][0]["n"] == 1
        assert common.MAX_OCR_CHARS == 2500


class TestCorpusPageFilter:
    """The corpus must skip library slips and keep metadata-bearing pages."""

    def test_short_page_is_noise(self):
        from scripts.prompt_eval.build_corpus import _is_noise_page

        assert _is_noise_page("ok", "hin") is True

    def test_library_marker_is_noise(self):
        from scripts.prompt_eval.build_corpus import _is_noise_page

        assert _is_noise_page("BANASTHALI VIDYAPEETH पुस्तकालय accession no 1234 " * 2, "hin") is True

    def test_latin_dominated_hindi_page_is_noise(self):
        from scripts.prompt_eval.build_corpus import _is_noise_page

        typed_form = "Accession No 447 Date of receipt 12/08/2005 Class No 891.43 " * 2
        assert _is_noise_page(typed_form, "hin") is True

    def test_short_title_page_is_kept(self):
        from scripts.prompt_eval.build_corpus import _is_noise_page

        # Measured in the corpus: this 17-character page was a book's title and
        # the length floor was discarding it.
        assert _is_noise_page("यह गली बिकाऊ नहीं", "hin") is False

    def test_library_word_inside_body_text_is_not_noise(self):
        from scripts.prompt_eval.build_corpus import _is_noise_page

        body = "इस पुस्तकालय में रखी पुस्तकों का विवरण इस प्रकार है। " * 40
        assert _is_noise_page(body, "hin") is False

    def test_latin_title_page_is_kept(self):
        from scripts.prompt_eval.build_corpus import _is_noise_page

        # Latin-dominant alone is not a reason to drop: a Latin-transliterated
        # ground truth can only ever match a Latin title page.
        assert _is_noise_page("Sadhu Aur Vaishya", "hin") is False

    def test_licence_page_is_noise(self):
        from scripts.prompt_eval.build_corpus import _is_noise_page

        page = "This work is licensed under https://creativecommons.org/licenses/by/4.0/ " * 2
        assert _is_noise_page(page, "hin") is True

    def test_normal_devanagari_page_is_kept(self):
        from scripts.prompt_eval.build_corpus import _is_noise_page

        page = "प्रकाशक: राजकमल प्रकाशन, नई दिल्ली। मुद्रक: नेशनल प्रिंटिंग प्रेस, नोएडा। " * 3
        assert _is_noise_page(page, "hin") is False

    def test_latin_page_kept_for_english_book(self):
        from scripts.prompt_eval.build_corpus import _is_noise_page

        page = "Published by National Book Trust, New Delhi. Printed at National Printing Press. " * 2
        assert _is_noise_page(page, "eng") is False

    def test_select_pages_drops_noise_and_caps_the_band(self):
        from scripts.prompt_eval import common
        from scripts.prompt_eval.build_corpus import _select_pages

        pages = [{"n": 1, "text": "x"}]  # noise (too short)
        pages += [{"n": n, "text": "प्रकाशक: राजकमल प्रकाशन, नई दिल्ली। " * 3} for n in range(2, 40)]
        kept = _select_pages(pages, "hin")
        assert all(p["n"] != 1 for p in kept)
        assert len(kept) <= common.FRONT_KEEP + common.TAIL_KEEP
        assert [p["n"] for p in kept] == sorted(p["n"] for p in kept)

    def test_select_pages_returns_empty_when_all_noise(self):
        from scripts.prompt_eval.build_corpus import _select_pages

        assert _select_pages([{"n": 1, "text": "x"}], "hin") == []
