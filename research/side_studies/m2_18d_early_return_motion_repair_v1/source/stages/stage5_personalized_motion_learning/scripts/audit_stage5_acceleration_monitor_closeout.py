#!/usr/bin/env python3
"""Read-only closeout audit for the Stage-5 acceleration monitor.

The audit aligns saved 5 ms traces at the historically relevant event.  It
does not run a new episode, alter controller authority, or use MuJoCo truth to
construct a deployable signal.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT


RESULTS_ROOT = STAGE5_ROOT / "results"
LIMIT_DEG_S2 = np.array([300.0, 600.0])
SAMPLE_PERIOD_S = 0.005
WINDOW_STEPS = {"5ms": 1, "20ms": 4}


@dataclass(frozen=True)
class CaseSpec:
    name: str
    relative_directory: str
    event_selection: str
    evidence_role: str


CASES = (
    CaseSpec(
        "human_stiffness_plus_15pct",
        "human_id_confidence_pacing_v1_attempt_01/"
        "stiffness_plus_15pct/episode_01",
        "current_monitor",
        "historical_human_mismatch_false_positive",
    ),
    CaseSpec(
        "human_mass_plus_8pct",
        "human_id_confidence_pacing_v1_attempt_01/mass_plus_8pct/episode_01",
        "current_monitor",
        "historical_human_mismatch_false_positive",
    ),
    CaseSpec(
        "human_mixed_effective_scales",
        "human_id_confidence_pacing_v1_attempt_01/"
        "mixed_effective_scales/episode_01",
        "current_monitor",
        "historical_human_mismatch_false_positive",
    ),
    CaseSpec(
        "interface_kt_0p7",
        "interface_mismatch_v1_attempt03/kt_0p7",
        "truth_20ms",
        "retained_true_20ms_human_motion_violation",
    ),
    CaseSpec(
        "interface_low_low_high",
        "acceleration_semantics_v2_targeted_attempt_02/low_low_high/"
        "seed_20260824",
        "truth_5ms",
        "retained_true_short_transient_violation",
    ),
    CaseSpec(
        "interface_kt_1p3",
        "interface_mismatch_v1_attempt03/kt_1p3",
        "current_monitor",
        "historical_monitor_abort_with_short_transient",
    ),
    CaseSpec(
        "posture_benefit_early_outbound_20260919_knee_biased",
        "posture_benefit_v1_formal_attempt_01/early_outbound/"
        "seed_20260919/knee_biased",
        "current_monitor",
        "historical_posture_benefit_monitor_abort",
    ),
    CaseSpec(
        "cr12_provisional_cuff_baseline",
        "cr12_provisional_cuff_baseline_20260918_attempt_02/execution",
        "current_monitor",
        "new_cr12_baseline_monitor_abort",
    ),
)


NEGATIVE_CONTROLS = (
    (
        "human_nominal",
        "human_id_confidence_pacing_v1_attempt_01/nominal/episode_01",
    ),
    (
        "human_damping_plus_20pct",
        "human_id_confidence_pacing_v1_attempt_01/"
        "damping_plus_20pct/episode_01",
    ),
)


def _over_limit(value: np.ndarray) -> bool:
    return bool(np.any(np.abs(value) > LIMIT_DEG_S2))


def _vector(value: np.ndarray) -> list[float] | None:
    array = np.asarray(value, dtype=float)
    return None if not np.all(np.isfinite(array)) else array.tolist()


def _fixed_window(
    time_s: np.ndarray,
    velocity_rad_s: np.ndarray,
    step: int,
) -> np.ndarray:
    result = np.full_like(velocity_rad_s, np.nan, dtype=float)
    if len(time_s) <= step:
        return result
    duration = time_s[step:] - time_s[:-step]
    expected = SAMPLE_PERIOD_S * step
    if not np.allclose(duration, expected, atol=1.0e-10, rtol=0.0):
        raise ValueError("saved trace does not provide an exact fixed window")
    result[step:] = np.degrees(
        (velocity_rad_s[step:] - velocity_rad_s[:-step]) / expected
    )
    return result


def _current_truth_interval(
    time_s: np.ndarray,
    interval_start_s: np.ndarray,
    truth_velocity_rad_s: np.ndarray,
    instantaneous_truth_rad_s2: np.ndarray,
) -> np.ndarray:
    result = np.empty_like(truth_velocity_rad_s, dtype=float)
    for index, (timestamp, start) in enumerate(
        zip(time_s, interval_start_s, strict=True)
    ):
        duration = float(timestamp - start)
        if duration <= 1.0e-12:
            result[index] = np.degrees(instantaneous_truth_rad_s2[index])
            continue
        matches = np.flatnonzero(
            np.isclose(time_s[: index + 1], start, atol=1.0e-10, rtol=0.0)
        )
        if len(matches) != 1:
            raise ValueError("monitor interval start is not a saved sample")
        result[index] = np.degrees(
            (truth_velocity_rad_s[index] - truth_velocity_rad_s[int(matches[0])])
            / duration
        )
    return result


def _first_over(values: np.ndarray) -> int:
    available = np.all(np.isfinite(values), axis=1)
    indices = np.flatnonzero(
        available & np.any(np.abs(np.nan_to_num(values)) > LIMIT_DEG_S2, axis=1)
    )
    if not len(indices):
        raise ValueError("requested event does not exist in saved trace")
    return int(indices[0])


def _event_index(
    selection: str,
    current: np.ndarray,
    truth_windows: dict[str, np.ndarray],
) -> int:
    if selection == "current_monitor":
        return _first_over(current)
    if selection == "truth_20ms":
        return _first_over(truth_windows["20ms"])
    if selection == "truth_5ms":
        return _first_over(truth_windows["5ms"])
    raise ValueError(f"unsupported event selection: {selection}")


def _norm(value: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(value, dtype=float)))


def _slew(
    values: np.ndarray,
    time_s: np.ndarray,
    index: int,
    component: slice | None = None,
) -> float | None:
    if index == 0:
        return None
    delta_t = float(time_s[index] - time_s[index - 1])
    current = np.asarray(values[index], dtype=float)
    previous = np.asarray(values[index - 1], dtype=float)
    if component is not None:
        current = current[component]
        previous = previous[component]
    return _norm(current - previous) / delta_t


def _last_command_change_age_ms(
    command: np.ndarray, time_s: np.ndarray, index: int
) -> float | None:
    if index == 0:
        return None
    delta = np.linalg.norm(np.diff(command[: index + 1], axis=0), axis=1)
    changed = np.flatnonzero(delta > 1.0e-10)
    if not len(changed):
        return None
    change_index = int(changed[-1]) + 1
    return 1000.0 * float(time_s[index] - time_s[change_index])


def _confusion(signal: np.ndarray, truth: np.ndarray) -> dict[str, int]:
    available = np.all(np.isfinite(signal), axis=1) & np.all(
        np.isfinite(truth), axis=1
    )
    signal_over = np.any(np.abs(signal[available]) > LIMIT_DEG_S2, axis=1)
    truth_over = np.any(np.abs(truth[available]) > LIMIT_DEG_S2, axis=1)
    return {
        "available_samples": int(np.count_nonzero(available)),
        "true_positive_samples": int(np.count_nonzero(signal_over & truth_over)),
        "false_positive_samples": int(np.count_nonzero(signal_over & ~truth_over)),
        "false_negative_samples": int(np.count_nonzero(~signal_over & truth_over)),
        "true_negative_samples": int(np.count_nonzero(~signal_over & ~truth_over)),
    }


def _control_context(summary: dict[str, Any], event_time_s: float) -> dict[str, Any]:
    transitions = summary.get("phase_transitions", [])
    nearby = [
        item
        for item in transitions
        if abs(float(item["time_s"]) - event_time_s) <= 0.020 + 1.0e-12
    ]
    human_model_transition = summary.get("human_model_control_transition", {})
    return {
        "nearby_task_phase_transitions_within_20ms": nearby,
        "mpc_status_counts": summary.get("mpc_status_counts"),
        "safety_filter_status_counts": summary.get("safety_filter_status_counts"),
        "brake_event_count": summary.get("brake_event_count"),
        "force_gate_event_count": summary.get("force_gate_event_count"),
        "structural_event_count": summary.get("structural_event_count"),
        "human_model_transition_count": human_model_transition.get(
            "transition_count"
        ),
    }


def _classify_event(
    motion_20ms: np.ndarray,
    truth_20ms: np.ndarray,
    motion_5ms: np.ndarray,
    truth_5ms: np.ndarray,
) -> dict[str, Any]:
    available_20ms = bool(np.all(np.isfinite(truth_20ms)))
    available_5ms = bool(np.all(np.isfinite(truth_5ms)))
    return {
        "deployable_20ms_human_motion_violation": (
            _over_limit(motion_20ms)
            if np.all(np.isfinite(motion_20ms))
            else None
        ),
        "evaluation_truth_20ms_human_motion_violation": (
            _over_limit(truth_20ms) if available_20ms else None
        ),
        "deployable_5ms_short_transient": (
            _over_limit(motion_5ms) if np.all(np.isfinite(motion_5ms)) else None
        ),
        "evaluation_truth_5ms_short_transient": (
            _over_limit(truth_5ms) if available_5ms else None
        ),
    }


def audit_case(spec: CaseSpec) -> dict[str, Any]:
    directory = RESULTS_ROOT / spec.relative_directory
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    with np.load(directory / "trace.npz", allow_pickle=False) as trace:
        time_s = np.asarray(trace["time_s"], dtype=float)
        current = np.degrees(
            np.asarray(trace["deployable_realized_acceleration_rad_s2"], dtype=float)
        )
        estimated_dq = np.asarray(
            trace["estimated_state_rad_rad_s"][:, 2:], dtype=float
        )
        truth_dq = np.asarray(trace["evaluation_human_dq_rad_s"], dtype=float)
        motion_windows = {
            label: _fixed_window(time_s, estimated_dq, step)
            for label, step in WINDOW_STEPS.items()
        }
        truth_windows = {
            label: _fixed_window(time_s, truth_dq, step)
            for label, step in WINDOW_STEPS.items()
        }
        current_truth = _current_truth_interval(
            time_s,
            np.asarray(trace["deployable_acceleration_interval_start_s"], dtype=float),
            truth_dq,
            np.asarray(
                trace["evaluation_only_instantaneous_acceleration_rad_s2"],
                dtype=float,
            ),
        )
        event_index = _event_index(spec.event_selection, current, truth_windows)

        force = np.asarray(trace["physical_cuff_force_world_n"], dtype=float)
        moment = np.asarray(trace["physical_cuff_moment_world_nm"], dtype=float)
        interface_x = np.asarray(
            trace["estimated_interface_translation_human_m"], dtype=float
        )
        interface_v = np.asarray(
            trace["estimated_interface_velocity_human_m_s"], dtype=float
        )
        interface_theta = np.asarray(
            trace["estimated_interface_rotation_human_rad"], dtype=float
        )
        interface_omega = np.asarray(
            trace["estimated_interface_angular_velocity_human_rad_s"], dtype=float
        )
        command = np.asarray(trace["executed_command_wrench_world"], dtype=float)
        action = np.asarray(trace["executed_generalized_action_nm"], dtype=float)
        phase = np.asarray(trace["task_phase"])
        instantaneous_truth = np.degrees(
            np.asarray(
                trace["evaluation_only_instantaneous_acceleration_rad_s2"],
                dtype=float,
            )[event_index]
        )

        result = {
            "name": spec.name,
            "evidence_role": spec.evidence_role,
            "trace_path": str((directory / "trace.npz").relative_to(STAGE5_ROOT)),
            "event_selection": spec.event_selection,
            "event": {
                "timestamp_s": float(time_s[event_index]),
                "task_phase": str(phase[event_index]),
                "current_model_based_acceleration_deg_s2": current[
                    event_index
                ].tolist(),
                "evaluation_truth_on_current_monitor_interval_deg_s2": (
                    current_truth[event_index].tolist()
                ),
                "deployable_history_acceleration_deg_s2": {
                    label: _vector(values[event_index])
                    for label, values in motion_windows.items()
                },
                "evaluation_truth_history_acceleration_deg_s2": {
                    label: _vector(values[event_index])
                    for label, values in truth_windows.items()
                },
                "evaluation_only_mujoco_instantaneous_qacc_deg_s2": (
                    instantaneous_truth.tolist()
                ),
                "cuff_wrench": {
                    "force_norm_n": _norm(force[event_index]),
                    "moment_norm_nm": _norm(moment[event_index]),
                    "force_slew_norm_n_s": _slew(force, time_s, event_index),
                    "moment_slew_norm_nm_s": _slew(moment, time_s, event_index),
                },
                "deployable_interface": {
                    "translation_norm_mm": 1000.0 * _norm(interface_x[event_index]),
                    "translation_rate_norm_mm_s": (
                        1000.0 * _norm(interface_v[event_index])
                    ),
                    "rotation_norm_deg": float(
                        np.degrees(_norm(interface_theta[event_index]))
                    ),
                    "rotation_rate_norm_deg_s": float(
                        np.degrees(_norm(interface_omega[event_index]))
                    ),
                },
                "robot_command": {
                    "force_command_norm_n": _norm(command[event_index, :3]),
                    "moment_command_norm_nm": _norm(command[event_index, 3:]),
                    "force_command_slew_norm_n_s": _slew(
                        command, time_s, event_index, slice(0, 3)
                    ),
                    "moment_command_slew_norm_nm_s": _slew(
                        command, time_s, event_index, slice(3, 6)
                    ),
                    "human_generalized_action_slew_norm_nm_s": _slew(
                        action, time_s, event_index
                    ),
                    "last_command_change_age_ms": _last_command_change_age_ms(
                        command, time_s, event_index
                    ),
                    "last_high_level_action_change_age_ms": (
                        _last_command_change_age_ms(action, time_s, event_index)
                    ),
                    "event_aligned_robot_joint_torque_slew": "unavailable_in_saved_trace",
                },
                "control_context": _control_context(
                    summary, float(time_s[event_index])
                ),
                "window_classification": _classify_event(
                    motion_windows["20ms"][event_index],
                    truth_windows["20ms"][event_index],
                    motion_windows["5ms"][event_index],
                    truth_windows["5ms"][event_index],
                ),
            },
            "whole_trace_20ms_history_confusion": _confusion(
                motion_windows["20ms"], truth_windows["20ms"]
            ),
        }
    return result


def audit_negative_control(name: str, relative_directory: str) -> dict[str, Any]:
    path = RESULTS_ROOT / relative_directory / "trace.npz"
    with np.load(path, allow_pickle=False) as trace:
        time_s = np.asarray(trace["time_s"], dtype=float)
        estimated_dq = np.asarray(
            trace["estimated_state_rad_rad_s"][:, 2:], dtype=float
        )
        truth_dq = np.asarray(trace["evaluation_human_dq_rad_s"], dtype=float)
    signal = _fixed_window(time_s, estimated_dq, WINDOW_STEPS["20ms"])
    truth = _fixed_window(time_s, truth_dq, WINDOW_STEPS["20ms"])
    return {
        "name": name,
        "trace_path": str(path.relative_to(STAGE5_ROOT)),
        "whole_trace_20ms_history_confusion": _confusion(signal, truth),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESULTS_ROOT / "acceleration_monitor_closeout_20260918",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema": "stage5_acceleration_monitor_closeout_v1",
        "saved_trace_only": True,
        "new_episode_run": False,
        "controller_or_monitor_changed": False,
        "registered_limit_deg_s2": LIMIT_DEG_S2.tolist(),
        "registered_human_motion_interval_ms": 20.0,
        "cases": [audit_case(spec) for spec in CASES],
        "preserved_negative_controls": [
            audit_negative_control(*spec) for spec in NEGATIVE_CONTROLS
        ],
        "event_aligned_robot_joint_torque_limitation": (
            "The historical common trace schema records executed Cartesian wrench "
            "but not per-sample robot joint-torque command; no torque slew was invented."
        ),
    }
    output_path = args.output_dir / "acceleration_monitor_closeout.json"
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(output_path)


if __name__ == "__main__":
    main()
