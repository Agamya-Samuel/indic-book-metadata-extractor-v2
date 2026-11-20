#!/usr/bin/env python3
"""Regenerate the Wikibase branding assets from the frontend's OKI logo.

    python3 docker/wikibase/make-branding.py

Reads ``frontend/public/Open_Knowledge_Initiatives_logo.png`` and writes:

* ``docker/wikibase/images/logo.png`` — the full lockup, unchanged.
* ``docker/wikibase/images/icon.png`` — a square icon built from the emblem.

The emblem is the left-hand mark of the lockup. Its box below was derived from
the source by connected-component analysis of the alpha channel (largest
component) plus a colour check: the emblem is multi-colour (teal + black),
while the wordmark to its right is single-colour black and sits on a separate
component. Keep the two in step if the source artwork is ever replaced.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "frontend" / "public" / "Open_Knowledge_Initiatives_logo.png"
IMAGES = REPO_ROOT / "docker" / "wikibase" / "images"

# (left, top, right, bottom) of the emblem inside the source artwork.
EMBLEM_BOX = (184, 252, 1012, 720)

ICON_SIZE = 512
ICON_PADDING = 0.04  # fraction of the canvas kept clear on each side


def main() -> int:
    if not SOURCE.is_file():
        print(f"missing source artwork: {SOURCE}", file=sys.stderr)
        return 1

    src = Image.open(SOURCE).convert("RGBA")
    if src.size != (2048, 1106):
        print(
            f"unexpected source size {src.size}; re-derive EMBLEM_BOX before using it",
            file=sys.stderr,
        )
        return 1

    x0, y0, x1, y1 = EMBLEM_BOX
    if not (0 <= x0 < x1 <= src.width and 0 <= y0 < y1 <= src.height):
        print(f"emblem box {EMBLEM_BOX} outside {src.size}", file=sys.stderr)
        return 1

    IMAGES.mkdir(parents=True, exist_ok=True)

    # The lockup is the artwork unmodified; only the icon is derived.
    shutil.copyfile(SOURCE, IMAGES / "logo.png")

    emblem = src.crop((x0, y0, x1, y1))
    usable = int(ICON_SIZE * (1 - 2 * ICON_PADDING))
    scale = min(usable / emblem.width, usable / emblem.height)
    resized = emblem.resize(
        (max(1, round(emblem.width * scale)), max(1, round(emblem.height * scale))),
        Image.LANCZOS,
    )

    icon = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    icon.paste(
        resized,
        ((ICON_SIZE - resized.width) // 2, (ICON_SIZE - resized.height) // 2),
    )
    icon.save(IMAGES / "icon.png", optimize=True)

    print(f"logo.png {src.width}x{src.height} (lockup)")
    print(f"icon.png {icon.width}x{icon.height} (emblem {emblem.width}x{emblem.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())