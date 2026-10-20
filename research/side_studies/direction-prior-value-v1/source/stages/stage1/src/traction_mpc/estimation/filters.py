"""Lightweight observation filters for Spring2D state preprocessing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np

from traction_mpc.common.types import Spring2DObservation


def observation_state(observation: Spring2DObservation) -> np.ndarray:
    return np.array(
        [observation.theta, observation.omega, observation.r, observation.r_dot],
        dtype=float,
    )


class BaseObservationFilter(ABC):
    """Base interface for state-only observation filters."""

    def __init__(self) -> None:
        self.x_hat: np.ndarray | None = None
        self._diagnostics: dict[str, Any] = self._default_diagnostics()

    @staticmethod
    def _default_diagnostics() -> dict[str, Any]:
        return {
            "bias_theta_hat": np.nan,
            "bias_omega_hat": np.nan,
            "bias_r_hat": np.nan,
            "bias_r_dot_hat": np.nan,
            "innovation_norm": np.nan,
            "covariance_trace": np.nan,
            "ukf_failed": False,
        }

    def reset(
        self,
        initial_observation: Spring2DObservation,
        true_state: np.ndarray | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        del true_state, model_params
        self.x_hat = observation_state(initial_observation)
        self._diagnostics = self._default_diagnostics()
        return self.get_state()

    def predict(
        self,
        action: np.ndarray,
        dt: float,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        del action, dt, model_params
        return self.get_state()

    @abstractmethod
    def update(
        self,
        observation: Spring2DObservation,
        dt: float,
        action: np.ndarray | None = None,
        true_state: np.ndarray | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        ...

    def get_state(self) -> np.ndarray:
        if self.x_hat is None:
            raise RuntimeError("Observation filter has not been reset.")
        return self.x_hat.copy()

    def get_diagnostics(self) -> dict[str, Any]:
        diagnostics = self._default_diagnostics()
        diagnostics.update(self._diagnostics)
        return diagnostics


class RawObservationFilter(BaseObservationFilter):
    """Pass raw noisy observations through unchanged."""

    def update(
        self,
        observation: Spring2DObservation,
        dt: float,
        action: np.ndarray | None = None,
        true_state: np.ndarray | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        del dt, action, true_state, model_params
        self.x_hat = observation_state(observation)
        self._diagnostics = self._default_diagnostics()
        return self.get_state()


class LowPassObservationFilter(BaseObservationFilter):
    """First-order low-pass filter over the full Spring2D state."""

    def __init__(self, lambda_gain: float):
        super().__init__()
        self.lambda_gain = float(lambda_gain)

    def update(
        self,
        observation: Spring2DObservation,
        dt: float,
        action: np.ndarray | None = None,
        true_state: np.ndarray | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        del dt, action, true_state, model_params
        y = observation_state(observation)
        if self.x_hat is None:
            self.x_hat = y
        else:
            self.x_hat = (1.0 - self.lambda_gain) * self.x_hat + self.lambda_gain * y
        self.x_hat[2] = max(float(self.x_hat[2]), 1.0e-6)
        self._diagnostics = self._default_diagnostics()
        return self.get_state()


@dataclass(frozen=True)
class AlphaBetaConfig:
    theta_alpha: float
    theta_beta: float
    r_alpha: float
    r_beta: float


class AlphaBetaObservationFilter(BaseObservationFilter):
    """Alpha-beta filters for theta/omega and r/r_dot pairs."""

    def __init__(self, cfg: AlphaBetaConfig):
        super().__init__()
        self.cfg = cfg

    def update(
        self,
        observation: Spring2DObservation,
        dt: float,
        action: np.ndarray | None = None,
        true_state: np.ndarray | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        del action, true_state, model_params
        y = observation_state(observation)
        if self.x_hat is None:
            self.x_hat = y
            self._diagnostics = self._default_diagnostics()
            return self.get_state()

        dt = float(dt)
        if dt <= 0.0:
            raise ValueError("Alpha-beta observation filter requires positive dt.")

        theta_pred = float(self.x_hat[0] + dt * self.x_hat[1])
        omega_pred = float(self.x_hat[1])
        e_theta = float(y[0] - theta_pred)
        theta_hat = theta_pred + self.cfg.theta_alpha * e_theta
        omega_hat = omega_pred + (self.cfg.theta_beta / dt) * e_theta

        r_pred = float(self.x_hat[2] + dt * self.x_hat[3])
        r_dot_pred = float(self.x_hat[3])
        e_r = float(y[2] - r_pred)
        r_hat = r_pred + self.cfg.r_alpha * e_r
        r_dot_hat = r_dot_pred + (self.cfg.r_beta / dt) * e_r

        self.x_hat = np.array([theta_hat, omega_hat, max(r_hat, 1.0e-6), r_dot_hat], dtype=float)
        self._diagnostics = self._default_diagnostics()
        return self.get_state()


class OracleStateFilter(BaseObservationFilter):
    """Simulation-only clean-state reference filter."""

    def reset(
        self,
        initial_observation: Spring2DObservation,
        true_state: np.ndarray | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        del model_params
        if true_state is None:
            raise ValueError("OracleStateFilter requires true_state on reset.")
        del initial_observation
        self.x_hat = np.asarray(true_state, dtype=float).copy()
        self._diagnostics = self._default_diagnostics()
        return self.get_state()

    def update(
        self,
        observation: Spring2DObservation,
        dt: float,
        action: np.ndarray | None = None,
        true_state: np.ndarray | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> np.ndarray:
        del observation, dt, action, model_params
        if true_state is None:
            raise ValueError("OracleStateFilter requires true_state on update.")
        self.x_hat = np.asarray(true_state, dtype=float).copy()
        self._diagnostics = self._default_diagnostics()
        return self.get_state()


def make_observation_filter(cfg: dict[str, Any] | None) -> BaseObservationFilter:
    cfg = dict(cfg or {})
    filter_type = str(cfg.get("type", "raw")).lower()
    if filter_type == "raw":
        return RawObservationFilter()
    if filter_type == "low_pass":
        return LowPassObservationFilter(lambda_gain=float(cfg.get("low_pass_lambda", 0.35)))
    if filter_type == "alpha_beta":
        ab_cfg = dict(cfg.get("alpha_beta", {}))
        return AlphaBetaObservationFilter(
            AlphaBetaConfig(
                theta_alpha=float(ab_cfg.get("theta_alpha", 0.55)),
                theta_beta=float(ab_cfg.get("theta_beta", 0.08)),
                r_alpha=float(ab_cfg.get("r_alpha", 0.55)),
                r_beta=float(ab_cfg.get("r_beta", 0.08)),
            )
        )
    if filter_type == "oracle":
        return OracleStateFilter()
    if filter_type in {"ukf", "ukf_bias"}:
        from traction_mpc.estimation.ukf import BiasAwareUKFStateEstimator, UKFStateEstimator

        condition_name = str(cfg.get("condition_name", cfg.get("_condition_name", ""))).lower()
        if filter_type == "ukf":
            return UKFStateEstimator(dict(cfg.get("ukf", {})), condition_name=condition_name)
        return BiasAwareUKFStateEstimator(dict(cfg.get("ukf_bias", {})), condition_name=condition_name)
    raise ValueError(f"Unknown observation filter type: {filter_type}")
