#!/usr/bin/env python3
"""Audit and summarize an already completed formal generalization study."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.report_generalization_analysis import (
    generate_final_generalization_summary,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matrix-config",
        type=Path,
        default=Path("configs/stage4_report_generalization_matrix.json"),
    )
    parser.add_argument("--formal-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    aggregate = generate_final_generalization_summary(
        matrix_path=args.matrix_config,
        formal_root=args.formal_root,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "integrity_passed": aggregate["integrity_audit"]["integrity_passed"],
                "arm_count": aggregate["integrity_audit"]["arm_count"],
                "output_dir": str(args.output_dir.resolve()),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
