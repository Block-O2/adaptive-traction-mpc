#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
python3 -c 'import sys; assert sys.version_info[:2]==(3,12), "Use Python 3.12, matching the local runtime minor version"'
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade 'pip==25.2'
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m pip freeze > INSTALLED_FREEZE.txt
.venv/bin/python preflight.py
# Deliberately no training invocation.
