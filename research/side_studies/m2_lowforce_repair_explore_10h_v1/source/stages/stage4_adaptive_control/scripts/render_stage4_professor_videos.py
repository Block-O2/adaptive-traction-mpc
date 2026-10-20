#!/usr/bin/env python3
"""Regenerate the three professor-facing MP4s from frozen traces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.report_validation_video import (
    render_final_professor_videos,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--visualization-source-manifest",
        type=Path,
        default=Path(
            "results/controller_validation/visualization_sources/"
            "visualization_source_manifest.json"
        ),
    )
    parser.add_argument(
        "--generalization-config",
        type=Path,
        default=Path("configs/stage4_report_generalization_matrix.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/local/professor_videos_replay"),
    )
    parser.add_argument("--fps", type=int, default=30, choices=(24, 30))
    args = parser.parse_args()
    manifest = render_final_professor_videos(
        visualization_manifest_path=args.visualization_source_manifest,
        generalization_matrix_path=args.generalization_config,
        output_dir=args.output_dir,
        fps=args.fps,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
