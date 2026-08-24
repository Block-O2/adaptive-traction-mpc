"""Adaptive MPC wrapper for Spring2D parameter-estimation experiments."""

from __future__ import annotations

from typing import Any

import numpy as np

from traction_mpc.common.types import Spring2DObservation
from traction_mpc.mpc.base_mpc import BaseMPC
from traction_mpc.mpc.fixed_mpc import FixedModelMPC


class AdaptiveMPC(BaseMPC):
    """Fixed-model MPC whose prediction parameters can be updated online."""

    estimated_parameter_names = ("m", "k", "b_r")

    def __init__(self, initial_model_params: dict[str, Any], mpc_params: dict[str, Any]):
        super().__init__(initial_model_params, mpc_params)
        self.current_model_params = dict(initial_model_params)
        self.controller = FixedModelMPC(self.current_model_params, self.mpc_params)
        self.last_update_diagnostics: dict[str, Any] = {}

    def reset(self) -> None:
        self.current_model_params = dict(self.model_params)
        self.controller = FixedModelMPC(self.current_model_params, self.mpc_params)
        self.controller.reset()
        self.last_update_diagnostics = {}

    def act(self, observation: Spring2DObservation) -> np.ndarray:
        return self.controller.act(observation)

    def set_target_theta(self, target_theta: float) -> None:
        self.controller.set_target_theta(float(target_theta))

    def get_last_solve_diagnostics(self) -> dict[str, Any]:
        return self.controller.get_last_diagnostics()

    def get_last_update_diagnostics(self) -> dict[str, Any]:
        return dict(self.last_update_diagnostics)

    def update_parameters(
        self,
        theta_hat: dict[str, float],
        alpha: float,
        bounds: dict[str, list[float] | tuple[float, float]] | None = None,
    ) -> dict[str, float]:
        """Smoothly update MPC prediction parameters from identifier output."""

        alpha_clipped = float(np.clip(alpha, 0.0, 1.0))
        new_params = dict(self.current_model_params)
        for name in self.estimated_parameter_names:
            old_value = float(self.current_model_params[name])
            target_value = float(theta_hat[name])
            smoothed = (1.0 - alpha_clipped) * old_value + alpha_clipped * target_value
            if bounds and name in bounds:
                lower, upper = bounds[name]
                smoothed = float(np.clip(smoothed, float(lower), float(upper)))
            new_params[name] = smoothed

        previous_last_action = self.controller.last_action.copy()
        previous_last_solution_existed = self.controller.last_result is not None
        self.current_model_params = new_params
        self.controller.set_model_params({
            name: float(new_params[name])
            for name in self.estimated_parameter_names
        })
        self.last_update_diagnostics = {
            "mpc_recreated_on_update": False,
            "solver_recreated_on_update": False,
            "last_action_preserved_on_update": bool(np.allclose(self.controller.last_action, previous_last_action)),
            "last_solution_existed_before_update": bool(previous_last_solution_existed),
            "last_solution_preserved_on_update": bool(previous_last_solution_existed and self.controller.last_result is not None),
        }
        return self.get_current_parameter_estimate()

    def get_current_parameter_estimate(self) -> dict[str, float]:
        return {
            name: float(self.current_model_params[name])
            for name in self.estimated_parameter_names
        }
