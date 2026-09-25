#!/usr/bin/env python3
"""Run minimum unchanged-parameter cases with isolated post-abort continuation."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.confidence_pacing import (
    Stage5ConfidencePacing,
    Stage5PacingEvidence,
    current_nominal_model_trust_from_shadow_service,
)
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_identification import Stage5HumanIDMeasurement
from traction_mpc_stage5.human_identification_reduced import (
    ReducedShadowHumanIdentificationService,
)
from traction_mpc_stage5.interface_mismatch import unique_cases
from traction_mpc_stage5.interface_robustness_campaign import scaled_interface
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE
from traction_mpc_stage5.near_limit_shadow import NearLimitShadowTarget
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK

from run_stage5_human_id_confidence_pacing_v1 import (
    _challenger_status,
    _geometry,
    _human,
    _latest_information,
    _load_config,
)


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _summary_record(name: str, role: str, directory: Path, summary: dict[str, Any]):
    artifact = directory / "diagnostic_post_abort_continuation.json"
    return {
        "case": name,
        "role": role,
        "directory": str(directory),
        "authoritative_task_status": summary["task_status"],
        "authoritative_abort_reason": summary["abort_reason"],
        "authoritative_abort_time_s": summary["task_duration_s"],
        "diagnostic_continuation_created": artifact.exists(),
        "diagnostic_artifact": (
            "diagnostic_post_abort_continuation.json" if artifact.exists() else None
        ),
    }


def _run_human_mismatch(
    *,
    name: str,
    scales: list[float],
    output_dir: Path,
    config: dict[str, Any],
    near_limit_shadow_targets: tuple[NearLimitShadowTarget, ...] = (),
    diagnostic_post_abort_continuation: bool = True,
) -> dict[str, Any]:
    geometry = _geometry()
    service = ReducedShadowHumanIdentificationService(geometry)
    service.begin_episode(0, 0.0)
    pacing = Stage5ConfidencePacing()
    human = _human(scales)

    def callback(payload: dict[str, Any]) -> dict[str, Any]:
        session_time_s = float(payload["episode_time_s"])
        service.observe(
            Stage5HumanIDMeasurement(
                arrival_time_s=session_time_s,
                sample_time_s=session_time_s,
                estimated_human_state_rad_rad_s=payload[
                    "estimated_human_state_rad_rad_s"
                ],
                measured_human_cuff_force_world_n=payload[
                    "measured_human_cuff_force_world_n"
                ],
                measured_human_cuff_moment_world_nm=payload[
                    "measured_human_cuff_moment_world_nm"
                ],
                measured_generalized_human_input_nm=payload[
                    "measured_generalized_human_input_nm"
                ],
                task_phase=str(payload["task_phase"]),
                interface_model_version=str(payload["interface_model_version"]),
            )
        )
        information = _latest_information(service)
        adequate, reason = current_nominal_model_trust_from_shadow_service(
            {"attempts": service.attempts}
        )
        pacing.update(
            Stage5PacingEvidence(
                session_time_s=session_time_s,
                identification_informative=bool(information.get("rank", 0) == 3),
                information_rank=int(information.get("rank", 0)),
                information_condition_number=float(
                    information.get("condition_number", float("inf"))
                ),
                current_nominal_model_adequate=adequate,
                current_model_evidence_reason=reason,
                challenger_status=_challenger_status(service),
                shadow_publication_count=len(service.publication_history) - 1,
            )
        )
        return pacing.status(session_time_s)

    def plant_factory(parameters):
        return Stage5SensorBoundaryPlant(human, interface_parameters=parameters)

    return run_goal_mpc_smoke(
        output_dir,
        maximum_duration_s=25.5,
        plant_interface_parameters=STAGE5_RIGID_INTERFACE,
        plant_case_name=f"diagnostic_continuation__{name}__episode_01",
        record_selected_horizon_diagnostics=False,
        use_loaded_local_hold=True,
        use_bumpless_return_handoff=True,
        initialize_loaded_equilibrium_with_plant_truth=True,
        interface_uncertainty_spec=None,
        planning_physical_force_ceiling_n=float(
            config["controller"]["planning_physical_force_ceiling_n"]
        ),
        planning_joint_velocity_ceiling_rad_s=tuple(
            np.radians(
                config["controller"][
                    "base_planning_joint_velocity_ceiling_deg_s"
                ]
            )
        ),
        mpc_config=HumanMPCConfig(
            random_seed=int(config["controller"]["cem_random_seed"])
        ),
        plant_factory=plant_factory,
        progress_pacing_callback=callback,
        diagnostic_post_abort_continuation=diagnostic_post_abort_continuation,
        near_limit_shadow_targets=near_limit_shadow_targets,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "diagnostic_continuation_cases",
    )
    args = parser.parse_args()
    output = args.output_dir
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    mismatch = {case.name: case for case in unique_cases()}

    def cr12_factory(parameters):
        return Stage5CR12SensorBoundaryPlant(
            STAGE5_HUMAN, interface_parameters=parameters
        )

    directory = output / "cr12_baseline"
    summary = run_goal_mpc_smoke(
        directory,
        maximum_duration_s=0.5,
        plant_factory=cr12_factory,
        plant_case_name="diagnostic_continuation__cr12_provisional_cuff_baseline",
        diagnostic_post_abort_continuation=True,
    )
    rows.append(_summary_record("cr12_baseline", "fast_transient", directory, summary))

    directory = output / "kt_1p3"
    summary = run_goal_mpc_smoke(
        directory,
        plant_interface_parameters=mismatch["kt_1p3"].plant_truth,
        plant_case_name="diagnostic_continuation__kt_1p3",
        record_selected_horizon_diagnostics=True,
        use_loaded_local_hold=True,
        use_bumpless_return_handoff=True,
        initialize_loaded_equilibrium_with_plant_truth=True,
        diagnostic_post_abort_continuation=True,
    )
    rows.append(_summary_record("kt_1p3", "fast_transient", directory, summary))

    directory = output / "low_low_high"
    summary = run_goal_mpc_smoke(
        directory,
        spec=replace(PROVISIONAL_LOW_MODERATE_GOAL_TASK, hold_duration_s=0.5),
        maximum_duration_s=25.0,
        plant_interface_parameters=scaled_interface(0.9, 0.9, 1.2),
        plant_case_name="diagnostic_continuation__low_low_high",
        record_selected_horizon_diagnostics=True,
        use_loaded_local_hold=True,
        use_bumpless_return_handoff=True,
        initialize_loaded_equilibrium_with_plant_truth=True,
        interface_uncertainty_spec=None,
        planning_physical_force_ceiling_n=180.0,
        planning_joint_velocity_ceiling_rad_s=tuple(np.radians([15.0, 25.0])),
        mpc_config=HumanMPCConfig(random_seed=20260824),
        diagnostic_post_abort_continuation=True,
    )
    rows.append(
        _summary_record("low_low_high", "fast_transient", directory, summary)
    )

    config = _load_config()
    case_scales = {
        case["name"]: case["truth_scales_evaluation_only"]
        for case in config["cases"]
    }
    for name in ("stiffness_plus_15pct", "mass_plus_8pct"):
        directory = output / name
        summary = _run_human_mismatch(
            name=name,
            scales=case_scales[name],
            output_dir=directory,
            config=config,
        )
        rows.append(
            _summary_record(name, "model_induced_false_alarm", directory, summary)
        )

    result = {
        "schema": "stage5_diagnostic_continuation_minimum_cases_v1",
        "evidence_category": "engineering_smoke_only",
        "scientific_parameters_changed": False,
        "abort_authority_changed": False,
        "threshold_changed": False,
        "diagnostic_continuation_policy": "FROZEN_LAST_EXECUTABLE_COMMAND",
        "cases": rows,
        "matched_benign_controls_reused": [
            "results/transition_response_shadow_v2_minimum_cases_20260918_attempt_03/nominal_torque_smoke",
            "results/human_id_confidence_pacing_v1_attempt_01/nominal/episode_01",
            "results/human_id_confidence_pacing_v1_attempt_01/damping_plus_20pct/episode_01",
        ],
    }
    _write(output / "cases_summary.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
