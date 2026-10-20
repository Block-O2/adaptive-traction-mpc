"""Shadow-only low-capacity Human transition residual model."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable

import numpy as np

from .acceleration_semantics import screen_cumulative_prefix_acceleration
from .controller_interface import InterfaceHoldPredictionBatch


RESIDUAL_MODEL_VERSION = "short_horizon_human_dq_residual_ridge_v1"


def _matrix(name: str, value: Any, columns: int | None = None) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.ndim != 2 or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be one finite matrix")
    if columns is not None and result.shape[1] != columns:
        raise ValueError(f"{name} must have {columns} columns")
    return result.copy()


@dataclass(frozen=True)
class StateDependentHumanTransitionResidualV1:
    """One standardized ridge map to four-prefix Human dq residuals."""

    feature_names: tuple[str, ...]
    feature_mean: np.ndarray
    feature_scale: np.ndarray
    support_min_standardized: np.ndarray
    support_max_standardized: np.ndarray
    target_mean_rad_s: np.ndarray
    target_scale_rad_s: np.ndarray
    coefficients: np.ndarray
    ridge: float
    training_group_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        count = len(self.feature_names)
        for name in (
            "feature_mean",
            "feature_scale",
            "support_min_standardized",
            "support_max_standardized",
        ):
            value = np.asarray(getattr(self, name), dtype=float)
            if value.shape != (count,) or not np.all(np.isfinite(value)):
                raise ValueError(f"{name} must be a finite feature vector")
            object.__setattr__(self, name, value.copy())
        if np.any(self.feature_scale <= 0.0):
            raise ValueError("feature_scale must be positive")
        if np.any(self.support_max_standardized < self.support_min_standardized):
            raise ValueError("feature support bounds are reversed")
        for name in ("target_mean_rad_s", "target_scale_rad_s"):
            value = np.asarray(getattr(self, name), dtype=float)
            if value.shape != (8,) or not np.all(np.isfinite(value)):
                raise ValueError(f"{name} must be a finite 8-vector")
            object.__setattr__(self, name, value.copy())
        if np.any(self.target_scale_rad_s <= 0.0):
            raise ValueError("target_scale_rad_s must be positive")
        coefficient = np.asarray(self.coefficients, dtype=float)
        if coefficient.shape != (count + 1, 8) or not np.all(
            np.isfinite(coefficient)
        ):
            raise ValueError("coefficients have inconsistent shape")
        object.__setattr__(self, "coefficients", coefficient.copy())
        if not np.isfinite(self.ridge) or self.ridge <= 0.0:
            raise ValueError("ridge must be finite and positive")

    def predict(self, features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        values = _matrix("features", features, len(self.feature_names))
        standardized = (values - self.feature_mean) / self.feature_scale
        design = np.column_stack([np.ones(len(values)), standardized])
        normalized_target = design @ self.coefficients
        residual = (
            normalized_target * self.target_scale_rad_s[None, :]
            + self.target_mean_rad_s[None, :]
        ).reshape(len(values), 4, 2)
        supported = np.all(
            (standardized >= self.support_min_standardized[None, :] - 1.0e-12)
            & (standardized <= self.support_max_standardized[None, :] + 1.0e-12),
            axis=1,
        )
        return residual, supported

    def with_calibration_support(self, features: np.ndarray) -> "StateDependentHumanTransitionResidualV1":
        values = _matrix("features", features, len(self.feature_names))
        standardized = (values - self.feature_mean) / self.feature_scale
        return replace(
            self,
            support_min_standardized=np.minimum(
                self.support_min_standardized, np.min(standardized, axis=0)
            ),
            support_max_standardized=np.maximum(
                self.support_max_standardized, np.max(standardized, axis=0)
            ),
        )

    def record(self) -> dict[str, Any]:
        return {
            "version": RESIDUAL_MODEL_VERSION,
            "target": "Human dq transition residual at 5/10/15/20 ms",
            "state_dimension": 8,
            "feature_count": len(self.feature_names),
            "feature_names": list(self.feature_names),
            "feature_mean": self.feature_mean,
            "feature_scale": self.feature_scale,
            "support_min_standardized": self.support_min_standardized,
            "support_max_standardized": self.support_max_standardized,
            "target_mean_rad_s": self.target_mean_rad_s,
            "target_scale_rad_s": self.target_scale_rad_s,
            "coefficients": self.coefficients,
            "ridge": self.ridge,
            "training_group_ids": list(self.training_group_ids),
            "online_truth_input": False,
            "independent_force_pose_or_acceleration_head": False,
        }


def fit_state_dependent_human_transition_residual_v1(
    *,
    features: np.ndarray,
    dq_residual_rad_s: np.ndarray,
    feature_names: tuple[str, ...],
    training_group_ids: tuple[str, ...],
    ridge: float = 5.0,
) -> StateDependentHumanTransitionResidualV1:
    x = _matrix("features", features, len(feature_names))
    y = np.asarray(dq_residual_rad_s, dtype=float)
    if y.shape != (len(x), 4, 2) or not np.all(np.isfinite(y)):
        raise ValueError("dq_residual_rad_s must be finite [sample,4,2]")
    y_flat = y.reshape(len(x), 8)
    feature_mean = np.mean(x, axis=0)
    feature_scale = np.std(x, axis=0)
    feature_scale = np.where(feature_scale > 1.0e-9, feature_scale, 1.0)
    x_standardized = (x - feature_mean) / feature_scale
    target_mean = np.mean(y_flat, axis=0)
    target_scale = np.std(y_flat, axis=0)
    target_scale = np.where(target_scale > 1.0e-9, target_scale, 1.0)
    y_standardized = (y_flat - target_mean) / target_scale
    design = np.column_stack([np.ones(len(x)), x_standardized])
    penalty = np.eye(design.shape[1]) * float(ridge)
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(
        design.T @ design + penalty, design.T @ y_standardized
    )
    return StateDependentHumanTransitionResidualV1(
        feature_names=tuple(feature_names),
        feature_mean=feature_mean,
        feature_scale=feature_scale,
        support_min_standardized=np.min(x_standardized, axis=0),
        support_max_standardized=np.max(x_standardized, axis=0),
        target_mean_rad_s=target_mean,
        target_scale_rad_s=target_scale,
        coefficients=coefficients,
        ridge=float(ridge),
        training_group_ids=tuple(training_group_ids),
    )


class ResidualCorrectedPreview:
    """Shadow wrapper applying one learned Human transition residual."""

    def __init__(
        self,
        base_preview: Any,
        model: StateDependentHumanTransitionResidualV1,
        feature_batch: Callable[[np.ndarray], np.ndarray],
        *,
        initial_human_dq_rad_s: np.ndarray,
        acceleration_limits_rad_s2: np.ndarray,
        acceleration_error_margin_rad_s2: np.ndarray,
        cuff_force_error_margin_n: float,
    ) -> None:
        self.base_preview = base_preview
        self.model = model
        self.feature_batch = feature_batch
        self.initial_human_dq_rad_s = np.asarray(
            initial_human_dq_rad_s, dtype=float
        ).copy()
        self.acceleration_limits_rad_s2 = np.asarray(
            acceleration_limits_rad_s2, dtype=float
        ).copy()
        self.acceleration_error_margin_rad_s2 = np.asarray(
            acceleration_error_margin_rad_s2, dtype=float
        ).copy()
        self.cuff_force_error_margin_n = float(cuff_force_error_margin_n)
        if self.initial_human_dq_rad_s.shape != (2,):
            raise ValueError("initial Human dq must be a pair")
        if self.acceleration_limits_rad_s2.shape != (2,):
            raise ValueError("acceleration limits must be a pair")
        if self.acceleration_error_margin_rad_s2.shape != (2,):
            raise ValueError("acceleration margin must be a pair")
        self._last_prediction: InterfaceHoldPredictionBatch | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base_preview, name)

    @property
    def preview(self) -> "ResidualCorrectedPreview":
        return self

    @property
    def last_prediction(self) -> InterfaceHoldPredictionBatch | None:
        return self._last_prediction

    def __call__(self, actions_nm: np.ndarray) -> InterfaceHoldPredictionBatch:
        actions = np.asarray(actions_nm, dtype=float)
        base = self.base_preview(actions)
        if base.prefix_times_s is None or base.predicted_prefix_states_rad_rad_s is None:
            raise RuntimeError("residual correction requires Human prefix states")
        times = np.asarray(base.prefix_times_s, dtype=float)
        features = self.feature_batch(actions)
        dq_residual, supported = self.model.predict(features)
        states = np.asarray(base.predicted_prefix_states_rad_rad_s, dtype=float).copy()
        states[..., 2:] += dq_residual
        q_residual = np.zeros((len(actions), 2), dtype=float)
        previous = np.zeros((len(actions), 2), dtype=float)
        previous_time = 0.0
        for index, time_s in enumerate(times):
            dt = float(time_s - previous_time)
            q_residual += 0.5 * dt * (previous + dq_residual[:, index])
            states[:, index, :2] += q_residual
            previous = dq_residual[:, index]
            previous_time = float(time_s)
        screen = screen_cumulative_prefix_acceleration(
            np.broadcast_to(self.initial_human_dq_rad_s, (len(actions), 2)),
            states[..., 2:],
            times,
            self.acceleration_limits_rad_s2,
        )
        qualified_margin = (
            screen.margin_rad_s2
            - self.acceleration_error_margin_rad_s2[None, None, :]
        )
        acceleration_feasible = np.all(qualified_margin >= -1.0e-12, axis=(1, 2))
        force_margin = (
            np.asarray(base.margin_to_physical_force_gate_n, dtype=float)
            - self.cuff_force_error_margin_n
        )
        feasible = (
            np.asarray(base.executable_batch.feasible, dtype=bool)
            & supported
            & acceleration_feasible
            & (force_margin >= -1.0e-9)
        )
        corrected = replace(
            base,
            feasible=feasible,
            margin_to_physical_force_gate_n=force_margin,
            acceleration_semantics_version=(
                "v2_plus_state_dependent_human_dq_residual_ridge_v1"
            ),
            predicted_prefix_states_rad_rad_s=states,
            predicted_prefix_acceleration_rad_s2=screen.acceleration_rad_s2,
            prefix_acceleration_margin_rad_s2=qualified_margin,
            prefix_acceleration_feasible=acceleration_feasible,
            prediction_supported=supported,
        )
        self._last_prediction = corrected
        return corrected


__all__ = [
    "RESIDUAL_MODEL_VERSION",
    "ResidualCorrectedPreview",
    "StateDependentHumanTransitionResidualV1",
    "fit_state_dependent_human_transition_residual_v1",
]
