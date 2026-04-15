#!/bin/bash
set -e
python3 -m venv /tmp/sf_venv
/tmp/sf_venv/bin/pip install jinja2 pyyaml requests
/tmp/sf_venv/bin/python build.py --site sites/esign_003
