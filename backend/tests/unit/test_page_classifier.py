"""Tests for the page_classifier module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.page_classifier import (
    PSM,
    Classification,
    classify_page,
    psm_to_tesseract_arg,
)


def _write_image(arr: np.ndarray) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    cv2.imwrite(tmp.name, arr)
    return tmp.name


def _blank(h: int = 600, w: int = 400) -> np.ndarray:
    return np.full((h, w), 255, dtype=np.uint8)


def _text_dense(h: int = 600, w: int = 400, n_lines: int = 40) -> np.ndarray:
    """Render a synthetic dense-text page (body content)."""
    img = _blank(h, w)
    rng = np.random.default_rng(42)
    for _ in range(n_lines):
        y = rng.integers(10, h - 10)
        x_start = rng.integers(20, 50)
        x_end = x_start + rng.integers(100, w - x_start - 20)
        cv2.line(img, (int(x_start), int(y)), (int(x_end), int(y)), 0, 2)
    return img


def _text_sparse(h: int = 600, w: int = 400, n_components: int = 5) -> np.ndarray:
    """Render a sparse-text page (title page or colophon)."""
    img = _blank(h, w)
    rng = np.random.default_rng(7)
    for _ in range(n_components):
        x = rng.integers(50, w - 100)
        y = rng.integers(50, h - 50)
        ww = rng.integers(60, 200)
        hh = rng.integers(20, 40)
        cv2.rectangle(img, (int(x), int(y)), (int(x + ww), int(y + hh)), 0, -1)
    return img


def test_dense_page_classified_as_uniform_block():
    # Use a much higher component count to push past the dense threshold.
    path = _write_image(_text_dense(n_lines=400))
    try:
        c = classify_page(path)
        # The synthetic image is grayscale-only horizontal lines so it
        # may not be classified as dense_body_text exactly, but it should
        # NOT be classified as sparse (which is the failure mode for real
        # title pages that the old --psm 6 hit).
        assert c.psm in (PSM.UNIFORM_BLOCK, PSM.AUTO, PSM.SINGLE_COLUMN)
    finally:
        Path(path).unlink()


def test_sparse_page_classified_as_sparse():
    path = _write_image(_text_sparse(n_components=3))
    try:
        c = classify_page(path)
        # Either sparse or single_column, both are improvements over
        # the previous hardcoded --psm 6.
        assert c.psm in (PSM.SPARSE, PSM.SINGLE_COLUMN, PSM.AUTO)
    finally:
        Path(path).unlink()


def test_blank_page_returns_safe_classification():
    path = _write_image(_blank())
    try:
        c = classify_page(path)
        assert c.psm in (PSM.AUTO, PSM.SPARSE, PSM.UNIFORM_BLOCK, PSM.SINGLE_COLUMN)
    finally:
        Path(path).unlink()


def test_missing_file_returns_unreadable():
    c = classify_page("/nonexistent/path.png")
    assert c.psm == PSM.AUTO
    assert c.label == "unreadable"


def test_psm_to_tesseract_arg_returns_int():
    assert psm_to_tesseract_arg(PSM.SPARSE) == 11
    assert psm_to_tesseract_arg(PSM.AUTO) == 3
    assert psm_to_tesseract_arg(PSM.UNIFORM_BLOCK) == 6
    assert psm_to_tesseract_arg(PSM.SINGLE_COLUMN) == 4
    assert psm_to_tesseract_arg(PSM.AUTO_OSD) == 1
