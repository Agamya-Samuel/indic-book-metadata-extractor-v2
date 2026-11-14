#!/usr/bin/env python3
"""Stdlib-only configuration-matrix runner for a remote Ollama node.

Runs the real per-batch extraction prompts from a make_eval_bundle.py bundle
under one configuration profile, writes one JSONL record per batch, and probes
the ollama container for resident memory, context and CPU.

Usage:
  python3 node_cfg.py <bundle.json> <model> <out.jsonl> --tag NAME
      [--num-ctx 8192] [--temperature 0] [--seed 42] [--repeat-penalty 1.0]
      [--num-predict 512] [--fmt schema|json] [--think] [--num-thread 0]
      [--batches core_identity,publication]
"""

import argparse
import json
import subprocess
import threading
import time
import urllib.request

API = "http://localhost:11434"


def call(payload, timeout=2400):
    req = urllib.request.Request(
        API + "/api/chat",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def tps(count, dur):
    return round(count / (dur / 1e9), 2) if count and dur else None


def meminfo_avail_mib():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except Exception:
        pass
    return None


class Sampler(threading.Thread):
    def __init__(self, period=1.0):
        super().__init__(daemon=True)
        self.period = period
        self.samples = []
        self.stop = False

    def run(self):
        while not self.stop:
            v = meminfo_avail_mib()
            if v is not None:
                self.samples.append(v)
            time.sleep(self.period)

    def min_avail(self):
        return min(self.samples) if self.samples else None


def probe():
    out = {}
    cmds = [
        ["sudo", "docker", "exec", "ollama", "ollama", "ps"],
        ["sudo", "docker", "stats", "--no-stream", "--format", "{{.CPUPerc}} {{.MemUsage}}", "ollama"],
    ]
    for i, cmd in enumerate(cmds):
        try:
            out[f"cmd{i}"] = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
        except Exception as exc:
            out[f"cmd{i}"] = f"err: {exc}"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle")
    ap.add_argument("model")
    ap.add_argument("out")
    ap.add_argument("--tag", default="cfg")
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--repeat-penalty", type=float, default=1.0)
    ap.add_argument("--num-predict", type=int, default=512)
    ap.add_argument("--fmt", choices=["schema", "json"], default="schema")
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--num-thread", type=int, default=0)
    ap.add_argument("--batches", default="")
    args = ap.parse_args()

    bundle = json.load(open(args.bundle, encoding="utf-8"))
    wanted = [b for b in args.batches.split(",") if b] if args.batches else None
    batches = [b for b in bundle["batches"] if not wanted or b["name"] in wanted]

    base = {
        "model": args.model,
        "stream": False,
        "keep_alive": "30m",
    }
    if args.think:
        base["think"] = False

    warm_opts = {"num_ctx": args.num_ctx, "num_predict": 1}
    if args.num_thread:
        warm_opts["num_thread"] = args.num_thread
    try:
        call(
            {
                "model": args.model,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "keep_alive": "30m",
                "options": warm_opts,
            }
        )
    except Exception as exc:
        print("warm failed:", exc, flush=True)

    with open(args.out, "a", encoding="utf-8") as out:
        for batch in batches:
            opts = {
                "num_ctx": args.num_ctx,
                "num_predict": args.num_predict,
                "temperature": args.temperature,
                "repeat_penalty": args.repeat_penalty,
                "seed": args.seed,
            }
            if args.num_thread:
                opts["num_thread"] = args.num_thread
            payload = dict(base)
            payload["options"] = opts
            payload["format"] = batch["schema"] if args.fmt == "schema" else "json"
            payload["messages"] = [
                {"role": "system", "content": bundle["system_prompt"]},
                {"role": "user", "content": batch["prompt"]},
            ]
            rec = {
                "tag": args.tag,
                "model": args.model,
                "batch": batch["name"],
                "book": bundle["book"],
                "num_ctx": args.num_ctx,
                "temperature": args.temperature,
                "seed": args.seed,
                "repeat_penalty": args.repeat_penalty,
                "num_predict": args.num_predict,
                "fmt": args.fmt,
                "think_false": args.think,
                "num_thread": args.num_thread,
                "text_chars": batch["text_chars"],
            }
            sampler = Sampler()
            sampler.start()
            t0 = time.time()
            try:
                res = call(payload)
            except Exception as exc:
                sampler.stop = True
                rec["error"] = str(exc)
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                print(rec, flush=True)
                continue
            rec["wall_s"] = round(time.time() - t0, 1)
            sampler.stop = True
            rec["min_avail_mib"] = sampler.min_avail()
            msg = res.get("message") or {}
            content = msg.get("content") or ""
            rec["thinking_chars"] = len(msg.get("thinking") or "")
            rec["eval_count"] = res.get("eval_count")
            rec["prompt_eval_count"] = res.get("prompt_eval_count")
            rec["gen_tok_s"] = tps(res.get("eval_count"), res.get("eval_duration"))
            rec["prefill_tok_s"] = tps(res.get("prompt_eval_count"), res.get("prompt_eval_duration"))
            rec["response_chars"] = len(content)
            rec["done_reason"] = res.get("done_reason")
            rec["parsed"] = None
            try:
                rec["parsed"] = json.loads(content)
                rec["json_valid"] = True
            except Exception:
                rec["json_valid"] = False
                rec["raw_snippet"] = content[:240]
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            print(
                f"  {batch['name']:16s} wall={rec['wall_s']}s gen={rec['gen_tok_s']} "
                f"prefill={rec['prefill_tok_s']} json={rec['json_valid']} "
                f"think={rec['thinking_chars']}",
                flush=True,
            )
    print("PROBE", json.dumps(probe()), flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
