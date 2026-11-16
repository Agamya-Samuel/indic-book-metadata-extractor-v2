#!/usr/bin/env bash
# Watchdog for the prompt-matrix run on the three benchmark nodes.
#
# Checks, per node: instance status, runner process, result growth, JSON
# validity of recent calls, Ollama responsiveness, CPU load and free disk.
#
# A dead *process* is recoverable here: run_eval.py resumes from the existing
# JSONL, so restarting it loses at most the call that was in flight. A
# TERMINATED *instance* is only reported (and optionally started), because
# starting a machine is a spend decision, not a health check.
#
# Usage:
#   node_watch.sh            # report only
#   node_watch.sh --fix      # also restart a dead runner / ollama
#
# Exit: 0 = all healthy or complete, 1 = something needs attention.
set -u

ZONE=asia-south1-c
PROJECT=algogini-gcp
GC="$HOME/google-cloud-sdk/bin/gcloud"
KEY="$HOME/.ssh/google_compute_engine"
FIX=0
[ "${1:-}" = "--fix" ] && FIX=1

# node index | expected calls (balanced shard: 2496 / 2496 / 2392)
NODES="test-node-1:0:2496 test-node-2:1:2496 test-node-3:2:2392"

ssh_node() { # <ip> <command>
  timeout 45 ssh -i "$KEY" -o ConnectTimeout=15 -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null -o BatchMode=yes "agamya@$1" "$2" 2>/dev/null
}

problems=0
report=""

