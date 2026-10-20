"""Build the Stage-5 control-abstraction study from saved engineering evidence.

This script is audit-only.  It reads repository artifacts and production source
contracts; it never instantiates a plant or changes controller behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from traction_mpc_stage3.executable_command import EXECUTION_CONTROL_DT_S
from traction_mpc_stage4.mpc import HumanMPCConfig


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
STAGE5_ROOT = REPOSITORY_ROOT / "stages" / "stage5_personalized_motion_learning"

EVIDENCE_PATHS = {
    "contact_role": STAGE5_ROOT
    / "results/engineering_validation/human_table_contact_role_audit_attempt_01/contact_role_audit.json",
    "support_domain": STAGE5_ROOT
    / "results/engineering_validation/prediction_support_domain_v1_attempt_02/prediction_support_domain.json",
    "matched_robot": STAGE5_ROOT
    / "results/engineering_validation/matched_ur10e_cr12_prediction_audit_attempt_04/matched_prediction_audit.json",
    "compact_predictor": STAGE5_ROOT
    / "results/engineering_validation/cr12_compact_execution_predictor_v1_attempt_03/summary.json",
    "rigid_predictor": STAGE5_ROOT
    / "results/engineering_validation/cr12_rigid_body_predictor_v1_attempt_03/summary.json",
    "disturbance_observer": STAGE5_ROOT
    / "results/engineering_validation/short_horizon_disturbance_observer_v1_attempt_06/disturbance_validation.json",
    "residual_learner": STAGE5_ROOT
    / "results/engineering_validation/short_horizon_residual_v1_attempt_01/residual_validation.json",
}


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_saved_evidence(evidence: dict[str, dict[str, Any]]) -> None:
    contact = evidence["contact_role"]
    support = evidence["support_domain"]
    residual = evidence["residual_learner"]
    if not contact["registered_task_contact_free_check"]["contact_free"]:
        raise RuntimeError("registered task is no longer contact-free in saved evidence")
    if not contact["observed_complete_contact_free_check"][
        "all_phases_contact_free_by_capsule_clearance"
    ]:
        raise RuntimeError("complete UR10e contact-free evidence is missing")
    if support["key_answers"][
        "continuous_supported_outbound_hold_return_route_observed"
    ]:
        raise RuntimeError("support-domain conclusion changed; refresh this audit")
    if not residual["next_decision_is_control_abstraction_change"]:
        raise RuntimeError("residual study no longer points to control abstraction")


def build_summary() -> dict[str, Any]:
    evidence = {name: _load(path) for name, path in EVIDENCE_PATHS.items()}
    _assert_saved_evidence(evidence)
    config = HumanMPCConfig()
    contact = evidence["contact_role"]
    support = evidence["support_domain"]
    compact = evidence["compact_predictor"]
    rigid = evidence["rigid_predictor"]
    observer = evidence["disturbance_observer"]
    residual = evidence["residual_learner"]
    matched = evidence["matched_robot"]

    summary: dict[str, Any] = {
        "schema": "stage5_control_abstraction_study_v1",
        "evidence_category": "read_only_saved_evidence_design_audit",
        "decision": (
            "CA2-A — HUMAN-SPACE HIGH-LEVEL MPC IS THE CLEANEST NEXT ABSTRACTION"
        ),
        "production_behavior_changed": False,
        "scope_invariants": {
            "controller_parameters_changed": False,
            "thresholds_changed": False,
            "task_changed": False,
            "contact_model_changed": False,
            "human_model_changed": False,
            "rl_or_value_changed": False,
            "stage3_or_stage4_changed": False,
            "new_rollout_executed": False,
        },
        "current_mpc_contract": {
            "optimizer": "CEM nonlinear shooting MPC",
            "decision_variable": (
                "two-DoF Human generalized motion-action increment delta_u_motion_nm"
            ),
            "executed_total_action": (
                "u_total = inverse_dynamics(q_hat,dq_hat,qdd=0) + delta_u_motion"
            ),
            "prediction_dt_s": config.prediction_dt_s,
            "horizon_steps": config.horizon_steps,
            "horizon_s": config.prediction_dt_s * config.horizon_steps,
            "candidate_count": config.candidate_count,
            "cem_iterations": config.cem_iterations,
            "objective": [
                "phase-goal Human q/dq tracking",
                "terminal Human q/dq error",
                "motion-action effort and slew",
                "HOLD admissible-set regulation",
            ],
            "high_level_constraints": [
                "Human and task q bounds",
                "Human dq and causal 20 ms acceleration envelope",
                "predicted physical cuff-force ceiling",
                "HOLD q/dq completion set",
            ],
            "execution_chain": [
                "Human generalized action",
                "Human-point cuff wrench allocation",
                "robot-point wrench transform",
                "fixed loaded cuff pose/twist feedback plus allocator wrench",
                "CR12 Jacobian transpose, bias/posture torque, torque clipping",
            ],
            "execution_control_dt_s": EXECUTION_CONTROL_DT_S,
            "first_action_prefix_times_s": [0.005, 0.010, 0.015, 0.020],
            "first_action_predicted_quantities": [
                "Human q/dq and cumulative acceleration",
                "interface translation/rotation and rates",
                "physical cuff force/moment",
                "executable command wrench",
            ],
            "full_horizon_predicted_quantities": [
                "Human q/dq",
                "nominal interface state",
                "requested/transmitted cuff wrench",
            ],
            "semantic_burden": (
                "MPC feasibility depends on a nominal command-to-interface-to-Human "
                "recurrence even though robot/cuff execution is a separate 5 ms loop"
            ),
        },
        "candidate_abstractions": {
            "A_human_waypoint_velocity": {
                "mpc_decision_variables": (
                    "short sequence of Human q waypoints and/or bounded dq targets"
                ),
                "prediction_model_needed": (
                    "slow Human kinematic/progress model with personalized reachable "
                    "motion envelope; no 5 ms robot rigid-body or interface recurrence"
                ),
                "lower_level_cr12_responsibility": (
                    "map the Human target through known Human/cuff geometry to a cuff "
                    "pose/twist reference, track it, and own wrench/torque/fast-transient limits"
                ),
                "high_level_checks_retained": [
                    "Human ROM and task q bounds",
                    "Human dq/pacing limits",
                    "causal realized 20 ms Human-acceleration authority",
                    "known-geometry shank/table clearance and phase completion",
                    "supervisory response to low-level infeasibility",
                ],
                "prediction_details_removed": [
                    "robot q/dq propagation",
                    "5 ms cuff tracking response",
                    "interface deformation recurrence",
                    "joint-torque prediction",
                    "short-transient wrench prediction as an MPC feasibility premise",
                ],
                "future_force_value_compatibility": (
                    "high: measured cuff-force integral and low-level limit activity can be "
                    "stage costs/context for a low-dimensional Human-state action value"
                ),
                "tradeoff_evaluation": {
                    "scientific_clarity": "strong_direct_match_to_registered_Human_task",
                    "prediction_burden": "lowest",
                    "realtime_feasibility": "strong",
                    "human_personalization": "strong",
                    "cumulative_force_optimization": "strong_but_uses_measured_or_slow_response_not_instantaneous_wrench_truth",
                    "real_CR12_portability": "strong_robot_independent_high_level_contract",
                },
                "task_representation": "supported_by_contact_free_registered_Human_path",
            },
            "B_cuff_pose_twist_reference": {
                "mpc_decision_variables": "cuff SE(3) pose/twist reference increments",
                "prediction_model_needed": (
                    "cuff-reference-to-Human response, including enough interface/load "
                    "behavior to evaluate Human motion and force"
                ),
                "lower_level_cr12_responsibility": (
                    "track cuff pose/twist and enforce robot wrench/torque/transient limits"
                ),
                "high_level_checks_retained": [
                    "mapped Human ROM, q/dq and clearance",
                    "phase completion",
                    "coarse cumulative interaction objective",
                ],
                "prediction_details_removed": [
                    "explicit robot rigid-body propagation",
                    "joint-torque prediction inside MPC",
                ],
                "future_force_value_compatibility": (
                    "high because cuff motion/load are native state/action context"
                ),
                "tradeoff_evaluation": {
                    "scientific_clarity": "moderate_task_goal_requires_inverse_Human_mapping",
                    "prediction_burden": "medium_interface_and_Human_response_remain",
                    "realtime_feasibility": "strong_if_cuff_tracking_is_treated_as_lower_level_contract",
                    "human_personalization": "moderate",
                    "cumulative_force_optimization": "strong",
                    "real_CR12_portability": "strong_standard_cartesian_reference_boundary",
                },
                "task_representation": (
                    "feasible through known Human/cuff geometry, but when generated from "
                    "Human q/dq it is the execution representation of option A"
                ),
            },
            "C_impedance_force_assisted_reference": {
                "mpc_decision_variables": (
                    "cuff pose/twist reference plus assist wrench and/or impedance schedule"
                ),
                "prediction_model_needed": (
                    "Human-interface closed-loop load response and hardware impedance behavior"
                ),
                "lower_level_cr12_responsibility": (
                    "execute variable impedance/assist and enforce F/T, torque and transient safety"
                ),
                "high_level_checks_retained": [
                    "Human motion envelope",
                    "task/clearance constraints",
                    "cumulative force/load objective",
                ],
                "prediction_details_removed": [
                    "explicit robot joint propagation only if hardware impedance is contractual"
                ],
                "future_force_value_compatibility": "very_high_but_confounded_by_impedance_policy",
                "tradeoff_evaluation": {
                    "scientific_clarity": "weakest_action_combines_motion_and_assistance",
                    "prediction_burden": "highest_of_the_three",
                    "realtime_feasibility": "uncertain_without_low_level_design",
                    "human_personalization": "strong_potential_but_more_parameters",
                    "cumulative_force_optimization": "strongest_direct_control",
                    "real_CR12_portability": "uncertain_requires_validated_FT_and_impedance_stack",
                },
                "task_representation": (
                    "possible but not required by the saved contact-free task evidence"
                ),
            },
        },
        "saved_evidence": {
            "task_contact_role": {
                "registered_contact_free": contact[
                    "registered_task_contact_free_check"
                ]["contact_free"],
                "registered_path_minimum_clearance_mm": contact[
                    "registered_task_contact_free_check"
                ]["minimum_clearance_mm"],
                "complete_ur10e_contact_free": contact[
                    "observed_complete_contact_free_check"
                ]["all_phases_contact_free_by_capsule_clearance"],
                "complete_ur10e_minimum_clearance_mm_observation_not_threshold": contact[
                    "observed_complete_contact_free_check"
                ]["minimum_clearance_mm"],
                "cr12_contact_classification": contact[
                    "cr12_contact_interpretation"
                ]["classification"],
            },
            "fast_prediction_failures": {
                "compact_accel_error_p95_deg_s2": compact["criteria"][
                    "human_acceleration_p95"
                ]["observed_deg_s2"],
                "compact_complete_mpc_p95_ms": compact["runtime"]["p95_ms"],
                "rigid_accel_error_p95_deg_s2": rigid["criteria"][
                    "human_acceleration_p95"
                ]["observed_deg_s2"],
                "rigid_complete_mpc_p95_ms": rigid["runtime"]["p95_ms"],
                "observer_accel_error_p95_deg_s2": observer["criteria"][
                    "human_acceleration"
                ]["observed_p95_deg_s2"],
                "observer_complete_mpc_p95_ms": observer["runtime"]["p95_ms"],
                "residual_accel_error_p95_deg_s2": residual["criteria"][
                    "human_acceleration"
                ]["observed_p95_deg_s2"],
                "residual_complete_mpc_p95_ms": residual["runtime"]["p95_ms"],
            },
            "support_domain": {
                "materially_improves_reliability": support["key_answers"][
                    "restriction_materially_improves_reliability"
                ],
                "meets_accuracy_targets": support["key_answers"][
                    "supported_subset_meets_existing_engineering_accuracy_targets"
                ],
                "continuous_phase_spanning_route": support["key_answers"][
                    "continuous_supported_outbound_hold_return_route_observed"
                ],
                "heldout_zero_action_solves": support["held_out"][
                    "solve_count_with_zero_supported_candidates"
                ],
            },
            "robot_comparison": {
                "decision": matched["decision"],
                "first_harmful_divergence": matched[
                    "first_harmful_feasibility_divergence"
                ],
            },
        },
        "responsibility_split_recommended": {
            "high_level_human_mpc": [
                "choose task-relevant Human q/dq waypoints on the existing 20 ms planning grid",
                "optimize phase progress, personalization, and cumulative measured interaction",
                "enforce Human ROM/dq/reference-clearance constraints",
            ],
            "cross_layer_supervisor": [
                "retain causal realized 20 ms Human-acceleration authority",
                "consume low-level feasible/fault/limit status",
                "retain task phase, Safety Filter/BRAKE outcome handling and abort semantics",
            ],
            "lower_level_cr12_execution": [
                "translate the Human target to cuff pose/twist through known geometry",
                "track cuff references and manage interface energy",
                "enforce cuff F/T, robot torque/collision and fast-transient protection",
            ],
        },
        "one_next_implementation": {
            "name": "HumanWaypointMPCShadowContractV1",
            "scope": (
                "shadow-only q/dq waypoint candidates with deterministic Human-to-cuff "
                "reference conversion; compare requested waypoint progress, realized Human "
                "motion, measured cumulative cuff force, and low-level feasibility"
            ),
            "must_not_include": [
                "new low-level gains",
                "new impedance mode",
                "new safety threshold",
                "production activation",
            ],
        },
        "limitations": [
            "No controlled closed-loop Human-waypoint controller has yet been implemented.",
            "Saved CR12 evidence ends in early OUTBOUND; full CR12 phase coverage is absent.",
            "The study selects a contract for the next shadow implementation, not a safety proof.",
        ],
        "source_artifacts": {
            name: {
                "path": str(path.relative_to(REPOSITORY_ROOT)),
                "sha256": _sha256(path),
            }
            for name, path in EVIDENCE_PATHS.items()
        },
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=STAGE5_ROOT
        / "results/engineering_validation/control_abstraction_study_v1_attempt_01/control_abstraction_summary.json",
    )
    args = parser.parse_args()
    summary = build_summary()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
