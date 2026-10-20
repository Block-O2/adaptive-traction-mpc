#!/usr/bin/env python3
"""Run the formal matched Stage-5 supported-model trust-to-gamma A/B."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.confidence_pacing import Stage5PacingEvidence
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE
from traction_mpc_stage5.trust_gamma_matched import (
    TRUST_GAMMA_ARMS,
    TRUST_GAMMA_CEM_SEEDS,
    build_control_human_model,
    extract_supported_model,
    initialize_supported_trust,
    load_trust_gamma_contract,
    source_artifact_path,
)


DEFAULT_OUTPUT = (
    STAGE5_ROOT / "results" / "trust_gamma_matched_v1_formal_attempt_01"
)


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


def _first_time(records: list[dict[str, Any]], predicate) -> float | None:
    for record in records:
        if predicate(record):
            return float(record["session_time_s"])
    return None


def _episode_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    hold = summary["loaded_local_hold"]
    return {
        "task_status": summary["task_status"],
        "abort_reason": summary["abort_reason"],
        "task_duration_s": float(summary["task_duration_s"]),
        "phase_transitions": summary["phase_transitions"],
        "estimated_terminal_error_deg": summary["estimated_terminal_error_deg"],
        "estimated_terminal_dq_deg_s": summary["estimated_terminal_dq_deg_s"],
        "hold": {
            "longest_continuous_goal_set_interval_s": hold[
                "longest_continuous_goal_set_interval_s"
            ],
            "return_entry_observed": hold["return_entry_observed"],
            "terminal_q_error_deg": hold["terminal_q_error_deg"],
            "terminal_dq_deg_s": hold["terminal_dq_deg_s"],
        },
        "peak_physical_cuff_force_n": summary["peak_physical_cuff_force_n"],
        "cumulative_physical_cuff_force_n_s": summary[
            "cumulative_physical_cuff_force_n_s"
        ],
        "peak_physical_cuff_moment_nm": summary["peak_physical_cuff_moment_nm"],
        "peak_abs_deployable_acceleration_deg_s2": summary[
            "peak_abs_estimated_joint_acceleration_deg_s2"
        ],
        "peak_abs_truth_acceleration_deg_s2_evaluation_only": summary[
            "peak_abs_evaluation_only_joint_acceleration_deg_s2"
        ],
        "motion_envelope": summary["motion_envelope"],
        "mpc_status_counts": summary["mpc_status_counts"],
        "no_safe_action_count": int(summary["mpc_failure_count"]),
        "force_gate_event_count": int(summary["force_gate_event_count"]),
        "safety_filter_status_counts": summary["safety_filter_status_counts"],
        "maximum_safety_filter_intervention_coordinate_norm": summary[
            "maximum_safety_filter_intervention_coordinate_norm"
        ],
        "brake_event_count": int(summary["brake_event_count"]),
        "mujoco_warning_counts": summary["mujoco_warning_counts"],
        "mpc_runtime_ms": summary["mpc_runtime_ms"],
        "path_freedom": {
            "maximum_normalized_q1_q2_progress_difference": summary[
                "maximum_normalized_q1_q2_progress_difference"
            ],
            "interpretation": summary["path_freedom_interpretation"],
        },
    }


def _run_arm(
    *,
    arm: str,
    output_dir: Path,
    contract: dict[str, Any],
    frozen_model,
) -> dict[str, Any]:
    trust, pacing = initialize_supported_trust(frozen_model)
    geometry = _geometry()
    control_model = build_control_human_model(geometry, frozen_model)
    fixed = contract["fixed_conditions"]
    reset_gap_s = float(
        contract["repetitions"]["physical_reset_gap_in_session_time_s"]
    )
    base_ceiling = tuple(
        np.radians(fixed["base_planning_joint_velocity_ceiling_deg_s"])
    )
    session_offset_s = 0.0
    repetitions: list[dict[str, Any]] = []
    arm_started = perf_counter()

    for repetition, seed in enumerate(TRUST_GAMMA_CEM_SEEDS, start=1):
        timeline: list[dict[str, Any]] = []
        support_at_start = trust.status().copy()
        filter_at_start = pacing.status(session_offset_s).copy()

        def callback(payload: dict[str, Any]) -> dict[str, Any]:
            session_time_s = session_offset_s + float(payload["episode_time_s"])
            diagnostic = pacing.update(
                Stage5PacingEvidence(
                    session_time_s=session_time_s,
                    identification_informative=False,
                    information_rank=0,
                    information_condition_number=float("inf"),
                    current_nominal_model_adequate=trust.supported,
                    current_model_evidence_reason=str(
                        trust.status()["state_reason"]
                    ),
                    challenger_status="disabled_no_model_updates",
                    shadow_publication_count=0,
                )
            )["pacing"]
            if arm == "fixed_pacing":
                executed = {
                    "gamma": 0.5,
                    "gamma_target": 0.5,
                    "gamma_rate_per_s": 0.0,
                }
            else:
                executed = diagnostic
            timeline.append(
                {
                    "session_time_s": session_time_s,
                    "episode_time_s": float(payload["episode_time_s"]),
                    "support_state": trust.status()["support_state"],
                    "support_evidence_version": trust.status()[
                        "support_evidence_version"
                    ],
                    "filtered_confidence": float(
                        diagnostic["filtered_current_model_confidence"]
                    ),
                    "hysteresis_high": bool(
                        diagnostic["execution_confidence_high"]
                    ),
                    "executed_gamma_target": float(executed["gamma_target"]),
                    "actual_gamma": float(executed["gamma"]),
                    "actual_gamma_rate_per_s": float(
                        executed["gamma_rate_per_s"]
                    ),
                    "unapplied_trust_gamma_target": (
                        float(diagnostic["gamma_target"])
                        if arm == "fixed_pacing"
                        else None
                    ),
                }
            )
            return executed

        human = _truth_human()

        def plant_factory(parameters):
            return Stage5SensorBoundaryPlant(human, interface_parameters=parameters)

        episode_dir = output_dir / arm / f"repetition_{repetition:02d}"
        started = perf_counter()
        summary = run_goal_mpc_smoke(
            episode_dir,
            maximum_duration_s=float(fixed["maximum_duration_s"]),
            plant_interface_parameters=STAGE5_RIGID_INTERFACE,
            plant_case_name=f"trust_gamma_v1__{arm}__rep{repetition:02d}",
            record_selected_horizon_diagnostics=False,
            use_loaded_local_hold=True,
            use_bumpless_return_handoff=True,
            initialize_loaded_equilibrium_with_plant_truth=True,
            interface_uncertainty_spec=None,
            planning_physical_force_ceiling_n=float(
                fixed["planning_physical_force_ceiling_n"]
            ),
            planning_joint_velocity_ceiling_rad_s=base_ceiling,
            mpc_config=HumanMPCConfig(random_seed=int(seed)),
            plant_factory=plant_factory,
            progress_pacing_callback=callback,
            initial_control_human_model=control_model,
            initial_control_human_model_version=frozen_model.model_id,
            prefix_backend="native",
        )
        wall_time_s = perf_counter() - started
        with np.load(episode_dir / "trace.npz") as loaded:
            gamma_trace = np.asarray(
                loaded["progress_pacing_gamma"], dtype=float
            )
            versions = np.asarray(
                loaded["control_human_model_version"], dtype=str
            )
        if set(versions.tolist()) != {frozen_model.model_id}:
            raise RuntimeError("active Human model changed during trust-gamma run")
        if summary["human_model_control_transition"]["transition_count"] != 0:
            raise RuntimeError("a successor was activated during frozen-model A/B")
        if arm == "fixed_pacing" and not np.allclose(
            gamma_trace, 0.5, atol=0.0, rtol=0.0
        ):
            raise RuntimeError("fixed pacing arm gamma changed")
        first_above = _first_time(
            timeline, lambda item: item["actual_gamma"] > 0.5 + 1.0e-12
        )
        first_one = _first_time(
            timeline, lambda item: item["actual_gamma"] >= 1.0 - 1.0e-12
        )
        repetitions.append(
            {
                "repetition": repetition,
                "cem_seed": int(seed),
                "active_model_id": frozen_model.model_id,
                "active_theta": list(frozen_model.theta),
                "raw_support_at_start": support_at_start,
                "filter_at_start": filter_at_start,
                "raw_support_at_end": trust.status(),
                "final_filtered_confidence": float(
                    timeline[-1]["filtered_confidence"]
                ),
                "final_hysteresis_high": bool(timeline[-1]["hysteresis_high"]),
                "final_gamma_target": float(
                    timeline[-1]["executed_gamma_target"]
                ),
                "final_actual_gamma": float(timeline[-1]["actual_gamma"]),
                "minimum_actual_gamma": float(
                    min(item["actual_gamma"] for item in timeline)
                ),
                "maximum_actual_gamma": float(
                    max(item["actual_gamma"] for item in timeline)
                ),
                "first_gamma_above_0p5_session_time_s": first_above,
                "first_gamma_at_1p0_session_time_s": first_one,
                "timeline": timeline,
                "control": _episode_metrics(summary),
                "wall_time_s": wall_time_s,
                "artifacts": {
                    "summary": str(
                        (episode_dir / "summary.json").relative_to(output_dir)
                    ),
                    "trace": str((episode_dir / "trace.npz").relative_to(output_dir)),
                },
            }
        )
        session_offset_s += float(summary["task_duration_s"]) + reset_gap_s
        print(
            json.dumps(
                {
                    "arm": arm,
                    "repetition": repetition,
                    "seed": seed,
                    "task_status": summary["task_status"],
                    "duration_s": summary["task_duration_s"],
                    "gamma_max": repetitions[-1]["maximum_actual_gamma"],
                    "final_filtered_confidence": repetitions[-1][
                        "final_filtered_confidence"
                    ],
                },
                sort_keys=True,
            ),
            flush=True,
        )
    return {
        "arm": arm,
        "repetitions": repetitions,
        "final_trust": trust.summary(),
        "final_pacing": pacing.summary(session_offset_s - reset_gap_s),
        "total_wall_time_s": perf_counter() - arm_started,
        "human_model_updates_enabled": False,
        "successor_activation_count": 0,
        "truth_available_to_trust_or_pacing": False,
    }


def _new_constraint_regression(
    fixed: dict[str, Any], trust: dict[str, Any]
) -> list[str]:
    a = fixed["control"]
    b = trust["control"]
    reasons: list[str] = []
    if a["task_status"] == "COMPLETE" and b["task_status"] != "COMPLETE":
        reasons.append("trust_arm_aborted_while_fixed_completed")
    for key in (
        "deployable_realized_acceleration_satisfied",
        "evaluation_only_acceleration_satisfied",
        "estimated_velocity_satisfied",
        "evaluation_only_velocity_satisfied",
        "mpc_predicted_acceleration_satisfied",
    ):
        if a["motion_envelope"][key] and not b["motion_envelope"][key]:
            reasons.append(f"new_motion_envelope_violation:{key}")
    if b["no_safe_action_count"] > a["no_safe_action_count"]:
        reasons.append("new_NO_SAFE_ACTION")
    if b["force_gate_event_count"] > a["force_gate_event_count"]:
        reasons.append("new_force_gate_event")
    if b["brake_event_count"] > a["brake_event_count"]:
        reasons.append("new_BRAKE_event")
    if (
        b["maximum_safety_filter_intervention_coordinate_norm"]
        > a["maximum_safety_filter_intervention_coordinate_norm"] + 1.0e-12
    ):
        reasons.append("new_Safety_Filter_intervention")
    if b["mujoco_warning_counts"] and not a["mujoco_warning_counts"]:
        reasons.append("new_MuJoCo_warning")
    return reasons


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    return float(np.mean([row["control"][key] for row in rows]))


def _analyze(arms: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fixed = arms["fixed_pacing"]["repetitions"]
    trust = arms["trust_driven_pacing"]["repetitions"]
    fixed_duration = np.asarray(
        [row["control"]["task_duration_s"] for row in fixed], dtype=float
    )
    trust_duration = np.asarray(
        [row["control"]["task_duration_s"] for row in trust], dtype=float
    )
    duration_improvement = float(
        (np.mean(fixed_duration) - np.mean(trust_duration))
        / np.mean(fixed_duration)
    )
    matched_shorter_count = int(np.count_nonzero(trust_duration < fixed_duration))
    material_efficiency = bool(
        duration_improvement >= 0.05 and matched_shorter_count >= 2
    )
    interaction = {}
    interaction_regression = False
    for key in (
        "peak_physical_cuff_force_n",
        "cumulative_physical_cuff_force_n_s",
        "peak_physical_cuff_moment_nm",
    ):
        a = _mean(fixed, key)
        b = _mean(trust, key)
        ratio = float(b / a) if a > 0.0 else float("inf")
        interaction[key] = {
            "fixed_mean": a,
            "trust_mean": b,
            "trust_to_fixed_ratio": ratio,
            "regression_over_10_percent": ratio > 1.10 + 1.0e-12,
        }
        interaction_regression = interaction_regression or ratio > 1.10 + 1.0e-12
    constraint_reasons = [
        _new_constraint_regression(a, b)
        for a, b in zip(fixed, trust, strict=True)
    ]
    authority_consistent = bool(
        all(row["raw_support_at_start"]["supported"] for row in trust)
        and trust[0]["filter_at_start"]["filtered_current_model_confidence"] == 0.0
        and trust[0]["minimum_actual_gamma"] == 0.5
        and trust[0]["first_gamma_above_0p5_session_time_s"] is not None
        and trust[0]["first_gamma_at_1p0_session_time_s"] is not None
        and all(row["active_model_id"] == trust[0]["active_model_id"] for row in trust)
    )
    any_constraint_regression = any(constraint_reasons)
    if not authority_consistent or interaction_regression or any_constraint_regression:
        code = "TG-C"
        label = "TRUST-DRIVEN PACING NOT SUPPORTED"
    elif material_efficiency:
        code = "TG-A"
        label = "TRUST-DRIVEN PACING SUPPORTED"
    else:
        code = "TG-B"
        label = "PACING MECHANISM WORKS, BENEFIT INSUFFICIENT"
    return {
        "decision": {"code": code, "label": label},
        "authority_consistent": authority_consistent,
        "efficiency": {
            "fixed_mean_duration_s": float(np.mean(fixed_duration)),
            "trust_mean_duration_s": float(np.mean(trust_duration)),
            "relative_mean_duration_improvement": duration_improvement,
            "matched_repetitions_shorter": matched_shorter_count,
            "material": material_efficiency,
        },
        "interaction": interaction,
        "meaningful_interaction_regression": interaction_regression,
        "matched_constraint_regression_reasons": constraint_reasons,
        "registered_constraint_regression": any_constraint_regression,
    }


def execute_formal(output_dir: Path) -> dict[str, Any]:
    contract = load_trust_gamma_contract()
    frozen = extract_supported_model(contract)
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    arms = {
        arm: _run_arm(
            arm=arm,
            output_dir=output_dir,
            contract=contract,
            frozen_model=frozen,
        )
        for arm in TRUST_GAMMA_ARMS
    }
    analysis = _analyze(arms)
    payload = _strict_jsonable(
        {
            "schema": "stage5_trust_gamma_matched_v1_results",
            "formal_execution_explicitly_authorized_by_user": True,
            "config_path": "configs/stage5_trust_gamma_matched_v1.json",
            "source_artifact_path": str(
                source_artifact_path(contract).relative_to(STAGE5_ROOT)
            ),
            "source_artifact_sha256": frozen.source_artifact_sha256,
            "frozen_supported_model": asdict(frozen),
            "arms": arms,
            "analysis": analysis,
            "decision": analysis["decision"],
            "same_active_model_both_arms": True,
            "human_model_updates_or_successor_activations": 0,
            "truth_available_to_online_trust_pacing_or_control": False,
            "acceleration_monitor_changed": False,
            "interface_adaptation_active": False,
            "value_or_RL_learning_active": False,
            "hard_realtime_or_WCET_claim": False,
            "wall_time_s": perf_counter() - started,
        }
    )
    result_path = output_dir / "trust_gamma_matched_results.json"
    result_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["decision"], indent=2, sort_keys=True), flush=True)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--execute-formal", action="store_true")
    arguments = parser.parse_args()
    contract = load_trust_gamma_contract()
    frozen = extract_supported_model(contract)
    if not arguments.execute_formal:
        print(
            json.dumps(
                _strict_jsonable(
                    {
                        "authorized": True,
                        "matched_seeds": TRUST_GAMMA_CEM_SEEDS,
                        "source_model": asdict(frozen),
                        "output_dir": str(arguments.output_dir),
                        "initial_raw_support": "SUPPORTED",
                        "initial_filtered_confidence": 0.0,
                        "initial_gamma": 0.5,
                    }
                ),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        )
        return
    execute_formal(arguments.output_dir)


if __name__ == "__main__":
    main()
