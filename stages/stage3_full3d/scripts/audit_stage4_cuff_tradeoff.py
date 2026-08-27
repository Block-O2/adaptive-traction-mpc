#!/usr/bin/env python3
"""Persist the exact fixed-tau one-dimensional cuff trade-off audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage4.cuff_tradeoff_audit import run_cuff_tradeoff_audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    with np.load(args.trace) as stored:
        trace = {name: stored[name] for name in stored.files}
    result = run_cuff_tradeoff_audit(trace)
    (args.output_dir / "audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    lines = [
        "# Stage 4 exact 1D cuff allocation trade-off",
        "",
        "Structural audit with tau_h fixed sample-by-sample. No controller rerun or weight change.",
        "",
        "`A_dagger w` is a minimum-norm equivalent cylindrical surface-load proxy, not pressure.",
        "",
        "| strategy | force peak/RMS | moment peak/RMS | surface peak/RMS | local patch peak | force-gate samples | equality peak |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in (
        "minimum_force",
        "minimum_surface_proxy",
        "current_one_to_one",
        "minimum_moment",
    ):
        item = result["strategies"][name]
        lines.append(
            f'| {name} | '
            f'{item["resultant_force_n"]["peak"]:.2f}/'
            f'{item["resultant_force_n"]["rms"]:.2f} N | '
            f'{item["abs_cuff_moment_nm"]["peak"]:.2f}/'
            f'{item["abs_cuff_moment_nm"]["rms"]:.2f} Nm | '
            f'{item["cylindrical_surface_effort_proxy_n"]["peak"]:.2f}/'
            f'{item["cylindrical_surface_effort_proxy_n"]["rms"]:.2f} N | '
            f'{item["maximum_local_patch_force_proxy_n"]:.2f} N | '
            f'{item["force_gate_exceedance_sample_count"]} | '
            f'{item["equality_residual_nm"]["peak"]:.2e} Nm |'
        )
    knee = result["knee_analysis"]
    lines.extend(
        [
            "",
            f'Knee weight ratio (surface/force): {knee["knee_point"]["surface_to_force_weight_ratio"]:.6g}',
            f'1:1 / knee ratio: {knee["one_to_one_weight_ratio_over_knee_ratio"]:.6g}',
        ]
    )
    (args.output_dir / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
