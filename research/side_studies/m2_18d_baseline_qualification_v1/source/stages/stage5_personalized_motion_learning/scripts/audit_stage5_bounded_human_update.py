#!/usr/bin/env python3
"""Saved-trace-only audit of one bounded Stage-5 Human-model correction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage3.human import soft_limit_torque
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
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc_smoke import FIXED_HUMAN_MODEL_VERSION
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_identification_reduced import (
    ReducedIntegralScaleIdentifier,
    Stage5ReducedHumanIDConfig,
)
from traction_mpc_stage5.human_model_update import (
    build_bounded_human_model_transition,
    classify_post_update_evidence,
)


SOURCE_ROOT = STAGE5_ROOT / "results" / "human_id_confidence_pacing_v1_attempt_01"
SOURCE_SUMMARY = SOURCE_ROOT / "confidence_pacing_results.json"
CASES = ("nominal", "damping_plus_20pct", "stiffness_plus_15pct")
ALLOWED_PHASES = {"OUTBOUND", "HOLD", "RETURN"}


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


def _block(
    trace: dict[str, np.ndarray],
    *,
    start_s: float,
    end_s: float,
    projection: np.ndarray,
    scales: dict[str, np.ndarray],
    role: str,
) -> dict[str, Any] | None:
    time = np.asarray(trace["time_s"], dtype=float)
    selected = np.flatnonzero(
        (time >= start_s - 1.0e-9) & (time <= end_s + 1.0e-9)
    )
    if len(selected) < 3 or time[selected[-1]] - time[selected[0]] < 0.18:
        return None
    state = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)[selected]
    torque = np.asarray(
        trace["deployable_measured_generalized_input_nm"], dtype=float
    )[selected]
    phase_values = np.asarray(trace["task_phase"], dtype=str)[selected]
    phases = list(dict.fromkeys(str(value) for value in phase_values))
    if any(value not in ALLOWED_PHASES for value in phases):
        return None
    contaminated = bool(
        any(
            np.linalg.norm(soft_limit_torque(item[:2], item[2:], STAGE5_HUMAN))
            > 1.0e-8
            for item in state
        )
    )
    if contaminated:
        return None
    full_regressor, target = integral_regression_block(
        time[selected], state, torque
    )
    regressor = full_regressor @ projection
    losses = {
        name: float(np.mean((regressor @ values - target) ** 2))
        for name, values in scales.items()
    }
    return {
        "start_time_s": float(time[selected[0]]),
        "end_time_s": float(time[selected[-1]]),
        "phase": phases[0] if len(phases) == 1 else "->".join(phases),
        "used_in_this_candidate_fit": False,
        "used_in_candidate_qualification": role == "candidate_qualification",
        "genuinely_later_post_decision_evaluation": role == "post_decision",
        "nonoverlapping_within_role": True,
        "loss_mse_nms2": losses,
        "successor_improvement_nms2": losses["predecessor"] - losses["successor"],
        "candidate_improvement_nms2": losses["predecessor"] - losses["candidate"],
    }


def _summarize_blocks(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    if not blocks:
        return {"block_count": 0}
    by_model = {}
    for name in ("predecessor", "successor", "candidate"):
        losses = np.asarray([item["loss_mse_nms2"][name] for item in blocks])
        by_model[name] = {
            "rmse_nms": float(np.sqrt(np.mean(losses))),
            "mean_block_mse_nms2": float(np.mean(losses)),
            "median_block_mse_nms2": float(np.median(losses)),
        }
    old = by_model["predecessor"]["mean_block_mse_nms2"]
    successor = by_model["successor"]["mean_block_mse_nms2"]
    candidate = by_model["candidate"]["mean_block_mse_nms2"]
    phases: dict[str, int] = {}
    for block in blocks:
        phases[block["phase"]] = phases.get(block["phase"], 0) + 1
    by_phase = {}
    for phase in phases:
        selected = [item for item in blocks if item["phase"] == phase]
        phase_models = {}
        for name in ("predecessor", "successor", "candidate"):
            losses = np.asarray(
                [item["loss_mse_nms2"][name] for item in selected]
            )
            phase_models[name] = {
                "rmse_nms": float(np.sqrt(np.mean(losses))),
                "mean_block_mse_nms2": float(np.mean(losses)),
            }
        phase_old = phase_models["predecessor"]["mean_block_mse_nms2"]
        phase_successor = phase_models["successor"]["mean_block_mse_nms2"]
        by_phase[phase] = {
            "block_count": len(selected),
            "models": phase_models,
            "successor_mean_paired_improvement_nms2": float(
                phase_old - phase_successor
            ),
            "successor_relative_improvement": (
                None
                if phase_old <= 1.0e-18
                else float((phase_old - phase_successor) / phase_old)
            ),
        }
    return {
        "block_count": len(blocks),
        "phase_block_counts": phases,
        "by_phase": by_phase,
        "models": by_model,
        "successor_mean_paired_improvement_nms2": float(old - successor),
        "successor_relative_improvement": (
            None if old <= 1.0e-18 else float((old - successor) / old)
        ),
        "candidate_mean_paired_improvement_nms2": float(old - candidate),
        "candidate_relative_improvement": (
            None if old <= 1.0e-18 else float((old - candidate) / old)
        ),
    }


def _analyze_case(case: dict[str, Any]) -> dict[str, Any]:
    name = str(case["case"]["name"])
    published = next(
        item
        for item in case["service_summary"]["attempts"]
        if item.get("status") == "published_to_shadow_incumbent"
    )
    identifier = ReducedIntegralScaleIdentifier()
    predecessor = np.asarray(published["reference_incumbent_scales"], dtype=float)
    candidate = np.asarray(published["candidate_scales"], dtype=float)
    transition = build_bounded_human_model_transition(
        identifier,
        predecessor,
        candidate,
        predecessor_version=FIXED_HUMAN_MODEL_VERSION,
        candidate_version=f"{name}:challenger-{published['challenger_index']}",
        successor_version=f"{FIXED_HUMAN_MODEL_VERSION}:{name}:bounded-successor-1",
    )
    successor = np.asarray(transition.successor_scales, dtype=float)
    stored = np.asarray(published["proposed_model_scales"], dtype=float)
    geometry = _geometry()
    prior_beta = nominal_base_parameters(STAGE5_HUMAN)
    projection = dynamic_scale_projection(prior_beta)
    models = {
        "predecessor": predecessor,
        "successor": successor,
        "candidate": candidate,
    }
    trace_path = SOURCE_ROOT / name / "episode_01" / "trace.npz"
    with np.load(trace_path) as loaded:
        trace = {key: loaded[key] for key in loaded.files}

    qualification_windows = published["evidence_history"][-1]["validation_windows"]
    qualification_blocks = [
        block
        for start, end in qualification_windows
        if (
            block := _block(
                trace,
                start_s=float(start),
                end_s=float(end),
                projection=projection,
                scales=models,
                role="candidate_qualification",
            )
        )
        is not None
    ]

    config = Stage5ReducedHumanIDConfig()
    window = config.identifier.integration_window_s
    first_post_start = float(published["decision_time_s"]) + (
        config.validation_embargo_integral_windows * window
    )
    last_time = float(np.asarray(trace["time_s"])[-1])
    post_blocks = []
    start = first_post_start
    while start + window <= last_time + 1.0e-9:
        block = _block(
            trace,
            start_s=start,
            end_s=start + window,
            projection=projection,
            scales=models,
            role="post_decision",
        )
        if block is not None:
            post_blocks.append(block)
        start += window

    paired = np.asarray(
        [
            item["loss_mse_nms2"]["successor"]
            - item["loss_mse_nms2"]["predecessor"]
            for item in post_blocks
        ],
        dtype=float,
    )
    evidence = classify_post_update_evidence(
        paired,
        config=config.trust,
        transition_index=int(published["challenger_index"]),
    )
    minimum_eigenvalues = {}
    for model_name, values in models.items():
        model = BaseParameterHumanModel(
            geometry,
            effective_base_parameters(values, prior_beta),
            STAGE5_HUMAN,
        )
        minimum_eigenvalues[model_name] = float(
            model.minimum_mass_matrix_eigenvalue()
        )
    return {
        "case": name,
        "truth_scales_evaluation_only": case["truth_scales_evaluation_only"],
        "source_trace": str(trace_path.relative_to(STAGE5_ROOT)),
        "historical_attempt": int(published["challenger_index"]),
        "fit_end_time_s": float(published["fit_end_time_s"]),
        "qualification_decision_time_s": float(published["decision_time_s"]),
        "historical_shadow_publication_version": next(
            item["version"]
            for item in case["service_summary"]["publication_history"]
            if abs(float(item["timestamp_s"]) - float(published["decision_time_s"]))
            <= 1.0e-9
        ),
        "transition": transition.to_dict(),
        "reconstructed_successor_matches_historical_proposed_max_abs": float(
            np.max(np.abs(successor - stored))
        ),
        "minimum_mass_matrix_eigenvalue": minimum_eigenvalues,
        "candidate_qualification_blocks": qualification_blocks,
        "candidate_qualification_summary": _summarize_blocks(
            qualification_blocks
        ),
        "genuinely_later_post_decision_blocks": post_blocks,
        "post_decision_summary": _summarize_blocks(post_blocks),
        "post_update_evidence": evidence,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE5_ROOT / "results" / "bounded_human_update_v1",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    saved = json.loads(SOURCE_SUMMARY.read_text(encoding="utf-8"))
    by_name = {str(item["case"]["name"]): item for item in saved["cases"]}
    cases = [_analyze_case(by_name[name]) for name in CASES]
    result = {
        "schema": "stage5_bounded_human_update_offline_audit_v1",
        "source_summary": str(SOURCE_SUMMARY.relative_to(STAGE5_ROOT)),
        "cases": cases,
        "current_control_model_changed": False,
        "shadow_model_applied_to_control": False,
        "new_rehabilitation_episode_run": False,
        "truth_used_for_fit_update_or_evidence": False,
        "truth_parameters_appended_for_evaluation_only": True,
        "state_reconstruction_depends_on_dynamic_scales": False,
        "state_reconstruction_dependency": (
            "nominal Kelvin-Voigt interface inversion plus fixed geometry only"
        ),
        "generalized_input_reconstruction_depends_on_dynamic_scales": False,
        "acceleration_monitor_changed": False,
        "runtime_optimized": False,
    }
    output = args.output_dir / "summary.json"
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
