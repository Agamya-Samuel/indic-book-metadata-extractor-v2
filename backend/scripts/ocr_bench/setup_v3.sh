#!/bin/bash
set -u
python3 -m venv /tmp/ocrvenv3
/tmp/ocrvenv3/bin/pip install -q --upgrade pip
/tmp/ocrvenv3/bin/pip install -q --index-url https://download.pytorch.org/whl/cpu torch
/tmp/ocrvenv3/bin/pip install -q transformers pillow regex python-Levenshtein pytesseract
/tmp/ocrvenv3/bin/python -c "import torch,transformers;print('V3_OK',torch.__version__,transformers.__version__)" || echo V3_FAIL
echo V3_DONE