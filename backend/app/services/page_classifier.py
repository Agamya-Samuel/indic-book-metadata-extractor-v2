"""Cheap, no-ML page classifier for picking the right Tesseract PSM.

Tesseract's --psm (page segmentation mode) dramatically affects accuracy
on title pages, copyright pages, and colophons. Hardcoding --psm 6 (uniform
block) is a known accuracy killer for these.

The classifier here is intentionally lightweight:

  * Run a fast connected-components analysis on a downsampled grayscale.
  * Use component density and aspect ratio to bucket the page.
  * Map each bucket to the PSM that's known to work best for it.

**--psm 11 (SPARSE) is deliberately not used for whole pages.** It tells
Tesseract to find as much text as possible with no layout assumptions, and on
Indic scripts it does the opposite of what it promises: decorative borders and
margins get read as Latin rubble and matras are dropped. Measured on the
ground-truth corpus, 25 of 72 front-matter pages were classified "sparse" and
their text was unusable; re-running the same pages at --psm 4 raised the
Devanagari share from 0.46-0.69 to 0.57-0.75. Short/loosely-set pages get
SINGLE_COLUMN (4) instead, which is the mode they actually need.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import cv2


class PSM(IntEnum):
    """Tesseract page segmentation modes we care about."""

    AUTO_OSD = 1
    AUTO = 3
    SINGLE_COLUMN = 4
    UNIFORM_BLOCK = 6


@dataclass(frozen=True)
class Classification:
    psm: PSM
    label: str  # human-readable for logging


def classify_page(image_path: str) -> Classification:
    """Classify a single page image and pick a Tesseract PSM.

    The heuristic is intentionally simple — we want this to add < 50ms
    per page so it doesn't dominate the OCR pipeline. Anything that
    isn't clearly a sparse page gets --psm 3 (auto), which is the
    safest general-purpose mode.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return Classification(psm=PSM.AUTO, label="unreadable")

    h, w = img.shape[:2]
    if h == 0 or w == 0:
        return Classification(psm=PSM.AUTO, label="empty")

    # Downsample for speed. 400px on the long edge is plenty.
    long_edge = max(h, w)
    if long_edge > 400:
        scale = 400 / long_edge
        small = cv2.resize(img, (int(w * scale), int(h * scale)))
    else:
        small = img

    # Binarize with Otsu to find text components.
    _, binary = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Find connected components of text.
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    # Filter to plausible text components: area 30-5000 pixels, aspect ratio sane.
    text_components = 0
    total_text_area = 0
    for i in range(1, n_labels):
        x, y, ww, hh, area = stats[i]
        if area < 30 or area > 5000:
            continue
        if hh == 0 or ww == 0:
            continue
        ar = max(ww, hh) / max(1, min(ww, hh))
        if ar > 10:  # very thin or very flat = likely noise
            continue
        text_components += 1
        total_text_area += area

    total_area = small.shape[0] * small.shape[1]
    density = total_text_area / total_area if total_area > 0 else 0

    # Heuristics tuned for the OKI sample books. At this downscale almost every
    # page lands under 60 components, so SINGLE_COLUMN must stay the exception:
    # AUTO (PSM 3) is the safest general mode, and measured identical to PSM 4
    # on normal body pages. Only clearly sparse pages get the single-column mode.
    if text_components < 40 and density < 0.08:
        return Classification(psm=PSM.SINGLE_COLUMN, label="sparse_colophon_or_blank")
    return Classification(psm=PSM.AUTO, label="default_auto")


def psm_to_tesseract_arg(psm: PSM) -> int:
    """Return the int Tesseract wants on the --psm flag."""
    return int(psm)
