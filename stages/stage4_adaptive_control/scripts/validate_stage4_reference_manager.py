#!/usr/bin/env python3
"""Short causal replay for the unified Stage-4 Reference Manager."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
from time import perf_counter_ns
from typing import Any

import numpy as np

from scripts.validate_stage4_brake_windows import (
    FIXTURES,
    _estimated_state,
    _initialize,
    _measurement,
    _model,
    _reconstructed_unsafe_action,
    _reference,
)
from traction_mpc_stage4.confidence_execution import UnifiedReferenceManager
from traction_mpc_stage4.cuff_allocator import (
    default_engineering_cuff_allocator,
)
from traction_mpc_stage4.minimal_adaptation import EstimatorConfidence
from traction_mpc_stage4.mpc import SAFE_ACTION
from traction_mpc_stage4.reference import cold_start_teaching_reference
from traction_mpc_stage4.safety_filter import (
    FILTER_INFEASIBLE,
    SAFE_FILTERED,
    SAFE_UNCHANGED,
    filter_executable_command,
    prepare_executable_force_filter_context,
)
from traction_mpc_stage4.track_brake import BRAKE, TrackBrakeSupervisor


def _confidence() -> EstimatorConfidence:
    return EstimatorConfidence(
        parameter_names=("a", "b"),
        sample_count=20,
        parameter_dimension=2,
        rank=2,
        condition_number=2.0,
        residual_rms=0.01,
        covariance=np.eye(2),
        standard_deviation=np.ones(2),
        accepted=True,
        reasons=(),
    )


def _actual_filter_metadata() -> tuple[dict[str, Any], dict[str, Any]]:
    fixture = FIXTURES[0]
    reference = _reference(fixture)
    plant = _initialize(reference)
    measurement = _measurement(plant.observe())
    model = _model()
    allocator = default_engineering_cuff_allocator()
    state = _estimated_state(model, measurement)
    unsafe_action, _ = _reconstructed_unsafe_action(
        fixture=fixture,
        plant=plant,
        measurement=measurement,
        state=state,
        model=model,
        reference=reference,
        allocator=allocator,
    )
    context = prepare_executable_force_filter_context(
        plant=plant,
        measurement=measurement,
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        reference=reference,
    )
    filtered = filter_executable_command(context, unsafe_action)
    if filtered.status != SAFE_FILTERED:
        raise RuntimeError("representative filter signal was not SAFE_FILTERED")
    nominal_action = model.inverse_dynamics(
        state[:2], state[2:], reference.ddq_rad_s2
    )
    unchanged = filter_executable_command(context, nominal_action)
    if unchanged.status != SAFE_UNCHANGED:
        raise RuntimeError("representative nominal signal was not SAFE_UNCHANGED")
    return unchanged.metadata(), filtered.metadata()


def _nominal_and_trust_regression(
    unchanged: dict[str, Any],
) -> dict[str, Any]:
    nominal = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=False,
    )
    nominal_error = {"q": 0.0, "dq": 0.0, "ddq": 0.0, "s": 0.0}
    for time_s in np.arange(0.0, 1.005, 0.005):
        nominal.update_from_safety_filter(time_s, unchanged)
        actual = nominal.reference(time_s)
        expected = cold_start_teaching_reference(time_s)
        nominal_error["q"] = max(
            nominal_error["q"], float(np.max(np.abs(actual.q_rad - expected.q_rad)))
        )
        nominal_error["dq"] = max(
            nominal_error["dq"],
            float(np.max(np.abs(actual.dq_rad_s - expected.dq_rad_s))),
        )
        nominal_error["ddq"] = max(
            nominal_error["ddq"],
            float(np.max(np.abs(actual.ddq_rad_s2 - expected.ddq_rad_s2))),
        )
        nominal_error["s"] = max(
            nominal_error["s"], abs(nominal.phase_time_s(time_s) - time_s)
        )

    baseline = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=True,
    )
    unified = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=True,
    )
    confidence = _confidence()
    trust_errors = {"s": 0.0, "alpha": 0.0, "q": 0.0, "dq": 0.0, "ddq": 0.0}
    trust_update_times = {1.0, 2.0, 3.0, 4.0}
    for time_s in np.arange(0.0, 4.505, 0.005):
        sample_time_s = round(float(time_s), 3)
        unified.update_from_safety_filter(sample_time_s, unchanged)
        if sample_time_s in trust_update_times:
            for manager in (baseline, unified):
                manager.update_from_confidence(
                    sample_time_s,
                    confidence,
                    confidence,
                    geometry_model_valid=True,
                    dynamic_model_valid=True,
                )
        expected_status = baseline.status(sample_time_s)
        actual_status = unified.status(sample_time_s)
        trust_errors["s"] = max(
            trust_errors["s"],
            abs(
                actual_status["reference_phase_time_s"]
                - expected_status["reference_phase_time_s"]
            ),
        )
        trust_errors["alpha"] = max(
            trust_errors["alpha"],
            abs(actual_status["speed_scale"] - expected_status["speed_scale"]),
        )
        expected = baseline.reference(sample_time_s)
        actual = unified.reference(sample_time_s)
        for key, left, right in (
            ("q", actual.q_rad, expected.q_rad),
            ("dq", actual.dq_rad_s, expected.dq_rad_s),
            ("ddq", actual.ddq_rad_s2, expected.ddq_rad_s2),
        ):
            trust_errors[key] = max(
                trust_errors[key], float(np.max(np.abs(left - right)))
            )
    return {
        "nominal_max_abs_error": nominal_error,
        "nominal_exact": all(value == 0.0 for value in nominal_error.values()),
        "confidence_only_max_abs_error": trust_errors,
        "confidence_only_exact": all(
            value == 0.0 for value in trust_errors.values()
        ),
        "confidence_only_regression_tolerance": 1.0e-12,
        "confidence_only_regression_passed": all(
            value <= 1.0e-12 for value in trust_errors.values()
        ),
        "confidence_force_interleaving_hz": 200,
    }


def _intervention_replay(
    unchanged: dict[str, Any],
    filtered: dict[str, Any],
) -> dict[str, Any]:
    manager = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=False,
    )
    # Use a moving section of the unchanged cold-start path.  The original
    # 0--1 s interval is an intentional hold and cannot reveal derivative
    # propagation or reference jerk.
    time = np.arange(4.5, 5.505, 0.005)
    intervention_start_s = 4.75
    intervention_end_s = 5.25
    alpha_cmd = []
    alpha_force = []
    alpha_trust = []
    phase = []
    q_ref = []
    dq_ref = []
    ddq_ref = []
    force_intervention = []
    executable_force = []
    status_history = []
    switch_continuity: list[dict[str, Any]] = []
    previous_filter_status = SAFE_UNCHANGED
    for time_s in time:
        metadata = (
            filtered
            if intervention_start_s <= time_s < intervention_end_s
            else unchanged
        )
        current_status = str(metadata["status"])
        before = manager.reference(time_s)
        manager.update_from_safety_filter(time_s, metadata)
        after = manager.reference(time_s)
        if current_status != previous_filter_status:
            switch_continuity.append(
                {
                    "time_s": float(time_s),
                    "from": previous_filter_status,
                    "to": current_status,
                    "q_jump_rad": float(np.linalg.norm(after.q_rad - before.q_rad)),
                    "dq_jump_rad_s": float(
                        np.linalg.norm(after.dq_rad_s - before.dq_rad_s)
                    ),
                    "ddq_jump_rad_s2": float(
                        np.linalg.norm(after.ddq_rad_s2 - before.ddq_rad_s2)
                    ),
                }
            )
        previous_filter_status = current_status
        state = manager.status(time_s)
        reference = manager.reference(time_s)
        alpha_cmd.append(state["speed_scale"])
        alpha_force.append(state["alpha_force"])
        alpha_trust.append(state["alpha_trust"])
        phase.append(state["reference_phase_time_s"])
        q_ref.append(reference.q_rad)
        dq_ref.append(reference.dq_rad_s)
        ddq_ref.append(reference.ddq_rad_s2)
        force_intervention.append(metadata["force_intervention_norm_n"])
        executable_force.append(metadata["filtered_executable_force_norm_n"])
        status_history.append(current_status)
    q_ref_array = np.asarray(q_ref)
    dq_ref_array = np.asarray(dq_ref)
    ddq_ref_array = np.asarray(ddq_ref)
    reference_jerk = np.gradient(ddq_ref_array, time, axis=0, edge_order=2)
    key_indices = [0, 49, 50, 74, 90, 149, 150, 175, 200]
    return {
        "time_s": time.tolist(),
        "filter_status": status_history,
        "alpha_cmd": alpha_cmd,
        "alpha_trust": alpha_trust,
        "alpha_force": alpha_force,
        "phase_s": phase,
        "force_intervention_norm_n": force_intervention,
        "executable_force_norm_n": executable_force,
        "key_samples": [
            {
                "time_s": float(time[index]),
                "status": status_history[index],
                "alpha_cmd": float(alpha_cmd[index]),
                "alpha_force": float(alpha_force[index]),
                "phase_s": float(phase[index]),
            }
            for index in key_indices
        ],
        "minimum_alpha_cmd": float(np.min(alpha_cmd)),
        "final_alpha_cmd": float(alpha_cmd[-1]),
        "final_phase_lag_s": float(time[-1] - phase[-1]),
        "intervention_window_s": [
            intervention_start_s,
            intervention_end_s,
        ],
        "switch_continuity": switch_continuity,
        "maximum_alpha_step": float(np.max(np.abs(np.diff(alpha_cmd)))),
        "maximum_phase_step_s": float(np.max(np.diff(phase))),
        "maximum_q_step_deg": float(
            np.max(np.linalg.norm(np.degrees(np.diff(q_ref_array, axis=0)), axis=1))
        ),
        "maximum_dq_step_deg_s": float(
            np.max(
                np.linalg.norm(np.degrees(np.diff(dq_ref_array, axis=0)), axis=1)
            )
        ),
        "maximum_ddq_step_deg_s2": float(
            np.max(
                np.linalg.norm(np.degrees(np.diff(ddq_ref_array, axis=0)), axis=1)
            )
        ),
        "reference_jerk_rms_deg_s3": float(
            np.sqrt(np.mean(np.degrees(reference_jerk) ** 2))
        ),
        "reference_jerk_peak_norm_deg_s3": float(
            np.max(np.linalg.norm(np.degrees(reference_jerk), axis=1))
        ),
        "reference_acceleration_rms_deg_s2": float(
            np.sqrt(np.mean(np.degrees(ddq_ref_array) ** 2))
        ),
        "reference_acceleration_peak_norm_deg_s2": float(
            np.max(np.linalg.norm(np.degrees(ddq_ref_array), axis=1))
        ),
    }


def _trust_force_interaction(filtered: dict[str, Any]) -> dict[str, Any]:
    manager = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=True,
    )
    manager.update_from_safety_filter(0.0, filtered)
    initial = manager.status(0.0)
    confidence = _confidence()
    for time_s in (1.0, 2.0):
        manager.update_from_confidence(
            time_s,
            confidence,
            confidence,
            geometry_model_valid=True,
            dynamic_model_valid=True,
        )
    trusted = manager.status(2.0)
    return {
        "initial": {
            "alpha_trust": initial["alpha_trust"],
            "alpha_force": initial["alpha_force"],
            "alpha_cmd": initial["alpha_cmd"],
        },
        "after_trust_cap_recovers": {
            "alpha_trust": trusted["alpha_trust"],
            "alpha_force": trusted["alpha_force"],
            "alpha_cmd": trusted["alpha_cmd"],
        },
        "minimum_rule_exact": bool(
            initial["alpha_cmd"]
            == min(1.0, initial["alpha_trust"], initial["alpha_force"])
            and trusted["alpha_cmd"]
            == min(1.0, trusted["alpha_trust"], trusted["alpha_force"])
        ),
    }


def _infeasible_brake_interface() -> dict[str, Any]:
    fixture = FIXTURES[0]
    reference = _reference(fixture)
    plant = _initialize(reference)
    measurement = _measurement(plant.observe())
    model = _model()
    allocator = default_engineering_cuff_allocator()
    state = _estimated_state(model, measurement)
    target_velocity, _ = model.geometry.cuff_velocity(
        reference.q_rad, reference.dq_rad_s
    )
    impossible = replace(
        measurement,
        attachment_velocity_m_s=(
            target_velocity - np.array([0.0, 2.0, 0.0])
        ),
    )
    context = prepare_executable_force_filter_context(
        plant=plant,
        measurement=impossible,
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        reference=reference,
    )
    action = model.inverse_dynamics(
        state[:2], state[2:], reference.ddq_rad_s2
    )
    result = filter_executable_command(context, action)
    if result.status != FILTER_INFEASIBLE:
        raise RuntimeError("unrecoverable fixture became filter-feasible")
    supervisor = TrackBrakeSupervisor()
    supervisor_decision = supervisor.command(
        plant=plant,
        measurement=impossible,
        estimated_state=state,
        human_model=model,
        cuff_allocator=allocator,
        track_reference=reference,
        proposed_action_nm=action,
        mpc_status=SAFE_ACTION,
    )
    manager = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=False,
    )
    alpha_before = manager.alpha_cmd
    manager_decision = manager.update_from_safety_filter(0.0, result)
    return {
        "filter_status": result.status,
        "reference_manager_brake_required": manager_decision.brake_required,
        "alpha_before": alpha_before,
        "alpha_after": manager.alpha_cmd,
        "alpha_was_not_guessed": manager_decision.alpha_force is None,
        "supervisor_mode": supervisor_decision.mode,
        "supervisor_trigger": supervisor_decision.trigger,
        "existing_brake_entered": supervisor_decision.mode == BRAKE,
        "automatic_return_to_track_implemented": False,
        "future_reentry_checkpoint": manager.brake_reentry_checkpoint(0.0),
    }


def _profile_update(filtered: dict[str, Any], samples: int) -> dict[str, Any]:
    manager = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=False,
    )
    values = np.empty(samples)
    warmup = 100
    for index in range(warmup + samples):
        started = perf_counter_ns()
        manager.update_from_safety_filter(0.005 * index, filtered)
        elapsed_ms = (perf_counter_ns() - started) / 1.0e6
        if index >= warmup:
            values[index - warmup] = elapsed_ms
    return {
        "warmup": warmup,
        "samples": samples,
        "mean_ms": float(np.mean(values)),
        "p95_ms": float(np.percentile(values, 95.0)),
        "max_ms": float(np.max(values)),
        "over_1_ms_count": int(np.count_nonzero(values > 1.0)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile-samples", type=int, default=10000)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    if args.profile_samples <= 0:
        raise ValueError("profile samples must be positive")
    unchanged, filtered = _actual_filter_metadata()
    payload = {
        "evidence_category": (
            "short_causal_reference_manager_engineering_replay_not_scientific"
        ),
        "full_high_rom_rollout_run": False,
        "single_reference_manager": True,
        "nominal_and_trust_regression": _nominal_and_trust_regression(
            unchanged
        ),
        "moderate_intervention_and_recovery": _intervention_replay(
            unchanged, filtered
        ),
        "trust_force_interaction": _trust_force_interaction(filtered),
        "filter_infeasible_brake_interface": _infeasible_brake_interface(),
        "runtime": _profile_update(filtered, args.profile_samples),
        "controller_architecture_unchanged": {
            "cem_solves_per_track_50hz_cycle": 1,
            "additional_cem_or_force_predictor": False,
            "safety_filter_and_brake_200hz_control_law_changed": False,
            "safety_filter_metadata_forwarded_to_reference_manager": True,
        },
        "scientific_variables_changed": [],
        "scientific_variables_explicitly_unchanged": [
            "MPC",
            "Safety Filter",
            "BRAKE",
            "trust equations and thresholds",
            "allocator",
            "gains",
            "200 N hard limit",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
