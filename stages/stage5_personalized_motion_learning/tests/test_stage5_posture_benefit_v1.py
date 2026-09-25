from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.goal_mpc_smoke import _apply_minimum_phase_duration
from traction_mpc_stage5.posture_benefit import (
    PostureRegion,
    PostureRegionIntervention,
    PostureRegionSpec,
    audit_posture_regions,
    outbound_normalized_progress,
    progress_to_q_rad,
)
from traction_mpc_stage5.task import (
    GoalTaskState,
    PROVISIONAL_LOW_MODERATE_GOAL_TASK,
    TaskPhase,
)


CONFIG = STAGE5_ROOT / "configs" / "stage5_posture_benefit_v1.json"
SCRIPT = STAGE5_ROOT / "scripts" / "run_stage5_posture_benefit_v1.py"
SPEC = importlib.util.spec_from_file_location("stage5_posture_benefit_v1", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_contract_freezes_regions_timing_and_control_authority() -> None:
    config = _config()
    condition = config["fixed_condition"]
    design = config["formal_design"]
    assert config["schema"] == "stage5_posture_benefit_v1"
    assert config["region_selection_rule"]["force_or_moment_results_used"] is False
    assert condition["gamma"] == 0.5
    assert condition["interface"] == "fixed_nominal"
    assert condition["human_model_updates_enabled"] is False
    assert condition["trust_to_gamma_authority"] is False
    assert condition["learned_value_or_actor_control"] is False
    assert [row["name"] for row in design["starts"]] == [
        "early_outbound",
        "early_return",
    ]
    assert [row["name"] for row in design["regions"]] == [
        "hip_biased",
        "balanced",
        "knee_biased",
    ]
    assert design["rollout_count"] == 18
    assert config["timing_contract"]["minimum_phase_duration_s"] == {
        "OUTBOUND": 6.0,
        "RETURN": 6.0,
    }
    assert config["control_authority"]["value_model_training"] is False
    assert config["control_authority"]["stage3_or_stage4_modified"] is False


def test_frozen_region_geometry_passes_force_blind_feasibility_audit() -> None:
    config = _config()
    design = config["formal_design"]
    gates = config["feasibility_gates"]
    audit = audit_posture_regions(
        task=PROVISIONAL_LOW_MODERATE_GOAL_TASK,
        starts=design["starts"],
        regions=design["regions"],
        maximum_waypoint_duration_s=design["maximum_waypoint_duration_s"],
        effective_velocity_deg_s=config["fixed_condition"][
            "effective_planning_joint_velocity_ceiling_deg_s"
        ],
        minimum_adjacent_center_distance=gates[
            "minimum_adjacent_center_distance_normalized"
        ],
        minimum_extreme_center_distance=gates[
            "minimum_extreme_center_distance_normalized"
        ],
    )
    assert audit["passed"] is True
    assert audit["force_or_moment_used_to_select_regions"] is False
    assert audit["equal_mean_normalized_progress"] is True
    assert audit["region_boxes_disjoint"] is True
    expected_q_deg = {
        "hip_biased": [14.375, 20.625],
        "balanced": [12.875, 23.125],
        "knee_biased": [11.375, 25.625],
    }
    assert all(
        np.allclose(audit["centers_q_deg"][name], expected)
        for name, expected in expected_q_deg.items()
    )


def test_progress_conversion_is_invertible() -> None:
    task = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    progress = np.array([0.625, 0.425])
    q = progress_to_q_rad(progress, task)
    assert np.allclose(outbound_normalized_progress(q, task), progress)


def test_region_intervention_changes_only_temporary_mpc_goal() -> None:
    task = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    intervention = PostureRegionIntervention(
        PostureRegionSpec(
            start_name="early_outbound",
            start_phase=TaskPhase.OUTBOUND,
            start_minimum_progress=0.25,
            region=PostureRegion.HIP_BIASED,
            center_progress=(0.625, 0.425),
            half_width_progress=(0.04, 0.04),
            maximum_waypoint_duration_s=2.0,
        )
    )
    intervention.activation_time_s = 1.0
    temporary = intervention.planning_spec(
        task,
        episode_time_s=1.5,
        phase=TaskPhase.OUTBOUND,
        q_rad=progress_to_q_rad([0.30, 0.30], task),
    )
    restored = intervention.planning_spec(
        task,
        episode_time_s=3.0,
        phase=TaskPhase.OUTBOUND,
        q_rad=progress_to_q_rad([0.30, 0.30], task),
    )
    assert np.allclose(
        temporary.outbound_goal_target_rad,
        progress_to_q_rad([0.625, 0.425], task),
    )
    assert restored is task
    action = np.array([3.0, 4.0])
    assert np.array_equal(
        intervention.candidate_action(
            action, episode_time_s=1.5, phase=TaskPhase.OUTBOUND
        ),
        action,
    )
    released = intervention.planning_spec(
        task,
        episode_time_s=1.6,
        phase=TaskPhase.OUTBOUND,
        q_rad=progress_to_q_rad([0.625, 0.425], task),
    )
    assert released is task
    assert intervention.consume_goal_transition() is True
    assert intervention.consume_goal_transition() is False


def test_phase_timing_floor_delays_success_without_changing_limits() -> None:
    previous = GoalTaskState(
        phase=TaskPhase.OUTBOUND,
        phase_elapsed_s=4.0,
        hold_elapsed_s=0.0,
        start_validated=True,
        outbound_hold_completed=False,
    )
    candidate = GoalTaskState(
        phase=TaskPhase.HOLD,
        phase_elapsed_s=0.0,
        hold_elapsed_s=0.0,
        start_validated=True,
        outbound_hold_completed=False,
    )
    delayed = _apply_minimum_phase_duration(
        previous,
        candidate,
        dt_s=0.005,
        minimum_phase_duration_s={TaskPhase.OUTBOUND: 6.0},
    )
    assert delayed.phase is TaskPhase.OUTBOUND
    assert delayed.phase_elapsed_s == 4.005
    assert PROVISIONAL_LOW_MODERATE_GOAL_TASK.phase_timeout_s == 10.0


def _formal_rows(*, reduction: float, separation: float = 0.40) -> list[dict]:
    rows = []
    for start in ("early_outbound", "early_return"):
        for seed in (20260917, 20260918, 20260919):
            progresses = {
                "hip_biased": [0.525 + separation / 2.0, 0.525 - separation / 2.0],
                "balanced": [0.525, 0.525],
                "knee_biased": [0.525 - separation / 2.0, 0.525 + separation / 2.0],
            }
            integrals = {
                "hip_biased": 100.0 * (1.0 - reduction),
                "balanced": 100.0,
                "knee_biased": 105.0,
            }
            for region in ("hip_biased", "balanced", "knee_biased"):
                rows.append(
                    {
                        "start_name": start,
                        "cem_seed": seed,
                        "region": region,
                        "decision_state_sha256": f"{start}-{seed}",
                        "region_reached": True,
                        "closest_progress": progresses[region],
                        "closest_q_deg": (
                            np.degrees(
                                progress_to_q_rad(
                                    progresses[region],
                                    PROVISIONAL_LOW_MODERATE_GOAL_TASK,
                                )
                            ).tolist()
                        ),
                        "remaining_task_duration_s": 10.0,
                        "future_cumulative_measured_cuff_force_n_s": integrals[region],
                        "task_complete": True,
                        "fixed_condition_valid": True,
                        "safety_valid": True,
                        "all_waypoint_prefixes_feasible": True,
                        "truth_used_for_controller_or_branch_decision": False,
                    }
                )
    return rows


def test_decision_logic_distinguishes_pb_a_b_c_and_d() -> None:
    config = _config()
    assert RUNNER._group_analysis(
        _formal_rows(reduction=0.06), config
    )["decision"] == "PB-A"
    assert RUNNER._group_analysis(
        _formal_rows(reduction=0.02), config
    )["decision"] == "PB-B"
    assert RUNNER._group_analysis(
        _formal_rows(reduction=0.06, separation=0.10), config
    )["decision"] == "PB-C"
    invalid = _formal_rows(reduction=0.06)
    invalid[0]["decision_state_sha256"] = "not-matched"
    assert RUNNER._group_analysis(invalid, config)["decision"] == "PB-D"
