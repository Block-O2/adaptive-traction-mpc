#!/usr/bin/env python3
"""Write the preregistered nominal/oracle trajectory-excitation design audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.trajectory_excitation import run_trajectory_excitation_audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    result = run_trajectory_excitation_audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
