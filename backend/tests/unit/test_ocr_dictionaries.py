from __future__ import annotations

from app.services.ocr_dictionaries import get_dictionary_paths


class TestGetDictionaryPaths:
    def test_hindi_returns_paths(self):
        words, patterns = get_dictionary_paths("hin")
        assert words is not None
        assert patterns is not None
        assert words.name == "hin.words"
        assert patterns.name == "hin.patterns"

    def test_telugu_returns_paths(self):
        words, patterns = get_dictionary_paths("tel")
        assert words is not None
        assert patterns is not None
        assert words.name == "tel.words"

    def test_english_returns_paths(self):
        words, patterns = get_dictionary_paths("eng")
        assert words is not None
        assert patterns is not None
        assert words.name == "eng.words"

    def test_unsupported_indic_scripts_return_none(self):
        # Tamil, Bengali, etc. have no dictionary — must not silently fall
        # back to English (would bias LSTM toward Latin transliteration).
        for code in ("tam", "kan", "mal", "ben", "guj", "pan", "ori", "mar", "san", "nepl"):
            words, patterns = get_dictionary_paths(code)
            assert words is None, f"unsupported lang {code} should return None, not {words}"
            assert patterns is None

    def test_unknown_language_returns_none(self):
        words, patterns = get_dictionary_paths("xyz_unknown")
        assert words is None
        assert patterns is None
