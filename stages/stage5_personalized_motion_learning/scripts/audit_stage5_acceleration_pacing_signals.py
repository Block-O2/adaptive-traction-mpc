#!/usr/bin/env python3
"""Read-only saved-trace audit of Stage-5 acceleration and pacing signals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT


RESULTS_ROOT = STAGE5_ROOT / "results"
LIMIT_DEG_S2 = np.array([300.0, 600.0])
WINDOW_STEPS = {"5ms": 1, "10ms": 2, "15ms": 3, "20ms": 4}
SAMPLE_PERIOD_S = 0.005

TRACE_SPECS = (
    (
        "nominal_human",
        "human_id",
        "human_id_confidence_pacing_v1_attempt_01/nominal/episode_01/trace.npz",
        "near_limit",
    ),
    (
        "damping_plus_20pct_human",
        "human_id",
        "human_id_confidence_pacing_v1_attempt_01/damping_plus_20pct/episode_01/trace.npz",
        "near_limit",
    ),
    (
        "stiffness_plus_15pct_human",
        "human_id",
        "human_id_confidence_pacing_v1_attempt_01/stiffness_plus_15pct/episode_01/trace.npz",
        "online_abort",
    ),
    (
        "mass_plus_8pct_human",
        "human_id",
        "human_id_confidence_pacing_v1_attempt_01/mass_plus_8pct/episode_01/trace.npz",
        "online_abort",
    ),
    (
        "mixed_human",
        "human_id",
        "human_id_confidence_pacing_v1_attempt_01/mixed_effective_scales/episode_01/trace.npz",
        "online_abort",
    ),
    (
        "interface_mismatch_kt_0p7",
        "interface_safety_stress",
        "interface_mismatch_v1_attempt03/kt_0p7/trace.npz",
        "truth_20ms_violation",
    ),
    (
        "interface_mismatch_kt_1p3",
        "interface_safety_stress",
        "interface_mismatch_v1_attempt03/kt_1p3/trace.npz",
        "online_abort",
    ),
    (
        "interface_v2_low_low_high",
        "interface_safety_stress",
        (
            "acceleration_semantics_v2_targeted_attempt_02/low_low_high/"
            "seed_20260824/trace.npz"
        ),
        "truth_5ms_violation",
    ),
)


def _over_limit(values: np.ndarray) -> np.ndarray:
    return np.any(np.abs(values) > LIMIT_DEG_S2, axis=-1)


def _classification(signal: np.ndarray, truth: np.ndarray) -> str:
    signal_over = bool(_over_limit(signal[None, :])[0])
    truth_over = bool(_over_limit(truth[None, :])[0])
    if signal_over and truth_over:
        return "above_limit_true_positive"
    if signal_over:
        return "above_limit_false_positive"
    if truth_over:
        return "below_limit_false_negative"
    return "below_limit_true_negative"


def _fixed_window(
    time_s: np.ndarray,
    velocity_deg_s: np.ndarray,
    step: int,
) -> np.ndarray:
    result = np.full_like(velocity_deg_s, np.nan)
    if len(time_s) <= step:
        return result
    duration = time_s[step:] - time_s[:-step]
    expected = SAMPLE_PERIOD_S * step
    if not np.allclose(duration, expected, atol=1.0e-10, rtol=0.0):
        raise ValueError("saved trace does not support an exact causal window")
    result[step:] = (velocity_deg_s[step:] - velocity_deg_s[:-step]) / expected
    return result


def _current_truth_interval(
    time_s: np.ndarray,
    interval_start_s: np.ndarray,
    truth_velocity_deg_s: np.ndarray,
    truth_instantaneous_deg_s2: np.ndarray,
) -> np.ndarray:
    result = np.empty_like(truth_velocity_deg_s)
    for index, (timestamp, start) in enumerate(
        zip(time_s, interval_start_s, strict=True)
    ):
        duration = float(timestamp - start)
        if duration <= 1.0e-12:
            result[index] = truth_instantaneous_deg_s2[index]
            continue
        matches = np.flatnonzero(
            np.isclose(time_s[: index + 1], start, atol=1.0e-10, rtol=0.0)
        )
        if len(matches) != 1:
            raise ValueError("monitor interval start is not a saved causal sample")
        result[index] = (
            truth_velocity_deg_s[index] - truth_velocity_deg_s[int(matches[0])]
        ) / duration
    return result


def _confusion(signal: np.ndarray, truth: np.ndarray) -> dict[str, Any]:
    available = np.all(np.isfinite(signal), axis=1) & np.all(
        np.isfinite(truth), axis=1
    )
    signal_over = _over_limit(signal[available])
    truth_over = _over_limit(truth[available])
    timestamps = int(np.count_nonzero(available))
    return {
        "available_samples": timestamps,
        "true_positive_samples": int(np.count_nonzero(signal_over & truth_over)),
        "false_positive_samples": int(np.count_nonzero(signal_over & ~truth_over)),
        "false_negative_samples": int(np.count_nonzero(~signal_over & truth_over)),
        "true_negative_samples": int(np.count_nonzero(~signal_over & ~truth_over)),
    }


def _first_detection(time_s: np.ndarray, signal: np.ndarray) -> float | None:
    available = np.all(np.isfinite(signal), axis=1)
    detected = available & _over_limit(np.nan_to_num(signal))
    indices = np.flatnonzero(detected)
    return None if not len(indices) else float(time_s[int(indices[0])])


def _select_event(
    event_kind: str,
    current: np.ndarray,
    truth_windows: dict[str, np.ndarray],
) -> int:
    if event_kind == "near_limit":
        return int(np.argmax(np.max(np.abs(current) / LIMIT_DEG_S2, axis=1)))
    if event_kind == "online_abort":
        indices = np.flatnonzero(_over_limit(current))
    elif event_kind == "truth_20ms_violation":
        indices = np.flatnonzero(_over_limit(truth_windows["20ms"]))
    elif event_kind == "truth_5ms_violation":
        indices = np.flatnonzero(_over_limit(truth_windows["5ms"]))
    else:
        raise ValueError(f"unsupported event kind: {event_kind}")
    if not len(indices):
        raise ValueError(f"saved trace has no requested event: {event_kind}")
    return int(indices[0])


def _vector_or_none(values: np.ndarray) -> list[float] | None:
    if not np.all(np.isfinite(values)):
        return None
    return np.asarray(values, dtype=float).tolist()


def _peak_abs_or_none(values: np.ndarray) -> list[float] | None:
    available = np.all(np.isfinite(values), axis=1)
    if not np.any(available):
        return None
    return np.max(np.abs(values[available]), axis=0).tolist()


def audit_trace(
    name: str,
    evidence_group: str,
    relative_path: str,
    event_kind: str,
) -> dict[str, Any]:
    path = RESULTS_ROOT / relative_path
    with np.load(path) as loaded:
        time_s = np.asarray(loaded["time_s"], dtype=float)
        estimated = np.degrees(
            np.asarray(loaded["estimated_state_rad_rad_s"], dtype=float)
        )
        truth_q = np.degrees(
            np.asarray(loaded["evaluation_human_q_rad"], dtype=float)
        )
        truth_dq = np.degrees(
            np.asarray(loaded["evaluation_human_dq_rad_s"], dtype=float)
        )
        current = np.degrees(
            np.asarray(
                loaded["deployable_realized_acceleration_rad_s2"], dtype=float
            )
        )
        current_truth = _current_truth_interval(
            time_s,
            np.asarray(
                loaded["deployable_acceleration_interval_start_s"], dtype=float
            ),
            truth_dq,
            np.degrees(
                np.asarray(
                    loaded["evaluation_only_instantaneous_acceleration_rad_s2"],
                    dtype=float,
                )
            ),
        )

    motion_windows = {
        label: _fixed_window(time_s, estimated[:, 2:], step)
        for label, step in WINDOW_STEPS.items()
    }
    truth_windows = {
        label: _fixed_window(time_s, truth_dq, step)
        for label, step in WINDOW_STEPS.items()
    }
    event_index = _select_event(event_kind, current, truth_windows)
    event_windows = {}
    for label in WINDOW_STEPS:
        signal = motion_windows[label][event_index]
        truth = truth_windows[label][event_index]
        event_windows[label] = {
            "motion_history_acceleration_deg_s2": _vector_or_none(signal),
            "truth_interval_acceleration_deg_s2": _vector_or_none(truth),
            "classification": (
                "unavailable"
                if not np.all(np.isfinite(signal))
                else _classification(signal, truth)
            ),
        }

    return {
        "name": name,
        "evidence_group": evidence_group,
        "trace_path": str(path.relative_to(STAGE5_ROOT)),
        "sample_period_s": SAMPLE_PERIOD_S,
        "event": {
            "selection": event_kind,
            "timestamp_s": float(time_s[event_index]),
            "estimated_q_deg": estimated[event_index, :2].tolist(),
            "estimated_dq_deg_s": estimated[event_index, 2:].tolist(),
            "truth_q_deg": truth_q[event_index].tolist(),
            "truth_dq_deg_s": truth_dq[event_index].tolist(),
            "current_online_acceleration_deg_s2": current[event_index].tolist(),
            "current_truth_interval_acceleration_deg_s2": current_truth[
                event_index
            ].tolist(),
            "current_classification": _classification(
                current[event_index], current_truth[event_index]
            ),
            "fixed_windows": event_windows,
        },
        "whole_trace": {
            "current_online": {
                "peak_abs_deg_s2": np.max(np.abs(current), axis=0).tolist(),
                "truth_peak_abs_same_interval_deg_s2": np.max(
                    np.abs(current_truth), axis=0
                ).tolist(),
                "first_detection_s": _first_detection(time_s, current),
                "truth_first_violation_same_interval_s": _first_detection(
                    time_s, current_truth
                ),
                "confusion": _confusion(current, current_truth),
            },
            "motion_history": {
                label: {
                    "peak_abs_deg_s2": _peak_abs_or_none(signal),
                    "truth_peak_abs_same_window_deg_s2": _peak_abs_or_none(
                        truth_windows[label]
                    ),
                    "first_detection_s": _first_detection(time_s, signal),
                    "truth_first_violation_same_window_s": _first_detection(
                        time_s, truth_windows[label]
                    ),
                    "confusion": _confusion(signal, truth_windows[label]),
                }
                for label, signal in motion_windows.items()
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESULTS_ROOT / "acceleration_pacing_signal_audit_v1",
    )
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    traces = [audit_trace(*spec) for spec in TRACE_SPECS]
    payload = {
        "schema": "stage5_acceleration_pacing_signal_audit_v1",
        "saved_trace_only": True,
        "new_episode_run": False,
        "registered_limit_deg_s2": LIMIT_DEG_S2.tolist(),
        "motion_history_uses_future_samples": False,
        "fixed_window_interpolation_used": False,
        "traces": traces,
    }
    output = args.output_dir / "acceleration_signal_audit.json"
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(output)


if __name__ == "__main__":
    main()
