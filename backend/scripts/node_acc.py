#!/usr/bin/env python3
"""Stdlib-only accuracy runner for a remote Ollama node.

Reads a bundle produced by make_eval_bundle.py, calls Ollama /api/chat for
each batch (grammar-constrained JSON), and writes one JSONL record per batch.

Usage:
    python3 node_acc.py <bundle.json> <model> <out.jsonl> [think0]
      think0 = "1" sets think=false (needed for thinking models)
"""

import json
import sys
import time
import urllib.request

API = "http://localhost:11434"


def call(payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        API + "/api/chat",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read().decode())


def gen(model, system_prompt, prompt, schema, think):
    base = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "num_ctx": 8192,
            "num_predict": 1024,
            "temperature": 0,
            "repeat_penalty": 1.1,
        },
    }
    if think:
        base["think"] = False
    # Try grammar-constrained; fall back to plain JSON mode.
    for fmt in (schema, "json"):
        payload = dict(base, format=fmt)
        try:
            return call(payload)
        except Exception as exc:  # noqa: BLE001
            if fmt is schema:
                continue
            raise exc
    raise RuntimeError("unreachable")


def tps(count, dur):
    if count and dur:
        return round(count / (dur / 1e9), 2)
    return None


def main():
    bundle = json.load(open(sys.argv[1], encoding="utf-8"))
    model = sys.argv[2]
    out_path = sys.argv[3]
    think = len(sys.argv) > 4 and sys.argv[4] == "1"

    # Warm load so load time is excluded from the first measured call.
    try:
        call(
            {
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "options": {"num_predict": 1},
            }
        )
    except Exception as exc:  # noqa: BLE001
        print("warm failed:", exc, flush=True)

    with open(out_path, "a", encoding="utf-8") as out:
        for batch in bundle["batches"]:
            rec = {"model": model, "batch": batch["name"], "think_false": think}
            t0 = time.time()
            try:
                res = gen(model, bundle["system_prompt"], batch["prompt"], batch["schema"], think)
            except Exception as exc:  # noqa: BLE001
                rec["error"] = str(exc)
                out.write(json.dumps(rec) + "\n")
                out.flush()
                print(rec, flush=True)
                continue
            rec["wall_s"] = round(time.time() - t0, 1)
            content = (res.get("message") or {}).get("content") or ""
            rec["thinking_chars"] = len((res.get("message") or {}).get("thinking") or "")
            rec["eval_count"] = res.get("eval_count")
            rec["gen_tok_s"] = tps(res.get("eval_count"), res.get("eval_duration"))
            rec["prefill_tok_s"] = tps(res.get("prompt_eval_count"), res.get("prompt_eval_duration"))
            rec["response_chars"] = len(content)
            rec["parsed"] = None
            try:
                rec["parsed"] = json.loads(content)
            except Exception:  # noqa: BLE001
                rec["raw_snippet"] = content[:200]
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            print(
                f"  {batch['name']:20s} wall={rec['wall_s']}s "
                f"gen={rec['gen_tok_s']} parse={'ok' if rec['parsed'] else 'FAIL'} "
                f"think={rec['thinking_chars']}ch",
                flush=True,
            )
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
