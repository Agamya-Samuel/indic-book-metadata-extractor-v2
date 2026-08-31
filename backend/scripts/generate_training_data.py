#!/usr/bin/env python3
"""Generate synthetic Tesseract training pages from a text corpus.

Renders each line of an input text file into a synthetic page image using the
requested fonts, then writes a ``training_text.txt`` manifest with
``<image_path>\t<ground_truth_text>`` pairs.

Usage:
    uv run python scripts/generate_training_data.py \
        --corpus /path/to/hindi_text.txt \
        --output-dir /app/storage/training_data/hin \
        --fonts "Noto Sans Devanagari" "Mangal" \
        --image-size 3000x3000

The output dir is what ``train_tesseract_lstm.sh`` consumes.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _list_system_fonts() -> list[Path]:
    """Best-effort scan of /usr/share/fonts."""
    roots = [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
    ]
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        out.extend(root.rglob("*.ttf"))
        out.extend(root.rglob("*.otf"))
    return out


def _resolve_fonts(requested: list[str]) -> list[Path]:
    available = {p.name.lower(): p for p in _list_system_fonts()}
    resolved: list[Path] = []
    for name in requested:
        key = name.lower() + ".ttf"
        if key in available:
            resolved.append(available[key])
            continue
        for fname, path in available.items():
            if name.lower() in fname:
                resolved.append(path)
                break
        else:
            print(f"WARNING: font not found: {name}", file=sys.stderr)
    return resolved


def _render_line(text: str, font: ImageFont.FreeTypeFont, image_w: int) -> Image.Image:
    """Render a single line of text onto a wide enough image."""
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    width = max(bbox[2] + 40, image_w)
    height = bbox[3] - bbox[1] + 40
    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), text, fill=0, font=font)
    return img


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", type=Path, required=True, help="UTF-8 text file, one line per training sample")
    parser.add_argument("--output-dir", type=Path, required=True, help="Where to write images + manifest")
    parser.add_argument("--fonts", nargs="+", default=["Noto Sans Devanagari"], help="Font names to cycle through")
    parser.add_argument("--image-size", default="3000x3000", help="Synthetic image size WxH")
    parser.add_argument("--max-lines", type=int, default=2000, help="Cap on training lines (Tesseract prefers variety)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    fonts = _resolve_fonts(args.fonts)
    if not fonts:
        print("ERROR: no fonts resolved. Install Noto Sans Devanagari or pass --fonts.", file=sys.stderr)
        return 2

    width, height = (int(s) for s in args.image_size.lower().split("x"))
    sample_font_size = 32
    loaded_fonts = [ImageFont.truetype(str(f), sample_font_size) for f in fonts]

    with open(args.corpus, encoding="utf-8") as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]
    random.shuffle(lines)
    lines = lines[: args.max_lines]

    manifest = args.output_dir / "training_text.txt"
    with open(manifest, "w", encoding="utf-8") as out:
        for idx, line in enumerate(lines):
            font = random.choice(loaded_fonts)
            img = _render_line(line, font, width)
            img_h = max(height, img.height)
            canvas = Image.new("L", (width, img_h), 255)
            canvas.paste(img, (0, 0))
            img_path = args.output_dir / f"line_{idx:06d}.png"
            canvas.save(img_path)
            out.write(f"{img_path}\t{line}\n")

    print(f"Wrote {len(lines)} training lines + manifest to {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())