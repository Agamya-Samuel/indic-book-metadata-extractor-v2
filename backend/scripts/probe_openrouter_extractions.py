#!/usr/bin/env python3
"""Probe OpenRouter's Extractions API (typed fields) against Indic title pages.

Unlike the Decisions API, these models answer with VALUES (a span of the input),
plus `confidence`, a span offset and -- where supported -- `p_null`.

!! This script SPENDS MONEY. !! Input-only pricing, no output tokens:
    cloudflare/clairic    $0.10 / 1M input tokens
    scaledown/extract     $0.04 / 1M input tokens
A 5-field image call costs ~$0.0004; a 5-field text call ~$0.00002-$0.0001.
It will not run without --yes-spend.

Modes mirror the six probes in learnings/009-decision-classification-models.md (section 10):
    image    real Telugu title-page image (tests the vendor's vision / built-in OCR)
    text     the page's proofread te.wikisource text (OCR-error-free upper bound)
    corrupt  the same Telugu text with p=0.45 glyph corruption (our OCR CER band)
    hindi    a synthetic Hindi title page

Usage:
    pdftoppm -f 3 -l 3 -r 150 -png \\
        backend/tests/fixtures/ground_truth/tel/2015.373190.Athma-Charitramu/original.pdf /tmp/tp
    python3 backend/scripts/probe_openrouter_extractions.py --model scaledown/extract \\
        --mode text --yes-spend
    python3 backend/scripts/probe_openrouter_extractions.py --model cloudflare/clairic \\
        --mode image --image /tmp/tp-003.png --yes-spend
"""

from __future__ import annotations

import argparse
import base64
import json
import random
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENDPOINT = "https://openrouter.ai/api/alpha/extractions"

# PDF page 3 of 2015.373190.Athma-Charitramu -- the title page, proofread on te.wikisource
PAGE3 = (
    "ఆంధ్రగ్రంథమాల : 22\n\nAUTOBIOGRAPHY:\nR. Venkata Sivudu, M. A., L. T., GUNTUR\n\n"
    "ఆత్మచరిత్రము.\n\nగ్రంథకర్త:\nరాయసము వెంకటశివుఁడు, యం. యె., యల్. టి.,\nగుంటూరు.\n\n"
    "ఆంధ్ర పత్రికా ముద్రాలయము : మద్రాసు.\n1933\n"
)
HINDI = "उम्मेदसिंह चरित्र।\n\nलेखक:\nलज्जाराम शर्मा।\n\nप्रकाशक:\nश्रीवेंकटेश्वर स्टीम् प्रेस, बम्बई।\n\nसन् १९१३।\n"
TELUGU_POOL = "అఆఇఈఉఊకఖగఘచఛజఝటఠడఢణతథదధనపఫబభమయరలవశషసహాిీుూెేొో్క్ం"
GROUND_TRUTH = {
    "title": "ఆత్మచరిత్రము",
    "author": "రాయసము వెంకటశివుఁడు",
    "publisher": "ఆంధ్ర పత్రికా ముద్రాలయము",
    "place_of_publication": "మద్రాసు",
    "publication_year": "1933",
}
FIELDS = {
    "title": {"type": "text", "instructions": "the title of the book as printed"},
    "author": {"type": "text", "instructions": "the author's personal name as printed"},
    "publisher": {"type": "text", "instructions": "the publisher or printing press name as printed"},
    "place_of_publication": {"type": "text", "instructions": "the place of publication as printed"},
    "publication_year": {"type": "text", "instructions": "the year of publication as printed"},
}


def api_key() -> str:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit(f"OPENROUTER_API_KEY not found in {REPO / '.env'}")


def corrupt(text: str, p: float, seed: int = 11) -> str:
    keep = "\n: .0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz,"
    rnd = random.Random(seed)
    return "".join(ch if (ch in keep or rnd.random() > p) else rnd.choice(TELUGU_POOL) for ch in text)


def build(model: str, mode: str, image: Path | None) -> dict:
    body: dict = {"model": model, "fields": FIELDS}
    if mode == "text":
        body["state"] = PAGE3
    elif mode == "corrupt":
        body["state"] = corrupt(PAGE3, 0.45)
    elif mode == "hindi":
        body["state"] = HINDI
    else:
        if image is None:
            sys.exit("--image is required for image mode")
        body["assets"] = {
            "tp": {
                "type": "image",
                "format": image.suffix.lstrip(".").replace("jpg", "jpeg"),
                "data_base64": base64.b64encode(image.read_bytes()).decode(),
            }
        }
        body["state"] = "tp"
    return body


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="scaledown/extract", choices=["scaledown/extract", "cloudflare/clairic"])
    ap.add_argument("--mode", default="text", choices=["text", "corrupt", "hindi", "image"])
    ap.add_argument("--image", type=Path, help="page image for --mode image")
    ap.add_argument("--yes-spend", action="store_true", help="acknowledge that this call costs money")
    args = ap.parse_args()

    body = build(args.model, args.mode, args.image)
    payload = json.dumps(body).encode()
    if not args.yes_spend:
        rate = {"cloudflare/clairic": 0.10, "scaledown/extract": 0.04}[args.model]
        if args.mode == "image":
            print(f"DRY RUN: {args.model} mode=image, request body {len(payload):,} bytes.")
            print(
                "Image tokens are counted by the provider, not from base64 length: the "
                "measured 5-field call on a 150-dpi Telugu page was 3,945 tokens = $0.00039."
            )
        else:
            print(
                f"DRY RUN: {args.model} mode={args.mode}, request body {len(payload):,} bytes "
                f"-> roughly ${len(payload) / 4 / 1e6 * rate:.6f} at ${rate}/M input tokens."
            )
        print("Re-run with --yes-spend to actually call. See the spend note in the module docstring.")
        return 0

    req = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"},
    )
    print("ground truth:", json.dumps(GROUND_TRUTH, ensure_ascii=False))
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            out = json.loads(r.read())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:600])
        return 1

    answers = out.get("fields") or out.get("answers") or {}
    for name in FIELDS:
        a = answers.get(name) or {}
        value = a.get("value")
        mark = "OK " if isinstance(value, str) and any(c > "\u0900" for c in value) else "?? "
        print(
            f"  {name:22s} {mark}value={value!r}  p_null={a.get('p_null')} "
            f"conf={a.get('confidence')} span={a.get('span')}"
        )
    print("usage:", json.dumps(out.get("usage", {}), ensure_ascii=False))
    print("truncated:", out.get("truncated"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
