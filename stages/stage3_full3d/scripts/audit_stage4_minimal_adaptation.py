#!/usr/bin/env python3
"""Write the mechanical observability audit for minimal Stage-4 adaptation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.minimal_observability import run_minimal_observability_audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_minimal_observability_audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
