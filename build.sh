#!/bin/bash
set -e
python3 -m venv /tmp/sf_venv || true
/tmp/sf_venv/bin/pip install --break-system-packages jinja2 pyyaml requests 2>/dev/null || pip install --break-system-packages jinja2 pyyaml requests
python3 build.py --site sites/esign_002
