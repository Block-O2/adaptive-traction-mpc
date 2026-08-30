"""Minimal and state-UKF-assisted integral Stage-4 estimator architectures."""

from __future__ import annotations

from typing import Any

import numpy as np

from traction_mpc_stage3.human import HUMAN, soft_limit_torque

from .estimator_v2 import AccumulatedCuffGeometryEstimator, BaseParameterHumanModel, PlanarCuffGeometry
from .integral_identifier import AccumulatedIntegralBaseDynamicIdentifier
from .state_ukf import StateOnlyHumanUKF, StateUKFConfig


class IntegralAdaptiveHumanEstimator:
    """Shared geometry/integral-dynamics estimator with an optional state UKF."""

    def __init__(
        self,
        initial_position_world_m: np.ndarray,
        initial_rotation_world_from_cuff: np.ndarray,
        initial_q_prior_rad: np.ndarray,
        *,
        use_state_ukf: bool,
        initial_time_s: float = 0.0,
        ukf_config: StateUKFConfig = StateUKFConfig(),
    ) -> None:
        self.use_state_ukf = bool(use_state_ukf)
        self.geometry_identifier = AccumulatedCuffGeometryEstimator(
            initial_position_world_m,
            initial_rotation_world_from_cuff,
            initial_q_prior_rad,
        )
        self.dynamic_identifier = AccumulatedIntegralBaseDynamicIdentifier()
        self.raw_history: list[dict[str, Any]] = []
        initial_state = self.geometry.estimate_state(
            initial_position_world_m,
            initial_rotation_world_from_cuff,
            np.zeros(3),
            np.zeros(3),
        )
        self.state_ukf = (
            StateOnlyHumanUKF(
                initial_state,
                initial_time_s,
                np.zeros(2),
                config=ukf_config,
            )
            if self.use_state_ukf
            else None
        )
        self.last_state = initial_state.copy()
        self.geometry_diagnostics: list[dict[str, Any]] = []
        self.dynamic_diagnostics: list[dict[str, Any]] = []
        self.ukf_diagnostics: list[dict[str, Any]] = []

    @property
    def geometry(self) -> PlanarCuffGeometry:
        return self.geometry_identifier.geometry

    @property
    def model(self) -> BaseParameterHumanModel:
        return BaseParameterHumanModel(
            self.geometry_identifier.geometry,
            self.dynamic_identifier.last_valid.copy(),
        )

    def observe(
        self,
        *,
        time_s: float,
        position_world_m: np.ndarray,
        rotation_world_from_cuff: np.ndarray,
        linear_velocity_world_m_s: np.ndarray,
        angular_velocity_world_rad_s: np.ndarray,
        force_world_n: np.ndarray,
        moment_world_nm: np.ndarray,
        bed_contaminated: bool,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        measured_state = self.geometry.estimate_state(
            position_world_m,
            rotation_world_from_cuff,
            linear_velocity_world_m_s,
            angular_velocity_world_rad_s,
        )
        measured_input = self.geometry.generalized_input_from_wrench(
            measured_state[:2], force_world_n, moment_world_nm
        )
        if self.state_ukf is not None:
            state, ukf_diag = self.state_ukf.step(
                time_s=time_s,
                measured_state=measured_state,
                measured_generalized_input_nm=measured_input,
                model=self.model,
            )
            self.ukf_diagnostics.append(dict(ukf_diag, time_s=float(time_s)))
        else:
            state = measured_state
            ukf_diag = {
                "enabled": False,
                "state_dimension": 0,
                "parameter_state_dimension": 0,
            }

        soft_limit_contaminated = bool(
            np.linalg.norm(soft_limit_torque(state[:2], state[2:], HUMAN)) > 1e-8
        )
        contaminated = bool(bed_contaminated or soft_limit_contaminated)
        geometry_diag = self.geometry_identifier.add_pose(
            time_s,
            position_world_m,
            rotation_world_from_cuff,
            contaminated=contaminated,
        )
        if geometry_diag["attempted"]:
            self.geometry_diagnostics.append(dict(geometry_diag, time_s=float(time_s)))
        if self.state_ukf is None:
            # Architecture A uses the newest last-valid geometry directly.
            state = self.geometry.estimate_state(
                position_world_m,
                rotation_world_from_cuff,
                linear_velocity_world_m_s,
                angular_velocity_world_rad_s,
            )

        raw = {
            "time_s": float(time_s),
            "state": np.asarray(state, dtype=float).copy(),
            "position_world_m": np.asarray(position_world_m, dtype=float).copy(),
            "rotation_world_from_cuff": np.asarray(
                rotation_world_from_cuff, dtype=float
            ).copy(),
            "force_world_n": np.asarray(force_world_n, dtype=float).copy(),
            "moment_world_nm": np.asarray(moment_world_nm, dtype=float).copy(),
            "bed_contaminated": bool(bed_contaminated),
            "soft_limit_contaminated": soft_limit_contaminated,
            "contaminated": contaminated,
        }
        self.raw_history.append(raw)
        self.last_state = np.asarray(state, dtype=float).copy()
        if self.geometry_identifier.trustworthy_time_s is not None:
            dynamic_diag = self.dynamic_identifier.attempt_update(
                self.raw_history, self.geometry
            )
            if dynamic_diag["attempted"]:
                self.dynamic_diagnostics.append(
                    dict(dynamic_diag, time_s=float(time_s))
                )
        else:
            dynamic_diag = self.dynamic_identifier._empty_diagnostics(
                "geometry_not_trustworthy"
            )
        return self.last_state.copy(), {
            "geometry": geometry_diag,
            "dynamics": dynamic_diag,
            "ukf": ukf_diag,
            "bed_contaminated": bool(bed_contaminated),
            "soft_limit_contaminated": soft_limit_contaminated,
        }
