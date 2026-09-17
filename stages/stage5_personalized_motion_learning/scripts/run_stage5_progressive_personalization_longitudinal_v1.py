#!/usr/bin/env python3
"""Run the preregistered five-repetition Stage-5 progressive A/B session."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE
from traction_mpc_stage5.progressive_personalization import (
    FROZEN_THETA_1,
    LONGITUDINAL_CEM_SEEDS,
    ProgressiveLongitudinalArm,
    ProgressiveLongitudinalSession,
    deployable_prediction_summary,
    fixed_progress_pacing_status,
    parameter_direction_diagnostics,
)


CONFIG_PATH = (
    STAGE5_ROOT
    / "configs"
    / "stage5_progressive_personalization_longitudinal_v1.json"
)


def _load_config() -> dict[str, Any]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_progressive_personalization_longitudinal_v1":
        raise ValueError("unexpected longitudinal progressive config schema")
    if payload.get("status") != "PREREGISTERED_BEFORE_NEW_OUTCOMES":
        raise ValueError("longitudinal progressive study must remain preregistered")
    repetitions = payload["repetitions"]
    if repetitions["maximum_per_arm"] != 5:
        raise ValueError("longitudinal study is frozen at five repetitions per arm")
    if tuple(repetitions["matched_cem_seeds"]) != LONGITUDINAL_CEM_SEEDS:
        raise ValueError("preregistered longitudinal seed schedule changed")
    if not repetitions["same_seed_for_both_arms_at_each_repetition"]:
        raise ValueError("longitudinal A/B requires matched per-repetition seeds")
    if not np.allclose(
        payload["initial_active_model"]["scales"],
        FROZEN_THETA_1,
        atol=0.0,
        rtol=0.0,
    ):
        raise ValueError("frozen theta_1 changed")
    controller = payload["controller"]
    if controller["gamma"] != 0.5 or controller["gamma_dynamic"]:
        raise ValueError("longitudinal study requires fixed gamma=0.5")
    identifier = payload["human_identification"]
    if (
        identifier["parameterization"] != ["alpha_M", "alpha_K", "alpha_D"]
        or identifier["lower_scales"] != [0.5, 0.5, 0.5]
        or identifier["upper_scales"] != [1.5, 1.5, 1.5]
        or identifier["smoothing_alpha"] != 0.1
        or identifier["maximum_step_fraction_of_span"] != 0.03
        or identifier["regularization_weight"] != 1.0e-3
    ):
        raise ValueError("frozen reduced Human-ID contract changed")
    return payload


def _geometry() -> PlanarCuffGeometry:
    rotation = STAGE5_GEOMETRY.world_from_human.rotation
    return PlanarCuffGeometry(
        origin_world_m=STAGE5_GEOMETRY.world_from_human.translation.copy(),
        plane_x_world=rotation[:, 0].copy(),
        joint_axis_world=rotation[:, 1].copy(),
        plane_z_world=rotation[:, 2].copy(),
        hip_plane_m=np.zeros(2),
        thigh_length_m=STAGE5_HUMAN.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([STAGE5_HUMAN.sleeve_center_m, 0.0]),
    )


def _truth_human():
    return replace(
        STAGE5_HUMAN,
        passive_damping_nms_rad=tuple(
            1.2 * np.asarray(STAGE5_HUMAN.passive_damping_nms_rad, dtype=float)
        ),
    )


def _control_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_status": summary["task_status"],
        "abort_reason": summary["abort_reason"],
        "task_duration_s": summary["task_duration_s"],
        "phase_transitions": summary["phase_transitions"],
        "estimated_terminal_error_deg": summary["estimated_terminal_error_deg"],
        "estimated_terminal_dq_deg_s": summary["estimated_terminal_dq_deg_s"],
        "peak_abs_estimated_joint_velocity_deg_s": summary[
            "peak_abs_estimated_joint_velocity_deg_s"
        ],
        "peak_abs_evaluation_only_joint_velocity_deg_s": summary[
            "peak_abs_evaluation_only_joint_velocity_deg_s"
        ],
        "peak_abs_deployable_acceleration_deg_s2": summary[
            "peak_abs_estimated_joint_acceleration_deg_s2"
        ],
        "peak_abs_evaluation_only_acceleration_deg_s2": summary[
            "peak_abs_evaluation_only_joint_acceleration_deg_s2"
        ],
        "motion_envelope": summary["motion_envelope"],
        "peak_physical_cuff_force_n": summary["peak_physical_cuff_force_n"],
        "cumulative_physical_cuff_force_n_s": summary[
            "cumulative_physical_cuff_force_n_s"
        ],
        "peak_physical_cuff_moment_nm": summary[
            "peak_physical_cuff_moment_nm"
        ],
        "physical_force_prediction_error": summary[
            "physical_force_prediction_error"
        ],
        "human_state_estimation_error": summary["human_state_estimation_error"],
        "mpc_status_counts": summary["mpc_status_counts"],
        "mpc_failure_count": summary["mpc_failure_count"],
        "safety_filter_status_counts": summary["safety_filter_status_counts"],
        "maximum_safety_filter_intervention_coordinate_norm": summary[
            "maximum_safety_filter_intervention_coordinate_norm"
        ],
        "brake_event_count": summary["brake_event_count"],
        "force_gate_event_count": summary["force_gate_event_count"],
        "structural_event_count": summary["structural_event_count"],
        "mujoco_warning_counts": summary["mujoco_warning_counts"],
        "mpc_runtime_ms": summary["mpc_runtime_ms"],
        "path_freedom": {
            "maximum_normalized_q1_q2_progress_difference": summary[
                "maximum_normalized_q1_q2_progress_difference"
            ],
            "interpretation": summary["path_freedom_interpretation"],
        },
    }


def _episode_regression(
    fixed: dict[str, Any], progressive: dict[str, Any]
) -> list[str]:
    a = fixed["control"]
    b = progressive["control"]
    reasons: list[str] = []
    if a["task_status"] == "COMPLETE" and b["task_status"] != "COMPLETE":
        reasons.append("progressive_aborted_while_fixed_completed")
    if b["mpc_failure_count"] > a["mpc_failure_count"]:
        reasons.append("more_no_safe_action_events")
    if b["force_gate_event_count"] > a["force_gate_event_count"]:
        reasons.append("more_force_gate_events")
    if b["brake_event_count"] > a["brake_event_count"]:
        reasons.append("more_brake_events")
    if (
        a["motion_envelope"]["deployable_realized_acceleration_satisfied"]
        and not b["motion_envelope"]["deployable_realized_acceleration_satisfied"]
    ):
        reasons.append("deployable_acceleration_envelope_regression")
    if (
        a["motion_envelope"]["evaluation_only_acceleration_satisfied"]
        and not b["motion_envelope"]["evaluation_only_acceleration_satisfied"]
    ):
        reasons.append("evaluation_acceleration_envelope_regression")
    if b["mujoco_warning_counts"]:
        reasons.append("mujoco_warning")
    return reasons


def _run_repetition(
    *,
    output_dir: Path,
    config: dict[str, Any],
    session: ProgressiveLongitudinalSession,
    repetition: int,
    seed: int,
    session_time_s: float,
    prefix_backend: str = "numpy",
) -> dict[str, Any]:
    arm = session.arm
    attempts_before = len(session.authority.service.attempts)
    history_before = len(session.authority.history)
    blocked_before = len(session.blocked_qualified_proposals)
    boundary = session.begin_repetition(repetition, session_time_s)
    active_at_start = session.active_model
    human = _truth_human()

    def plant_factory(parameters):
        return Stage5SensorBoundaryPlant(human, interface_parameters=parameters)

    controller = config["controller"]
    episode_dir = output_dir / arm.value / f"repetition_{repetition:02d}"
    wall_start = perf_counter()
    summary = run_goal_mpc_smoke(
        episode_dir,
        maximum_duration_s=float(controller["maximum_duration_s"]),
        plant_interface_parameters=STAGE5_RIGID_INTERFACE,
        plant_case_name=f"progressive_personalization__{arm.value}__rep{repetition:02d}",
        record_selected_horizon_diagnostics=False,
        use_loaded_local_hold=True,
        use_bumpless_return_handoff=True,
        initialize_loaded_equilibrium_with_plant_truth=True,
        interface_uncertainty_spec=None,
        planning_physical_force_ceiling_n=float(
            controller["planning_physical_force_ceiling_n"]
        ),
        planning_joint_velocity_ceiling_rad_s=tuple(
            np.radians(controller["base_planning_joint_velocity_ceiling_deg_s"])
        ),
        mpc_config=HumanMPCConfig(random_seed=seed),
        plant_factory=plant_factory,
        progress_pacing_callback=fixed_progress_pacing_status,
        control_human_model_callback=session.observe,
        initial_control_human_model=session.control_human_model,
        initial_control_human_model_version=active_at_start.model_id,
        prefix_backend=prefix_backend,
    )
    wall_time_s = perf_counter() - wall_start
    with np.load(episode_dir / "trace.npz") as loaded:
        trace = {key: loaded[key] for key in loaded.files}
    gamma = np.asarray(trace["progress_pacing_gamma"], dtype=float)
    versions = np.asarray(trace["control_human_model_version"], dtype=str)
    if not np.allclose(gamma, 0.5, atol=0.0, rtol=0.0):
        raise RuntimeError("longitudinal progressive gamma changed")
    if set(versions.tolist()) != {active_at_start.model_id}:
        raise RuntimeError("active Human model changed within a repetition")
    if summary["human_model_control_transition"]["transition_count"] != 0:
        raise RuntimeError("Goal-MPC applied an in-repetition Human-model transition")
    finalized = session.finalize_repetition()
    attempts = session.authority.service.attempts[attempts_before:]
    active_prediction = deployable_prediction_summary(trace, active_at_start.theta)
    theta_1_prediction = deployable_prediction_summary(trace, FROZEN_THETA_1)
    return {
        "arm": arm.value,
        "repetition": repetition,
        "cem_seed": seed,
        "session_start_time_s": session_time_s,
        "boundary": {
            "active_model_id": boundary.active_model_id,
            "active_theta": list(boundary.active_theta),
            "activation": boundary.activation,
        },
        "active_model_fixed_within_repetition": True,
        "active_model_id": active_at_start.model_id,
        "active_theta": list(active_at_start.theta),
        "active_post_update_support_at_start": (
            active_at_start.post_update_support.value
        ),
        "authority_end": finalized,
        "new_authority_events": session.authority.history[history_before:],
        "new_blocked_qualified_proposals": session.blocked_qualified_proposals[
            blocked_before:
        ],
        "human_identification": {
            "new_attempts": attempts,
            "new_attempt_status_counts": dict(
                Counter(str(item["status"]) for item in attempts)
            ),
            "session_measurement_count": len(
                session.authority.service.raw_history
            ),
            "rejected_measurement_count": (
                session.authority.service.rejected_measurements
            ),
            "truth_available_to_service": False,
        },
        "prediction": {
            "active_model": active_prediction,
            "fixed_theta_1_reference_on_same_deployable_trace": theta_1_prediction,
        },
        "gamma": {
            "minimum": float(np.min(gamma)),
            "maximum": float(np.max(gamma)),
            "final": float(gamma[-1]),
            "fixed": True,
        },
        "control": _control_metrics(summary),
        "wall_time_s": wall_time_s,
        "artifacts": {
            "summary": str((episode_dir / "summary.json").relative_to(output_dir)),
            "trace": str((episode_dir / "trace.npz").relative_to(output_dir)),
        },
    }


def _parameter_evolution(session: ProgressiveLongitudinalSession) -> dict[str, Any]:
    models = sorted(
        session.authority.lineage.values(), key=lambda item: item.update_index
    )
    rows = []
    deltas = []
    for model in models:
        delta = np.asarray(model.bounded_transition_delta, dtype=float)
        if model.activation_repetition > 1:
            deltas.append(delta)
        rows.append(
            {
                "model_id": model.model_id,
                "update_index": model.update_index,
                "theta": list(model.theta),
                "predecessor_model_id": model.predecessor_model_id,
                "activation_repetition": model.activation_repetition,
                "activation_time_s": model.activation_time_s,
                "post_update_support": model.post_update_support.value,
                "bounded_transition_delta": list(model.bounded_transition_delta),
                "update_norm": float(np.linalg.norm(delta)),
            }
        )
    direction = parameter_direction_diagnostics(deltas)
    final_theta = np.asarray(session.active_model.theta, dtype=float)
    return {
        "models": rows,
        "active_transition_count_beyond_theta_1": int(len(models) - 1),
        "parameter_direction_reversal": {
            "alpha_M": direction["reversal_count"]["alpha_M"] > 0,
            "alpha_K": direction["reversal_count"]["alpha_K"] > 0,
            "alpha_D": direction["reversal_count"]["alpha_D"] > 0,
        },
        "parameter_direction_reversal_count": direction["reversal_count"],
        "parameter_direction_oscillation": direction["oscillatory"],
        "oscillation_semantics": (
            "at least two sign reversals in one bounded-update component; one "
            "change followed by a stable direction is reported as a reversal "
            "but not mislabeled as oscillation"
        ),
        "alpha_D_consistent_direction": (
            direction["reversal_count"]["alpha_D"] == 0
        ),
        "final_distance_to_evaluation_only_truth": float(
            np.linalg.norm(final_theta - np.array([1.0, 1.0, 1.2]))
        ),
        "truth_distance_used_for_online_decisions": False,
    }


def _decision(
    rows_by_arm: dict[str, list[dict[str, Any]]],
    parameter_evolution: dict[str, Any],
    authority_consistent: bool,
) -> dict[str, Any]:
    fixed = rows_by_arm[ProgressiveLongitudinalArm.FIXED_THETA_1.value]
    progressive = rows_by_arm[ProgressiveLongitudinalArm.PROGRESSIVE.value]
    paired_regressions = [
        _episode_regression(a, b) for a, b in zip(fixed, progressive, strict=True)
    ]
    any_regression = any(paired_regressions)
    negative = any(
        model["post_update_support"] == "negative"
        for model in parameter_evolution["models"]
    )
    oscillation = any(
        parameter_evolution["parameter_direction_oscillation"].values()
    )
    transitions = parameter_evolution["active_transition_count_beyond_theta_1"]
    supported_transition_predecessors = all(
        model["post_update_support"] == "positive"
        for model in parameter_evolution["models"][1:-1]
    )
    active_losses = [
        row["prediction"]["active_model"]["ALL_PHASES"].get(
            "mean_squared_loss_nms2"
        )
        for row in progressive
    ]
    theta_1_losses = [
        row["prediction"]["fixed_theta_1_reference_on_same_deployable_trace"][
            "ALL_PHASES"
        ].get("mean_squared_loss_nms2")
        for row in progressive
    ]
    prediction_nonworse_after_updates = all(
        active is not None
        and reference is not None
        and active <= reference + 1.0e-12
        for row, active, reference in zip(
            progressive, active_losses, theta_1_losses, strict=True
        )
        if row["boundary"]["activation"] is not None
    )
    if (
        transitions >= 2
        and supported_transition_predecessors
        and not oscillation
        and prediction_nonworse_after_updates
        and not any_regression
        and authority_consistent
        and not negative
    ):
        code = "PP2-A"
        label = "PROGRESSIVE PERSONALIZATION FEASIBLE"
        reason = (
            "at least two causally supported boundary corrections occurred with "
            "stable model evolution, deployable prediction improvement, and no "
            "matched closed-loop regression"
        )
    elif (
        transitions == 1
        and not any_regression
        and authority_consistent
        and not negative
    ):
        code = "PP2-B"
        label = "PROGRESSIVE LOOP WORKS, BUT EVIDENCE/ADAPTATION IS TOO SLOW"
        reason = (
            "the authority loop applied at least one correction without a matched "
            "closed-loop regression, but fewer than two further supported "
            "corrections occurred within five repetitions"
        )
    else:
        code = "PP2-C"
        label = "PROGRESSIVE PERSONALIZATION NOT SUPPORTED"
        reason = (
            "negative evidence, parameter reversal, closed-loop degradation, or "
            "authority inconsistency was observed"
        )
    return {
        "code": code,
        "label": label,
        "reason": reason,
        "paired_closed_loop_regression_reasons": paired_regressions,
        "prediction_nonworse_than_theta_1_after_each_activation": (
            prediction_nonworse_after_updates
        ),
        "authority_consistent": authority_consistent,
    }


def _plot_theta(output_dir: Path, evolution: dict[str, Any]) -> None:
    models = evolution["models"]
    repetitions = [item["activation_repetition"] for item in models]
    theta = np.asarray([item["theta"] for item in models], dtype=float)
    fig, axis = plt.subplots(figsize=(7.2, 4.2))
    labels = ("alpha_M", "alpha_K", "alpha_D")
    for index, label in enumerate(labels):
        axis.plot(repetitions, theta[:, index], marker="o", label=label)
    axis.axhline(1.2, color="tab:red", linestyle=":", label="truth alpha_D (evaluation only)")
    axis.set_xlabel("activation repetition")
    axis.set_ylabel("scale")
    axis.set_xticks(range(1, 6))
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "progressive_theta_evolution.png", dpi=170)
    plt.close(fig)


def _strict_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _strict_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return _strict_jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _strict_jsonable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            STAGE5_ROOT
            / "results"
            / "progressive_personalization_longitudinal_v1_attempt_01"
        ),
    )
    parser.add_argument(
        "--reanalyze-existing",
        action="store_true",
        help="recompute derived parameter/decision fields without rerunning episodes",
    )
    arguments = parser.parse_args()
    output_dir = arguments.output_dir
    if arguments.reanalyze_existing:
        result_path = output_dir / "progressive_personalization_results.json"
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        evolution = payload["progressive_parameter_evolution"]
        deltas = [
            np.asarray(item["bounded_transition_delta"], dtype=float)
            for item in evolution["models"][1:]
        ]
        direction = parameter_direction_diagnostics(deltas)
        evolution["parameter_direction_reversal"] = {
            name: count > 0
            for name, count in direction["reversal_count"].items()
        }
        evolution["parameter_direction_reversal_count"] = direction[
            "reversal_count"
        ]
        evolution["parameter_direction_oscillation"] = direction["oscillatory"]
        evolution["oscillation_semantics"] = (
            "at least two sign reversals in one bounded-update component; one "
            "change followed by a stable direction is reported as a reversal "
            "but not mislabeled as oscillation"
        )
        evolution["alpha_D_consistent_direction"] = (
            direction["reversal_count"]["alpha_D"] == 0
        )
        payload["decision"] = _decision(
            payload["arms"], evolution, authority_consistent=True
        )
        payload["post_run_analysis_correction"] = {
            "episodes_rerun": False,
            "raw_metrics_changed": False,
            "issue": (
                "the first analysis pass conflated one component-direction "
                "reversal with oscillation and could emit PP2-B even when four "
                "supported corrections occurred"
            ),
            "correction": (
                "report all sign reversals, classify oscillation only after at "
                "least two reversals, and restrict PP2-B to exactly one applied "
                "correction as required by the preregistered decision wording"
            ),
        }
        payload = _strict_jsonable(payload)
        result_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        _plot_theta(output_dir, evolution)
        print(json.dumps(payload["decision"], indent=2, sort_keys=True))
        return
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    config = _load_config()
    geometry = _geometry()
    sessions = {
        arm.value: ProgressiveLongitudinalSession(
            geometry,
            arm,
            session_id=f"pp2-{arm.value}",
        )
        for arm in ProgressiveLongitudinalArm
    }
    rows_by_arm = {arm.value: [] for arm in ProgressiveLongitudinalArm}
    session_times = {arm.value: 0.0 for arm in ProgressiveLongitudinalArm}
    reset_gap = float(
        config["repetitions"]["physical_reset_gap_in_session_time_s"]
    )
    wall_start = perf_counter()
    authority_consistent = True

    for repetition, seed in enumerate(LONGITUDINAL_CEM_SEEDS, start=1):
        for arm in ProgressiveLongitudinalArm:
            session = sessions[arm.value]
            row = _run_repetition(
                output_dir=output_dir,
                config=config,
                session=session,
                repetition=repetition,
                seed=seed,
                session_time_s=session_times[arm.value],
            )
            rows_by_arm[arm.value].append(row)
            session_times[arm.value] += (
                float(row["control"]["task_duration_s"]) + reset_gap
            )
            if arm is ProgressiveLongitudinalArm.FIXED_THETA_1 and not np.allclose(
                row["active_theta"], FROZEN_THETA_1, atol=0.0, rtol=0.0
            ):
                authority_consistent = False
            print(
                json.dumps(
                    {
                        "arm": arm.value,
                        "repetition": repetition,
                        "status": row["control"]["task_status"],
                        "active_theta": row["active_theta"],
                        "post_update_support": row["authority_end"][
                            "post_update_support"
                        ],
                        "queued": row["authority_end"]["queued_update"] is not None,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    progressive_evolution = _parameter_evolution(
        sessions[ProgressiveLongitudinalArm.PROGRESSIVE.value]
    )
    decision = _decision(rows_by_arm, progressive_evolution, authority_consistent)
    comparisons = []
    for fixed, progressive in zip(
        rows_by_arm[ProgressiveLongitudinalArm.FIXED_THETA_1.value],
        rows_by_arm[ProgressiveLongitudinalArm.PROGRESSIVE.value],
        strict=True,
    ):
        comparisons.append(
            {
                "repetition": fixed["repetition"],
                "seed": fixed["cem_seed"],
                "fixed_status": fixed["control"]["task_status"],
                "progressive_status": progressive["control"]["task_status"],
                "fixed_duration_s": fixed["control"]["task_duration_s"],
                "progressive_duration_s": progressive["control"]["task_duration_s"],
                "fixed_prediction_loss_nms2": fixed["prediction"]["active_model"][
                    "ALL_PHASES"
                ].get("mean_squared_loss_nms2"),
                "progressive_prediction_loss_nms2": progressive["prediction"][
                    "active_model"
                ]["ALL_PHASES"].get("mean_squared_loss_nms2"),
                "progressive_minus_fixed_force_integral_n_s": (
                    progressive["control"]["cumulative_physical_cuff_force_n_s"]
                    - fixed["control"]["cumulative_physical_cuff_force_n_s"]
                ),
                "closed_loop_regression_reasons": _episode_regression(
                    fixed, progressive
                ),
            }
        )
    payload = {
        "schema": "stage5_progressive_personalization_longitudinal_v1_results",
        "evidence_category": config["evidence_category"],
        "config_path": str(CONFIG_PATH.relative_to(STAGE5_ROOT)),
        "preregistered_seed_schedule": list(LONGITUDINAL_CEM_SEEDS),
        "same_seed_for_both_arms_per_repetition": True,
        "truth_condition_evaluation_only": [1.0, 1.0, 1.2],
        "truth_available_to_online_authority": False,
        "gamma_fixed": 0.5,
        "acceleration_monitor_changed": False,
        "interface_identification_active": False,
        "value_or_rl_learning_active": False,
        "arms": rows_by_arm,
        "arm_authority_summaries": {
            name: session.authority.summary() for name, session in sessions.items()
        },
        "blocked_qualified_proposals": {
            name: session.blocked_qualified_proposals
            for name, session in sessions.items()
        },
        "progressive_parameter_evolution": progressive_evolution,
        "fixed_vs_progressive_comparison": comparisons,
        "decision": decision,
        "total_wall_time_s": perf_counter() - wall_start,
    }
    payload = _strict_jsonable(payload)
    (output_dir / "progressive_personalization_results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _plot_theta(output_dir, progressive_evolution)
    print(json.dumps(decision, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
