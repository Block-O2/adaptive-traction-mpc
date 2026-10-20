"""Causal, shadow-only response windows around Stage-5 execution events.

The observer records an event only after its execution context is known, then
appends samples as they become available.  It never reads future samples,
MuJoCo truth, or model-based acceleration and has no task/abort interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from .split_acceleration_monitor import SplitAccelerationShadowSample


TRANSITION_RESPONSE_WINDOW_S = 0.020
TRANSITION_RESPONSE_VERSION = "transition_response_shadow_v2"

MPC_COMMAND_UPDATE = "MPC_COMMAND_UPDATE"
SUPPORT_LOAD_STATE_TRANSITION = "SUPPORT_LOAD_STATE_TRANSITION"
TASK_PHASE_TRANSITION = "TASK_PHASE_TRANSITION"
INTERFACE_LOADED_TRANSITION = "INTERFACE_LOADED_TRANSITION"
INTERFACE_UNLOADED_TRANSITION = "INTERFACE_UNLOADED_TRANSITION"
EXECUTION_STATE_CHANGE = "EXECUTION_STATE_CHANGE"
ACCELERATION_MONITOR_ABORT = "ACCELERATION_MONITOR_ABORT"
NEAR_LIMIT_BENIGN_TRIGGER = "NEAR_LIMIT_BENIGN_TRIGGER"


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise TypeError(f"unsupported transition metadata value: {type(value)!r}")


def _sample_record(
    sample: SplitAccelerationShadowSample, response_elapsed_s: float
) -> dict[str, Any]:
    return {
        "sample_timestamp_s": float(sample.sample_timestamp_s),
        "response_elapsed_s": float(response_elapsed_s),
        "human_motion_20ms_acceleration_rad_s2": (
            sample.human_motion_acceleration_rad_s2.tolist()
        ),
        "human_motion_20ms_valid": bool(sample.human_motion_valid),
        "human_motion_20ms_history_coverage_s": float(
            sample.human_motion_history_coverage_s
        ),
        "fast_motion_5ms_acceleration_rad_s2": (
            sample.fast_motion_acceleration_rad_s2.tolist()
        ),
        "fast_motion_5ms_valid": bool(sample.fast_motion_valid),
        "fast_alignment_interval_s": float(sample.fast_alignment_interval_s),
        "cuff_wrench_world": sample.cuff_wrench_world.tolist(),
        "cuff_wrench_slew_world_per_s": (
            sample.cuff_wrench_slew_world_per_s.tolist()
        ),
        "interface_translation_human_m": (
            sample.interface_translation_human_m.tolist()
        ),
        "interface_velocity_human_m_s": (
            sample.interface_velocity_human_m_s.tolist()
        ),
        "interface_rotation_human_rad": (
            sample.interface_rotation_human_rad.tolist()
        ),
        "interface_angular_velocity_human_rad_s": (
            sample.interface_angular_velocity_human_rad_s.tolist()
        ),
        "command_wrench_world": sample.command_wrench_world.tolist(),
        "command_wrench_slew_world_per_s": (
            sample.command_wrench_slew_world_per_s.tolist()
        ),
        "robot_joint_torque_command_nm": (
            sample.robot_joint_torque_command_nm.tolist()
        ),
        "robot_joint_torque_slew_nm_s": (
            sample.robot_joint_torque_slew_nm_s.tolist()
        ),
        "robot_joint_torque_available": bool(
            sample.robot_joint_torque_available
        ),
        "robot_joint_torque_slew_valid": bool(
            sample.robot_joint_torque_slew_valid
        ),
    }


def _finite_vector_rows(
    samples: list[dict[str, Any]], field: str
) -> tuple[np.ndarray, np.ndarray]:
    elapsed = np.asarray([sample["response_elapsed_s"] for sample in samples])
    values = np.asarray([sample[field] for sample in samples], dtype=float)
    valid = np.all(np.isfinite(values), axis=1)
    return elapsed[valid], values[valid]


def _vector_shape_features(
    samples: list[dict[str, Any]], field: str
) -> dict[str, Any]:
    """Return threshold-free response-shape descriptors for one vector signal."""

    elapsed, values = _finite_vector_rows(samples, field)
    if not len(elapsed):
        return {
            "valid_sample_count": 0,
            "elapsed_ms": [],
            "l2_trajectory": [],
        }
    norms = np.linalg.norm(values, axis=1)
    peak_index = int(np.argmax(norms))
    centered_time = elapsed - np.mean(elapsed)
    denominator = float(centered_time @ centered_time)
    slopes = (
        np.zeros(values.shape[1])
        if denominator <= 1.0e-18
        else centered_time @ (values - np.mean(values, axis=0)) / denominator
    )
    norm_slope = (
        0.0
        if denominator <= 1.0e-18
        else float(centered_time @ (norms - np.mean(norms)) / denominator)
    )
    return {
        "valid_sample_count": int(len(elapsed)),
        "elapsed_ms": (1000.0 * elapsed).tolist(),
        "l2_trajectory": norms.tolist(),
        "initial_vector": values[0].tolist(),
        "final_vector": values[-1].tolist(),
        "net_change_vector": (values[-1] - values[0]).tolist(),
        "component_linear_slope_per_s": slopes.tolist(),
        "initial_l2": float(norms[0]),
        "final_l2": float(norms[-1]),
        "final_minus_initial_l2": float(norms[-1] - norms[0]),
        "linear_l2_slope_per_s": norm_slope,
        "peak_l2": float(norms[peak_index]),
        "peak_elapsed_ms": float(1000.0 * elapsed[peak_index]),
        "successive_l2_deltas": np.diff(norms).tolist(),
        "trapezoidal_l2_integral": float(np.trapezoid(norms, elapsed)),
    }


def response_shape_features(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe complete causal response shape without adding classifications."""

    fields = (
        "human_motion_20ms_acceleration_rad_s2",
        "fast_motion_5ms_acceleration_rad_s2",
        "cuff_wrench_world",
        "cuff_wrench_slew_world_per_s",
        "interface_translation_human_m",
        "interface_velocity_human_m_s",
        "interface_rotation_human_rad",
        "interface_angular_velocity_human_rad_s",
        "command_wrench_world",
        "command_wrench_slew_world_per_s",
        "robot_joint_torque_command_nm",
        "robot_joint_torque_slew_nm_s",
    )
    return {
        "threshold_free": True,
        "classification_or_gate": None,
        "signals": {
            field: _vector_shape_features(samples, field) for field in fields
        },
    }


