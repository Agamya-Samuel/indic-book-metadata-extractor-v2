#!/usr/bin/env python3
"""Fix Latin-script ``title``/``label``/``author`` in the GT (plans/011, Phase 1).

Some scaffolds store a Roman transliteration (e.g. "Rayasam Venkata Shivudu")
where the book shows the name in Telugu/Devanagari script. This transliterates
those values into the book's own script with a free OpenRouter model, leaving
genuine English titles unchanged. Every change is marked
``prefilled_needs_verification`` with ``field_source=openrouter_transliteration``.

Usage:
    cd backend
    uv run python -m scripts.fix_script --key-file ../reference/openrouter
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx

GT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ground_truth"
API = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "baidu/ernie-5.5-flash-preview:free"
SCRIPT = {"tel": "Telugu", "hin": "Devanagari (Hindi)"}
TARGET_FIELDS = ("title", "label", "author")


def is_latin(text: str) -> bool:
    return not any("\u0900" <= c <= "\u097f" or "\u0c00" <= c <= "\u0c7f" for c in str(text))


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def transliterate(client: httpx.AsyncClient, key: str, script: str, values: dict) -> dict:
    prompt = (
        f"Transliterate these romanised Indic names into {script} script. "
        "If a value is an original English title (not a transliteration), return it unchanged. "
        f"Reply with ONLY a JSON object with the same keys.\n{json.dumps(values, ensure_ascii=False)}"
    )
    r = client.post(API, headers={"Authorization": f"Bearer {key}"}, json={
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
        "temperature": 0,
    })
    r.raise_for_status()
    return parse_json((r.json().get("choices", [{}])[0].get("message", {}) or {}).get("content") or "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=GT_ROOT)
    ap.add_argument("--key-file", type=Path, default=Path("../reference/openrouter"))
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    key = args.key_file.read_text(encoding="utf-8").strip()
    books = sorted(args.root.glob("*/*/expected_metadata.json"))
    if args.limit:
        books = books[: args.limit]

    fixed = tasks = 0
    with httpx.Client(timeout=120.0) as client:
        for gt in books:
            env = json.loads(gt.read_text(encoding="utf-8"))
            em = env.get("expected_metadata", {})
            lang = env.get("language", "tel")
            need = {f: str(em[f]) for f in TARGET_FIELDS if em.get(f) and is_latin(str(em[f]))}
            if not need:
                continue
            tasks += 1
            try:
                out = transliterate(client, key, SCRIPT.get(lang, "Telugu"), need)
            except Exception as e:  # noqa: BLE001
                print(f"  ERR {gt.parent.name[:40]}: {str(e)[:60]}", file=sys.stderr)
                time.sleep(args.delay)
                continue
            changed = 0
            for f, v in out.items():
                if f in need and v and not is_latin(str(v)) and str(v) != str(em[f]):
                    em[f] = str(v).strip()
                    env.setdefault("field_source", {})[f] = "openrouter_transliteration"
                    env.setdefault("field_status", {})[f] = "prefilled_needs_verification"
                    changed += 1
            if changed:
                fixed += changed
                gt.write_text(json.dumps(env, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"  {gt.parent.parent.name}/{gt.parent.name[:40]:40s} {list(need)} -> {changed} fixed")
            time.sleep(args.delay)

    print(f"\n{tasks} books needed fixing · {fixed} fields transliterated")
    return 0


if __name__ == "__main__":
    sys.exit(main())