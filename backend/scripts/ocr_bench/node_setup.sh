#!/bin/bash
set -u
export DEBIAN_FRONTEND=noninteractive
if ! python3 -m venv /tmp/ocrvenv 2>/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-venv
  python3 -m venv /tmp/ocrvenv
fi
/tmp/ocrvenv/bin/pip install -q --upgrade pip
/tmp/ocrvenv/bin/pip install -q python-Levenshtein
echo "LEV_DONE"
/tmp/ocrvenv/bin/pip install -q paddlepaddle paddleocr || echo "PADDLE_INSTALL_FAIL"
/tmp/ocrvenv/bin/python -c "import paddle,paddleocr;print('PADDLE_OK',paddle.__version__,paddleocr.__version__)" || echo "PADDLE_IMPORT_FAIL"
echo SETUP_DONE