#!/usr/bin/env bash
# Run the prompt matrix on one benchmark node.
#
# Sharding is by BOOK, not by record: a node keeps all eight batches of a book
# together, so Ollama's system-prompt prefix stays cached for the whole variant
# instead of alternating between prompt variants on every call (~4x slower).
#
# Typical use, on each node after bundles are copied to ~/bundles:
#   bash ~/run_matrix.sh 0/3          # node 1
#   bash ~/run_matrix.sh 1/3          # node 2
#   bash ~/run_matrix.sh 2/3          # node 3
#
# Usage: run_matrix.sh <i/N> [bundle-glob] [out-dir]
set -u

SHARD=${1:?usage: run_matrix.sh <i/N> [bundle-glob] [out-dir]}
BUNDLE_GLOB=${2:-$HOME/bundles/*.jsonl}
OUT_DIR=${3:-$HOME/results}

HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$OUT_DIR/matrix.$(echo "$SHARD" | tr '/' '_').jsonl"
mkdir -p "$OUT_DIR"

# shellcheck disable=SC2086
BUNDLES=$(ls $BUNDLE_GLOB 2>/dev/null)
if [ -z "$BUNDLES" ]; then
  echo "no bundles matched $BUNDLE_GLOB" >&2
  exit 2
fi

echo "shard=$SHARD  out=$OUT"
echo "bundles:"; for b in $BUNDLES; do echo "  $b"; done

python3 "$HERE/run_eval.py" \
  --bundles $BUNDLES \
  --out "$OUT" \
  --book-index "$SHARD"

echo "MATRIX_DONE -> $OUT"
