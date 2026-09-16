#!/usr/bin/env python3
"""Preregistered small reduced Human-ID shadow validation.

Only the pure stiffness and mixed cases create new MuJoCo smoke traces.  The
other three cases reuse the frozen Human-ID v1 traces.  All estimator decisions
use deployable measurements; truth scales are appended after replay for
evaluation only.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import lsq_linear

from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.integral_identifier import integral_regression_block
from traction_mpc_stage4.minimal_adaptation import (
    dynamic_scale_projection,
    effective_base_parameters,
)
from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.controller_interface import CONTROLLER_NOMINAL_INTERFACE
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_identification import Stage5HumanIDMeasurement
from traction_mpc_stage5.human_identification_reduced import (
    ReducedIntegralScaleIdentifier,
    ReducedScaleIdentifierConfig,
    ReducedShadowHumanIdentificationService,
    reduced_information,
)
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE


CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_human_id_reduced_shadow_v1.json"
V1_RESULT_ROOT = STAGE5_ROOT / "results" / "human_id_shadow_v1_diagnostic_attempt_03"


def _load_config() -> dict[str, Any]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_human_id_reduced_shadow_v1":
        raise ValueError("unexpected reduced Human-ID config schema")
    if len(payload.get("cases", [])) != 5:
        raise ValueError("the preregistered reduced matrix has exactly five cases")
    if payload["controller"]["human_adaptation_in_control"] is not False:
        raise ValueError("shadow Human adaptation cannot enter control")
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


def _human_from_scales(scales: np.ndarray):
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


def _read_trace(case_dir: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    with np.load(case_dir / "trace.npz") as loaded:
        trace = {key: loaded[key] for key in loaded.files}
    summary = json.loads((case_dir / "summary.json").read_text(encoding="utf-8"))
    return trace, summary


def _run_new_case(
    case: dict[str, Any], case_dir: Path, config: dict[str, Any]
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    human = _human_from_scales(case["truth_scales_evaluation_only"])

    def plant_factory(parameters):
        return Stage5SensorBoundaryPlant(human, interface_parameters=parameters)

    controller = config["controller"]
    run_goal_mpc_smoke(
        case_dir,
        maximum_duration_s=25.5,
        plant_interface_parameters=STAGE5_RIGID_INTERFACE,
        plant_case_name=f"human_id_reduced_shadow__{case['name']}__fixed_nominal_interface",
        record_selected_horizon_diagnostics=False,
        use_loaded_local_hold=True,
        use_bumpless_return_handoff=True,
        initialize_loaded_equilibrium_with_plant_truth=True,
        interface_uncertainty_spec=None,
        planning_physical_force_ceiling_n=float(
            controller["planning_physical_force_ceiling_n"]
        ),
        planning_joint_velocity_ceiling_rad_s=tuple(
            np.radians(controller["planning_joint_velocity_ceiling_deg_s"])
        ),
        mpc_config=HumanMPCConfig(random_seed=int(controller["cem_random_seed"])),
        plant_factory=plant_factory,
    )
    return _read_trace(case_dir)


def _v1_case_directory(name: str) -> Path:
    return V1_RESULT_ROOT / name


def _raw_history(trace: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, timestamp in enumerate(trace["time_s"]):
        output.append(
            {
                "time_s": float(timestamp),
                "state": np.asarray(trace["estimated_state_rad_rad_s"][index], dtype=float),
                "force_world_n": np.asarray(
                    trace["deployable_measured_cuff_force_world_n"][index], dtype=float
                ),
                "moment_world_nm": np.asarray(
                    trace["deployable_measured_cuff_moment_world_nm"][index], dtype=float
                ),
                "generalized_input_nm": np.asarray(
                    trace["deployable_measured_generalized_input_nm"][index], dtype=float
                ),
                "contaminated": False,
                "source_index": index,
                "task_phase": str(trace["task_phase"][index]),
            }
        )
    return output


def _replay_service(
    trace: dict[str, np.ndarray], geometry: PlanarCuffGeometry
) -> ReducedShadowHumanIdentificationService:
    service = ReducedShadowHumanIdentificationService(geometry)
    for index, timestamp in enumerate(trace["time_s"]):
        service.observe(
            Stage5HumanIDMeasurement(
                arrival_time_s=float(timestamp),
                sample_time_s=float(timestamp),
                estimated_human_state_rad_rad_s=trace[
                    "estimated_state_rad_rad_s"
                ][index],
                measured_human_cuff_force_world_n=trace[
                    "deployable_measured_cuff_force_world_n"
                ][index],
                measured_human_cuff_moment_world_nm=trace[
                    "deployable_measured_cuff_moment_world_nm"
                ][index],
                measured_generalized_human_input_nm=trace[
                    "deployable_measured_generalized_input_nm"
                ][index],
                task_phase=str(trace["task_phase"][index]),
                interface_model_version=CONTROLLER_NOMINAL_INTERFACE.model_version,
            )
        )
    return service


def _information_for_history(
    history: list[dict[str, Any]],
    geometry: PlanarCuffGeometry,
    *,
    window_s: float = 0.20,
) -> dict[str, Any]:
    identifier = ReducedIntegralScaleIdentifier(
        replace(
            ReducedScaleIdentifierConfig(),
            integration_window_s=window_s,
            minimum_integral_blocks=1,
        )
    )
    regressor, target, contaminated = identifier.integral_blocks(history, geometry)
    result = reduced_information(regressor)
    result.update(
        {
            "integral_block_count": int(len(target) // 2),
            "contaminated_integral_windows": int(contaminated),
            "window_s": window_s,
        }
    )
    return result


def _identifiability_audit(
    trace: dict[str, np.ndarray], geometry: PlanarCuffGeometry
) -> dict[str, Any]:
    history = _raw_history(trace)
    phase = {
        name: _information_for_history(
            [item for item in history if item["task_phase"] == name], geometry
        )
        for name in ("OUTBOUND", "HOLD", "RETURN")
    }
    latest = history[-1]["time_s"] if history else 0.0
    prefixes = {}
    for duration in (1.25, 2.50, latest):
        label = "full_available" if abs(duration - latest) < 1.0e-9 else f"{duration:.2f}s"
        prefixes[label] = _information_for_history(
            [item for item in history if item["time_s"] <= duration + 1.0e-12],
            geometry,
        )
    windows = {
        f"{window:.2f}s": _information_for_history(history, geometry, window_s=window)
        for window in (0.10, 0.20, 0.40)
    }
    return {
        "whole_available": _information_for_history(history, geometry),
        "phase_wise": phase,
        "history_prefix": prefixes,
        "integration_window_sensitivity": windows,
        "regularization_counted_as_data_information": False,
    }


def _fit_with_regularization(
    history: list[dict[str, Any]], geometry: PlanarCuffGeometry, weight: float
) -> list[float] | None:
    identifier = ReducedIntegralScaleIdentifier(
        replace(
            ReducedScaleIdentifierConfig(),
            regularization_weight=weight,
            minimum_integral_blocks=1,
        )
    )
    regressor, target, _ = identifier.integral_blocks(history, geometry)
    if not len(target):
        return None
    root = np.sqrt(weight)
    matrix = np.vstack([regressor, root * np.diag(1.0 / identifier.span)])
    rhs = np.concatenate([target, root * identifier.prior / identifier.span])
    fit = lsq_linear(matrix, rhs, bounds=(identifier.lower, identifier.upper))
    return np.asarray(fit.x, dtype=float).tolist()


def _regularization_and_initialization_sensitivity(
    trace: dict[str, np.ndarray], geometry: PlanarCuffGeometry
) -> dict[str, Any]:
    history = _raw_history(trace)
    fits = {
        f"{weight:g}": _fit_with_regularization(history, geometry, weight)
        for weight in (0.0, 1.0e-4, 1.0e-3, 1.0e-2)
    }
    candidate = fits["0.001"]
    identifier = ReducedIntegralScaleIdentifier()
    proposed = (
        {
            label: identifier.bounded_smoothed_step(
                np.full(3, initial), np.asarray(candidate, dtype=float)
            ).tolist()
            for label, initial in (("incumbent_0.9", 0.9), ("incumbent_1.0", 1.0), ("incumbent_1.1", 1.1))
        }
        if candidate is not None
        else None
    )
    return {
        "regularization_weight_to_candidate": fits,
        "candidate_optimizer": "bounded_convex_linear_least_squares",
        "multi_start_applicable": False,
        "reason": "lsq_linear has no local-minimum start dependence",
        "incumbent_sensitivity_applies_only_to_bounded_smoothed_publication": proposed,
        "latent_state_initialization_applicable": False,
        "latent_state_reason": "integral regression consumes measured deployable q,dq and carries no fitted latent rollout state",
    }


def _phase_integrated_prediction(
    trace: dict[str, np.ndarray], nominal: np.ndarray, retained: np.ndarray
) -> dict[str, Any]:
    time = np.asarray(trace["time_s"], dtype=float)
    state = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)
    torque = np.asarray(trace["deployable_measured_generalized_input_nm"], dtype=float)
    phase = np.asarray(trace["task_phase"], dtype=str)
    result = {}
    for name in ("OUTBOUND", "HOLD", "RETURN"):
        indices = np.flatnonzero(phase == name)
        residuals = {"nominal": [], "retained": []}
        if len(indices):
            start = float(time[indices[0]])
            end = float(time[indices[-1]])
            while start + 0.20 <= end + 1.0e-12:
                selected = indices[
                    (time[indices] >= start - 1.0e-12)
                    & (time[indices] <= start + 0.20 + 1.0e-12)
                ]
                if len(selected) >= 3 and time[selected[-1]] - time[selected[0]] >= 0.18:
                    regressor, target = integral_regression_block(
                        time[selected], state[selected], torque[selected]
                    )
                    residuals["nominal"].extend((regressor @ nominal - target).tolist())
                    residuals["retained"].extend((regressor @ retained - target).tolist())
                start += 0.20
        if not residuals["nominal"]:
            result[name] = {"block_count": 0}
            continue
        old = np.asarray(residuals["nominal"])
        new = np.asarray(residuals["retained"])
        old_rmse = float(np.sqrt(np.mean(old**2)))
        new_rmse = float(np.sqrt(np.mean(new**2)))
        result[name] = {
            "block_count": len(old) // 2,
            "nominal_rmse_nms": old_rmse,
            "retained_rmse_nms": new_rmse,
            "improvement_fraction": (
                float((old_rmse - new_rmse) / old_rmse) if old_rmse > 0.0 else 0.0
            ),
            "nominal_max_abs_nms": float(np.max(np.abs(old))),
            "retained_max_abs_nms": float(np.max(np.abs(new))),
        }
    return result


def _dynamics_prediction(
    trace: dict[str, np.ndarray], geometry: PlanarCuffGeometry, beta: np.ndarray
) -> dict[str, Any]:
    model = BaseParameterHumanModel(geometry, beta, STAGE5_HUMAN)
    time = np.asarray(trace["time_s"], dtype=float)
    state = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)
    torque = np.asarray(trace["deployable_measured_generalized_input_nm"], dtype=float)
    output = {}
    for steps, label in ((1, "one_step_5ms"), (4, "short_horizon_20ms")):
        errors = []
        for index in range(0, len(time) - steps):
            predicted = state[index].copy()
            valid = True
            for offset in range(steps):
                dt = float(time[index + offset + 1] - time[index + offset])
                if abs(dt - 0.005) > 1.0e-6:
                    valid = False
                    break
                predicted = model.step_dynamics(predicted, torque[index + offset], dt)
            if valid:
                errors.append(predicted - state[index + steps])
        if not errors:
            output[label] = {"sample_count": 0}
            continue
        error = np.asarray(errors)
        q_deg = np.degrees(error[:, :2])
        dq_deg_s = np.degrees(error[:, 2:])
        output[label] = {
            "sample_count": len(error),
            "q_rmse_deg": float(np.sqrt(np.mean(q_deg**2))),
            "q_max_abs_deg": float(np.max(np.abs(q_deg))),
            "dq_rmse_deg_s": float(np.sqrt(np.mean(dq_deg_s**2))),
            "dq_max_abs_deg_s": float(np.max(np.abs(dq_deg_s))),
            "input_semantics": "recorded future deployable generalized inputs; evaluation only",
        }
    return output


def _strict_future_integrated_prediction(
    trace: dict[str, np.ndarray], service: ReducedShadowHumanIdentificationService
) -> dict[str, Any]:
    if len(service.publication_history) <= 1:
        return {"available": False, "reason": "no accepted shadow publication"}
    publication = service.publication_history[-1]
    start = float(publication["timestamp_s"] + 0.20)
    time = np.asarray(trace["time_s"], dtype=float)
    state = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)
    torque = np.asarray(trace["deployable_measured_generalized_input_nm"], dtype=float)
    nominal = nominal_base_parameters(STAGE5_HUMAN)
    retained = np.asarray(publication["beta"], dtype=float)
    old = []
    new = []
    block_start = start
    while block_start + 0.20 <= float(time[-1]) + 1.0e-12:
        selected = np.flatnonzero(
            (time >= block_start - 1.0e-12)
            & (time <= block_start + 0.20 + 1.0e-12)
        )
        if len(selected) >= 3 and time[selected[-1]] - time[selected[0]] >= 0.18:
            regressor, target = integral_regression_block(
                time[selected], state[selected], torque[selected]
            )
            old.extend((regressor @ nominal - target).tolist())
            new.extend((regressor @ retained - target).tolist())
        block_start += 0.20
    if not old:
        return {"available": False, "reason": "episode ended before post-publication embargoed block"}
    old_values = np.asarray(old)
    new_values = np.asarray(new)
    old_rmse = float(np.sqrt(np.mean(old_values**2)))
    new_rmse = float(np.sqrt(np.mean(new_values**2)))
    return {
        "available": True,
        "start_time_s": start,
        "block_count": len(old) // 2,
        "nominal_rmse_nms": old_rmse,
        "retained_rmse_nms": new_rmse,
        "improvement_fraction": float((old_rmse - new_rmse) / old_rmse),
        "nominal_max_abs_nms": float(np.max(np.abs(old_values))),
        "retained_max_abs_nms": float(np.max(np.abs(new_values))),
    }


def _case_result(
    case: dict[str, Any],
    trace: dict[str, np.ndarray],
    control_summary: dict[str, Any],
    geometry: PlanarCuffGeometry,
) -> dict[str, Any]:
    service = _replay_service(trace, geometry)
    shadow = service.summary()
    nominal = nominal_base_parameters(STAGE5_HUMAN)
    retained_beta = np.asarray(shadow["retained_model"]["beta"], dtype=float)
    truth = np.asarray(case["truth_scales_evaluation_only"], dtype=float)
    retained_scales = np.asarray(shadow["retained_model"]["scales"], dtype=float)
    attempts = shadow["attempts"]
    candidate_scales = [
        item.get("candidate_scales")
        for item in attempts
        if item.get("candidate_scales") is not None
    ]
    first_attempt = (
        float(attempts[0]["fit_end_time_s"]) if attempts else None
    )
    nominal_dynamics = _dynamics_prediction(trace, geometry, nominal)
    retained_dynamics = _dynamics_prediction(trace, geometry, retained_beta)
    return {
        "case": case,
        "task_control": {
            "status": control_summary["task_status"],
            "abort_reason": control_summary.get("abort_reason"),
            "duration_s": control_summary["task_duration_s"],
            "phase_transitions": control_summary["phase_transitions"],
            "time_available_before_first_attempt_s": first_attempt,
            "mpc_status_counts": control_summary["mpc_status_counts"],
            "safety_filter_status_counts": control_summary[
                "safety_filter_status_counts"
            ],
            "brake_event_count": control_summary["brake_event_count"],
            "force_gate_event_count": control_summary["force_gate_event_count"],
            "mujoco_warning_counts": control_summary["mujoco_warning_counts"],
        },
        "identification": {
            "candidate_scales": candidate_scales,
            "retained_scales": retained_scales.tolist(),
            "attempt_count": shadow["attempt_count"],
            "attempt_status_counts": shadow["attempt_status_counts"],
            "first_accepted_publication_time_s": shadow[
                "first_trustworthy_candidate_time_s"
            ],
            "publication_history": shadow["publication_history"],
            "attempts": attempts,
            "bound_hit_count": int(
                sum(
                    bool(item.get("training_diagnostics", {}).get("bound_hit", False))
                    for item in attempts
                )
            ),
            "identifiability": _identifiability_audit(trace, geometry),
            "sensitivity": _regularization_and_initialization_sensitivity(
                trace, geometry
            ),
            "shadow_only": True,
            "applied_to_control": False,
        },
        "prediction": {
            "whole_phase_integrated_torque": _phase_integrated_prediction(
                trace, nominal, retained_beta
            ),
            "strict_post_publication_future_integrated_torque": _strict_future_integrated_prediction(
                trace, service
            ),
            "nominal_dynamics": nominal_dynamics,
            "retained_dynamics": retained_dynamics,
        },
        "evaluation_only_truth": {
            "truth_scales": truth.tolist(),
            "retained_scale_error": (retained_scales - truth).tolist(),
            "retained_scale_error_l2": float(np.linalg.norm(retained_scales - truth)),
            "candidate_direction_correct": [
                [
                    bool(np.sign(value - 1.0) == np.sign(target - 1.0))
                    if abs(target - 1.0) > 1.0e-12
                    else None
                    for value, target in zip(candidate, truth, strict=True)
                ]
                for candidate in candidate_scales
            ],
            "used_by_online_identifier_or_trust": False,
        },
        "isolation": {
            "fixed_nominal_interface": True,
            "fixed_nominal_human_model_in_control": True,
            "truth_input_to_service": False,
            "interface_identification_active": False,
            "value_or_RL_learning": False,
        },
    }


def _decision(cases: list[dict[str, Any]]) -> dict[str, Any]:
    complete = [row for row in cases if row["task_control"]["status"] == "COMPLETE"]
    full_rank = all(
        row["identification"]["identifiability"]["whole_available"]["rank"] == 3
        for row in complete
    )
    published = [
        row
        for row in cases
        if len(row["identification"]["publication_history"]) > 1
    ]
    useful = [
        row
        for row in published
        if row["prediction"]["strict_post_publication_future_integrated_torque"].get(
            "improvement_fraction", -np.inf
        )
        > 0.0
    ]
    supported_directions = set()
    for row in useful:
        truth = np.asarray(row["evaluation_only_truth"]["truth_scales"])
        for index, value in enumerate(truth):
            if abs(value - 1.0) > 1.0e-12:
                supported_directions.add(index)
    if full_rank and len(useful) >= 2 and len(supported_directions) == 3:
        classification = "R-A"
        reason = "all three effective directions have useful causal held-out support"
    elif full_rank and useful and len(supported_directions) in (1, 2):
        classification = "R-B"
        reason = "numerical scale3 rank is stable, but useful causal evidence supports only a subset of effective directions"
    else:
        classification = "R-C"
        reason = "the reduced model did not establish stable causal held-out prediction benefit"
    return {
        "classification": classification,
        "reason": reason,
        "complete_case_count": len(complete),
        "whole_trace_full_rank_for_complete_cases": full_rank,
        "shadow_publication_case_names": [row["case"]["name"] for row in published],
        "useful_strict_future_case_names": [row["case"]["name"] for row in useful],
        "supported_direction_indices_evaluation_only": sorted(supported_directions),
        "closed_loop_AB_preregistered": classification == "R-A",
        "closed_loop_AB_run": False,
        "human_adaptation_activated": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "human_id_reduced_shadow_v1_diagnostic",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = _load_config()
    geometry = _geometry()
    rows = []
    for case in config["cases"]:
        if case["trace_source"].startswith("reuse_"):
            trace, summary = _read_trace(_v1_case_directory(case["name"]))
        else:
            trace, summary = _run_new_case(
                case, args.output_dir / case["name"], config
            )
        rows.append(_case_result(case, trace, summary, geometry))
    decision = _decision(rows)
    result = {
        "schema": "stage5_human_id_reduced_shadow_v1_results",
        "config_path": str(CONFIG_PATH.relative_to(STAGE5_ROOT)),
        "fixed_interface_model_version": CONTROLLER_NOMINAL_INTERFACE.model_version,
        "mapping_projection": dynamic_scale_projection(
            nominal_base_parameters(STAGE5_HUMAN)
        ).tolist(),
        "cases": rows,
        "decision": decision,
        "evidence_category": "small_preregistered_shadow_validation",
        "formal_or_authoritative": False,
    }
    (args.output_dir / "reduced_shadow_results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "decision": decision,
                "cases": [
                    {
                        "name": row["case"]["name"],
                        "status": row["task_control"]["status"],
                        "abort_reason": row["task_control"]["abort_reason"],
                        "attempt_status": row["identification"][
                            "attempt_status_counts"
                        ],
                        "retained_scales": row["identification"]["retained_scales"],
                        "condition": row["identification"]["identifiability"][
                            "whole_available"
                        ]["condition_number"],
                        "max_correlation": row["identification"][
                            "identifiability"
                        ]["whole_available"]["maximum_abs_parameter_correlation"],
                        "strict_future": row["prediction"][
                            "strict_post_publication_future_integrated_torque"
                        ],
                    }
                    for row in rows
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
