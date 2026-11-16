#!/usr/bin/env bash
# Train (fine-tune) a Tesseract LSTM model on Indic-script data.
#
# Usage:
#   ./scripts/train_tesseract_lstm.sh \
#     --lang hin \
#     --base-model /usr/share/tesseract-ocr/5/tessdata/hin.traineddata \
#     --output-dir /app/storage/models/hin_v2 \
#     --training-dir /app/storage/training_data/hin \
#     --fonts "Noto Sans Devanagari, Mangal"
#
# Training length is controlled by tesstrain.sh/lstmtraining; this wrapper no
# longer accepts a no-op --epochs flag.
#
# Prereqs:
#   - tesseract-ocr, tesseract-ocr-<lang>, libtesseract-dev
#   - The tesseract-ocr training toolchain (tesstrain.sh from
#     https://github.com/tesseract-ocr/tesseract — installed in the trainer image)
#   - Indic fonts installed on the host
#
# The output is /output-dir/<lang>.traineddata, ready to be symlinked into
# TESSERACT_TESSDATA_DIR.

set -euo pipefail

LANG_CODE=""
BASE_MODEL=""
OUTPUT_DIR=""
TRAINING_DIR=""
FONTS=""
LANGDATA_DIR="${LANGDATA_DIR:-/usr/share/tesseract-ocr/5/langdata}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lang) LANG_CODE="$2"; shift 2 ;;
    --base-model) BASE_MODEL="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --training-dir) TRAINING_DIR="$2"; shift 2 ;;
    --fonts) FONTS="$2"; shift 2 ;;
    *) echo "Unknown flag: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$LANG_CODE" || -z "$BASE_MODEL" || -z "$OUTPUT_DIR" || -z "$TRAINING_DIR" ]]; then
  echo "Required: --lang, --base-model, --output-dir, --training-dir" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

# tesstrain.sh from tesseract-ocr/tesseract. Expected at /usr/local/bin/tesstrain.sh
# (installed by the trainer Dockerfile) or override via TESSTRAIN_SH env var.
TESSTRAIN_SH="${TESSTRAIN_SH:-/usr/local/bin/tesstrain.sh}"
if [[ ! -x "$TESSTRAIN_SH" ]]; then
  echo "tesstrain.sh not found at $TESSTRAIN_SH. Set TESSTRAIN_SH or rebuild the trainer image." >&2
  exit 1
fi

echo "Fine-tuning $LANG_CODE → $OUTPUT_DIR"
echo "  base model: $BASE_MODEL"
echo "  training data: $TRAINING_DIR"
echo "  fonts: ${FONTS:-<default>}"

# --fontlist takes one or more names; accept a comma-separated --fonts value.
font_args=()
if [[ -n "$FONTS" ]]; then
  IFS=',' read -r -a font_names <<< "$FONTS"
  for name in "${font_names[@]}"; do
    name="$(echo "$name" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -n "$name" ]] && font_args+=(--fontlist "$name")
  done
fi

# tesstrain.sh: --training_text and --start_model are the real flags;
# --trainlistfile/--continue_from/--traineddata do not exist.
bash "$TESSTRAIN_SH" \
  --lang "$LANG_CODE" \
  --start_model "$BASE_MODEL" \
  --training_text "$TRAINING_DIR/training_text.txt" \
  --fonts_dir /usr/share/fonts \
  --langdata_dir "$LANGDATA_DIR" \
  --output_dir "$OUTPUT_DIR" \
  --maxpages "${MAX_PAGES:-1000}" \
  --tessdata_dir /usr/share/tesseract-ocr/5/tessdata \
  "${font_args[@]}"

# If tesstrain emitted an LSTM, graft it into a copy of the base traineddata.
# combine_tessdata -o takes the traineddata followed by component files.
if [[ -f "$OUTPUT_DIR/${LANG_CODE}.lstm" && ! -f "$OUTPUT_DIR/${LANG_CODE}.traineddata" ]]; then
  cp "$BASE_MODEL" "$OUTPUT_DIR/${LANG_CODE}.traineddata"
  combine_tessdata -o "$OUTPUT_DIR/${LANG_CODE}.traineddata" "$OUTPUT_DIR/${LANG_CODE}.lstm"
fi
echo "Done. Output: $OUTPUT_DIR/${LANG_CODE}.traineddata"