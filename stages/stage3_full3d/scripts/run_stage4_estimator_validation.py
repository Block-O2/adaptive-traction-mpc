from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage4.evaluation import run_stage4_case


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summaries = {}
    for true_case in ("nominal", "moderate"):
        summary, trace = run_stage4_case(
            controller_kind="adaptive",
            true_case=true_case,
        )
        summaries[true_case] = summary
        (args.output_dir / f"{true_case}_adaptive.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        np.savez_compressed(
            args.output_dir / f"{true_case}_adaptive_trace.npz",
            **trace,
        )
    (args.output_dir / "summary.json").write_text(
        json.dumps(summaries, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