@dataclass
class TransitionResponseWindow:
    """One causally accumulated 0--20 ms event response."""

    event_id: int
    event_timestamp_s: float
    labels: tuple[str, ...]
    metadata: dict[str, Any]
    samples: list[dict[str, Any]] = field(default_factory=list)
    complete: bool = False

    def append(self, sample: SplitAccelerationShadowSample) -> None:
        elapsed = float(sample.sample_timestamp_s - self.event_timestamp_s)
        if elapsed < -1.0e-12 or elapsed > TRANSITION_RESPONSE_WINDOW_S + 1.0e-12:
            return
        if self.samples and np.isclose(
            self.samples[-1]["sample_timestamp_s"],
            sample.sample_timestamp_s,
            atol=1.0e-12,
            rtol=0.0,
        ):
            return
        self.samples.append(_sample_record(sample, max(0.0, elapsed)))
        if np.isclose(
            elapsed,
            TRANSITION_RESPONSE_WINDOW_S,
            atol=1.0e-10,
            rtol=0.0,
        ):
            self.complete = True

    def as_record(self) -> dict[str, Any]:
        return _jsonable({
            "event_id": self.event_id,
            "event_timestamp_s": self.event_timestamp_s,
            "labels": list(self.labels),
            "metadata": _jsonable(self.metadata),
            "sample_count": len(self.samples),
            "complete_0_to_20ms": self.complete,
            "samples": list(self.samples),
            "response_shape_features": response_shape_features(self.samples),
        })


