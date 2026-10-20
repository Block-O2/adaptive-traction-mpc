#!/usr/bin/env python3
"""Run the small one-factor Stage-5 Interface Mismatch v1 engineering sweep."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.goal_mpc_smoke import (
    InitialConditionValidationError,
    run_goal_mpc_smoke,
)
from traction_mpc_stage5.interface_mismatch import (
    CHECKPOINT_SUMMARY_PATH,
    compact_cell,
    compact_startup_abort,
    expanded_matrix_rows,
    interface_record,
    load_and_validate_config,
    unique_cases,
)


def _nominal_reproduction(
    checkpoint: dict[str, object], fresh: dict[str, object]
) -> dict[str, object]:
    numeric_keys = (
        "task_duration_s",
        "peak_physical_cuff_force_n",
        "cumulative_physical_cuff_force_n_s",
        "peak_physical_cuff_moment_nm",
        "peak_interface_translation_mm",
        "peak_interface_rotation_deg",
        "maximum_normalized_q1_q2_progress_difference",
    )
    array_keys = (
        "peak_abs_estimated_joint_velocity_deg_s",
        "peak_abs_evaluation_only_joint_velocity_deg_s",
        "peak_abs_estimated_joint_acceleration_deg_s2",
        "peak_abs_evaluation_only_joint_acceleration_deg_s2",
    )
    deltas: dict[str, object] = {
        key: float(fresh[key]) - float(checkpoint[key]) for key in numeric_keys
    }
    deltas.update(
        {
            key: (
                np.asarray(fresh[key], dtype=float)
                - np.asarray(checkpoint[key], dtype=float)
            ).tolist()
            for key in array_keys
        }
    )
    exact_keys = (
        "task_status",
        "phase_transitions",
        "mpc_solve_count",
        "mpc_status_counts",
        "safety_filter_status_counts",
        "brake_event_count",
        "force_gate_event_count",
        "mujoco_warning_counts",
    )
    return {
        "checkpoint_summary": str(
            CHECKPOINT_SUMMARY_PATH.relative_to(STAGE5_ROOT)
        ),
        "exact_field_equality": {
            key: fresh[key] == checkpoint[key] for key in exact_keys
        },
        "deterministic_metric_delta_fresh_minus_checkpoint": deltas,
        "runtime_is_profiled_but_not_deterministic": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "interface_mismatch_v1",
    )
    args = parser.parse_args()
    output_dir = args.output_dir
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite sweep output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    config = load_and_validate_config()
    cells = []
    raw_summaries: dict[str, dict[str, object]] = {}
    for case in unique_cases():
        case_dir = output_dir / case.name
        try:
            summary = run_goal_mpc_smoke(
                case_dir,
                plant_interface_parameters=case.plant_truth,
                plant_case_name=f"interface_mismatch_v1__{case.name}",
                record_selected_horizon_diagnostics=True,
                use_loaded_local_hold=True,
                stop_on_return_entry=False,
                use_bumpless_return_handoff=True,
                initialize_loaded_equilibrium_with_plant_truth=True,
            )
        except InitialConditionValidationError as error:
            startup_record = dict(error.diagnostics)
            (case_dir / "startup_abort.json").write_text(
                json.dumps(startup_record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            cells.append(compact_startup_abort(case, startup_record))
            raw_summaries[case.name] = startup_record
            continue
        raw_summaries[case.name] = summary
        with np.load(case_dir / "trace.npz") as trace:
            cells.append(compact_cell(case, summary, trace))

    checkpoint = json.loads(CHECKPOINT_SUMMARY_PATH.read_text(encoding="utf-8"))
    nominal_reproduction = _nominal_reproduction(
        checkpoint, raw_summaries["nominal_1p0"]
    )
    aggregate = {
        "schema": "stage5_interface_mismatch_v1_results",
        "evidence_category": config["evidence_category"],
        "deterministic_checkpoint": config["deterministic_checkpoint"],
        "controller_nominal_interface_frozen": config[
            "controller_nominal_interface"
        ],
        "plant_truth_base_interface": config["plant_truth_base_interface"],
        "shared_checkpoint_settings": config["shared_checkpoint_settings"],
        "controller_reads_plant_truth": False,
        "full_factorial": False,
        "unique_run_count": len(cells),
        "experiment_matrix": expanded_matrix_rows(),
        "nominal_reproduction": nominal_reproduction,
        "cells": cells,
        "controller_retuned": False,
        "learning_active": False,
        "clinical_or_hardware_safety_validation": False,
    }
    (output_dir / "sweep_summary.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
