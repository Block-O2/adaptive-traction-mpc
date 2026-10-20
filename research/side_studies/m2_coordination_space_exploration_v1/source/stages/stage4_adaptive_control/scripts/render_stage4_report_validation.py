#!/usr/bin/env python3
"""Render one saved four-controller report-validation comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.report_validation_renderer import (
    RENDERER_SMOKE_CATEGORY,
    render_comparison,
    render_generalization_comparison,
    render_manifest_media_set,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", type=Path)
    parser.add_argument(
        "--matrix-config",
        type=Path,
        default=Path("configs/stage4_report_validation_matrix.json"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=8)
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--mp4", action="store_true")
    parser.add_argument("--generalization-config", type=Path)
    parser.add_argument("--source-phase-manifest", type=Path)
    parser.add_argument("--visualization-source-manifest", type=Path)
    parser.add_argument("--media-set")
    parser.add_argument("--scene-id")
    parser.add_argument("--renderer-smoke", action="store_true")
    args = parser.parse_args()
    manifest_mode = args.visualization_source_manifest is not None
    if not manifest_mode and (args.generalization_config is None) != (
        args.source_phase_manifest is None
    ):
        parser.error(
            "generalization rendering requires both --generalization-config "
            "and --source-phase-manifest"
        )
    if manifest_mode:
        if args.case_dir is not None or args.source_phase_manifest is not None:
            parser.error("manifest rendering does not accept case/source-phase inputs")
        if args.generalization_config is None or args.media_set is None:
            parser.error(
                "manifest rendering requires --generalization-config and --media-set"
            )
        manifest = render_manifest_media_set(
            visualization_manifest_path=args.visualization_source_manifest,
            generalization_matrix_path=args.generalization_config,
            media_set_id=args.media_set,
            scene_id=args.scene_id,
            output_dir=args.output_dir,
            fps=args.fps,
            max_frames=args.max_frames,
            write_mp4=args.mp4,
            render_classification=(
                RENDERER_SMOKE_CATEGORY
                if args.renderer_smoke
                else "professor_report_visualization"
            ),
        )
    elif args.generalization_config is not None:
        if args.case_dir is None:
            parser.error("generalization case rendering requires --case-dir")
        manifest = render_generalization_comparison(
            case_dir=args.case_dir,
            source_phase_manifest_path=args.source_phase_manifest,
            generalization_matrix_path=args.generalization_config,
            output_dir=args.output_dir,
            fps=args.fps,
            max_frames=args.max_frames,
            write_mp4=args.mp4,
        )
    else:
        if args.case_dir is None:
            parser.error("report-validation rendering requires --case-dir")
        if args.media_set is not None or args.scene_id is not None or args.renderer_smoke:
            parser.error("manifest-only flags require --visualization-source-manifest")
        manifest = render_comparison(
            case_dir=args.case_dir,
            matrix_path=args.matrix_config,
            output_dir=args.output_dir,
            fps=args.fps,
            max_frames=args.max_frames,
            write_mp4=args.mp4,
        )
    print(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