for entry in $NODES; do
  name=${entry%%:*}; rest=${entry#*:}
  shard=${rest%%:*}; expected=${rest##*:}

  info=$("$GC" compute instances describe "$name" --zone="$ZONE" --project="$PROJECT" \
         --format="value(status,networkInterfaces[0].accessConfigs[0].natIP)" 2>/dev/null)
  status=$(echo "$info" | cut -f1)
  ip=$(echo "$info" | cut -f2)

  if [ "$status" != "RUNNING" ] || [ -z "$ip" ]; then
    report+="❌ $name: instance $status${ip:+ (no IP)} — needs a start decision"$'\n'
    problems=1
    continue
  fi

  remote=$(ssh_node "$ip" '
    done=$(cat ~/results/matrix.'"$shard"'_3.jsonl 2>/dev/null | wc -l)
    alive=$(pgrep -fc "[r]un_eval.py --bundles" || true)
    build=$(pgrep -fc "[b]uild_corpus" || true)
    # Only a run that was deliberately launched may be restarted. Without this
    # marker an idle node was mistaken for a dead matrix and extraction was
    # relaunched on top of an unfinished corpus rebuild (2026-11-15).
    marker=$(test -f ~/results/.matrix_expected && echo 1 || echo 0)
    cexpected=$(test -f ~/results/.corpus_expected && echo 1 || echo 0)
    newmeta=$(grep -l text_variant ~/peval/prompt_eval/corpus/ocr/*/*.json 2>/dev/null | wc -l)
    load=$(cut -d" " -f1 /proc/loadavg)
    disk=$(df -Pm / | awk "NR==2{print \$4}")
    ollama=$(curl -s -m 5 -o /dev/null -w "%{http_code}" http://127.0.0.1:11434/api/tags)
    bad=$(tail -20 ~/results/matrix.'"$shard"'_3.jsonl 2>/dev/null | grep -c "\"json_valid\": false\|\"error\":")
    last=$(tail -1 "$(ls -t ~/eval*.log 2>/dev/null | head -1)" 2>/dev/null | cut -c1-70)
    ocrtail=$(tail -1 ~/ocr5.log 2>/dev/null | cut -c1-60)
    # A rebuild is only complete when its own log printed the final summary.
    cstate=$(tail -3 ~/ocr5.log 2>/dev/null | grep -c "manifest ->" || true)
    echo "$done|$alive|$load|$disk|$ollama|$bad|$last|$build|$newmeta|$marker|$cexpected|$cstate|$ocrtail"
  ')

  if [ -z "$remote" ]; then
    report+="❌ $name: unreachable over SSH (instance RUNNING, ip $ip)"$'\n'
    problems=1
    continue
  fi

  IFS='|' read -r done alive load disk ollama bad last build newmeta marker cexpected cstate ocrtail <<<"$remote"
  note=""
  node_problem=0

  if [ "$build" -gt 0 ]; then
    # Corpus rebuild phase. Starting extraction here is what burned 8.5 h of
    # calls on a stale corpus — this branch must never launch run_eval.py.
    note="🔨 corpus rebuild running (${newmeta} books written)"
    [ -n "$ocrtail" ] && note+=" | ${ocrtail}"
    if ssh_node "$ip" "grep -q Traceback ~/ocr5.log"; then
      node_problem=1
      note+=" | ❌ Traceback in ~/ocr5.log"
    fi
  elif [ "$cexpected" -eq 1 ] && [ "$cstate" -eq 0 ]; then
    node_problem=1
    if [ "$FIX" -eq 1 ]; then
      ssh_node "$ip" "cd ~/peval && setsid nohup ~/peval/venv/bin/python -m scripts.prompt_eval.build_corpus --track ocr </dev/null >~/ocr5.log 2>&1 & sleep 2; pgrep -fc \"[b]uild_corpus\"" >/dev/null
      note="⚠️  rebuild was dead — RESTARTED (resumes at ${newmeta} books)"
    else
      note="❌ rebuild dead at ${newmeta} books (rerun with --fix)"
    fi
  elif [ "$cexpected" -eq 1 ] && [ "$cstate" -eq 1 ]; then
    note="✅ rebuild complete (${newmeta} books)"
    [ "$FIX" -eq 1 ] && ssh_node "$ip" "rm -f ~/results/.corpus_expected" >/dev/null
  elif [ "$done" -ge "$expected" ] && [ "$alive" -eq 0 ] && [ "$marker" -eq 1 ]; then
    note="✅ COMPLETE ($done/$expected)"
    [ "$FIX" -eq 1 ] && ssh_node "$ip" "rm -f ~/results/.matrix_expected" >/dev/null
  elif [ "$alive" -eq 0 ] && [ "$marker" -eq 1 ]; then
    node_problem=1
    if [ "$FIX" -eq 1 ]; then
      ssh_node "$ip" "cd ~/peval && setsid nohup ~/peval/venv/bin/python scripts/prompt_eval/run_eval.py --bundles \$(ls ~/bundles/V*.ocr.jsonl) --out ~/results/matrix.${shard}_3.jsonl --book-index ${shard}/3 </dev/null >~/eval.log 2>&1 & sleep 2; pgrep -fc \"[r]un_eval.py --bundles\"" >/dev/null
      note="⚠️  runner was dead — RESTARTED at $done/$expected"
    else
      note="❌ runner dead at $done/$expected (rerun with --fix)"
    fi
  elif [ "$alive" -eq 0 ]; then
    # No process and no launch marker: idle, not broken.
    note="⏸  idle (no runner; nothing restarted)"
  else
    pct=$((done * 100 / expected))
    note="✅ running $done/$expected (${pct}%)"
  fi

  # Ollama: only meaningful while a matrix runner is actually alive.
  if [ "$alive" -gt 0 ] && [ "$ollama" != "200" ]; then
    node_problem=1
    if [ "$FIX" -eq 1 ]; then
      ssh_node "$ip" "sudo systemctl restart ollama; sleep 8; curl -s -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:11434/api/tags" >/dev/null
      note+=" | ⚠️  ollama was down — RESTARTED"
    else
      note+=" | ❌ ollama not responding (HTTP $ollama)"
    fi
  fi

  if [ "$bad" -gt 0 ]; then
    node_problem=1
    note+=" | ⚠️  $bad bad/errored record(s) in the last 20"
  fi
  if [ "${disk:-9999}" -lt 1024 ]; then
    node_problem=1
    note+=" | ❌ low disk: ${disk} MB free"
  fi
  if [ "$(echo "$load > 12" | bc 2>/dev/null || echo 0)" = "1" ]; then
    note+=" | ⚠️  load $load (something else may be running)"
  fi

  [ "$node_problem" -eq 1 ] && problems=1
  report+="$name ($ip): $note"$'\n'
  report+="    last: ${last:-<no log>}"$'\n'
done

echo "=== prompt-matrix watchdog $(date -u '+%Y-%m-%dT%H:%M:%SZ') (fix=$FIX) ==="
printf '%s' "$report"
if [ "$problems" -eq 0 ]; then
  echo "ALL OK"
else
  echo "ATTENTION NEEDED"
fi
exit "$problems"
