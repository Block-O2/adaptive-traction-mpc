#!/usr/bin/env python3
"""Small Stage-5 fixed-interface Human-ID shadow diagnostic."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage4.estimator_v2 import (
    DYNAMIC_BASE_PARAMETER_NAMES,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.integral_identifier import integral_regression_block
from traction_mpc_stage4.minimal_adaptation import dynamic_scale_projection
from traction_mpc_stage4.mpc import HumanMPCConfig
from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.controller_interface import CONTROLLER_NOMINAL_INTERFACE
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc_smoke import run_goal_mpc_smoke
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_identification import (
    ShadowHumanIdentificationService,
    Stage5HumanIDMeasurement,
)
from traction_mpc_stage5.mechanics import STAGE5_RIGID_INTERFACE


CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_human_id_shadow_v1.json"


def _load_config() -> dict[str, Any]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_human_id_shadow_v1":
        raise ValueError("unexpected Human-ID shadow config schema")
    if payload["fixed_interface"]["interface_adaptation"] is not False:
        raise ValueError("Human-ID isolation forbids interface adaptation")
    if payload["controller"]["human_adaptation_in_control"] is not False:
        raise ValueError("shadow diagnostic forbids Human adaptation in control")
    if len(payload.get("cases", [])) != 4:
        raise ValueError("small shadow diagnostic requires exactly four cases")
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


def _human(case: dict[str, Any]):
    return replace(
        STAGE5_HUMAN,
        body_mass_kg=STAGE5_HUMAN.body_mass_kg * float(case["mass_scale"]),
        passive_stiffness_nm_rad=tuple(
            np.asarray(STAGE5_HUMAN.passive_stiffness_nm_rad)
            * float(case["stiffness_scale"])
        ),
        passive_damping_nms_rad=tuple(
            np.asarray(STAGE5_HUMAN.passive_damping_nms_rad)
            * float(case["damping_scale"])
        ),
        q_rest_rad=tuple(
            np.asarray(STAGE5_HUMAN.q_rest_rad)
            + np.radians(np.asarray(case["rest_offset_deg"], dtype=float))
        ),
    )


def _phase_prediction_metrics(
    trace: dict[str, np.ndarray],
    prior_beta: np.ndarray,
    shadow_beta: np.ndarray,
    *,
    window_s: float = 0.20,
) -> dict[str, Any]:
    time = np.asarray(trace["time_s"], dtype=float)
    state = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)
    torque = np.asarray(trace["deployable_measured_generalized_input_nm"], dtype=float)
    phase = np.asarray(trace["task_phase"], dtype=str)
    result: dict[str, Any] = {}
    for name in ("OUTBOUND", "HOLD", "RETURN"):
        indices = np.flatnonzero(phase == name)
        blocks: list[tuple[np.ndarray, np.ndarray]] = []
        if len(indices):
            start_t = float(time[indices[0]])
            end_t = float(time[indices[-1]])
            block_start = start_t
            while block_start + window_s <= end_t + 1.0e-12:
                selected = indices[
                    (time[indices] >= block_start - 1.0e-12)
                    & (time[indices] <= block_start + window_s + 1.0e-12)
                ]
                if len(selected) >= 3 and time[selected[-1]] - time[selected[0]] >= 0.9 * window_s:
                    blocks.append(
                        integral_regression_block(
                            time[selected], state[selected], torque[selected]
                        )
                    )
                block_start += window_s
        if not blocks:
            result[name] = {"block_count": 0}
            continue
        prior_residual = np.concatenate([x @ prior_beta - y for x, y in blocks])
        shadow_residual = np.concatenate([x @ shadow_beta - y for x, y in blocks])
        prior_rmse = float(np.sqrt(np.mean(prior_residual**2)))
        shadow_rmse = float(np.sqrt(np.mean(shadow_residual**2)))
        result[name] = {
            "block_count": len(blocks),
            "nominal_integrated_torque_rmse_nms": prior_rmse,
            "shadow_integrated_torque_rmse_nms": shadow_rmse,
            "shadow_improvement_fraction": (
                float((prior_rmse - shadow_rmse) / prior_rmse)
                if prior_rmse > 0.0
                else 0.0
            ),
        }
    return result


def _full_and_reduced_information(
    service: ShadowHumanIdentificationService,
) -> dict[str, Any]:
    regressor, target, contaminated = service.identifier._integral_blocks(
        service.raw_history, service.geometry
    )
    prior = service.identifier.population_prior
    projection = dynamic_scale_projection(prior)
    matrices = {
        "beta11": regressor * service.identifier.span,
        "effective_scale3": regressor @ projection,
    }
    output: dict[str, Any] = {
        "integral_block_count": int(len(target) // 2),
        "contaminated_integral_windows": int(contaminated),
    }
    for name, matrix in matrices.items():
        if matrix.shape[0] == 0:
            output[name] = {
                "rank": 0,
                "dimension": int(matrix.shape[1]),
                "condition_number": float("inf"),
                "singular_values": [],
                "maximum_abs_correlation": float("nan"),
                "reason": "no_complete_integral_block_before_termination",
            }
            continue
        norms = np.linalg.norm(matrix, axis=0)
        normalized = matrix / np.where(norms > 1.0e-15, norms, 1.0)
        singular = np.linalg.svd(normalized, compute_uv=False)
        rank = int(np.linalg.matrix_rank(normalized, tol=singular[0] * 1.0e-10))
        covariance = np.linalg.pinv(matrix.T @ matrix, rcond=1.0e-12)
        std = np.sqrt(np.maximum(np.diag(covariance), 0.0))
        correlation = np.divide(
            covariance,
            np.outer(std, std),
            out=np.full_like(covariance, np.nan),
            where=np.outer(std, std) > 0.0,
        )
        np.fill_diagonal(correlation, 0.0)
        output[name] = {
            "rank": rank,
            "dimension": int(matrix.shape[1]),
            "condition_number": (
                float(singular[0] / singular[-1])
                if singular[-1] > 1.0e-15
                else float("inf")
            ),
            "singular_values": singular.tolist(),
            "maximum_abs_correlation": float(np.nanmax(np.abs(correlation))),
        }
    return output


def _run_case(case: dict[str, Any], case_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    human = _human(case)

    def plant_factory(parameters):
        return Stage5SensorBoundaryPlant(human, interface_parameters=parameters)

    controller = config["controller"]
    summary = run_goal_mpc_smoke(
        case_dir,
        maximum_duration_s=25.5,
        plant_interface_parameters=STAGE5_RIGID_INTERFACE,
        plant_case_name=f"human_id_shadow__{case['name']}__fixed_nominal_interface",
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
        mpc_config=HumanMPCConfig(random_seed=20260824),
        plant_factory=plant_factory,
    )
    with np.load(case_dir / "trace.npz") as loaded:
        trace = {key: loaded[key] for key in loaded.files}
    geometry = _geometry()
    service = ShadowHumanIdentificationService(geometry)
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
    service_summary = service.summary()
    prior = nominal_base_parameters(STAGE5_HUMAN)
    truth_beta = nominal_base_parameters(human)
    shadow = np.asarray(service_summary["retained_model"]["beta"], dtype=float)
    phase_prediction = _phase_prediction_metrics(trace, prior, shadow)
    information = _full_and_reduced_information(service)
    nominal_error = float(np.linalg.norm((prior - truth_beta) / np.abs(prior)))
    shadow_error = float(np.linalg.norm((shadow - truth_beta) / np.abs(prior)))
    return {
        "case": case,
        "task_status": summary["task_status"],
        "abort_reason": summary.get("abort_reason"),
        "duration_s": summary["task_duration_s"],
        "phase_transitions": summary["phase_transitions"],
        "safety": {
            "mpc_status_counts": summary["mpc_status_counts"],
            "safety_filter_status_counts": summary["safety_filter_status_counts"],
            "brake_event_count": summary["brake_event_count"],
            "force_gate_event_count": summary["force_gate_event_count"],
            "mujoco_warning_counts": summary["mujoco_warning_counts"],
        },
        "truth_beta_evaluation_only": truth_beta.tolist(),
        "truth_relative_to_nominal_beta_evaluation_only": (
            truth_beta / prior
        ).tolist(),
        "nominal_beta_relative_error_l2_evaluation_only": nominal_error,
        "shadow_beta_relative_error_l2_evaluation_only": shadow_error,
        "shadow_parameter_error_change_evaluation_only": shadow_error - nominal_error,
        "shadow_service": service_summary,
        "information": information,
        "phase_prediction": phase_prediction,
        "control_isolation": {
            "fixed_nominal_human_model_in_mpc": True,
            "shadow_model_applied_to_control": False,
            "fixed_nominal_interface_plant_and_controller": True,
            "truth_input_to_shadow_service": False,
        },
    }


def _decision(rows: list[dict[str, Any]]) -> dict[str, Any]:
    nonnominal = [row for row in rows if row["case"]["name"] != "nominal"]
    publications = sum(
        len(row["shadow_service"]["publication_history"]) > 1 for row in nonnominal
    )
    full_rank_cases = sum(
        row["information"]["beta11"]["rank"] == 11 for row in rows
    )
    full_correlations = [
        row["information"]["beta11"]["maximum_abs_correlation"]
        for row in rows
        if np.isfinite(
            row["information"]["beta11"]["maximum_abs_correlation"]
        )
    ]
    reduced_rank_cases = sum(
        row["information"]["effective_scale3"]["rank"] == 3 for row in rows
    )
    reduced_conditions = [
        row["information"]["effective_scale3"]["condition_number"]
        for row in rows
        if np.isfinite(
            row["information"]["effective_scale3"]["condition_number"]
        )
    ]
    if publications >= 2 and full_correlations and max(full_correlations) < 0.98:
        outcome = "H-A"
        reason = "representative mismatches published causally validated, practically conditioned shadow models"
    elif full_rank_cases >= 2 and reduced_rank_cases >= 2:
        outcome = "H-B"
        reason = (
            "the task supplies dynamic information, but full beta11 remains "
            "practically correlated; the three-scale projection is better conditioned"
        )
    else:
        outcome = "H-C"
        reason = "insufficient deployable-domain rank or future prediction evidence"
    return {
        "classification": outcome,
        "reason": reason,
        "nonnominal_shadow_publication_count": publications,
        "beta11_full_rank_case_count": full_rank_cases,
        "beta11_max_correlation_range": (
            [float(min(full_correlations)), float(max(full_correlations))]
            if full_correlations
            else None
        ),
        "effective_scale3_full_rank_case_count": reduced_rank_cases,
        "effective_scale3_condition_range": (
            [float(min(reduced_conditions)), float(max(reduced_conditions))]
            if reduced_conditions
            else None
        ),
        "closed_loop_adaptation_started": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "human_id_shadow_v1_diagnostic",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = _load_config()
    rows = []
    for case in config["cases"]:
        rows.append(_run_case(case, args.output_dir / case["name"], config))
    result = {
        "schema": "stage5_human_id_shadow_v1_diagnostic_results",
        "config_path": str(CONFIG_PATH.relative_to(STAGE5_ROOT)),
        "fixed_interface_model_version": CONTROLLER_NOMINAL_INTERFACE.model_version,
        "case_count": len(rows),
        "cases": rows,
        "decision": _decision(rows),
        "parameter_names": list(DYNAMIC_BASE_PARAMETER_NAMES),
        "evidence_category": "small_diagnostic_shadow_validation",
        "formal_or_authoritative": False,
    }
    (args.output_dir / "shadow_results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"decision": result["decision"], "cases": [
        {
            "name": row["case"]["name"],
            "task_status": row["task_status"],
            "attempts": row["shadow_service"]["attempt_count"],
            "attempt_status": row["shadow_service"]["attempt_status_counts"],
            "first_trustworthy_s": row["shadow_service"]["first_trustworthy_candidate_time_s"],
            "beta11_condition": row["information"]["beta11"]["condition_number"],
            "beta11_correlation": row["information"]["beta11"]["maximum_abs_correlation"],
            "scale3_condition": row["information"]["effective_scale3"]["condition_number"],
        }
        for row in rows
    ]}, indent=2))


if __name__ == "__main__":
    main()
