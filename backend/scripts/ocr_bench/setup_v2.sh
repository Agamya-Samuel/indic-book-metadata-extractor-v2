#!/bin/bash
set -u
python3 -m venv /tmp/ocrvenv2
/tmp/ocrvenv2/bin/pip install -q --upgrade pip
/tmp/ocrvenv2/bin/pip install -q "paddlepaddle==2.6.2"
/tmp/ocrvenv2/bin/pip install -q "paddleocr==2.7.3" python-Levenshtein
/tmp/ocrvenv2/bin/python -c "import paddle,paddleocr;print('V2_OK',paddle.__version__,paddleocr.__version__)" || echo V2_FAIL
echo V2_DONE