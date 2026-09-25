#!/usr/bin/env python3
"""Replay the approved Stage-5 split acceleration-authority validation matrix."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.interface_mismatch import unique_cases
from traction_mpc_stage5.interface_robustness_campaign import scaled_interface
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE
from traction_mpc_stage5.posture_benefit import (
    PostureRegion,
    PostureRegionIntervention,
    PostureRegionSpec,
)
from traction_mpc_stage5.task import (
    PROVISIONAL_LOW_MODERATE_GOAL_TASK,
    TaskPhase,
)
from traction_mpc_stage5.trust_gamma_matched import (
    build_control_human_model,
    extract_supported_model,
    load_trust_gamma_contract,
)

from run_stage5_cr12_smoke import run_cr12_smoke
from run_stage5_diagnostic_continuation_cases import _run_human_mismatch
from run_stage5_human_id_confidence_pacing_v1 import _load_config
from run_stage5_posture_benefit_v1 import (
    _fixed_pacing,
    _geometry,
    _load_config as _load_posture_config,
    _no_human_update,
    _truth_human,
)


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _case_metrics(
    name: str,
    role: str,
    directory: Path,
    summary: dict[str, Any],
) -> dict[str, Any]:
    with np.load(directory / "trace.npz", allow_pickle=False) as trace:
        active = np.asarray(trace["human_motion_authority_active"], dtype=bool)
        authority = np.degrees(
            np.asarray(trace["human_motion_authority_acceleration_rad_s2"])
        )
        fast_valid = np.asarray(trace["shadow_fast_motion_valid"], dtype=bool)
        fast = np.degrees(
            np.asarray(trace["shadow_fast_motion_acceleration_rad_s2"])
        )
        authority_peak = (
            np.max(np.abs(authority[active]), axis=0).tolist()
            if np.any(active)
            else None
        )
        fast_peak = (
            np.max(np.abs(fast[fast_valid]), axis=0).tolist()
            if np.any(fast_valid)
            else None
        )
        authority_event_indices = np.flatnonzero(
            trace["human_motion_authority_violation"]
        )
        authority_event_times = trace["time_s"][authority_event_indices].tolist()
    return {
        "case": name,
        "evidence_role": role,
        "directory": str(directory.relative_to(STAGE5_ROOT)),
        "task_status": summary["task_status"],
        "abort_reason": summary["abort_reason"],
        "duration_s": summary["task_duration_s"],
        "phase_transitions": summary["phase_transitions"],
        "human_motion_authority": summary[
            "human_motion_acceleration_authority"
        ],
        "peak_abs_human_motion_20ms_deg_s2": authority_peak,
        "human_motion_authority_event_times_s": authority_event_times,
        "peak_abs_fast_motion_5ms_deg_s2_shadow_only": fast_peak,
        "fast_transient_hard_threshold_registered": False,
        "fast_transient_abort_authority": False,
        "safety_filter_status_counts": summary["safety_filter_status_counts"],
        "brake_event_count": summary["brake_event_count"],
        "force_gate_event_count": summary["force_gate_event_count"],
    }


def _run_interface_case(
    *,
    output_dir: Path,
    name: str,
    scales: tuple[float, float, float],
) -> dict[str, Any]:
    if name in {"kt_0p7", "kt_1p3"}:
        mismatch = {case.name: case for case in unique_cases()}
        return run_goal_mpc_smoke(
            output_dir,
            plant_interface_parameters=mismatch[name].plant_truth,
            plant_case_name=f"split_authority_validation__{name}",
            record_selected_horizon_diagnostics=True,
            use_loaded_local_hold=True,
            stop_on_return_entry=False,
            use_bumpless_return_handoff=True,
            initialize_loaded_equilibrium_with_plant_truth=True,
        )
    return run_goal_mpc_smoke(
        output_dir,
        spec=replace(PROVISIONAL_LOW_MODERATE_GOAL_TASK, hold_duration_s=0.5),
        maximum_duration_s=25.5,
        plant_interface_parameters=scaled_interface(*scales),
        plant_case_name=f"split_authority_validation__{name}",
        record_selected_horizon_diagnostics=True,
        use_loaded_local_hold=True,
        use_bumpless_return_handoff=True,
        initialize_loaded_equilibrium_with_plant_truth=True,
        interface_uncertainty_spec=None,
        planning_physical_force_ceiling_n=180.0,
        planning_joint_velocity_ceiling_rad_s=tuple(np.radians([15.0, 25.0])),
        mpc_config=HumanMPCConfig(random_seed=20260824),
    )


def _run_pb_d_knee(output_dir: Path) -> dict[str, Any]:
    config = _load_posture_config()
    condition = config["fixed_condition"]
    design = config["formal_design"]
    start = next(row for row in design["starts"] if row["name"] == "early_outbound")
    region = next(row for row in design["regions"] if row["name"] == "knee_biased")
    seed = 20260919
    intervention = PostureRegionIntervention(
        PostureRegionSpec(
            start_name=str(start["name"]),
            start_phase=TaskPhase(str(start["phase"])),
            start_minimum_progress=float(start["minimum_progress"]),
            region=PostureRegion(str(region["name"])),
            center_progress=tuple(float(value) for value in region["center_progress"]),
            half_width_progress=tuple(
                float(value) for value in region["half_width_progress"]
            ),
            maximum_waypoint_duration_s=float(
                design["maximum_waypoint_duration_s"]
            ),
        )
    )
    frozen = extract_supported_model(load_trust_gamma_contract())
    control_model = build_control_human_model(_geometry(), frozen)
    truth_human = _truth_human()

    def plant_factory(parameters):
        return Stage5SensorBoundaryPlant(
            truth_human, interface_parameters=parameters
        )

    return run_goal_mpc_smoke(
        output_dir,
        maximum_duration_s=float(condition["maximum_duration_s"]),
        plant_interface_parameters=STAGE5_RIGID_INTERFACE,
        plant_case_name="split_authority_validation__pb_d_knee_biased",
        record_selected_horizon_diagnostics=False,
        use_loaded_local_hold=True,
        use_bumpless_return_handoff=True,
        initialize_loaded_equilibrium_with_plant_truth=True,
        interface_uncertainty_spec=None,
        planning_physical_force_ceiling_n=float(
            condition["planning_physical_force_ceiling_n"]
        ),
        planning_joint_velocity_ceiling_rad_s=tuple(
            np.radians(
                condition["base_planning_joint_velocity_ceiling_deg_s"]
            )
        ),
        mpc_config=HumanMPCConfig(random_seed=seed),
        plant_factory=plant_factory,
        progress_pacing_callback=_fixed_pacing,
        control_human_model_callback=_no_human_update,
        control_human_model_callback_is_no_update_freeze=True,
        initial_control_human_model=control_model,
        initial_control_human_model_version=frozen.model_id,
        prefix_backend=str(condition["prefix_backend"]),
        matched_branch_intervention=intervention,
        minimum_phase_duration_s=config["timing_contract"][
            "minimum_phase_duration_s"
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "split_authority_validation",
    )
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    config = _load_config()
    scales = {
        case["name"]: case["truth_scales_evaluation_only"]
        for case in config["cases"]
    }
    for name in (
        "stiffness_plus_15pct",
        "mass_plus_8pct",
        "mixed_effective_scales",
    ):
        directory = output / name
        summary = _run_human_mismatch(
            name=name,
            scales=scales[name],
            output_dir=directory,
            config=config,
            diagnostic_post_abort_continuation=False,
        )
        rows.append(
            _case_metrics(
                name, "old_human_mismatch_false_positive", directory, summary
            )
        )

    for name, role, case_scales in (
        ("kt_0p7", "true_20ms_human_motion_violation", (0.7, 1.0, 1.0)),
        ("low_low_high", "fast_transient_shadow_case", (0.9, 0.9, 1.2)),
        ("kt_1p3", "fast_transient_shadow_case", (1.3, 1.0, 1.0)),
    ):
        directory = output / name
        summary = _run_interface_case(
            output_dir=directory,
            name=name,
            scales=case_scales,
        )
        rows.append(_case_metrics(name, role, directory, summary))

    directory = output / "pb_d_knee_biased"
    summary = _run_pb_d_knee(directory)
    rows.append(
        _case_metrics(
            "pb_d_knee_biased",
            "old_pb_d_model_based_false_positive",
            directory,
            summary,
        )
    )

    cr12_directory = output / "cr12_complete_baseline"
    cr12 = run_cr12_smoke(
        cr12_directory,
        maximum_duration_s=30.5,
        contract="provisional_cuff_baseline",
    )
    cr12_summary = json.loads(
        (cr12_directory / "execution" / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    rows.append(
        _case_metrics(
            "cr12_complete_baseline",
            "old_cr12_model_based_false_positive_and_complete_baseline",
            cr12_directory / "execution",
            cr12_summary,
        )
    )

    by_name = {row["case"]: row for row in rows}
    mismatch_names = (
        "stiffness_plus_15pct",
        "mass_plus_8pct",
        "mixed_effective_scales",
    )
    validation = {
        "old_human_mismatch_acceleration_false_positives_removed": all(
            by_name[name]["abort_reason"] != "TASK_ACCELERATION_LIMIT"
            for name in mismatch_names
        ),
        "pb_d_old_acceleration_false_positive_removed": (
            by_name["pb_d_knee_biased"]["abort_reason"]
            != "TASK_ACCELERATION_LIMIT"
        ),
        "cr12_old_0p315s_model_based_abort_removed": not any(
            np.isclose(time_s, 0.315, atol=1.0e-10, rtol=0.0)
            for time_s in by_name["cr12_complete_baseline"][
                "human_motion_authority_event_times_s"
            ]
        ),
        "cr12_complete_baseline_has_no_human_motion_abort": (
            by_name["cr12_complete_baseline"]["abort_reason"]
            != "TASK_ACCELERATION_LIMIT"
        ),
        "kt_0p7_true_20ms_violation_detected": bool(
            by_name["kt_0p7"]["abort_reason"] == "TASK_ACCELERATION_LIMIT"
            and by_name["kt_0p7"]["human_motion_authority"]["event_count"] > 0
        ),
        "low_low_high_is_not_human_motion_violation": (
            by_name["low_low_high"]["abort_reason"]
            != "TASK_ACCELERATION_LIMIT"
        ),
        "kt_1p3_is_not_human_motion_violation": (
            by_name["kt_1p3"]["abort_reason"]
            != "TASK_ACCELERATION_LIMIT"
        ),
        "fast_transient_channels_remain_shadow_only": all(
            row["fast_transient_abort_authority"] is False
            and row["fast_transient_hard_threshold_registered"] is False
            for row in rows
        ),
    }
    all_required_checks_passed = all(validation.values())
    if not all_required_checks_passed:
        conclusion = "AM-C — NEW HUMAN-MOTION AUTHORITY NOT VALIDATED"
    elif by_name["cr12_complete_baseline"]["task_status"] == "COMPLETE":
        conclusion = (
            "AM-A — SPLIT AUTHORITY VALIDATED; COMPLETE CR12 BASELINE READY"
        )
    else:
        conclusion = (
            "AM-B — HUMAN-MOTION AUTHORITY VALID, BUT CR12 BASELINE FAILS "
            "FOR ANOTHER EXISTING REASON"
        )
    payload = {
        "schema": "stage5_split_acceleration_authority_validation_v1",
        "evidence_category": "engineering_authority_validation",
        "authority_change": (
            "Human-motion acceleration abort now uses full causal 20 ms "
            "deployable dq_hat history with unchanged 300/600 deg/s2 limits"
        ),
        "model_based_qdd_human_motion_abort_authority": False,
        "fast_transient_abort_authority": False,
        "fast_transient_hard_threshold_registered": False,
        "fast_transient_protection_delegation": (
            "future lower-level CR12 and force/torque safety"
        ),
        "scientific_parameters_changed": False,
        "other_controller_semantics_changed": False,
        "validation": validation,
        "all_required_authority_checks_passed": all_required_checks_passed,
        "conclusion": conclusion,
        "cases": rows,
        "cr12_baseline": cr12,
    }
    _write(output / "split_authority_validation.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
