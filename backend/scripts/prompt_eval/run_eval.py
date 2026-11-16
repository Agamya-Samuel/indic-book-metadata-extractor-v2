#!/usr/bin/env python3
"""Run prompt bundles against Ollama's native ``/api/chat`` (stdlib only).

Designed to be copied to a bare benchmark node: no backend install, no
pydantic, no app imports. Bundles are produced locally by
``build_bundles.py`` and contain everything needed to make the call.

Guarantees that matter for a fair comparison:

* every request uses the same generation options (they travel with the bundle);
* ``think:false`` is sent, so a thinking model cannot spend the output budget
  on its reasoning channel and return nothing (learnings/018);
* ``num_ctx``/``num_thread`` never change mid-run, so Ollama's prompt-prefix
  cache stays warm (~4x faster, learnings/018 finding 7);
* the runner is **resumable** — a re-run skips ``(variant, book, batch)`` keys
  already present in the output, so a node reboot costs one batch, not one run.

Usage:
    python3 run_eval.py --bundles V00.clean.jsonl --out results/V00.clean.jsonl
    python3 run_eval.py --bundles *.jsonl --out results/all.jsonl --shard 1/3
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_API = "http://localhost:11434"


def post(api: str, path: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        f"{api}{path}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def warm(api: str, model: str, config: dict, timeout: float) -> None:
    """Load the model once so load time is not billed to the first prompt."""
    try:
        post(
            api,
            "/api/chat",
            {
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "keep_alive": config.get("keep_alive", "30m"),
                "think": False,
                "options": {
                    "num_ctx": config.get("num_ctx"),
                    "num_predict": 1,
                    "num_thread": config.get("num_thread"),
                },
            },
            timeout,
        )
    except Exception as exc:  # noqa: BLE001 - a failed warm-up is not fatal
        print(f"warn: warm-up failed: {exc}", file=sys.stderr, flush=True)


def build_payload(record: dict, config: dict) -> dict:
    return {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": record["system_prompt"]},
            {"role": "user", "content": record["prompt"]},
        ],
        "stream": False,
        "keep_alive": config.get("keep_alive", "30m"),
        "think": bool(config.get("think", False)),
        "format": record["schema"] if config.get("fmt") == "schema" else "json",
        "options": {
            "num_ctx": config.get("num_ctx", 4096),
            "num_predict": config.get("num_predict", 512),
            "temperature": config.get("temperature", 0.0),
            "seed": config.get("seed", 42),
            "repeat_penalty": config.get("repeat_penalty", 1.0),
            "num_thread": config.get("num_thread", 3),
        },
    }


def load_done(out_path: Path) -> set[str]:
    if not out_path.is_file():
        return set()
    done = set()
    with out_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["key"])
            except Exception:  # noqa: BLE001 - tolerate a truncated last line
                continue
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundles", nargs="+", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--limit", type=int, default=0, help="Max records this invocation")
    parser.add_argument(
        "--shard",
        default="",
        help="'i/N' to run every i-th record (0-based), for splitting across nodes",
    )
    parser.add_argument(
        "--book-index",
        default="",
        help=(
            "'i/N' to run only books assigned to this node by stable hash. Prefer this over "
            "--shard: it keeps all of a book's batches on one node, so the system-prompt "
            "prefix stays cached instead of alternating between variants."
        ),
    )
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    records: list[dict] = []
    for path in args.bundles:
        with path.open(encoding="utf-8") as handle:
            records.extend(json.loads(line) for line in handle if line.strip())
    if not records:
        print("error: no bundle records", file=sys.stderr)
        return 2

    if args.shard:
        index, total = (int(part) for part in args.shard.split("/"))
        if not 0 <= index < total:
            print(f"error: shard {args.shard} out of range", file=sys.stderr)
            return 2
        records = records[index::total]

    if args.book_index:
        index, total = (int(part) for part in args.book_index.split("/"))
        if not 0 <= index < total:
            print(f"error: book-index {args.book_index} out of range", file=sys.stderr)
            return 2
        # Round-robin over *sorted unique* books: balanced to within one book,
        # and every node agrees on the assignment because the sort is stable.
        # A hash split was tried first and produced 2600/3016/1768 calls — a
        # 46-hour tail on the unlucky node.
        books_sorted = sorted({r["sample_id"] for r in records})
        mine = {book for position, book in enumerate(books_sorted) if position % total == index}
        records = [r for r in records if r["sample_id"] in mine]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    done = set() if args.no_resume else load_done(args.out)
    pending = [record for record in records if record["key"] not in done]
    if args.limit:
        pending = pending[: args.limit]

    config = records[0]["config"]
    print(
        f"{len(records)} record(s) in scope, {len(done)} already done, {len(pending)} to run "
        f"@ {args.api}  model={config['model']} ctx={config['num_ctx']} "
        f"temp={config['temperature']} seed={config['seed']} fmt={config['fmt']}",
        flush=True,
    )
    if not pending:
        print("nothing to do", flush=True)
        return 0

    warm(args.api, config["model"], config, args.timeout)

    failures = 0
    started = time.time()
    with args.out.open("a", encoding="utf-8") as out:
        for position, record in enumerate(pending, start=1):
            payload = build_payload(record, config)
            result: dict = {
                "key": record["key"],
                "variant": record["variant"],
                "track": record["track"],
                "sample_id": record["sample_id"],
                "book": record["book"],
                "language": record["language"],
                "batch": record["batch"],
                "case": record.get("case"),
                "output_mode": record.get("output_mode", "batch_schema"),
                "model": config["model"],
                "config": {
                    key: config.get(key)
                    for key in ("num_ctx", "num_predict", "temperature", "seed", "repeat_penalty", "fmt", "num_thread")
                },
            }
            t0 = time.time()
            try:
                response = post(args.api, "/api/chat", payload, args.timeout)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")[:400]
                # A model may reject a schema it cannot compile; degrade to
                # plain JSON mode rather than losing the data point.
                if payload["format"] != "json":
                    payload["format"] = "json"
                    try:
                        response = post(args.api, "/api/chat", payload, args.timeout)
                        result["schema_rejected"] = body
                    except Exception as retry_exc:  # noqa: BLE001
                        result["error"] = f"{type(retry_exc).__name__}: {retry_exc}"
                        result["wall_s"] = round(time.time() - t0, 1)
                        out.write(json.dumps(result, ensure_ascii=False) + "\n")
                        out.flush()
                        failures += 1
                        continue
                else:
                    result["error"] = f"{type(exc).__name__}: {body}"
                    result["wall_s"] = round(time.time() - t0, 1)
                    out.write(json.dumps(result, ensure_ascii=False) + "\n")
                    out.flush()
                    failures += 1
                    continue
            except Exception as exc:  # noqa: BLE001 - record and keep going
                result["error"] = f"{type(exc).__name__}: {exc}"
                result["wall_s"] = round(time.time() - t0, 1)
                out.write(json.dumps(result, ensure_ascii=False) + "\n")
                out.flush()
                failures += 1
                continue

            message = response.get("message") or {}
            content = message.get("content") or ""
            result.update(
                {
                    "wall_s": round(time.time() - t0, 1),
                    "response_chars": len(content),
                    "thinking_chars": len(message.get("thinking") or ""),
                    "done_reason": response.get("done_reason"),
                    "prompt_eval_count": response.get("prompt_eval_count"),
                    "eval_count": response.get("eval_count"),
                    "total_duration_ms": round((response.get("total_duration") or 0) / 1e6, 1) or None,
                    "load_duration_ms": round((response.get("load_duration") or 0) / 1e6, 1) or None,
                    "raw": content,
                }
            )
            try:
                result["parsed"] = json.loads(content)
                result["json_valid"] = True
            except Exception:  # noqa: BLE001 - invalid JSON is a data point, not a crash
                result["parsed"] = None
                result["json_valid"] = False
                result["raw_snippet"] = content[:240]

            out.write(json.dumps(result, ensure_ascii=False) + "\n")
            out.flush()

            elapsed = time.time() - started
            eta = (elapsed / position) * (len(pending) - position) / 60
            print(
                f"[{position}/{len(pending)}] {record['variant']:4s} {record['batch']:22s} "
                f"{record['book'][:26]:26s} wall={result['wall_s']:6.1f}s "
                f"json={'ok' if result['json_valid'] else 'FAIL'} "
                f"tok={result.get('eval_count')} eta={eta:.0f}m",
                flush=True,
            )

    print(f"done: {len(pending) - failures} ok, {failures} failed -> {args.out}", flush=True)
    return 0 if failures < len(pending) else 1


if __name__ == "__main__":
    raise SystemExit(main())
