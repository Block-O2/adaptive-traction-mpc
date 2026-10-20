#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ "${1:-}" != "--enable" ]]; then
  echo 'Disabled. Explicit user start: bash smoke.sh --enable' >&2
  exit 2
fi
PY=.venv/bin/python
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
# One 14-minute wall cap around the complete qualify/update/resume/evaluate flow.
$PY resource_guard.py --out runs/cloud_smoke_guard_01 --seconds 840 -- $PY smoke_sequence.py --enable
