#!/usr/bin/env python3
"""Validate one shadow-only joint deployable prediction support domain."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.frames import RigidTransform
from traction_mpc_stage3.robot import UR10eTorqueRobot
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.cr12_plant import solve_cr12_stage5_ik
from traction_mpc_stage5.cr12_robot import CR12TorqueRobot
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.ik import solve_stage5_ik
from traction_mpc_stage5.prediction_support_domain import (
    CALIBRATION_DISTANCE_QUANTILE,
    PredictionSupportDomainV1,
    fit_prediction_support_domain_v1,
)

import audit_stage5_human_table_contact_role as contact_audit


ACCELERATION_ERROR_TARGET_DEG_S2 = np.asarray([30.0, 60.0])
FORCE_RMSE_TARGET_N = 5.0
FORCE_P95_TARGET_N = 10.0
ROUTE_SAMPLE_PERIOD_S = 0.020


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    return value


def _history_valid(row: dict[str, Any]) -> bool:
    """Frozen saved-case history rule; no truth or outcome is consulted."""

    feature = np.asarray(row["feature"], dtype=float)
    return bool(row["timestamp_s"] >= 0.010 and np.all(np.isfinite(feature)))


def _fit(source: dict[str, Any]) -> PredictionSupportDomainV1:
    rows = source["evaluated_cases"]
    development = [row for row in rows if row["split"] == "train"]
    calibration = [row for row in rows if row["split"] == "calibration"]
    feature_names = tuple(source["model"]["feature_names"])
    return fit_prediction_support_domain_v1(
        feature_names=feature_names,
        development_features=np.asarray([row["feature"] for row in development]),
        calibration_features=np.asarray([row["feature"] for row in calibration]),
        development_group_ids=tuple(
            sorted({str(row["group_id"]) for row in development})
        ),
        calibration_group_ids=tuple(
            sorted({str(row["group_id"]) for row in calibration})
        ),
        calibration_distance_quantile=CALIBRATION_DISTANCE_QUANTILE,
    )


def _label_rows(rows: list[dict[str, Any]], domain: PredictionSupportDomainV1) -> None:
    for row in rows:
        row["support_decision"] = domain.evaluate(
            np.asarray(row["feature"], dtype=float),
            causal_history_valid=_history_valid(row),
        ).record()


def _error_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "candidate_count": 0,
            "acceleration_absolute_error_p95_deg_s2": None,
            "acceleration_absolute_error_max_deg_s2": None,
            "cuff_force_vector_rmse_n": None,
            "cuff_force_error_p95_n": None,
            "cuff_force_error_max_n": None,
        }
    acceleration = np.asarray(
        [np.asarray(row["base"]["acceleration_error_deg_s2"])[-1] for row in rows]
    )
    force_vectors = np.vstack(
        [np.asarray(row["base"]["force_error_world_n"]) for row in rows]
    )
    force_norm = np.linalg.norm(force_vectors, axis=1)
    return {
        "candidate_count": len(rows),
        "acceleration_absolute_error_p95_deg_s2": np.percentile(
            np.abs(acceleration), 95.0, axis=0
        ),
        "acceleration_absolute_error_max_deg_s2": np.max(
            np.abs(acceleration), axis=0
        ),
        "cuff_force_vector_rmse_n": float(
            np.sqrt(np.mean(np.sum(np.square(force_vectors), axis=1)))
        ),
        "cuff_force_error_p95_n": float(np.percentile(force_norm, 95.0)),
        "cuff_force_error_max_n": float(np.max(force_norm)),
    }


def _group_candidate_counts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = sorted({str(row["group_id"]) for row in rows})
    result = []
    for group in groups:
        members = [row for row in rows if row["group_id"] == group]
        result.append(
            {
                "group_id": group,
                "robot": members[0]["robot"],
                "region": members[0]["region"],
                "timestamp_s": members[0]["timestamp_s"],
                "candidate_count": len(members),
                "supported_candidate_count": sum(
                    row["support_decision"]["supported"] for row in members
                ),
                "unsupported_reason_counts": dict(
                    Counter(
                        reason
                        for row in members
                        for reason in row["support_decision"]["reasons"]
                    )
                ),
            }
        )
    return result


def _evaluate_cases(
    rows: list[dict[str, Any]], domain: PredictionSupportDomainV1
) -> dict[str, Any]:
    _label_rows(rows, domain)
    supported = [row for row in rows if row["support_decision"]["supported"]]
    unsupported = [row for row in rows if not row["support_decision"]["supported"]]
    violating = [row for row in rows if row["truth_violating"]]
    benign = [row for row in rows if row["truth_benign"]]
    false_accept = [
        row
        for row in rows
        if row["base"]["predicted_accepted"] and row["truth_violating"]
    ]
    group_counts = _group_candidate_counts(rows)
    reason_counts = Counter(
        reason
        for row in unsupported
        for reason in row["support_decision"]["reasons"]
    )
    return {
        "all": _error_metrics(rows),
        "supported": _error_metrics(supported),
        "unsupported": _error_metrics(unsupported),
        "supported_candidate_fraction": len(supported) / len(rows),
        "truth_violating_candidate_count": len(violating),
        "truth_violating_unsupported_count": sum(
            not row["support_decision"]["supported"] for row in violating
        ),
        "truth_violating_unsupported_fraction": (
            None
            if not violating
            else sum(not row["support_decision"]["supported"] for row in violating)
            / len(violating)
        ),
        "benign_candidate_count": len(benign),
        "benign_supported_count": sum(
            row["support_decision"]["supported"] for row in benign
        ),
        "benign_supported_fraction": (
            None
            if not benign
            else sum(row["support_decision"]["supported"] for row in benign)
            / len(benign)
        ),
        "base_false_accept_count": len(false_accept),
        "base_false_accept_unsupported_count": sum(
            not row["support_decision"]["supported"] for row in false_accept
        ),
        "base_false_accept_unsupported_fraction": (
            None
            if not false_accept
            else sum(
                not row["support_decision"]["supported"] for row in false_accept
            )
            / len(false_accept)
        ),
        "supported_candidates_per_solve": group_counts,
        "minimum_supported_candidates_per_solve": min(
            item["supported_candidate_count"] for item in group_counts
        ),
        "median_supported_candidates_per_solve": float(
            np.median([item["supported_candidate_count"] for item in group_counts])
        ),
        "solve_count_with_zero_supported_candidates": sum(
            item["supported_candidate_count"] == 0 for item in group_counts
        ),
        "unsupported_reason_counts": dict(reason_counts),
        "candidate_labels": [
            {
                "case": f"{row['group_id']}::{row['candidate_name']}",
                "robot": row["robot"],
                "region": row["region"],
                "truth_violating": row["truth_violating"],
                "truth_benign": row["truth_benign"],
                "base_predicted_accepted": row["base"]["predicted_accepted"],
                **row["support_decision"],
            }
            for row in rows
        ],
    }


def _world_cuff_to_base_flange(position: np.ndarray, rotation: np.ndarray) -> RigidTransform:
    world_from_cuff = RigidTransform(rotation, position)
    world_from_flange = world_from_cuff.compose(
        STAGE5_GEOMETRY.end_effector_from_cuff.inverse()
    )
    return STAGE5_GEOMETRY.world_from_base.inverse().compose(world_from_flange)


def _feature_from_trace(
    trace: dict[str, np.ndarray],
    index: int,
    robot_q: np.ndarray,
    robot_dq: np.ndarray,
    robot: str,
    feature_names: tuple[str, ...],
) -> tuple[np.ndarray, bool]:
    previous_action = trace["executed_generalized_action_nm"][index - 1]
    older_action = trace["executed_generalized_action_nm"][index - 2]
    candidate_action = trace["executed_generalized_action_nm"][index]
    cuff_rotation = trace["deployable_robot_cuff_rotation_world"][index]
    blocks = {
        "robot_q": robot_q,
        "robot_dq": robot_dq,
        "human": trace["estimated_state_rad_rad_s"][index],
        "cuff_position": trace["deployable_robot_cuff_position_world_m"][index],
        "cuff_rotvec": Rotation.from_matrix(cuff_rotation).as_rotvec(),
        "cuff_linear_velocity": trace[
            "deployable_robot_cuff_linear_velocity_world_m_s"
        ][index],
        "cuff_angular_velocity": trace[
            "deployable_robot_cuff_angular_velocity_world_rad_s"
        ][index],
        "interface_displacement": trace[
            "estimated_interface_translation_human_m"
        ][index],
        "interface_velocity": trace[
            "estimated_interface_velocity_human_m_s"
        ][index],
        "interface_rotation": trace[
            "estimated_interface_rotation_human_rad"
        ][index],
        "interface_angular_velocity": trace[
            "estimated_interface_angular_velocity_human_rad_s"
        ][index],
        "measured_force": trace["deployable_measured_cuff_force_world_n"][index],
        "measured_moment": trace["deployable_measured_cuff_moment_world_nm"][index],
        "previous_action": previous_action,
        "previous_action_delta": previous_action - older_action,
        "shank_clearance": np.asarray(
            [
                contact_audit.shank_clearance_m(
                    trace["estimated_state_rad_rad_s"][index, :2]
                )
            ]
        ),
        "robot_identity_cr12": np.asarray([1.0 if robot == "cr12" else 0.0]),
        "candidate_action": candidate_action,
        "candidate_minus_previous": candidate_action - previous_action,
    }
    values: dict[str, float] = {}
    for prefix, block in blocks.items():
        for coordinate, value in enumerate(np.asarray(block, dtype=float)):
            values[f"{prefix}_{coordinate}"] = float(value)
    feature = np.asarray([values[name] for name in feature_names], dtype=float)
    history_valid = bool(
        index >= 2
        and np.all(np.isfinite(feature))
        and trace["task_observation_age_s"][index] <= 0.005 + 1.0e-12
    )
    return feature, history_valid


def _route_audit(
    robot: str,
    trace_path: Path,
    domain: PredictionSupportDomainV1,
) -> dict[str, Any]:
    trace = dict(np.load(trace_path, allow_pickle=True))
    time_s = trace["time_s"]
    stride = int(round(ROUTE_SAMPLE_PERIOD_S / 0.005))
    indices = list(range(max(2, stride), len(time_s), stride))
    for phase in ("OUTBOUND", "HOLD", "RETURN"):
        phase_indices = np.flatnonzero(trace["task_phase"] == phase)
        if len(phase_indices):
            indices.append(int(phase_indices[0]))
            indices.append(int(phase_indices[-1]))
    indices = sorted(set(index for index in indices if index >= 2))
    kinematic_robot: Any
    solver: Any
    if robot == "cr12":
        kinematic_robot = CR12TorqueRobot()
        solver = solve_cr12_stage5_ik
    else:
        kinematic_robot = UR10eTorqueRobot()
        solver = solve_stage5_ik
    route = []
    previous_q = None
    for index in indices:
        target = _world_cuff_to_base_flange(
            trace["deployable_robot_cuff_position_world_m"][index],
            trace["deployable_robot_cuff_rotation_world"][index],
        )
        robot_q = solver(kinematic_robot, target, previous_q_rad=previous_q)
        kinematic_robot.set_configuration(robot_q)
        cuff_jacobian = kinematic_robot.rigid_offset_jacobian(
            STAGE5_GEOMETRY.end_effector_from_cuff.translation
        )
        cuff_twist = np.concatenate(
            [
                trace["deployable_robot_cuff_linear_velocity_world_m_s"][index],
                trace["deployable_robot_cuff_angular_velocity_world_rad_s"][index],
            ]
        )
        robot_dq = np.linalg.lstsq(cuff_jacobian, cuff_twist, rcond=None)[0]
        feature, history_valid = _feature_from_trace(
            trace,
            index,
            robot_q,
            robot_dq,
            robot,
            domain.feature_names,
        )
        decision = domain.evaluate(
            feature, causal_history_valid=history_valid
        ).record()
        route.append(
            {
                "time_s": float(time_s[index]),
                "phase": str(trace["task_phase"][index]),
                "clearance_mm": float(
                    1000.0 * feature[domain.clearance_index]
                ),
                **decision,
            }
        )
        previous_q = robot_q
    phase_summary = {}
    for phase in ("OUTBOUND", "HOLD", "RETURN"):
        samples = [row for row in route if row["phase"] == phase]
        phase_summary[phase] = {
            "sample_count": len(samples),
            "supported_count": sum(row["supported"] for row in samples),
            "supported_fraction": (
                None if not samples else sum(row["supported"] for row in samples) / len(samples)
            ),
            "all_sampled_selected_commands_supported": bool(
                samples and all(row["supported"] for row in samples)
            ),
            "unsupported_reason_counts": dict(
                Counter(
                    reason
                    for row in samples
                    for reason in row["reasons"]
                )
            ),
        }
    observed_phases = [phase for phase, item in phase_summary.items() if item["sample_count"]]
    return {
        "robot": robot,
        "trace": str(trace_path.resolve()),
        "sampling_period_s": ROUTE_SAMPLE_PERIOD_S,
        "robot_state_source": (
            "offline IK/Jacobian reconstruction from deployable measured cuff pose/twist; "
            "online evaluator takes measured robot q/dq directly"
        ),
        "phase_summary": phase_summary,
        "continuous_supported_route_observed": bool(
            observed_phases == ["OUTBOUND", "HOLD", "RETURN"]
            and all(
                phase_summary[phase]["all_sampled_selected_commands_supported"]
                for phase in observed_phases
            )
        ),
        "samples": route,
    }


def _plot(output: Path, held: list[dict[str, Any]], counts: list[dict[str, Any]]) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.4))
    for supported, color, label in (
        (True, "#1b9e77", "SUPPORTED"),
        (False, "#d95f02", "UNSUPPORTED"),
    ):
        rows = [row for row in held if row["support_decision"]["supported"] == supported]
        if not rows:
            continue
        axes[0].scatter(
            [row["support_decision"]["joint_distance"] for row in rows],
            [abs(row["base"]["acceleration_error_deg_s2"][-1][1]) for row in rows],
            color=color,
            label=label,
            alpha=0.8,
        )
    axes[0].axvline(
        held[0]["support_decision"]["joint_distance_limit"],
        color="black",
        linestyle="--",
        linewidth=1.0,
    )
    axes[0].set_xlabel("joint deployable support distance")
    axes[0].set_ylabel("knee 20 ms absolute error [deg/s²]")
    axes[0].grid(alpha=0.25)
    axes[0].legend()

    labels = [f"{row['robot']}\n{row['timestamp_s']:.3f}" for row in counts]
    axes[1].bar(
        np.arange(len(counts)),
        [row["supported_candidate_count"] for row in counts],
        color="#377eb8",
    )
    axes[1].axhline(1.0, color="black", linestyle="--", linewidth=1.0)
    axes[1].set_xticks(np.arange(len(counts)), labels, rotation=30, ha="right")
    axes[1].set_ylabel("supported candidates per 5-candidate solve")
    axes[1].grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(output / "support_domain_heldout.png", dpi=180)
    plt.close(figure)


def run(output: Path, source_path: Path) -> dict[str, Any]:
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True, exist_ok=True)
    source = json.loads(source_path.read_text())
    rows = source["evaluated_cases"]
    domain = _fit(source)
    calibration_rows = [row for row in rows if row["split"] == "calibration"]
    held_rows = [row for row in rows if row["split"] == "held_out"]
    regression_rows = [row for row in rows if row["split"] == "historical_regression"]
    calibration = _evaluate_cases(calibration_rows, domain)
    held = _evaluate_cases(held_rows, domain)
    regression = _evaluate_cases(regression_rows, domain)

    held_supported = held["supported"]
    all_metrics = held["all"]
    accuracy_pass = bool(
        held_supported["candidate_count"] > 0
        and np.all(
            np.asarray(held_supported["acceleration_absolute_error_p95_deg_s2"])
            <= ACCELERATION_ERROR_TARGET_DEG_S2
        )
        and held_supported["cuff_force_vector_rmse_n"] <= FORCE_RMSE_TARGET_N
        and held_supported["cuff_force_error_p95_n"] <= FORCE_P95_TARGET_N
    )
    materially_improved = bool(
        held_supported["candidate_count"] > 0
        and np.all(
            np.asarray(held_supported["acceleration_absolute_error_p95_deg_s2"])
            < np.asarray(all_metrics["acceleration_absolute_error_p95_deg_s2"])
        )
        and held_supported["cuff_force_vector_rmse_n"]
        < all_metrics["cuff_force_vector_rmse_n"]
    )

    ur_route = _route_audit(
        "ur10e",
        STAGE5_ROOT
        / "results/trust_gamma_matched_v1_formal_attempt_01/fixed_pacing/repetition_01/trace.npz",
        domain,
    )
    cr_route = _route_audit(
        "cr12",
        STAGE5_ROOT
        / "results/cr12_split_authority_baseline_attempt_03/execution/trace.npz",
        domain,
    )
    task_compatible = bool(
        ur_route["continuous_supported_route_observed"]
        and held["solve_count_with_zero_supported_candidates"] == 0
    )
    critical_excluded = bool(
        regression["base_false_accept_count"] > 0
        and regression["base_false_accept_count"]
        == regression["base_false_accept_unsupported_count"]
    )
    if accuracy_pass and critical_excluded and task_compatible:
        decision = "SD-A — SUPPORT DOMAIN IS RELIABLE AND TASK-COMPATIBLE"
        next_step = (
            "design a controlled domain-constrained CR12 validation; do not run it automatically"
        )
    elif materially_improved and critical_excluded:
        decision = "SD-B — SUPPORT DOMAIN IMPROVES RELIABILITY BUT IS TOO RESTRICTIVE"
        next_step = (
            "the remaining structural problem is missing phase-spanning support and overlapping "
            "predictor error inside benign non-contact regions; do not add another predictor automatically"
        )
    else:
        decision = "SD-C — SUPPORT DOMAIN DOES NOT SEPARATE RELIABLE FROM UNRELIABLE PREDICTIONS"
        next_step = (
            "the remaining structural problem is prediction error overlapping the deployable nominal "
            "state/context manifold; do not add another predictor automatically"
        )

    result = {
        "schema": "stage5_shadow_prediction_support_domain_v1",
        "evidence_category": "bounded_shadow_saved_evidence_validation",
        "decision": decision,
        "support_domain": domain.record(),
        "data_split": {
            "source": str(source_path.resolve()),
            "development_group_ids": list(domain.development_group_ids),
            "calibration_group_ids": list(domain.calibration_group_ids),
            "held_out_group_ids": sorted(
                {str(row["group_id"]) for row in held_rows}
            ),
            "neighboring_window_leakage": False,
            "truth_used_to_fit_support": False,
        },
        "calibration": calibration,
        "held_out": held,
        "historical_regression": regression,
        "criteria": {
            "supported_prediction_accuracy": {
                "targets": {
                    "acceleration_p95_deg_s2": ACCELERATION_ERROR_TARGET_DEG_S2,
                    "force_rmse_n": FORCE_RMSE_TARGET_N,
                    "force_p95_n": FORCE_P95_TARGET_N,
                },
                "observed": held_supported,
                "status": "PASS" if accuracy_pass else "FAIL",
            },
            "material_improvement_inside_support": {
                "status": "PASS" if materially_improved else "FAIL"
            },
            "critical_historical_false_accept_exclusion": {
                "false_accept_count": regression["base_false_accept_count"],
                "unsupported_count": regression[
                    "base_false_accept_unsupported_count"
                ],
                "status": "PASS" if critical_excluded else "FAIL",
            },
            "task_route_compatibility": {
                "continuous_ur10e_route": ur_route[
                    "continuous_supported_route_observed"
                ],
                "held_out_zero_supported_solve_count": held[
                    "solve_count_with_zero_supported_candidates"
                ],
                "status": "PASS" if task_compatible else "FAIL",
            },
        },
        "continuous_route_audit": {"ur10e": ur_route, "cr12": cr_route},
        "key_answers": {
            "restriction_materially_improves_reliability": materially_improved,
            "supported_subset_meets_existing_engineering_accuracy_targets": accuracy_pass,
            "critical_cr12_false_accepts_all_outside_support": critical_excluded,
            "all_heldout_solves_retain_a_supported_candidate": held[
                "solve_count_with_zero_supported_candidates"
            ]
            == 0,
            "continuous_supported_outbound_hold_return_route_observed": ur_route[
                "continuous_supported_route_observed"
            ],
            "registered_task_contact_free_but_support_domain_complete": False,
        },
        "remaining_structural_problem": (
            "the development/calibration set covers only early OUTBOUND and current model error "
            "overlaps benign non-contact states; geometric avoidability does not create a validated "
            "predictor-supported HOLD/RETURN manifold"
        ),
        "one_next_step": next_step,
        "scope_invariants": {
            "shadow_only": True,
            "activated_in_mpc": False,
            "controller_or_abort_decision_changed": False,
            "mujoco_truth_online_input": False,
            "observed_4p97mm_clearance_used_as_threshold": False,
            "controller_parameters_changed": False,
            "thresholds_changed": False,
            "task_or_contact_model_changed": False,
            "rl_or_value_changed": False,
            "stage3_or_stage4_changed": False,
            "new_rollout_executed": False,
        },
    }
    _plot(output, held_rows, held["supported_candidates_per_solve"])
    (output / "prediction_support_domain.json").write_text(
        json.dumps(_jsonable(result), indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    (output / "support_domain_model.json").write_text(
        json.dumps(_jsonable(domain.record()), indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/engineering_validation/short_horizon_residual_v1_attempt_01/residual_validation.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results/engineering_validation/prediction_support_domain_v1_attempt_01"
        ),
    )
    args = parser.parse_args()
    result = run(args.output_dir, args.source)
    print(
        json.dumps(
            _jsonable(
                {
                    "decision": result["decision"],
                    "criteria": result["criteria"],
                    "key_answers": result["key_answers"],
                    "held_out": result["held_out"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