class TransitionResponseShadowV2:
    """Record causal event labels and deployable response windows only."""

    version = TRANSITION_RESPONSE_VERSION
    shadow_only = True
    abort_authority = False
    hard_threshold_active = False

    def __init__(self) -> None:
        self._latest_sample: SplitAccelerationShadowSample | None = None
        self._windows: list[TransitionResponseWindow] = []
        self._active: list[TransitionResponseWindow] = []
        self._next_event_id = 1
        self._support_load_state: str | None = None
        self._task_phase: str | None = None
        self._interface_load_state: str | None = None
        self._execution_state: dict[str, str] = {}

    @property
    def windows(self) -> tuple[TransitionResponseWindow, ...]:
        return tuple(self._windows)

    def observe(self, sample: SplitAccelerationShadowSample) -> None:
        if self._latest_sample is not None:
            if sample.sample_timestamp_s < self._latest_sample.sample_timestamp_s - 1e-12:
                raise ValueError("response observer requires causal sample order")
            if np.isclose(
                sample.sample_timestamp_s,
                self._latest_sample.sample_timestamp_s,
                atol=1.0e-12,
                rtol=0.0,
            ):
                return
        self._latest_sample = sample
        still_active = []
        for window in self._active:
            elapsed = sample.sample_timestamp_s - window.event_timestamp_s
            if elapsed <= TRANSITION_RESPONSE_WINDOW_S + 1.0e-12:
                window.append(sample)
            if elapsed < TRANSITION_RESPONSE_WINDOW_S - 1.0e-12:
                still_active.append(window)
        self._active = still_active

    def record_context(
        self,
        *,
        event_timestamp_s: float,
        mpc_command_update: bool,
        support_load_state: str,
        task_phase: str,
        interface_load_state: str,
        execution_state: Mapping[str, str | None],
        metadata: Mapping[str, Any],
    ) -> TransitionResponseWindow | None:
        """Compare only current/past context and start a response if it changed."""

        timestamp = float(event_timestamp_s)
        if self._latest_sample is None or not np.isclose(
            self._latest_sample.sample_timestamp_s,
            timestamp,
            atol=1.0e-10,
            rtol=0.0,
        ):
            raise ValueError("event must be registered at the latest causal sample")
        labels: list[str] = []
        transitions: dict[str, Any] = {}
        if mpc_command_update:
            labels.append(MPC_COMMAND_UPDATE)
        if self._support_load_state is not None and (
            support_load_state != self._support_load_state
        ):
            labels.append(SUPPORT_LOAD_STATE_TRANSITION)
            transitions["support_load_state"] = {
                "before": self._support_load_state,
                "after": support_load_state,
            }
        if self._task_phase is not None and task_phase != self._task_phase:
            labels.append(TASK_PHASE_TRANSITION)
            transitions["task_phase"] = {
                "before": self._task_phase,
                "after": task_phase,
            }
        if self._interface_load_state is not None and (
            interface_load_state != self._interface_load_state
        ):
            labels.append(
                INTERFACE_LOADED_TRANSITION
                if interface_load_state == "LOADED"
                else INTERFACE_UNLOADED_TRANSITION
            )
            transitions["interface_load_state"] = {
                "before": self._interface_load_state,
                "after": interface_load_state,
            }
        for name, value in execution_state.items():
            if value is None:
                continue
            current = str(value)
            if name in self._execution_state and self._execution_state[name] != current:
                labels.append(f"{EXECUTION_STATE_CHANGE}:{name}")
                transitions[name] = {
                    "before": self._execution_state[name],
                    "after": current,
                }
            self._execution_state[name] = current

        self._support_load_state = str(support_load_state)
        self._task_phase = str(task_phase)
        self._interface_load_state = str(interface_load_state)
        if not labels:
            return None
        event_metadata = dict(_jsonable(metadata))
        event_metadata["context_transitions"] = transitions
        event_metadata["support_load_state"] = str(support_load_state)
        event_metadata["task_phase"] = str(task_phase)
        event_metadata["interface_load_state"] = str(interface_load_state)
        event_metadata["execution_state"] = {
            name: value for name, value in self._execution_state.items()
        }
        window = TransitionResponseWindow(
            event_id=self._next_event_id,
            event_timestamp_s=timestamp,
            labels=tuple(dict.fromkeys(labels)),
            metadata=event_metadata,
        )
        self._next_event_id += 1
        window.append(self._latest_sample)
        self._windows.append(window)
        self._active.append(window)
        return window

    def record_acceleration_monitor_abort(
        self, *, event_timestamp_s: float, metadata: Mapping[str, Any]
    ) -> TransitionResponseWindow:
        """Start one diagnostic-only window at an authoritative monitor abort."""

        timestamp = float(event_timestamp_s)
        if self._latest_sample is None or not np.isclose(
            self._latest_sample.sample_timestamp_s,
            timestamp,
            atol=1.0e-10,
            rtol=0.0,
        ):
            raise ValueError("abort event must use the latest causal shadow sample")
        window = TransitionResponseWindow(
            event_id=self._next_event_id,
            event_timestamp_s=timestamp,
            labels=(ACCELERATION_MONITOR_ABORT,),
            metadata=dict(_jsonable(metadata)),
        )
        self._next_event_id += 1
        window.append(self._latest_sample)
        self._windows.append(window)
        self._active.append(window)
        return window

    def record_near_limit_benign_trigger(
        self, *, event_timestamp_s: float, metadata: Mapping[str, Any]
    ) -> TransitionResponseWindow:
        """Start one shadow-only response at a planned non-abort state."""

        timestamp = float(event_timestamp_s)
        if self._latest_sample is None or not np.isclose(
            self._latest_sample.sample_timestamp_s,
            timestamp,
            atol=1.0e-10,
            rtol=0.0,
        ):
            raise ValueError("near-limit event must use the latest causal sample")
        window = TransitionResponseWindow(
            event_id=self._next_event_id,
            event_timestamp_s=timestamp,
            labels=(NEAR_LIMIT_BENIGN_TRIGGER,),
            metadata=dict(_jsonable(metadata)),
        )
        self._next_event_id += 1
        window.append(self._latest_sample)
        self._windows.append(window)
        self._active.append(window)
        return window

    def artifact(self, *, time_origin_s: float = 0.0) -> dict[str, Any]:
        records = [window.as_record() for window in self._windows]
        origin = float(time_origin_s)
        if not np.isfinite(origin):
            raise ValueError("time origin must be finite")
        for record in records:
            record["event_timestamp_s"] -= origin
            for sample in record["samples"]:
                sample["sample_timestamp_s"] -= origin
        label_counts: dict[str, int] = {}
        for window in self._windows:
            for label in window.labels:
                label_counts[label] = label_counts.get(label, 0) + 1
        return _jsonable({
            "schema": TRANSITION_RESPONSE_VERSION,
            "shadow_only": True,
            "abort_authority": False,
            "hard_threshold_active": False,
            "window_s": TRANSITION_RESPONSE_WINDOW_S,
            "causal_append_only": True,
            "event_count": len(records),
            "complete_window_count": sum(window.complete for window in self._windows),
            "partial_window_count": sum(not window.complete for window in self._windows),
            "label_counts": label_counts,
            "events": records,
        })


__all__ = [
    "ACCELERATION_MONITOR_ABORT",
    "EXECUTION_STATE_CHANGE",
    "INTERFACE_LOADED_TRANSITION",
    "INTERFACE_UNLOADED_TRANSITION",
    "MPC_COMMAND_UPDATE",
    "NEAR_LIMIT_BENIGN_TRIGGER",
    "SUPPORT_LOAD_STATE_TRANSITION",
    "TASK_PHASE_TRANSITION",
    "TRANSITION_RESPONSE_VERSION",
    "TRANSITION_RESPONSE_WINDOW_S",
    "TransitionResponseShadowV2",
    "TransitionResponseWindow",
    "response_shape_features",
]
