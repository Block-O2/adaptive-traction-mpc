#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
python_bin="${PYTHON_BIN:-python3.12}"
env_path="${1:-$PWD/.deployment-work/offline-env}"
"$python_bin" -c 'import sys; assert sys.version_info[:2] == (3,12), "Linux CPython 3.12 required"'
test ! -e "$env_path" || { echo 'Use a new environment directory; existing files are preserved.' >&2; exit 1; }
"$python_bin" -m venv "$env_path"
"$env_path/bin/python" -m pip install --require-hashes -r deployment/requirements-offline.lock
"$env_path/bin/python" -m pip check
echo "Offline arithmetic environment ready: $env_path"
