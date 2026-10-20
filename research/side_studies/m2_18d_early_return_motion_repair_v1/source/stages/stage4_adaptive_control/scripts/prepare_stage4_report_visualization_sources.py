#!/usr/bin/env python3
"""Audit saved evidence and prepare a trace-only visualization source manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.report_generalization_visualization import (
    build_visualization_source_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-config", type=Path, required=True)
    parser.add_argument("--statistical-root", type=Path, required=True)
    parser.add_argument("--trajectory-demo-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = build_visualization_source_manifest(
        matrix_path=args.matrix_config,
        statistical_root=args.statistical_root,
        demo_root=args.trajectory_demo_root,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "integrity_passed": result["trajectory_demo_integrity_audit"][
                    "integrity_passed"
                ],
                "trajectory_case_count": result[
                    "trajectory_generalization_dataset"
                ]["case_count"],
                "output_dir": str(args.output_dir.resolve()),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
