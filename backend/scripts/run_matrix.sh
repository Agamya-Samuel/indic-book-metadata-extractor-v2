#!/usr/bin/env bash
# Configuration matrix for the 49-field extraction LLM on the 4 vCPU / 16 GB node.
# One variable per profile, real Telugu prompts from two verified books.
set -u
OUT=/tmp/cfg.jsonl
: > "$OUT"
H="$HOME"

run() {
  local book="$1" model="$2"; shift 2
  python3 "$H/node_cfg.py" "$book" "$model" "$OUT" "$@"
}

for B in "$H/bundle_athma.json" "$H/bundle_andhra.json"; do
  echo "===== BOOK $B ====="
  run "$B" phi4-mini:latest --tag phi4_base   --num-ctx 8192 --temperature 0   --seed 42 --repeat-penalty 1.0 --num-predict 512 --fmt schema
  run "$B" gemma4:e4b       --tag gem_base    --num-ctx 8192 --temperature 0   --seed 42 --repeat-penalty 1.0 --num-predict 512 --fmt schema --think
  run "$B" gemma4:e4b       --tag gem_seed7   --num-ctx 8192 --temperature 0   --seed 7  --repeat-penalty 1.0 --num-predict 512 --fmt schema --think
  run "$B" gemma4:e4b       --tag gem_temp03  --num-ctx 8192 --temperature 0.3 --seed 42 --repeat-penalty 1.0 --num-predict 512 --fmt schema --think
  run "$B" gemma4:e4b       --tag gem_rep11   --num-ctx 8192 --temperature 0   --seed 42 --repeat-penalty 1.1 --num-predict 512 --fmt schema --think
  run "$B" gemma4:e4b       --tag gem_json    --num-ctx 8192 --temperature 0   --seed 42 --repeat-penalty 1.0 --num-predict 512 --fmt json   --think
  run "$B" gemma4:e4b       --tag gem_thr4    --num-ctx 8192 --temperature 0   --seed 42 --repeat-penalty 1.0 --num-predict 512 --fmt schema --think --num-thread 4
  run "$B" gemma4:e4b       --tag gem_ctx4096 --num-ctx 4096 --temperature 0   --seed 42 --repeat-penalty 1.0 --num-predict 512 --fmt schema --think
done
echo MATRIX_DONE
