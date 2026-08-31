#!/usr/bin/env bash
# Train (fine-tune) a Tesseract LSTM model on Indic-script data.
#
# Usage:
#   ./scripts/train_tesseract_lstm.sh \
#     --lang hin \
#     --base-model /path/to/indic-ocr/hin.traineddata \
#     --output-dir /app/storage/models/hin_v2 \
#     --training-dir /app/storage/training_data/hin \
#     --fonts "Noto Sans Devanagari, Mangal" \
#     --epochs 200
#
# Prereqs:
#   - tesseract-ocr, tesseract-ocr-<lang>, libtesseract-dev
#   - The tesseract-ocr training toolchain (tesstrain.sh from
#     https://github.com/tesseract-ocr/tesseract — installed in the trainer image)
#   - Indic fonts installed on the host
#
# The output is /output-dir/<lang>.traineddata, ready to be symlinked into
# OCR_CUSTOM_MODEL_DIR.

set -euo pipefail

LANG_CODE=""
BASE_MODEL=""
OUTPUT_DIR=""
TRAINING_DIR=""
FONTS=""
EPOCHS="200"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lang) LANG_CODE="$2"; shift 2 ;;
    --base-model) BASE_MODEL="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --training-dir) TRAINING_DIR="$2"; shift 2 ;;
    --fonts) FONTS="$2"; shift 2 ;;
    --epochs) EPOCHS="$2"; shift 2 ;;
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
echo "  epochs: $EPOCHS"

bash "$TESSTRAIN.sh" \
  --lang "$LANG_CODE" \
  --traineddata "$BASE_MODEL" \
  --trainlistfile "$TRAINING_DIR/training_text.txt" \
  --fonts_dir /usr/share/fonts \
  --fontconfig_tmpdir /tmp/fontconfig \
  --output_dir "$OUTPUT_DIR" \
  --maxpages "${MAX_PAGES:-1000}" \
  --tessdata_dir /usr/share/tesseract-ocr/5/tessdata \
  --continue_from "$OUTPUT_DIR/${LANG_CODE}.lstm"

# Combine the trained LSTM into a .traineddata file
cd "$OUTPUT_DIR"
combine_tessdata -e "$BASE_MODEL" "${LANG_CODE}.lstm" "${LANG_CODE}.traineddata"
echo "Done. Output: $OUTPUT_DIR/${LANG_CODE}.traineddata"