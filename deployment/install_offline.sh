#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
python_bin="${PYTHON_BIN:-python3.12}"
env_path="${1:-$PWD/.deployment-work/offline-env}"
"$python_bin" -c 'import sys; assert sys.version_info[:2] == (3,12), "Linux CPython 3.12 required"'
test ! -e "$env_path" || { echo 'Use a new environment directory; existing files are preserved.' >&2; exit 1; }
if "$python_bin" -c 'import ensurepip' >/dev/null 2>&1; then
  "$python_bin" -m venv "$env_path"
  pip_command=("$env_path/bin/python" -m pip)
else
  : "${PIP_BOOTSTRAP_PYTHON:?Install python3.12-venv, or set PIP_BOOTSTRAP_PYTHON to a trusted Python with modern pip (supports --python).}"
  "$PIP_BOOTSTRAP_PYTHON" -m pip --help | grep -q -- --python
  "$python_bin" -m venv --without-pip "$env_path"
  pip_command=("$PIP_BOOTSTRAP_PYTHON" -m pip --python "$env_path/bin/python")
fi
"${pip_command[@]}" install --require-hashes -r deployment/requirements-offline.lock
"${pip_command[@]}" check
echo "Offline arithmetic environment ready: $env_path"
