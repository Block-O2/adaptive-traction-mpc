#!/usr/bin/env python3
"""Regenerate Stage-5 engineering validation data and schematics."""

from __future__ import annotations

import json
from pathlib import Path

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.validation import run_stage5_validation


def main() -> None:
    output = STAGE5_ROOT / "results" / "geometry_mechanics_validation_v1"
    report = run_stage5_validation(output)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
