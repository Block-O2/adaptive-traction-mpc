#!/usr/bin/env python3
"""Run the minimum unchanged-semantics torque traces required by V2."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.interface_mismatch import unique_cases
from traction_mpc_stage5.interface_robustness_campaign import scaled_interface
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            STAGE5_ROOT / "results" / "transition_response_shadow_v2_minimum_cases"
        ),
    )
    args = parser.parse_args()
    output = args.output_dir
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)

    mismatch = {case.name: case for case in unique_cases()}
    rows: list[dict[str, object]] = []

    nominal = run_goal_mpc_smoke(
        output / "nominal_torque_smoke",
        maximum_duration_s=0.5,
        plant_case_name="transition_response_v2__nominal_torque_smoke",
    )
    rows.append(
        {
            "case": "nominal_torque_smoke",
            "role": "benign_command_response",
            "source_contract": "unchanged_default_stage5_engineering_smoke",
            "summary": nominal,
        }
    )

    kt_1p3 = run_goal_mpc_smoke(
        output / "kt_1p3_torque_smoke",
        maximum_duration_s=0.5,
        plant_interface_parameters=mismatch["kt_1p3"].plant_truth,
        plant_case_name="transition_response_v2__kt_1p3_torque_smoke",
        record_selected_horizon_diagnostics=True,
        use_loaded_local_hold=True,
        stop_on_return_entry=False,
        use_bumpless_return_handoff=True,
        initialize_loaded_equilibrium_with_plant_truth=True,
    )
    rows.append(
        {
            "case": "kt_1p3_torque_smoke",
            "role": "genuine_short_execution_interface_transient",
            "source_contract": "unchanged_interface_mismatch_v1_kt_1p3",
            "summary": kt_1p3,
        }
    )

    low_low_high_task = replace(
        PROVISIONAL_LOW_MODERATE_GOAL_TASK, hold_duration_s=0.5
    )
    low_low_high = run_goal_mpc_smoke(
        output / "low_low_high_torque_smoke",
        spec=low_low_high_task,
        maximum_duration_s=25.0,
        plant_interface_parameters=scaled_interface(0.9, 0.9, 1.2),
        plant_case_name="transition_response_v2__low_low_high_torque_smoke",
        record_selected_horizon_diagnostics=True,
        use_loaded_local_hold=True,
        stop_on_return_entry=False,
        use_bumpless_return_handoff=True,
        initialize_loaded_equilibrium_with_plant_truth=True,
        interface_uncertainty_spec=None,
        planning_physical_force_ceiling_n=180.0,
        planning_joint_velocity_ceiling_rad_s=tuple(np.radians([15.0, 25.0])),
        mpc_config=HumanMPCConfig(random_seed=20260824),
    )
    rows.append(
        {
            "case": "low_low_high_torque_smoke",
            "role": "genuine_startup_short_transient",
            "source_contract": (
                "unchanged_acceleration_semantics_v2_low_low_high_seed_20260824"
            ),
            "summary": low_low_high,
        }
    )

    result = {
        "schema": "stage5_transition_response_shadow_v2_minimum_cases",
        "evidence_category": "engineering_smoke_only",
        "scientific_parameters_changed": False,
        "abort_authority_changed": False,
        "threshold_changed": False,
        "case_count": len(rows),
        "cases": rows,
    }
    _write(output / "minimum_cases_summary.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
