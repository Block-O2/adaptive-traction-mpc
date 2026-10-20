#!/usr/bin/env python3
"""Mechanical Phase-3 interface validation; not a scientific experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.estimator_v2 import dynamic_regressor_row, nominal_base_parameters
from traction_mpc_stage5.architecture_recovery_v2.effective_model import (
    EffectiveGeometryFit,
    build_planar_geometry,
)
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import (
    AdaptiveHumanWaypointHWMPCV22,
    EventDrivenAdaptiveHWMPCV22,
    StateResidualBeliefUpdaterV22,
)
from traction_mpc_stage5.human_waypoint_feedback_mpc import HumanWaypointFeedbackMPCV1
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def validate(config_path: Path, output_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "architecture_recovery_v2_phase3_hwmpc_v3":
        raise ValueError("unexpected Phase-3 validation schema")
    if config.get("evidence_category") != "mechanical_interface_smoke":
        raise ValueError("Phase-3 validation must not be represented as formal evidence")

    fit = EffectiveGeometryFit(
        hip_xz_m=np.array([0.0, 0.062]),
        thigh_length_m=0.437,
        knee_to_cuff_m=0.288,
        residual_rms_m=0.0,
        maximum_residual_m=0.0,
        condition_number=1.0,
        sample_count=100,
        angular_span_rad=1.0,
        accepted=True,
        reason="calibrated_interface_fixture",
    )
    updater = StateResidualBeliefUpdaterV22.from_accepted_geometry_fit(fit)
    q = np.radians([20.0, 35.0])
    dq = np.zeros(2)
    ddq = np.radians([2.0, -3.0])
    torque = (
        dynamic_regressor_row(q, dq, ddq) @ nominal_base_parameters()
        + np.array([1.0, -0.5])
    )
    update = updater.observe_dynamics(
        q_rad=q,
        dq_rad_s=dq,
        ddq_rad_s2=ddq,
        applied_generalized_torque_nm=torque,
    )
    belief = updater.snapshot()

    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    scheduler = QuinticHumanWaypointSchedulerV1(spec, belief.human_model())
    adaptive_planner = AdaptiveHumanWaypointHWMPCV22(
        HumanWaypointFeedbackMPCV1(spec, scheduler)
    )
    controller = EventDrivenAdaptiveHWMPCV22(spec, adaptive_planner)
    start = np.asarray(spec.start_return_target_rad)
    goal = np.asarray(spec.outbound_goal_target_rad)
    start_state = np.concatenate([start, np.zeros(2)])
    goal_state = np.concatenate([goal, np.zeros(2)])
    controller.start(start, np.zeros(2))
    phases = []
    steps = [
        (start_state, start_state, 2.2),
        (goal_state, goal_state, 0.005),
        (goal_state, goal_state, spec.hold_duration_s),
        (start_state, start_state, 0.005),
    ]
    for state, reference, dt_s in steps:
        outcome = controller.observe_and_plan(
            belief=belief,
            current_deployable_state=state,
            current_reference_state=reference,
            dt_s=dt_s,
        )
        phases.append(outcome.task_state.phase.value)

    record = controller.record()
    decisions = record["planner"]["planner"]["decisions"]
    screens = [
        evaluation["execution_screen"]
        for decision in decisions
        for evaluation in decision["evaluations"]
        if evaluation["execution_screen"].get("evaluated")
    ]
    checks = {
        "belief_update_accepted": update["accepted_for_belief"] is True,
        "belief_has_no_truth_input": updater.record()["hidden_oracle_inputs"] == [],
        "belief_drives_all_plans": all(
            screen["belief_sequence"] == belief.sequence for screen in screens
        ),
        "adaptive_mechanics_screen_exercised": bool(screens),
        "direct_state_feedback_candidates": record["planner"][
            "fixed_r_or_path_template_used"
        ] is False,
        "old_robot_interface_predictor_absent": record["planner"][
            "old_robot_interface_predictor_used"
        ] is False,
        "event_driven_not_absolute_clock": phases[0] == TaskPhase.OUTBOUND.value,
        "actual_arrival_starts_hold": phases[1] == TaskPhase.HOLD.value,
        "valid_hold_dwell_starts_return": phases[2] == TaskPhase.RETURN.value,
        "actual_return_settling_completes": phases[3] == TaskPhase.COMPLETE.value,
        "value_hook_exposed": record["planner"]["value_hook_signature"]
        == "V(state_or_belief, candidate_next_waypoint)",
        "default_value_hook_zero": record["planner"]["value_hook_default"] == 0.0,
        "no_value_or_rl_training": record["planner"][
            "value_or_rl_training_performed"
        ] is False,
        "learning_transition_contract_complete": bool(record["learning_records"])
        and record["pending_learning_record"] is None
        and all(
            set(record["learning_record_contract"]) <= set(transition)
            and transition["status"] == "FINALIZED"
            and transition["provenance"]["deployable_truth_consumed"] is False
            for transition in record["learning_records"]
        ),
    }
    source_paths = [
        Path(
            "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/"
            "architecture_recovery_v2/phase3_human_waypoint.py"
        ),
        Path(
            "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/"
            "human_waypoint_feedback_mpc.py"
        ),
        Path(
            "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/"
            "human_waypoint_scheduler.py"
        ),
        Path(
            "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/"
            "human_waypoint_shadow.py"
        ),
        Path(
            "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/"
            "architecture_recovery_v2/functional_benchmark.py"
        ),
        Path(
            "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/"
            "architecture_recovery_v2/effective_model.py"
        ),
        Path(
            "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/"
            "task.py"
        ),
        Path(
            "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/"
            "geometry.py"
        ),
        Path(
            "stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/"
            "human.py"
        ),
        Path("stages/stage4_adaptive_control/src/traction_mpc_stage4/estimator_v2.py"),
        Path("stages/stage4_adaptive_control/src/traction_mpc_stage4/human_model.py"),
        Path("stages/stage4_adaptive_control/src/traction_mpc_stage4/mpc.py"),
        Path("stages/stage3_full3d/src/traction_mpc_stage3/human.py"),
        Path("stages/stage3_full3d/src/traction_mpc_stage3/executable_command.py"),
        Path(
            "stages/stage5_personalized_motion_learning/tests/"
            "architecture_recovery_v2/test_phase3_human_waypoint.py"
        ),
        Path(
            "stages/stage5_personalized_motion_learning/tests/"
            "architecture_recovery_v2/test_functional_firewall.py"
        ),
        Path(
            "stages/stage5_personalized_motion_learning/tests/"
            "test_stage5_hwmpc_state_feedback_v1.py"
        ),
        config_path,
        Path(__file__),
    ]
    result = {
        "schema": "architecture_recovery_v2_phase3_hwmpc_validation_v3",
        "evidence_category": "mechanical_interface_smoke",
        "config_path": str(config_path),
        "config_sha256": _sha256(config_path),
        "source_manifest": {
            str(path): _sha256(path) for path in source_paths
        },
        "passed": all(checks.values()),
        "checks": checks,
        "phase_sequence": phases,
        "belief": belief.value_state_record(),
        "belief_updater": updater.record(),
        "architecture": record,
        "limitations": [
            "simulation-only mechanical interface validation",
            "no physical CR12 actuation or human testing",
            "no hardware real-time validation",
            "no RL, value-learning, or imitation-learning training",
            "the historical detailed robot/interface predictor is intentionally absent",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(_jsonable(result), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if not result["passed"]:
        raise RuntimeError("Phase-3 mechanical interface validation failed")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = validate(args.config, args.output)
    print(json.dumps({"passed": result["passed"], "checks": result["checks"]}))


if __name__ == "__main__":
    main()
