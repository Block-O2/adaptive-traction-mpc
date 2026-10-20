#!/usr/bin/env python3
"""Small multi-repetition confidence-pacing Human-ID feasibility study."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from traction_mpc_stage4.estimator_v2 import (
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.integral_identifier import integral_regression_block
from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.confidence_pacing import (
    Stage5ConfidencePacing,
    Stage5PacingEvidence,
    current_nominal_model_trust_from_shadow_service,
)
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.controller_interface import CONTROLLER_NOMINAL_INTERFACE
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_identification import Stage5HumanIDMeasurement
from traction_mpc_stage5.human_identification_reduced import (
    ReducedShadowHumanIdentificationService,
    reduced_information,
)
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE


CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_human_id_confidence_pacing_v1.json"
FIXED_BASELINE_PATH = STAGE5_ROOT / "docs" / "HUMAN_ID_REDUCED_SHADOW_V1_SUMMARY.json"


def _load_config() -> dict[str, Any]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_human_id_confidence_pacing_v1":
        raise ValueError("unexpected confidence-pacing config schema")
    if payload["session"]["maximum_repetitions"] != 5:
        raise ValueError("this feasibility study is frozen at up to five repetitions")
    if payload["controller"]["shadow_model_applied_to_control"] is not False:
        raise ValueError("shadow Human model cannot enter control")
    if payload["fixed_interface"]["interface_adaptation"] is not False:
        raise ValueError("interface adaptation must remain disabled")
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


def _human(scales: list[float]):
    alpha_m, alpha_k, alpha_d = np.asarray(scales, dtype=float)
    return replace(
        STAGE5_HUMAN,
        body_mass_kg=STAGE5_HUMAN.body_mass_kg * alpha_m,
        passive_stiffness_nm_rad=tuple(
            np.asarray(STAGE5_HUMAN.passive_stiffness_nm_rad) * alpha_k
        ),
        passive_damping_nms_rad=tuple(
            np.asarray(STAGE5_HUMAN.passive_damping_nms_rad) * alpha_d
        ),
    )


def _phase_prediction(
    trace: dict[str, np.ndarray], beta: np.ndarray
) -> dict[str, Any]:
    time = np.asarray(trace["time_s"], dtype=float)
    state = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)
    torque = np.asarray(trace["deployable_measured_generalized_input_nm"], dtype=float)
    phase = np.asarray(trace["task_phase"], dtype=str)
    result = {}
    for name in ("OUTBOUND", "HOLD", "RETURN"):
        indices = np.flatnonzero(phase == name)
        residuals = []
        if len(indices):
            start = float(time[indices[0]])
            end = float(time[indices[-1]])
            while start + 0.20 <= end + 1.0e-12:
                selected = indices[
                    (time[indices] >= start - 1.0e-12)
                    & (time[indices] <= start + 0.20 + 1.0e-12)
                ]
                if (
                    len(selected) >= 3
                    and time[selected[-1]] - time[selected[0]] >= 0.18
                ):
                    regressor, target = integral_regression_block(
                        time[selected], state[selected], torque[selected]
                    )
                    residuals.extend((regressor @ beta - target).tolist())
                start += 0.20
        if residuals:
            values = np.asarray(residuals)
            result[name] = {
                "block_count": len(values) // 2,
                "rmse_nms": float(np.sqrt(np.mean(values**2))),
                "maximum_abs_nms": float(np.max(np.abs(values))),
            }
        else:
            result[name] = {"block_count": 0}
    return result


def _latest_information(
    service: ReducedShadowHumanIdentificationService,
) -> dict[str, Any]:
    if not service.attempts:
        return {"rank": 0, "condition_number": float("inf")}
    return dict(
        service.attempts[-1].get("training_diagnostics", {}).get(
            "information", {"rank": 0, "condition_number": float("inf")}
        )
    )


def _challenger_status(service: ReducedShadowHumanIdentificationService) -> str:
    if service.active_challenger is not None:
        return str(service.active_challenger["status"])
    if service.attempts:
        return str(service.attempts[-1]["status"])
    return "none"


def _episode_prediction_models(
    service: ReducedShadowHumanIdentificationService,
) -> dict[str, np.ndarray]:
    nominal = nominal_base_parameters(STAGE5_HUMAN)
    latest_attempt = service.attempts[-1] if service.attempts else None
    challenger = (
        nominal
        if latest_attempt is None or latest_attempt.get("proposed_model_beta") is None
        else np.asarray(latest_attempt["proposed_model_beta"], dtype=float)
    )
    return {
        "nominal_control_incumbent": nominal,
        "latest_shadow_challenger": challenger,
        "retained_shadow_incumbent": np.asarray(service.publication.beta, dtype=float),
    }


def _run_case(
    case: dict[str, Any], output_dir: Path, config: dict[str, Any]
) -> dict[str, Any]:
    geometry = _geometry()
    service = ReducedShadowHumanIdentificationService(geometry)
    pacing = Stage5ConfidencePacing()
    human = _human(case["truth_scales_evaluation_only"])
    session_offset_s = 0.0
    reset_gap_s = float(config["session"]["physical_reset_gap_in_session_time_s"])
    base_ceiling = tuple(
        np.radians(config["controller"]["base_planning_joint_velocity_ceiling_deg_s"])
    )
    episode_rows = []
    consecutive_insufficient_aborts = 0
    previous_total_blocks = 0
    session_wall_start = perf_counter()

    for repetition in range(1, int(config["session"]["maximum_repetitions"]) + 1):
        episode_index = repetition - 1
        service.begin_episode(episode_index, session_offset_s)
        attempts_before = len(service.attempts)

        def callback(payload: dict[str, Any]) -> dict[str, Any]:
            session_time_s = session_offset_s + float(payload["episode_time_s"])
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

        episode_dir = output_dir / f"episode_{repetition:02d}"
        wall_start = perf_counter()
        summary = run_goal_mpc_smoke(
            episode_dir,
            maximum_duration_s=25.5,
            plant_interface_parameters=STAGE5_RIGID_INTERFACE,
            plant_case_name=(
                f"confidence_pacing__{case['name']}__rep{repetition:02d}"
            ),
            record_selected_horizon_diagnostics=False,
            use_loaded_local_hold=True,
            use_bumpless_return_handoff=True,
            initialize_loaded_equilibrium_with_plant_truth=True,
            interface_uncertainty_spec=None,
            planning_physical_force_ceiling_n=float(
                config["controller"]["planning_physical_force_ceiling_n"]
            ),
            planning_joint_velocity_ceiling_rad_s=base_ceiling,
            mpc_config=HumanMPCConfig(
                random_seed=int(config["controller"]["cem_random_seed"])
            ),
            plant_factory=plant_factory,
            progress_pacing_callback=callback,
        )
        episode_wall_s = perf_counter() - wall_start
        with np.load(episode_dir / "trace.npz") as loaded:
            trace = {key: loaded[key] for key in loaded.files}

        regressor, target, contaminated = service.identifier.integral_blocks(
            service.raw_history, geometry
        )
        total_blocks = int(len(target) // 2)
        episode_blocks = total_blocks - previous_total_blocks
        previous_total_blocks = total_blocks
        information = reduced_information(regressor)
        new_attempts = service.attempts[attempts_before:]
        models = _episode_prediction_models(service)
        gamma = np.asarray(trace["progress_pacing_gamma"], dtype=float)
        prediction = {
            name: _phase_prediction(trace, beta) for name, beta in models.items()
        }
        episode_rows.append(
            {
                "repetition": repetition,
                "task_status": summary["task_status"],
                "abort_reason": summary.get("abort_reason"),
                "task_duration_s": summary["task_duration_s"],
                "phase_transitions": summary["phase_transitions"],
                "gamma": {
                    "minimum": float(np.min(gamma)),
                    "mean": float(np.mean(gamma)),
                    "final": float(gamma[-1]),
                    "time_at_frozen_minimum_s": float(
                        0.005 * np.count_nonzero(np.isclose(gamma, 0.5))
                    ),
                },
                "motion_force": {
                    "peak_estimated_velocity_deg_s": summary[
                        "peak_abs_estimated_joint_velocity_deg_s"
                    ],
                    "peak_truth_velocity_deg_s": summary[
                        "peak_abs_evaluation_only_joint_velocity_deg_s"
                    ],
                    "peak_deployable_acceleration_deg_s2": summary[
                        "peak_abs_estimated_joint_acceleration_deg_s2"
                    ],
                    "peak_truth_acceleration_deg_s2": summary[
                        "peak_abs_evaluation_only_joint_acceleration_deg_s2"
                    ],
                    "peak_force_n": summary["peak_physical_cuff_force_n"],
                    "peak_moment_nm": summary["peak_physical_cuff_moment_nm"],
                    "force_gate_events": summary["force_gate_event_count"],
                    "brake_events": summary["brake_event_count"],
                    "safety_filter_status_counts": summary[
                        "safety_filter_status_counts"
                    ],
                    "mujoco_warning_counts": summary["mujoco_warning_counts"],
                },
                "identification": {
                    "episode_clean_integral_blocks": episode_blocks,
                    "session_clean_integral_blocks": total_blocks,
                    "contaminated_windows": int(contaminated),
                    "rank": information["rank"],
                    "condition_number": information["condition_number"],
                    "maximum_abs_parameter_correlation": information[
                        "maximum_abs_parameter_correlation"
                    ],
                    "new_attempts": new_attempts,
                    "total_attempt_count": len(service.attempts),
                    "challenger_status": _challenger_status(service),
                    "retained_shadow_scales": service.retained_scales.tolist(),
                    "shadow_publication_count": len(service.publication_history) - 1,
                },
                "prediction": prediction,
                "wall_time_s": episode_wall_s,
            }
        )

        if len(service.publication_history) > 1:
            stop_reason = "qualified_shadow_publication"
            break
        if summary["task_status"] == "ABORTED":
            consecutive_insufficient_aborts += 1
        else:
            consecutive_insufficient_aborts = 0
        if (
            consecutive_insufficient_aborts >= 2
            and total_blocks < service.config.identifier.minimum_integral_blocks
        ):
            stop_reason = "repeated_abort_below_first_fit_information"
            break
        session_offset_s += float(summary["task_duration_s"]) + reset_gap_s
    else:
        stop_reason = "maximum_five_repetitions"

    final_summary = service.summary()
    first_publication = (
        None
        if len(service.publication_history) <= 1
        else service.publication_history[1]
    )
    first_publication_repetition = None
    if first_publication is not None:
        timestamp = float(first_publication["timestamp_s"])
        for boundary in reversed(service.episode_boundaries):
            if timestamp >= float(boundary["session_start_time_s"]) - 1.0e-12:
                first_publication_repetition = int(boundary["episode_index"]) + 1
                break
    return {
        "case": case,
        "episodes": episode_rows,
        "stop_reason": stop_reason,
        "repetition_count": len(episode_rows),
        "total_task_time_s": float(
            sum(row["task_duration_s"] for row in episode_rows)
        ),
        "total_wall_time_s": perf_counter() - session_wall_start,
        "first_fit_session_time_s": (
            None
            if not service.attempts
            else float(service.attempts[0]["fit_end_time_s"])
        ),
        "first_shadow_publication": first_publication,
        "first_shadow_publication_repetition": first_publication_repetition,
        "service_summary": final_summary,
        "pacing_summary": pacing.summary(
            float(service.last_sample_time_s or session_offset_s)
        ),
        "truth_scales_evaluation_only": case["truth_scales_evaluation_only"],
        "truth_used_online": False,
        "model_applied_to_control": False,
    }


def _decision(cases: list[dict[str, Any]]) -> dict[str, Any]:
    early_names = {
        "mass_plus_8pct",
        "stiffness_plus_15pct",
        "mixed_effective_scales",
    }
    early_with_fit = [
        row["case"]["name"]
        for row in cases
        if row["case"]["name"] in early_names
        and row["service_summary"]["attempt_count"] > 0
    ]
    nonnominal_publications = [
        row["case"]["name"]
        for row in cases
        if row["case"]["name"] != "nominal"
        and len(row["service_summary"]["publication_history"]) > 1
    ]
    unstable = any(
        attempt.get("training_diagnostics", {}).get("bound_hit", False)
        for row in cases
        for attempt in row["service_summary"]["attempts"]
    )
    if (
        len(early_with_fit) == 3
        and len(nonnominal_publications) >= 3
        and not unstable
    ):
        classification = "P-A"
        reason = (
            "all prior early-abort cases reached a fit and representative "
            "mismatches published within five repetitions"
        )
    elif early_with_fit and not unstable:
        classification = "P-B"
        reason = (
            "minimum confidence pacing preserved at least one prior early-abort "
            "case long enough to fit, but trusted publication evidence remained "
            "incomplete"
        )
    else:
        classification = "P-C"
        reason = (
            "confidence pacing did not create useful stable information before "
            "repeated termination"
        )
    return {
        "classification": classification,
        "reason": reason,
        "formerly_early_abort_cases_reaching_fit": early_with_fit,
        "nonnominal_publication_cases": nonnominal_publications,
        "bound_hit_or_instability_observed": unstable,
        "closed_loop_AB_preregistered": classification == "P-A",
        "closed_loop_AB_run": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "human_id_confidence_pacing_v1",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = _load_config()
    fixed = json.loads(FIXED_BASELINE_PATH.read_text(encoding="utf-8"))
    fixed_by_name = {item["name"]: item for item in fixed["cases"]}
    cases = []
    for case in config["cases"]:
        row = _run_case(case, args.output_dir / case["name"], config)
        row["previous_fixed_pacing_single_episode"] = fixed_by_name[case["name"]]
        cases.append(row)
        print(
            json.dumps(
                {
                    "completed_case": case["name"],
                    "repetitions": row["repetition_count"],
                    "stop_reason": row["stop_reason"],
                    "episode_statuses": [
                        item["task_status"] for item in row["episodes"]
                    ],
                    "attempt_status": row["service_summary"][
                        "attempt_status_counts"
                    ],
                    "retained_scales": row["service_summary"]["retained_model"][
                        "scales"
                    ],
                }
            ),
            flush=True,
        )
    result = {
        "schema": "stage5_human_id_confidence_pacing_v1_results",
        "config_path": str(CONFIG_PATH.relative_to(STAGE5_ROOT)),
        "cases": cases,
        "decision": _decision(cases),
        "old_single_episode_decision_preserved": "R-C",
        "fixed_nominal_interface": True,
        "fixed_nominal_human_model_in_goal_mpc": True,
        "formal_or_authoritative": False,
    }
    (args.output_dir / "confidence_pacing_results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"decision": result["decision"]}, indent=2))


if __name__ == "__main__":
    main()
