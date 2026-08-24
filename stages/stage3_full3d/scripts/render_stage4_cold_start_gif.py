from __future__ import annotations

import argparse
from pathlib import Path

from traction_mpc_stage4.presentation import render_one_shot_gif


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--fps", type=int, default=8)
    args = parser.parse_args()
    render_one_shot_gif(
        args.summary,
        args.trace,
        args.output,
        fps=args.fps,
        preview_path=args.preview,
    )


if __name__ == "__main__":
    main()
