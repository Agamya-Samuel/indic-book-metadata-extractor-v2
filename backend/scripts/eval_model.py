#!/usr/bin/env python3
"""Evaluate a Tesseract .traineddata file against a held-out test set.

Usage:
    uv run python scripts/eval_model.py \
        --model /app/storage/models/hin_v2/hin.traineddata \
        --test-list /app/storage/training_data/hin/test.tsv \
        --base-model /usr/share/tesseract-ocr/5/tessdata/hin.traineddata \
        --max-cer-degradation 2.0

The test list is a TSV with ``<image_path>\t<ground_truth_text>`` lines.

Exits non-zero if the new model's Character Error Rate (CER) is more than
``--max-cer-degradation`` points worse than the base model — this prevents a
bad fine-tune from being deployed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import Levenshtein  # type: ignore[import-untyped]  # provided via uv dependency below
import pytesseract
from PIL import Image


def _edit_distance(a: str, b: str) -> int:
    if not a or not b:
        return max(len(a), len(b))
    return Levenshtein.distance(a, b)


def _score_one(model: Path, image: Path, ground_truth: str, lang: str) -> float:
    img = Image.open(image)
    pytesseract.pytesseract.tessdata_dir = str(model.parent)
    predicted = pytesseract.image_to_string(img, lang=lang, config="--psm 6").strip()
    if not ground_truth:
        return 0.0 if not predicted else 1.0
    return _edit_distance(predicted, ground_truth) / max(len(ground_truth), 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--base-model", type=Path, required=True)
    parser.add_argument("--test-list", type=Path, required=True)
    parser.add_argument("--lang", required=True)
    parser.add_argument("--max-cer-degradation", type=float, default=2.0)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    samples: list[tuple[Path, str]] = []
    with open(args.test_list, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.rstrip("\n")
            if not ln:
                continue
            img, gt = ln.split("\t", 1)
            samples.append((Path(img), gt))
    samples = samples[: args.limit]

    new_cer = sum(_score_one(args.model, img, gt, args.lang) for img, gt in samples) / len(samples)
    base_cer = sum(_score_one(args.base_model, img, gt, args.lang) for img, gt in samples) / len(samples)

    delta = new_cer - base_cer
    print(f"Base CER:  {base_cer:.4f}")
    print(f"New  CER:  {new_cer:.4f}")
    print(f"Delta:     {delta:+.4f}")

    if delta > args.max_cer_degradation:
        print(
            f"FAIL: new model is {delta:.4f} CER worse than base (threshold {args.max_cer_degradation}).",
            file=sys.stderr,
        )
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())