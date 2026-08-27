#!/usr/bin/env python3
"""Persist the Stage-4 reduced-estimator predictive engineering audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from traction_mpc_stage4.reduced_estimator_audit import (
    run_reduced_estimator_predictive_audit,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    result = run_reduced_estimator_predictive_audit()
    (args.output_dir / "audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    lines = [
        "# Stage 4 reduced-estimator predictive audit",
        "",
        "Offline engineering evidence only. The validated geometry + 11-base integral estimator remains unchanged.",
        "",
        "| case | full rank/cond | reduced rank/cond | full torque RMSE | reduced torque RMSE | reduced normalized RMSE |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for case in result["cases"]:
        observability = case["integral_observability"]
        prediction = case["generalized_torque_prediction"]
        full = prediction["integral_fit_11_base"]
        reduced = prediction["best_integral_fit_reduced_3_scale"]
        lines.append(
            f'| {case["case"]} | '
            f'{observability["full_11_base"]["rank"]}/'
            f'{observability["full_11_base"]["column_normalized_condition_number"]:.1f} | '
            f'{observability["reduced_3_scale"]["rank"]}/'
            f'{observability["reduced_3_scale"]["column_normalized_condition_number"]:.1f} | '
            f'{full["combined_rmse_nm"]:.6f} Nm | '
            f'{reduced["combined_rmse_nm"]:.6f} Nm | '
            f'{reduced["normalized_combined_rmse_percent_of_true_torque_rms"]:.3f}% |'
        )
    (args.output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
