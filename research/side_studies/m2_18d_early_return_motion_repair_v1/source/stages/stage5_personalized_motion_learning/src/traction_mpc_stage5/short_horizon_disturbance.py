"""Shadow-only causal low-dimensional short-horizon disturbance observer."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from traction_mpc_stage3.executable_command import DEFAULT_LOW_LEVEL_COMMAND_GAINS

from .controller_interface import InterfaceHoldPredictionBatch


DISTURBANCE_OBSERVER_VERSION = "short_horizon_disturbance_observer_v1"


def _vector(name: str, value: Any, size: int) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite {size}-vector")
    return result.copy()


def predicted_physical_cuff_wrench_world(
    preview: Any, prediction: InterfaceHoldPredictionBatch
) -> np.ndarray:
    """Return exact captured prefix wrench, or reconstruct diagnostic endpoints."""

    if prediction.predicted_prefix_physical_cuff_wrench_world is not None:
        return np.asarray(
            prediction.predicted_prefix_physical_cuff_wrench_world, dtype=float
        ).copy()
    states = prediction.predicted_prefix_states_rad_rad_s
    x = prediction.predicted_prefix_interface_displacement_human_m
    u = prediction.predicted_prefix_interface_velocity_human_m_s
    theta = prediction.predicted_prefix_interface_rotation_human_rad
    omega = prediction.predicted_prefix_interface_angular_velocity_human_rad_s
    if any(value is None for value in (states, x, u, theta, omega)):
        raise RuntimeError("physical cuff wrench requires captured prefix diagnostics")
    states_array = np.asarray(states, dtype=float)
    count, prefix_count, _ = states_array.shape
    traces = getattr(preview, "last_prefix_substep_traces", ())
    if len(traces) == prefix_count and all(
        np.asarray(trace).shape[1] == count for trace in traces
    ):
        return np.stack(
            [np.asarray(trace, dtype=float)[-1, :, 16:22] for trace in traces],
            axis=1,
        )
    parameters = preview.predictor.parameters
    x_array = np.asarray(x, dtype=float)
    u_array = np.asarray(u, dtype=float)
    theta_array = np.asarray(theta, dtype=float)
    omega_array = np.asarray(omega, dtype=float)
    force_human = (
        np.asarray(parameters.translation_stiffness_n_m)[None, None, :]
        * (x_array - np.asarray(parameters.rest_translation_human_m)[None, None, :])
        + np.asarray(parameters.translation_damping_ns_m)[None, None, :] * u_array
    )
    couple_human = parameters.rotation_stiffness_nm_rad * (
        theta_array
        - np.asarray(parameters.rest_rotation_rotvec_human_rad)[None, None, :]
    ) + parameters.rotation_damping_nms_rad * omega_array
    moment_human = couple_human + np.cross(
        x_array + np.asarray(parameters.rest_translation_human_m)[None, None, :],
        force_human,
    )
    _, rotation = preview._prefix_geometry_batch(
        states_array[..., :2].reshape(-1, 2)
    )
    rotation = rotation.reshape(count, prefix_count, 3, 3)
    return np.concatenate(
        [
            np.einsum("ntij,ntj->nti", rotation, force_human),
            np.einsum("ntij,ntj->nti", rotation, moment_human),
        ],
        axis=2,
    )


@dataclass(frozen=True)
class ShortHorizonDisturbanceState:
    """Five deployable residual coordinates with explicit history validity."""

    human_acceleration_residual_rad_s2: np.ndarray
    cuff_force_residual_world_n: np.ndarray
    history_coverage_s: float
    update_count: int
    valid: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "human_acceleration_residual_rad_s2",
            _vector(
                "human_acceleration_residual_rad_s2",
                self.human_acceleration_residual_rad_s2,
                2,
            ),
        )
        object.__setattr__(
            self,
            "cuff_force_residual_world_n",
            _vector(
                "cuff_force_residual_world_n",
                self.cuff_force_residual_world_n,
                3,
            ),
        )
        if not np.isfinite(self.history_coverage_s) or self.history_coverage_s < 0.0:
            raise ValueError("history_coverage_s must be finite and nonnegative")
        if self.update_count < 0:
            raise ValueError("update_count must be nonnegative")

    @property
    def vector(self) -> np.ndarray:
        return np.concatenate(
            [
                self.human_acceleration_residual_rad_s2,
                self.cuff_force_residual_world_n,
            ]
        )


class CausalShortHorizonDisturbanceObserver:
    """EMA observer driven only by one-step deployable prediction innovations."""

    def __init__(
        self,
        *,
        control_dt_s: float = 0.005,
        time_constant_s: float = 0.020,
        minimum_history_s: float = 0.020,
    ) -> None:
        for name, value in (
            ("control_dt_s", control_dt_s),
            ("time_constant_s", time_constant_s),
            ("minimum_history_s", minimum_history_s),
        ):
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        self.control_dt_s = float(control_dt_s)
        self.time_constant_s = float(time_constant_s)
        self.minimum_history_s = float(minimum_history_s)
        self.alpha = float(1.0 - np.exp(-control_dt_s / time_constant_s))
        self.reset()

    def reset(self) -> None:
        self._estimate = np.zeros(5, dtype=float)
        self._coverage_s = 0.0
        self._update_count = 0

    @property
    def state(self) -> ShortHorizonDisturbanceState:
        return ShortHorizonDisturbanceState(
            human_acceleration_residual_rad_s2=self._estimate[:2],
            cuff_force_residual_world_n=self._estimate[2:],
            history_coverage_s=self._coverage_s,
            update_count=self._update_count,
            valid=self._coverage_s + 1.0e-12 >= self.minimum_history_s,
        )

    def update(
        self,
        *,
        previous_predicted_human_dq_rad_s: np.ndarray,
        measured_human_dq_hat_rad_s: np.ndarray,
        previous_predicted_cuff_force_world_n: np.ndarray,
        measured_cuff_force_world_n: np.ndarray,
        prediction_supported: bool,
    ) -> ShortHorizonDisturbanceState:
        predicted_dq = _vector(
            "previous_predicted_human_dq_rad_s",
            previous_predicted_human_dq_rad_s,
            2,
        )
        measured_dq = _vector(
            "measured_human_dq_hat_rad_s", measured_human_dq_hat_rad_s, 2
        )
        predicted_force = _vector(
            "previous_predicted_cuff_force_world_n",
            previous_predicted_cuff_force_world_n,
            3,
        )
        measured_force = _vector(
            "measured_cuff_force_world_n", measured_cuff_force_world_n, 3
        )
        if not prediction_supported:
            self._estimate.fill(0.0)
            self._coverage_s = 0.0
            self._update_count = 0
            return self.state
        innovation = np.concatenate(
            [
                (measured_dq - predicted_dq) / self.control_dt_s,
                measured_force - predicted_force,
            ]
        )
        self._estimate += self.alpha * (innovation - self._estimate)
        self._coverage_s += self.control_dt_s
        self._update_count += 1
        return self.state

    def record(self) -> dict[str, Any]:
        return {
            "version": DISTURBANCE_OBSERVER_VERSION,
            "state_dimension": 5,
            "coordinates": ["hip_accel", "knee_accel", "cuff_fx", "cuff_fy", "cuff_fz"],
            "online_inputs": {
                "base_predictor": (
                    "deployable robot q/dq, cuff pose/twist/wrench, Human "
                    "q_hat/dq_hat, current/previous command, and interface state; "
                    "the unchanged default preview may use only its existing subset"
                ),
                "observer_innovation": (
                    "previous predicted +5 ms Human dq and cuff force versus "
                    "current deployable dq_hat and measured cuff force"
                ),
            },
            "outputs": (
                "constant 0-20 ms corrections to Human acceleration and WORLD "
                "cuff force, applied at 5/10/15/20 ms"
            ),
            "command_semantics": (
                "candidate Human action held 20 ms; executable wrench and joint "
                "torque refreshed every 5 ms and held over each 5 ms interval"
            ),
            "operating_range": (
                "registered Stage-5 OUTBOUND states with finite deployable history; "
                "HOLD and RETURN are unvalidated"
            ),
            "control_dt_s": self.control_dt_s,
            "time_constant_s": self.time_constant_s,
            "minimum_history_s": self.minimum_history_s,
            "alpha": self.alpha,
            "truth_input": False,
        }


class DisturbanceCorrectedPreview:
    """Protocol wrapper applying one frozen disturbance state to base predictions."""

    def __init__(
        self,
        base_preview: Any,
        state: ShortHorizonDisturbanceState,
        *,
        acceleration_error_margin_rad_s2: np.ndarray | None = None,
        cuff_force_error_margin_n: float = 0.0,
    ) -> None:
        self.base_preview = base_preview
        self.state = state
        self.acceleration_error_margin_rad_s2 = _vector(
            "acceleration_error_margin_rad_s2",
            (
                np.zeros(2)
                if acceleration_error_margin_rad_s2 is None
                else acceleration_error_margin_rad_s2
            ),
            2,
        )
        if np.any(self.acceleration_error_margin_rad_s2 < 0.0):
            raise ValueError("acceleration error margin must be nonnegative")
        if not np.isfinite(cuff_force_error_margin_n) or cuff_force_error_margin_n < 0.0:
            raise ValueError("cuff force error margin must be finite and nonnegative")
        self.cuff_force_error_margin_n = float(cuff_force_error_margin_n)
        self._last_prediction: InterfaceHoldPredictionBatch | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base_preview, name)

    @property
    def last_prediction(self) -> InterfaceHoldPredictionBatch | None:
        return self._last_prediction

    @property
    def preview(self) -> "DisturbanceCorrectedPreview":
        return self

    def __call__(self, actions_nm: np.ndarray) -> InterfaceHoldPredictionBatch:
        base = self.base_preview(actions_nm)
        if base.prefix_times_s is None:
            raise RuntimeError("disturbance correction requires prefix times")
        if base.predicted_prefix_states_rad_rad_s is None:
            raise RuntimeError("disturbance correction requires Human prefixes")
        if base.predicted_prefix_executable_wrench_world is None:
            raise RuntimeError("disturbance correction requires command prefixes")
        times = np.asarray(base.prefix_times_s, dtype=float)
        states = np.asarray(base.predicted_prefix_states_rad_rad_s, dtype=float).copy()
        wrench = predicted_physical_cuff_wrench_world(self.base_preview, base)
        acceleration = np.asarray(
            base.predicted_prefix_acceleration_rad_s2, dtype=float
        ).copy()
        if self.state.valid:
            disturbance = self.state.human_acceleration_residual_rad_s2
            states[..., :2] += (
                0.5 * times[None, :, None] ** 2 * disturbance[None, None, :]
            )
            states[..., 2:] += times[None, :, None] * disturbance[None, None, :]
            acceleration += disturbance[None, None, :]
            wrench[..., :3] += self.state.cuff_force_residual_world_n[None, None, :]
        qualified_margin = (
            np.asarray(self.base_preview.acceleration_limits_rad_s2)[None, None, :]
            - np.abs(acceleration)
            - self.acceleration_error_margin_rad_s2[None, None, :]
        )
        acceleration_feasible = np.all(qualified_margin >= -1.0e-12, axis=(1, 2))
        force_norm = np.linalg.norm(wrench[..., :3], axis=2)
        moment_norm = np.linalg.norm(wrench[..., 3:], axis=2)
        peak_force = np.max(force_norm, axis=1)
        peak_moment = np.max(moment_norm, axis=1)
        force_margin = (
            self.base_preview.predictor.planning_force_ceiling_n
            - peak_force
            - self.cuff_force_error_margin_n
        )
        command = np.asarray(base.predicted_prefix_executable_wrench_world, dtype=float)
        gains = DEFAULT_LOW_LEVEL_COMMAND_GAINS
        future_command_feasible = np.all(
            np.linalg.norm(command[..., :3], axis=2)
            <= gains.translational_force_gate_n + gains.force_gate_tolerance_n,
            axis=1,
        )
        feasible = (
            np.asarray(base.executable_batch.feasible, dtype=bool)
            & (
                np.ones(len(base.feasible), dtype=bool)
                if base.prediction_supported is None
                else np.asarray(base.prediction_supported, dtype=bool)
            )
            & future_command_feasible
            & acceleration_feasible
            & (force_margin >= -1.0e-9)
            & bool(self.state.valid)
        )
        mean_wrench = np.mean(wrench, axis=1)
        corrected = replace(
            base,
            feasible=feasible,
            predicted_peak_force_n=peak_force,
            predicted_endpoint_force_world_n=wrench[:, -1, :3],
            predicted_mean_force_world_n=mean_wrench[:, :3],
            predicted_peak_moment_nm=peak_moment,
            predicted_endpoint_moment_world_nm=wrench[:, -1, 3:],
            predicted_mean_moment_world_nm=mean_wrench[:, 3:],
            margin_to_physical_force_gate_n=force_margin,
            acceleration_semantics_version=(
                "rigid_body_plus_causal_5d_disturbance_v1"
            ),
            predicted_prefix_states_rad_rad_s=states,
            predicted_prefix_acceleration_rad_s2=acceleration,
            prefix_acceleration_margin_rad_s2=qualified_margin,
            prefix_acceleration_feasible=acceleration_feasible,
            predicted_prefix_physical_cuff_wrench_world=wrench,
            prediction_supported=(
                np.ones(len(base.feasible), dtype=bool)
                if base.prediction_supported is None
                else np.asarray(base.prediction_supported, dtype=bool)
            ),
        )
        self._last_prediction = corrected
        return corrected


__all__ = [
    "CausalShortHorizonDisturbanceObserver",
    "DISTURBANCE_OBSERVER_VERSION",
    "DisturbanceCorrectedPreview",
    "ShortHorizonDisturbanceState",
    "predicted_physical_cuff_wrench_world",
]
