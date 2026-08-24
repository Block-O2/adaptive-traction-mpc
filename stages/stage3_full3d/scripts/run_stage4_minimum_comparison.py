from __future__ import annotations

import argparse
from pathlib import Path

from traction_mpc_stage4.evaluation import run_minimum_comparison


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run_minimum_comparison(args.output_dir)


if __name__ == "__main__":
    main()
