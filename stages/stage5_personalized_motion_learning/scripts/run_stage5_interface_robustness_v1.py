#!/usr/bin/env python3
"""Run the six predeclared Interface Robustness v1 development episodes."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage3.spring_damper_interface import InterfaceParameters
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.goal_mpc_smoke import (
    InitialConditionValidationError,
    run_goal_mpc_smoke,
)
from traction_mpc_stage5.interface_robustness import (
    load_interface_robustness_contract,
    score_trace,
)
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK


def _scaled_plant(case: dict[str, object]) -> InterfaceParameters:
    base = STAGE5_RIGID_INTERFACE
    return InterfaceParameters(
        translation_stiffness_n_m=tuple(
            float(case["Kt_scale"]) * np.asarray(base.translation_stiffness_n_m)
        ),
        translation_damping_ns_m=tuple(
            float(case["D_scale"]) * np.asarray(base.translation_damping_ns_m)
        ),
        rotation_stiffness_nm_rad=(
            float(case["Kr_scale"]) * base.rotation_stiffness_nm_rad
        ),
        rotation_damping_nms_rad=(
            float(case["D_scale"]) * base.rotation_damping_nms_rad
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "interface_robustness_v1_development",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    contract = load_interface_robustness_contract()
    development = contract["development_v1"]
    planning_velocity = tuple(
        np.radians(development["planning_joint_velocity_ceiling_deg_s"])
    )
    rows = []
    for case in development["cases"]:
        case_dir = args.output_dir / str(case["name"])
        hold_s = float(case["hold_s"])
        task = replace(PROVISIONAL_LOW_MODERATE_GOAL_TASK, hold_duration_s=hold_s)
        plant = _scaled_plant(case)
        try:
            summary = run_goal_mpc_smoke(
                case_dir,
                spec=task,
                maximum_duration_s=(30.5 if hold_s >= 5.0 else 25.5),
                plant_interface_parameters=plant,
                plant_case_name=f"interface_robustness_v1__{case['name']}",
                record_selected_horizon_diagnostics=True,
                use_loaded_local_hold=True,
                stop_on_return_entry=False,
                use_bumpless_return_handoff=True,
                initialize_loaded_equilibrium_with_plant_truth=True,
                interface_uncertainty_spec=None,
                planning_physical_force_ceiling_n=float(
                    development["planning_physical_force_ceiling_n"]
                ),
                planning_joint_velocity_ceiling_rad_s=planning_velocity,
            )
        except InitialConditionValidationError as error:
            startup = dict(error.diagnostics)
            (case_dir / "startup_abort.json").write_text(
                json.dumps(startup, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            rows.append(
                {
                    "case": case,
                    "online_result": "ABORTED",
                    "abort_reason": startup["abort_reason"],
                    "evaluation_acceptance": False,
                    "initialization_failure": True,
                    "new_episode_index": len(rows) + 1,
                }
            )
            continue
        with np.load(case_dir / "trace.npz") as trace:
            score = score_trace(
                summary,
                trace,
                contract,
                long_hold_expected=hold_s >= 5.0,
            )
        rows.append(
            {
                "case": case,
                "score": score,
                "initialization_failure": False,
                "new_episode_index": len(rows) + 1,
            }
        )
    result = {
        "schema": "stage5_interface_robustness_v1_development_results",
        "evidence_category": "engineering_development_only",
        "episode_count": len(rows),
        "maximum_episode_budget": development["maximum_new_episodes"],
        "implementation_version": "V1",
        "controller_architecture_changed": False,
        "fixed_nominal_interface_model": True,
        "online_interface_identification_active": False,
        "interface_uncertainty_bank_control_authority": False,
        "planning_physical_force_ceiling_n": development[
            "planning_physical_force_ceiling_n"
        ],
        "physical_force_gate_n": contract["registered_hard_limits_unchanged"][
            "physical_cuff_force_gate_n"
        ],
        "planning_joint_velocity_ceiling_deg_s": development[
            "planning_joint_velocity_ceiling_deg_s"
        ],
        "registered_joint_velocity_limits_deg_s": contract[
            "registered_hard_limits_unchanged"
        ]["joint_velocity_deg_s"],
        "truth_used_online": False,
        "final_campaign_authorized": False,
        "rows": rows,
    }
    (args.output_dir / "development_summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
