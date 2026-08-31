from __future__ import annotations

import unicodedata

from app.services.ocr_postprocess import (
    Correction,
    _danda_cleanup,
    _zwj_cleanup,
    normalize_text,
)


class TestNormalizeText:
    def test_empty_string(self):
        cleaned, corrections = normalize_text("", "hin")
        assert cleaned == ""
        assert corrections == []

    def test_passthrough_english(self):
        cleaned, corrections = normalize_text("Hello World", "eng")
        assert cleaned == "Hello World"
        # NFC may or may not flag; should not have spurious corrections
        rule_names = {c["rule"] for c in corrections}
        assert "danda_normalize" not in rule_names

    def test_nfc_normalization(self):
        # 'café' with combining acute — NFD form
        nfd = "cafe\u0301"
        cleaned, corrections = normalize_text(nfd, "eng")
        assert cleaned == unicodedata.normalize("NFC", nfd)

    def test_danda_pipe_replacement(self):
        cleaned, corrections = normalize_text("a | b", "hin")
        assert cleaned == "a । b"
        rules = [c["rule"] for c in corrections]
        assert "danda_normalize" in rules

    def test_double_danda_first(self):
        cleaned, _ = normalize_text("x || y", "hin")
        assert cleaned == "x ॥ y"

    def test_anusvara_skipped_for_non_devanagari(self):
        cleaned, corrections = normalize_text("संकल्प", "tam")
        # Tamil language flag → anusvara rule should not fire
        assert not any(c["rule"] == "devanagari_anusvara_to_class_nasal" for c in corrections)


class TestDandaCleanup:
    def test_double_first(self):
        out, corrections = _danda_cleanup("a || b")
        assert out == "a ॥ b"

    def test_single_pipe(self):
        out, _ = _danda_cleanup("a | b")
        assert out == "a । b"


class TestZwjCleanup:
    def test_strips_zwj(self):
        out, corrections = _zwj_cleanup("a\u200db")
        assert out == "ab"
        assert any(c.rule == "strip_spurious_zwj" for c in corrections)

    def test_strips_zwnj(self):
        out, corrections = _zwj_cleanup("a\u200cb")
        assert out == "ab"
        assert any(c.rule == "strip_spurious_zwnj" for c in corrections)

    def test_no_op_when_absent(self):
        out, corrections = _zwj_cleanup("plain")
        assert out == "plain"
        assert corrections == []


class TestCorrectionDataclass:
    def test_to_dict(self):
        c = Correction(original="a", replacement="b", position=10, rule="test")
        d = c.to_dict()
        assert d == {"original": "a", "replacement": "b", "position": 10, "rule": "test"}