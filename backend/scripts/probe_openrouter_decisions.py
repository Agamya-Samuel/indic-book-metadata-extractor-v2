#!/usr/bin/env python3
"""Probe OpenRouter's Decisions API (typed judgments) against Indic title pages.

Free routes only: every call here must report usage.cost == 0. Uses the
`decisions` output modality, where a model answers `choice` / `noul` / `score`
questions about a `state` and returns typed answers with probabilities --
never values. Step 1 demonstrates that a value-typed field is refused.

Steps:
    1. --schema-check   send a {"type": "text"} question and show the HTTP 400
    2. classify a Telugu + a Hindi title page (choice / noul / score)
    3. --corrupt        repeat under simulated OCR glyph corruption (p = .20/.45)

Usage:
    python3 backend/scripts/probe_openrouter_decisions.py [--model M] [--corrupt]

Findings are written up in learnings/009-decision-classification-models.md (section 9).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
FREE_MODEL = "parallel/decisions-fast:free"

TELUGU = (
    "ఆత్మచరిత్రము\nరచయిత: రాయసం వెంకట శివుడు\n"
    "ప్రచురణకర్త: ఆంధ్ర పత్రికా ముద్రాలయము\nమద్రాసు 1933\n"
    "  ॥ ౧ ॥  (పుట 2)  ---  ఆం.ప.ముద్రాలయము, చెన్నపురి"
)
HINDI = (
    "उम्मेदसिंह चरित्र\nलेखक: लज्जाराम शर्मा\n"
    "प्रकाशक: श्रीवेंकटेश्वर स्टीम् प्रेस, बम्बई\n१९१३\n"
    "  ---  पृष्ठ २ ..... मूल्य ४ आना"
)
TELUGU_POOL = "అఆఇఈఉఊకఖగఘచఛజఝటఠడఢణతథదధనపఫబభమయరలవశషసహాిీుూెేొో్క్ం"

QUESTIONS = {
    "language": {
        "type": "choice",
        "instructions": "Which language is this text written in?",
        "criteria": {
            "telugu": "Telugu, written in Telugu script",
            "hindi": "Hindi, written in Devanagari script",
            "english": "English",
            "sanskrit": "Sanskrit",
            "other": "none of the above",
        },
    },
    "has_title": {
        "type": "noul",
        "instructions": "Does the text state the title of the book itself?",
        "criteria": {"true": "a work title is stated", "false": "no work title is present"},
    },
    "form": {
        "type": "choice",
        "instructions": "What form of creative work is described?",
        "criteria": {
            "book": "an independent book",
            "journal": "a journal or periodical issue",
            "article": "an article inside a journal",
            "manuscript": "a manuscript",
            "other": "none of the above",
        },
    },
    "has_publisher": {
        "type": "noul",
        "instructions": "Does the text name a publisher or press?",
        "criteria": {"true": "a publisher or press is named", "false": "no publisher is named"},
    },
}


def api_key() -> str:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit(f"OPENROUTER_API_KEY not found in {REPO / '.env'}")


def post(key: str, body: dict) -> tuple[int, object]:
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:600]


def corrupt(text: str, p: float, seed: int = 7) -> str:
    rnd = random.Random(seed)
    return "".join(
        ch if (ch in "\n: " or rnd.random() > p) else rnd.choice(TELUGU_POOL) for ch in text
    )


def show(label: str, status: int, body: object) -> None:
    print(f"\n===== {label} | HTTP {status} =====")
    if isinstance(body, str):
        print(body)
        return
    answers = body.get("answers", {})
    for qid, a in answers.items():
        kind = a.get("type")
        if kind == "choice":
            print(f"  {qid:14s} choice={a['choice']!r} conf={a['confidence']:.3f}")
        elif kind == "noul":
            print(f"  {qid:14s} noul={a['noul']:.3f}")
        else:
            print(f"  {qid:14s} {kind}={a.get(kind)} conf={a.get('confidence')}")
    usage = body.get("usage", {})
    print(f"  usage: in={usage.get('input_tokens')} out={usage.get('output_tokens')} "
          f"cost=${usage.get('cost')}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default=FREE_MODEL, help=f"decision model id (default: {FREE_MODEL})")
    ap.add_argument("--corrupt", action="store_true", help="also run the Telugu state at p=0.20 and p=0.45")
    args = ap.parse_args()
    key = api_key()

    # 1. value-typed question is refused by the API itself
    bad = {"publisher_name": {"type": "text", "instructions": "the publisher name, verbatim"}}
    status, body = post(key, {"model": args.model, "state": TELUGU, "questions": bad})
    print("===== 1. value-typed field (expect HTTP 400) =====")
    print(f"HTTP {status}: {str(body)[:300]}")

    # 2. classification on both scripts
    for label, state in (("TELUGU", TELUGU), ("HINDI", HINDI)):
        status, body = post(key, {"model": args.model, "state": state, "questions": QUESTIONS})
        show(label, status, body)

    # 3. robustness under simulated OCR corruption
    if args.corrupt:
        for p in (0.20, 0.45):
            status, body = post(
                key, {"model": args.model, "state": corrupt(TELUGU, p), "questions": QUESTIONS}
            )
            show(f"TELUGU corrupted p={p}", status, body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
