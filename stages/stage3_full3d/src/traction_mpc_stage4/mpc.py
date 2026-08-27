"""Constrained Human-space MPC used by fixed and adaptive Stage-4 controllers."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Literal

import numpy as np

from traction_mpc_stage3.human import (
    CUFF_TRANSLATIONAL_FORCE_GATE_N,
    HUMAN,
    TRACKING_KD_RAD_S2_PER_RAD_S,
    TRACKING_KP_RAD_S2_PER_RAD,
    HumanV2Parameters,
)
from traction_mpc_stage3.reference import CuffPoseReference, _world_from_cuff

from .cuff_allocator import CuffAwareSagittalAllocator, default_engineering_cuff_allocator
from .estimator_v2 import BaseParameterHumanModel
from .human_model import allocate_generalized_action, inverse_dynamics, step_dynamics
from .surface_loads import CylindricalSurfaceConfig, CylindricalSurfaceLoadModel


def _step_model(state: np.ndarray, action: np.ndarray, dt_s: float, human: Any) -> np.ndarray:
    if hasattr(human, "step_dynamics"):
        return human.step_dynamics(state, action, dt_s)
    return step_dynamics(state, action, dt_s, human)


def _inverse_model(
    q_rad: np.ndarray,
    dq_rad_s: np.ndarray,
    ddq_rad_s2: np.ndarray,
    human: Any,
) -> np.ndarray:
    if hasattr(human, "inverse_dynamics"):
        return human.inverse_dynamics(q_rad, dq_rad_s, ddq_rad_s2)
    return inverse_dynamics(q_rad, dq_rad_s, ddq_rad_s2, human)


def _allocate_model(action: np.ndarray, q_rad: np.ndarray, human: Any) -> dict[str, Any]:
    if hasattr(human, "allocate_generalized_action"):
        return human.allocate_generalized_action(action, q_rad)
    return allocate_generalized_action(action, q_rad, human)


@dataclass(frozen=True)
class HumanMPCConfig:
    prediction_dt_s: float = 0.02
    horizon_steps: int = 15
    candidate_count: int = 32
    elite_count: int = 6
    cem_iterations: int = 2
    exploration_std_nm: tuple[float, float] = (10.0, 5.0)
    exploration_std_floor_nm: tuple[float, float] = (1.0, 0.5)
    random_seed: int = 20260824
    q_error_scale_rad: tuple[float, float] = (np.radians(2.0), np.radians(2.0))
    dq_error_scale_rad_s: tuple[float, float] = (np.radians(8.0), np.radians(8.0))
    action_scale_nm: tuple[float, float] = (60.0, 30.0)
    action_rate_scale_nm: tuple[float, float] = (20.0, 10.0)
    action_weight: float = 2.0e-3
    action_rate_weight: float = 5.0e-3
    resultant_force_weight: float = 0.0
    cylindrical_surface_effort_weight: float = 0.0
    wrench_slew_weight: float = 0.0
    cylindrical_cuff_length_m: float = 0.080
    interaction_force_normalization_n: float = CUFF_TRANSLATIONAL_FORCE_GATE_N

    def __post_init__(self) -> None:
        interaction_weights = (
            self.resultant_force_weight,
            self.cylindrical_surface_effort_weight,
            self.wrench_slew_weight,
        )
        if any(weight < 0.0 for weight in interaction_weights):
            raise ValueError("interaction weights must be nonnegative")
        if self.cylindrical_cuff_length_m <= 0.0:
            raise ValueError("cylindrical cuff length must be positive")
        if self.interaction_force_normalization_n <= 0.0:
            raise ValueError("interaction force normalization must be positive")

    @property
    def interaction_aware(self) -> bool:
        return bool(
            self.resultant_force_weight > 0.0
            or self.cylindrical_surface_effort_weight > 0.0
            or self.wrench_slew_weight > 0.0
        )

    def objective_contract(self) -> dict[str, Any]:
        return {
            "tracking": (
                "sum(||(q-q_ref)/q_scale||^2 + "
                "||(dq-dq_ref)/dq_scale||^2)"
            ),
            "generalized_action": (
                "action_weight * sum(||u/action_scale||^2)"
            ),
            "generalized_action_slew": (
                "action_rate_weight * sum(||delta_u/action_rate_scale||^2)"
            ),
            "resultant_cuff_force": (
                "resultant_force_weight * sum(||F||^2/F_normalization^2)"
            ),
            "equivalent_cylindrical_surface_effort": (
                "cylindrical_surface_effort_weight * "
                "sum(||A_dagger*w_cuff||^2/F_normalization^2)"
            ),
            "wrench_slew": (
                "wrench_slew_weight * sum((||delta_F_world||^2 + "
                "||delta_M_world/r_cuff||^2)/F_normalization^2)"
            ),
            "surface_proxy_interpretation": (
                "minimum-norm equivalent cylindrical patch-force effort; "
                "not pressure and not a comfort or tissue-load measurement"
            ),
            "raw_shear_comfort_metric_used": False,
            "weights": {
                "action_weight": self.action_weight,
                "action_rate_weight": self.action_rate_weight,
                "resultant_force_weight": self.resultant_force_weight,
                "cylindrical_surface_effort_weight": (
                    self.cylindrical_surface_effort_weight
                ),
                "wrench_slew_weight": self.wrench_slew_weight,
            },
            "normalization": {
                "q_error_scale_rad": list(self.q_error_scale_rad),
                "dq_error_scale_rad_s": list(self.dq_error_scale_rad_s),
                "action_scale_nm": list(self.action_scale_nm),
                "action_rate_scale_nm": list(self.action_rate_scale_nm),
                "interaction_force_normalization_n": (
                    self.interaction_force_normalization_n
                ),
                "moment_to_force_lever_arm_m": CylindricalSurfaceConfig(
                    self.cylindrical_cuff_length_m
                ).radius_m,
            },
        }


INTERACTION_AWARE_MPC_CONFIG = HumanMPCConfig(
    resultant_force_weight=0.10,
    cylindrical_surface_effort_weight=0.05,
    wrench_slew_weight=0.05,
)


class HumanSpaceMPC:
    """Nonlinear shooting MPC over desired Human generalized cuff action."""

    def __init__(
        self,
        config: HumanMPCConfig = HumanMPCConfig(),
        *,
        cuff_allocator: Any | None = None,
        candidate_audit_solve_indices: frozenset[int] | None = None,
        implementation: Literal["scalar", "batched"] = "batched",
        record_timing_breakdown: bool = False,
    ) -> None:
        if implementation not in {"scalar", "batched"}:
            raise ValueError("implementation must be scalar or batched")
        self.config = config
        self.implementation = implementation
        self.record_timing_breakdown = bool(record_timing_breakdown)
        self.uses_default_engineering_cuff_allocator = cuff_allocator is None
        self.cuff_allocator = (
            default_engineering_cuff_allocator()
            if cuff_allocator is None
            else cuff_allocator
        )
        self.candidate_audit_solve_indices = (
            frozenset()
            if candidate_audit_solve_indices is None
            else frozenset(candidate_audit_solve_indices)
        )
        self.candidate_audit_history: list[dict[str, Any]] = []
        self.last_sequence: np.ndarray | None = None
        self.last_action = np.zeros(2)
        self.solve_count = 0
        self.failure_count = 0
        self.last_diagnostics: dict[str, Any] = {}
        self.rng = np.random.default_rng(config.random_seed)
        self.surface_model = CylindricalSurfaceLoadModel(
            CylindricalSurfaceConfig(config.cylindrical_cuff_length_m)
        )
        self.surface_operator = self.surface_model.minimum_norm_operator
        self.surface_metric = self.surface_operator.T @ self.surface_operator
        self.q_scale = np.asarray(config.q_error_scale_rad, dtype=float)
        self.dq_scale = np.asarray(config.dq_error_scale_rad_s, dtype=float)
        self.action_scale = np.asarray(config.action_scale_nm, dtype=float)
        self.rate_scale = np.asarray(config.action_rate_scale_nm, dtype=float)
        self._last_population_timing_s: dict[str, float] = {}

    def _allocate(
        self, action: np.ndarray, q_rad: np.ndarray, human: Any
    ) -> dict[str, Any]:
        return self.cuff_allocator.allocate(action, q_rad, human)

    def reset(self) -> None:
        self.last_sequence = None
        self.last_action = np.zeros(2)
        self.solve_count = 0
        self.failure_count = 0
        self.last_diagnostics = {}
        self.candidate_audit_history = []
        self.rng = np.random.default_rng(self.config.random_seed)

    def _candidate_audit_record(
        self,
        *,
        solve_index: int,
        iteration: int,
        candidate_index: int,
        sequence: np.ndarray,
        evaluation: tuple[float, float, np.ndarray | None],
        state: np.ndarray,
        q_ref: np.ndarray,
        dq_ref: np.ndarray,
        q_scale: np.ndarray,
        dq_scale: np.ndarray,
        action_scale: np.ndarray,
        rate_scale: np.ndarray,
        human: Any,
    ) -> dict[str, Any]:
        """Return audit-only cost and cuff metrics without changing ranking."""

        total_cost, margin, states = evaluation
        record: dict[str, Any] = {
            "solve_index": solve_index,
            "iteration": iteration,
            "candidate_index": candidate_index,
            "feasible": bool(states is not None and margin >= -1e-9),
            "minimum_constraint_margin": float(margin),
            "actual_total_objective": float(total_cost),
            "first_generalized_torque_nm": np.asarray(sequence[0]).tolist(),
            "sequence_nm": np.asarray(sequence).tolist(),
        }
        if states is None:
            return record
        tracking_q = float(np.sum(((states[:, :2] - q_ref) / q_scale) ** 2))
        tracking_dq = float(np.sum(((states[:, 2:] - dq_ref) / dq_scale) ** 2))
        action_cost = float(
            self.config.action_weight * np.sum((sequence / action_scale) ** 2)
        )
        previous = np.vstack([self.last_action, sequence[:-1]])
        action_slew_cost = float(
            self.config.action_rate_weight
            * np.sum(((sequence - previous) / rate_scale) ** 2)
        )
        interaction, allocations = self._interaction_cost_terms(
            state, sequence, states, human
        )
        force = np.asarray(
            [float(allocation["force_norm_n"]) for allocation in allocations]
        )
        moment = np.asarray(
            [
                abs(
                    float(
                        np.asarray(allocation.get("sagittal_wrench", [0.0, 0.0, 0.0]))[
                            2
                        ]
                    )
                )
                for allocation in allocations
            ]
        )
        surface = np.asarray(
            [
                float(allocation["cylindrical_surface_effort_n"])
                for allocation in allocations
            ]
        )
        tracking_cost = tracking_q + tracking_dq
        base_cost = tracking_cost + action_cost + action_slew_cost
        registered_interaction_cost = (
            INTERACTION_AWARE_MPC_CONFIG.resultant_force_weight
            * interaction["normalized_resultant_force_squared_sum"]
            + INTERACTION_AWARE_MPC_CONFIG.cylindrical_surface_effort_weight
            * interaction["normalized_cylindrical_surface_effort_squared_sum"]
            + INTERACTION_AWARE_MPC_CONFIG.wrench_slew_weight
            * interaction["normalized_wrench_slew_squared_sum"]
        )
        record.update(
            {
                "tracking_cost": tracking_cost,
                "q_tracking_cost": tracking_q,
                "dq_tracking_cost": tracking_dq,
                "action_cost": action_cost,
                "action_slew_cost": action_slew_cost,
                "base_task_objective": base_cost,
                "registered_interaction_cost": float(registered_interaction_cost),
                "registered_interaction_total_objective": float(
                    base_cost + registered_interaction_cost
                ),
                "normalized_resultant_force_squared_sum": interaction[
                    "normalized_resultant_force_squared_sum"
                ],
                "normalized_cylindrical_surface_effort_squared_sum": interaction[
                    "normalized_cylindrical_surface_effort_squared_sum"
                ],
                "normalized_wrench_slew_squared_sum": interaction[
                    "normalized_wrench_slew_squared_sum"
                ],
                "predicted_resultant_force_n": {
                    "peak": float(np.max(force)),
                    "rms": float(np.sqrt(np.mean(force**2))),
                },
                "predicted_abs_sagittal_moment_nm": {
                    "peak": float(np.max(moment)),
                    "rms": float(np.sqrt(np.mean(moment**2))),
                },
                "predicted_cylindrical_surface_proxy_n": {
                    "peak": float(np.max(surface)),
                    "rms": float(np.sqrt(np.mean(surface**2))),
                },
            }
        )
        return record

    def _rollout(self, state: np.ndarray, sequence: np.ndarray, human: HumanV2Parameters) -> np.ndarray:
        states = [np.asarray(state, dtype=float)]
        for action in sequence:
            states.append(_step_model(states[-1], action, self.config.prediction_dt_s, human))
        return np.asarray(states)

    def _reference_arrays(
        self,
        time_s: float,
        reference_fn: Callable[[float], CuffPoseReference],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        references = [
            reference_fn(time_s + (index + 1) * self.config.prediction_dt_s)
            for index in range(self.config.horizon_steps)
        ]
        return (
            np.array([item.q_rad for item in references]),
            np.array([item.dq_rad_s for item in references]),
            np.array([item.ddq_rad_s2 for item in references]),
        )

    def _seed_sequence(
        self,
        state: np.ndarray,
        q_ref: np.ndarray,
        dq_ref: np.ndarray,
        ddq_ref: np.ndarray,
        human: HumanV2Parameters,
    ) -> np.ndarray:
        predicted = np.asarray(state, dtype=float).copy()
        actions = []
        for q_target, dq_target, qdd_target in zip(q_ref, dq_ref, ddq_ref, strict=True):
            qdd_command = (
                qdd_target
                - TRACKING_KP_RAD_S2_PER_RAD * (predicted[:2] - q_target)
                - TRACKING_KD_RAD_S2_PER_RAD_S * (predicted[2:] - dq_target)
            )
            action = _inverse_model(predicted[:2], predicted[2:], qdd_command, human)
            actions.append(action)
            predicted = _step_model(predicted, action, self.config.prediction_dt_s, human)
        heuristic = np.asarray(actions)
        if self.last_sequence is None:
            return heuristic
        warm = np.vstack([self.last_sequence[1:], self.last_sequence[-1]])
        return 0.35 * warm + 0.65 * heuristic

    @staticmethod
    def _world_from_cuff_rotation(q_rad: np.ndarray, human: Any) -> np.ndarray:
        if hasattr(human, "geometry"):
            return np.asarray(human.geometry.cuff_pose(q_rad).rotation, dtype=float)
        return np.asarray(_world_from_cuff(q_rad).rotation, dtype=float)

    def _interaction_cost_terms(
        self,
        state: np.ndarray,
        sequence: np.ndarray,
        predicted_states: np.ndarray,
        human: Any,
    ) -> tuple[dict[str, float], list[dict[str, Any]]]:
        allocations = [
            self._allocate(action, predicted[:2], human)
            for action, predicted in zip(sequence, predicted_states, strict=True)
        ]
        normalization_squared = self.config.interaction_force_normalization_n**2
        force_squared = 0.0
        surface_squared = 0.0
        wrenches_world: list[np.ndarray] = []
        for allocation, predicted in zip(allocations, predicted_states, strict=True):
            wrench_world = np.asarray(allocation["wrench_world"], dtype=float)
            wrenches_world.append(wrench_world)
            force_squared += float(wrench_world[:3] @ wrench_world[:3])
            rotation = self._world_from_cuff_rotation(predicted[:2], human)
            wrench_cuff = np.concatenate(
                [rotation.T @ wrench_world[:3], rotation.T @ wrench_world[3:]]
            )
            equivalent_surface_load = self.surface_operator @ wrench_cuff
            surface_squared += float(
                equivalent_surface_load @ equivalent_surface_load
            )

        previous_wrench = np.asarray(
            self._allocate(self.last_action, state[:2], human)["wrench_world"],
            dtype=float,
        )
        wrench_slew_force_equivalent_squared = 0.0
        radius = self.surface_model.config.radius_m
        for wrench_world in wrenches_world:
            delta = wrench_world - previous_wrench
            wrench_slew_force_equivalent_squared += float(
                delta[:3] @ delta[:3] + (delta[3:] @ delta[3:]) / radius**2
            )
            previous_wrench = wrench_world

        normalized_force = force_squared / normalization_squared
        normalized_surface = surface_squared / normalization_squared
        normalized_slew = (
            wrench_slew_force_equivalent_squared / normalization_squared
        )
        return (
            {
                "resultant_force_cost": (
                    self.config.resultant_force_weight * normalized_force
                ),
                "cylindrical_surface_effort_cost": (
                    self.config.cylindrical_surface_effort_weight
                    * normalized_surface
                ),
                "wrench_slew_cost": self.config.wrench_slew_weight * normalized_slew,
                "normalized_resultant_force_squared_sum": normalized_force,
                "normalized_cylindrical_surface_effort_squared_sum": (
                    normalized_surface
                ),
                "normalized_wrench_slew_squared_sum": normalized_slew,
            },
            allocations,
        )

    @staticmethod
    def _batched_soft_limit_torque(
        q_rad: np.ndarray, dq_rad_s: np.ndarray
    ) -> np.ndarray:
        """Vectorized equivalent of the frozen two-joint soft-limit law."""

        q = np.asarray(q_rad, dtype=float)
        dq = np.asarray(dq_rad_s, dtype=float)
        lower = (
            np.asarray(HUMAN.q_min_rad)
            + HUMAN.soft_limit_margin_rad
            - HUMAN.soft_limit_numerical_tolerance_rad
        )
        upper = (
            np.asarray(HUMAN.q_max_rad)
            - HUMAN.soft_limit_margin_rad
            + HUMAN.soft_limit_numerical_tolerance_rad
        )
        torque = np.zeros_like(q)
        below = q < lower
        above = q > upper
        lower_z = np.where(
            below, (lower - q) / HUMAN.soft_limit_margin_rad, 0.0
        )
        upper_z = np.where(
            above, (q - upper) / HUMAN.soft_limit_margin_rad, 0.0
        )
        torque += np.where(
            below,
            HUMAN.soft_limit_boundary_torque_nm * lower_z**3
            + HUMAN.soft_limit_damping_nms_rad
            * lower_z**2
            * np.maximum(-dq, 0.0),
            0.0,
        )
        torque += np.where(
            above,
            -HUMAN.soft_limit_boundary_torque_nm * upper_z**3
            - HUMAN.soft_limit_damping_nms_rad
            * upper_z**2
            * np.maximum(dq, 0.0),
            0.0,
        )
        return torque

    def _batched_base_continuous_dynamics(
        self,
        state: np.ndarray,
        action: np.ndarray,
        human: BaseParameterHumanModel,
    ) -> np.ndarray:
        """Evaluate the unchanged 11-base dynamics over a candidate batch."""

        x = np.asarray(state, dtype=float)
        q1 = x[..., 0]
        q2 = x[..., 1]
        dq1 = x[..., 2]
        dq2 = x[..., 3]
        phi = q1 - q2
        cosine = np.cos(q2)
        sine = np.sin(q2)
        beta = np.asarray(human.beta, dtype=float)
        zero_acceleration = np.empty(x.shape[:-1] + (2,), dtype=float)
        zero_acceleration[..., 0] = (
            beta[2] * sine * (-2.0 * dq1 * dq2 + dq2**2)
            + beta[3] * np.cos(q1)
            + beta[4] * np.cos(phi)
            + beta[5] * q1
            - beta[7]
            + beta[9] * dq1
        )
        zero_acceleration[..., 1] = (
            beta[2] * sine * dq1**2
            - beta[4] * np.cos(phi)
            + beta[6] * q2
            - beta[8]
            + beta[10] * dq2
        )
        zero_acceleration -= self._batched_soft_limit_torque(
            x[..., :2], x[..., 2:]
        )
        mass = np.empty(x.shape[:-1] + (2, 2), dtype=float)
        mass[..., 0, 0] = beta[0] + 2.0 * beta[2] * cosine
        mass[..., 0, 1] = -(beta[1] + beta[2] * cosine)
        mass[..., 1, 0] = mass[..., 0, 1]
        mass[..., 1, 1] = beta[1]
        acceleration = np.linalg.solve(
            mass,
            (np.asarray(action, dtype=float) - zero_acceleration)[..., None],
        )[..., 0]
        return np.concatenate([x[..., 2:], acceleration], axis=-1)

    def _batched_base_step(
        self,
        state: np.ndarray,
        action: np.ndarray,
        human: BaseParameterHumanModel,
    ) -> np.ndarray:
        dt = self.config.prediction_dt_s
        k1 = self._batched_base_continuous_dynamics(state, action, human)
        k2 = self._batched_base_continuous_dynamics(
            state + 0.5 * dt * k1, action, human
        )
        k3 = self._batched_base_continuous_dynamics(
            state + 0.5 * dt * k2, action, human
        )
        k4 = self._batched_base_continuous_dynamics(
            state + dt * k3, action, human
        )
        return state + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0

    def _batched_cuff_force_norm(
        self,
        action: np.ndarray,
        q_rad: np.ndarray,
        human: BaseParameterHumanModel,
    ) -> np.ndarray:
        """Batch the frozen 1:1 equality-constrained cuff allocation."""

        if not isinstance(self.cuff_allocator, CuffAwareSagittalAllocator):
            raise TypeError("batched allocation requires the frozen cuff-aware allocator")
        geometry = human.geometry
        q = np.asarray(q_rad, dtype=float)
        q1 = q[..., 0]
        phi = q1 - q[..., 1]
        plane_x = np.asarray(geometry.plane_x_world, dtype=float)
        plane_z = np.asarray(geometry.plane_z_world, dtype=float)
        axis = np.asarray(geometry.joint_axis_world, dtype=float)
        e1_perp = (
            -np.sin(q1)[..., None] * plane_x
            + np.cos(q1)[..., None] * plane_z
        )
        shank_perp = (
            -np.sin(phi)[..., None] * plane_x
            + np.cos(phi)[..., None] * plane_z
        )
        first = (
            geometry.thigh_length_m * e1_perp
            + geometry.cuff_distance_m * shank_perp
        )
        second = -geometry.cuff_distance_m * shank_perp
        jacobian = np.stack([first, second], axis=-1)
        force_basis = np.column_stack([plane_x, plane_z])
        force_map = np.einsum("...wi,wj->...ij", jacobian, force_basis)
        matrix = np.empty(q.shape[:-1] + (2, 3), dtype=float)
        matrix[..., :, :2] = force_map
        matrix[..., :, 2] = np.array([-1.0, 1.0])

        world_mapping = np.zeros((6, 3), dtype=float)
        world_mapping[:3, :2] = force_basis
        world_mapping[3:, 2] = axis
        cuff_angle = phi - geometry.cuff_offset_rad
        cuff_x = (
            np.cos(cuff_angle)[..., None] * plane_x
            + np.sin(cuff_angle)[..., None] * plane_z
        )
        cuff_z = (
            -np.sin(cuff_angle)[..., None] * plane_x
            + np.cos(cuff_angle)[..., None] * plane_z
        )
        rotation = np.stack(
            [cuff_x, np.broadcast_to(axis, cuff_x.shape), cuff_z], axis=-1
        )
        transformed = np.zeros(q.shape[:-1] + (6, 3), dtype=float)
        transformed[..., :3, :] = np.einsum(
            "...ji,jk->...ik", rotation, world_mapping[:3, :]
        )
        transformed[..., 3:, :] = np.einsum(
            "...ji,jk->...ik", rotation, world_mapping[3:, :]
        )
        operator = self.cuff_allocator.surface_model.minimum_norm_operator
        surface_metric = operator.T @ operator
        surface_weight = (
            self.cuff_allocator.config.cylindrical_surface_effort_weight
        )
        hessian = surface_weight * np.einsum(
            "...wi,wv,...vj->...ij",
            transformed,
            surface_metric,
            transformed,
        )
        hessian[..., 0, 0] += self.cuff_allocator.config.resultant_force_weight
        hessian[..., 1, 1] += self.cuff_allocator.config.resultant_force_weight
        inverse_hessian_bt = np.linalg.solve(
            hessian, np.swapaxes(matrix, -1, -2)
        )
        dual = matrix @ inverse_hessian_bt
        dual_solution = np.linalg.solve(
            dual, np.asarray(action, dtype=float)[..., None]
        )[..., 0]
        sagittal = np.einsum(
            "...ij,...j->...i", inverse_hessian_bt, dual_solution
        )
        wrench_world = np.einsum("wi,...i->...w", world_mapping, sagittal)
        return np.linalg.norm(wrench_world[..., :3], axis=-1)

    def _can_use_batched_population(self, human: Any) -> bool:
        return bool(
            self.implementation == "batched"
            and isinstance(human, BaseParameterHumanModel)
            and isinstance(self.cuff_allocator, CuffAwareSagittalAllocator)
            and not self.config.interaction_aware
        )

    def _evaluate_population(
        self,
        state: np.ndarray,
        candidates: np.ndarray,
        q_ref: np.ndarray,
        dq_ref: np.ndarray,
        human: Any,
    ) -> list[tuple[float, float, np.ndarray | None]]:
        if not self._can_use_batched_population(human):
            return [
                self._evaluate_sequence(state, candidate, q_ref, dq_ref, human)
                for candidate in candidates
            ]
        candidate = np.asarray(candidates, dtype=float)
        if not np.all(np.isfinite(candidate)) or np.max(np.abs(candidate)) > 1.0e6:
            return [
                self._evaluate_sequence(state, item, q_ref, dq_ref, human)
                for item in candidate
            ]
        count = candidate.shape[0]
        section_start = perf_counter() if self.record_timing_breakdown else 0.0
        states = np.empty(
            (count, self.config.horizon_steps + 1, 4), dtype=float
        )
        states[:, 0, :] = np.asarray(state, dtype=float)
        rollout_setup_s = (
            perf_counter() - section_start if self.record_timing_breakdown else 0.0
        )
        try:
            with np.errstate(over="raise", invalid="raise"):
                section_start = (
                    perf_counter() if self.record_timing_breakdown else 0.0
                )
                for step in range(self.config.horizon_steps):
                    states[:, step + 1, :] = self._batched_base_step(
                        states[:, step, :], candidate[:, step, :], human
                    )
                dynamics_s = (
                    perf_counter() - section_start
                    if self.record_timing_breakdown
                    else 0.0
                )
                predicted = states[:, 1:, :]
                section_start = (
                    perf_counter() if self.record_timing_breakdown else 0.0
                )
                force_norm = self._batched_cuff_force_norm(
                    candidate, predicted[..., :2], human
                )
                cuff_allocation_s = (
                    perf_counter() - section_start
                    if self.record_timing_breakdown
                    else 0.0
                )
        except (ValueError, OverflowError, FloatingPointError, np.linalg.LinAlgError):
            return [
                self._evaluate_sequence(state, item, q_ref, dq_ref, human)
                for item in candidate
            ]
        section_start = perf_counter() if self.record_timing_breakdown else 0.0
        finite = np.all(np.isfinite(predicted), axis=(1, 2))
        bounded = np.max(np.abs(predicted), axis=(1, 2)) <= 1.0e6
        q_cost = np.sum(
            ((predicted[..., :2] - q_ref[None, ...]) / self.q_scale) ** 2,
            axis=(1, 2),
        )
        dq_cost = np.sum(
            ((predicted[..., 2:] - dq_ref[None, ...]) / self.dq_scale) ** 2,
            axis=(1, 2),
        )
        effort = self.config.action_weight * np.sum(
            (candidate / self.action_scale) ** 2, axis=(1, 2)
        )
        delta = np.empty_like(candidate)
        delta[:, 0, :] = candidate[:, 0, :] - self.last_action
        delta[:, 1:, :] = candidate[:, 1:, :] - candidate[:, :-1, :]
        smoothness = self.config.action_rate_weight * np.sum(
            (delta / self.rate_scale) ** 2, axis=(1, 2)
        )
        lower = predicted[..., :2] - np.asarray(human.q_min_rad)
        upper = np.asarray(human.q_max_rad) - predicted[..., :2]
        force_margin = CUFF_TRANSLATIONAL_FORCE_GATE_N - force_norm
        margin = np.min(
            np.concatenate(
                [lower.reshape(count, -1), upper.reshape(count, -1), force_margin],
                axis=1,
            ),
            axis=1,
        )
        costs = q_cost + dq_cost + effort + smoothness
        valid = finite & bounded & np.isfinite(force_norm).all(axis=1)
        result = [
            (
                float(costs[index]) if valid[index] else 1.0e30,
                float(margin[index]) if valid[index] else -1.0e6,
                predicted[index] if valid[index] else None,
            )
            for index in range(count)
        ]
        if self.record_timing_breakdown:
            self._last_population_timing_s = {
                "candidate_rollout_python_overhead": rollout_setup_s,
                "dynamics_propagation": dynamics_s,
                "cuff_constraint_allocation": cuff_allocation_s,
                "cost_constraint_evaluation": perf_counter() - section_start,
            }
        return result

    def _evaluate_sequence(
        self,
        state: np.ndarray,
        sequence: np.ndarray,
        q_ref: np.ndarray,
        dq_ref: np.ndarray,
        human: Any,
        *,
        previous_action: np.ndarray | None = None,
    ) -> tuple[float, float, np.ndarray | None]:
        """Evaluate one sequence under the production objective and constraints."""

        shape = (self.config.horizon_steps, 2)
        candidate = np.asarray(sequence).reshape(shape)
        if not np.all(np.isfinite(candidate)) or np.max(np.abs(candidate)) > 1.0e6:
            return 1.0e30, -1.0e6, None
        try:
            with np.errstate(over="raise", invalid="raise"):
                states = self._rollout(np.asarray(state, dtype=float), candidate, human)[
                    1:
                ]
        except (ValueError, OverflowError, FloatingPointError, np.linalg.LinAlgError):
            return 1.0e30, -1.0e6, None
        if not np.all(np.isfinite(states)) or np.max(np.abs(states)) > 1.0e6:
            return 1.0e30, -1.0e6, None

        q_cost = np.sum(((states[:, :2] - q_ref) / self.q_scale) ** 2)
        dq_cost = np.sum(((states[:, 2:] - dq_ref) / self.dq_scale) ** 2)
        effort = self.config.action_weight * np.sum(
            (candidate / self.action_scale) ** 2
        )
        prior_action = (
            self.last_action
            if previous_action is None
            else np.asarray(previous_action, dtype=float)
        )
        previous = np.vstack([prior_action, candidate[:-1]])
        smoothness = self.config.action_rate_weight * np.sum(
            ((candidate - previous) / self.rate_scale) ** 2
        )
        lower = states[:, :2] - np.asarray(human.q_min_rad)
        upper = np.asarray(human.q_max_rad) - states[:, :2]
        try:
            interaction, allocations = self._interaction_cost_terms(
                np.asarray(state, dtype=float), candidate, states, human
            )
            force_margin = np.asarray(
                [
                    CUFF_TRANSLATIONAL_FORCE_GATE_N
                    - float(allocation["force_norm_n"])
                    for allocation in allocations
                ],
                dtype=float,
            )
        except (ValueError, RuntimeError, FloatingPointError):
            return 1.0e30, -1.0e6, None
        margin = float(
            np.min(
                np.concatenate(
                    [lower.reshape(-1), upper.reshape(-1), force_margin]
                )
            )
        )
        interaction_cost = (
            interaction["resultant_force_cost"]
            + interaction["cylindrical_surface_effort_cost"]
            + interaction["wrench_slew_cost"]
        )
        return float(
            q_cost + dq_cost + effort + smoothness + interaction_cost
        ), margin, states

    def _refine_selected_sequence(
        self,
        sequence: np.ndarray,
        evaluation: tuple[float, float, np.ndarray | None],
        evaluate: Callable[
            [np.ndarray], tuple[float, float, np.ndarray | None]
        ],
    ) -> tuple[
        np.ndarray,
        tuple[float, float, np.ndarray | None],
        dict[str, Any],
    ]:
        """Optional post-CEM hook; the base optimizer remains CEM-only."""

        return sequence, evaluation, {
            "enabled": False,
            "accepted": False,
            "candidate_evaluations": 0,
            "feasible_candidate_evaluations": 0,
            "objective_before": float(evaluation[0]),
            "objective_after": float(evaluation[0]),
            "objective_improvement": 0.0,
        }

    def solve(
        self,
        state: np.ndarray,
        time_s: float,
        reference_fn: Callable[[float], CuffPoseReference],
        human: HumanV2Parameters,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        solve_timing_start = perf_counter() if self.record_timing_breakdown else 0.0
        x0 = np.asarray(state, dtype=float)
        q_ref, dq_ref, ddq_ref = self._reference_arrays(time_s, reference_fn)
        seed = self._seed_sequence(x0, q_ref, dq_ref, ddq_ref, human)
        shape = (self.config.horizon_steps, 2)
        q_scale = self.q_scale
        dq_scale = self.dq_scale
        action_scale = self.action_scale
        rate_scale = self.rate_scale

        def evaluate(sequence: np.ndarray) -> tuple[float, float, np.ndarray | None]:
            return self._evaluate_sequence(
                x0,
                sequence,
                q_ref,
                dq_ref,
                human,
            )

        mean = seed.copy()
        std = np.broadcast_to(np.asarray(self.config.exploration_std_nm), shape).copy()
        floor = np.broadcast_to(np.asarray(self.config.exploration_std_floor_nm), shape)
        best_sequence: np.ndarray | None = None
        best_cost = float("inf")
        best_margin = float("-inf")
        best_states: np.ndarray | None = None
        feasible_candidate_count = 0
        audit_this_call = self.solve_count in self.candidate_audit_solve_indices
        call_audit: list[dict[str, Any]] = []
        iteration_audit: list[dict[str, Any]] = []
        global_stage_start = perf_counter()
        sampling_runtime_s = 0.0
        population_runtime_s = 0.0
        elite_update_runtime_s = 0.0
        population_sections_s = {
            "dynamics_propagation": 0.0,
            "cuff_constraint_allocation": 0.0,
            "cost_constraint_evaluation": 0.0,
        }
        for iteration in range(self.config.cem_iterations):
            section_start = perf_counter() if self.record_timing_breakdown else 0.0
            candidates = self.rng.normal(mean, std, size=(self.config.candidate_count, *shape))
            candidates[0] = mean
            if self.record_timing_breakdown:
                sampling_runtime_s += perf_counter() - section_start
                section_start = perf_counter()
            evaluations = self._evaluate_population(
                x0, candidates, q_ref, dq_ref, human
            )
            if self.record_timing_breakdown:
                population_runtime_s += perf_counter() - section_start
                for key in population_sections_s:
                    population_sections_s[key] += self._last_population_timing_s.get(
                        key, 0.0
                    )
            if audit_this_call:
                call_audit.extend(
                    self._candidate_audit_record(
                        solve_index=self.solve_count,
                        iteration=iteration,
                        candidate_index=index,
                        sequence=candidate,
                        evaluation=evaluations[index],
                        state=x0,
                        q_ref=q_ref,
                        dq_ref=dq_ref,
                        q_scale=q_scale,
                        dq_scale=dq_scale,
                        action_scale=action_scale,
                        rate_scale=rate_scale,
                        human=human,
                    )
                    for index, candidate in enumerate(candidates)
                )
            section_start = perf_counter() if self.record_timing_breakdown else 0.0
            feasible = [index for index, (_, margin, states) in enumerate(evaluations) if states is not None and margin >= -1e-9]
            feasible_candidate_count += len(feasible)
            if not feasible:
                if audit_this_call:
                    iteration_audit.append(
                        {
                            "iteration": iteration,
                            "feasible_indices": [],
                            "elite_indices": [],
                            "updated_mean_nm": mean.tolist(),
                            "updated_std_nm": std.tolist(),
                        }
                    )
                if self.record_timing_breakdown:
                    elite_update_runtime_s += perf_counter() - section_start
                continue
            ordered = sorted(feasible, key=lambda index: evaluations[index][0])
            if evaluations[ordered[0]][0] < best_cost:
                selected = ordered[0]
                best_sequence = candidates[selected].copy()
                best_cost, best_margin, best_states = evaluations[selected]
            elites = candidates[ordered[: min(self.config.elite_count, len(ordered))]]
            mean = np.mean(elites, axis=0)
            std = np.maximum(np.std(elites, axis=0), floor)
            if audit_this_call:
                iteration_audit.append(
                    {
                        "iteration": iteration,
                        "feasible_indices": feasible,
                        "elite_indices": ordered[
                            : min(self.config.elite_count, len(ordered))
                        ],
                        "updated_mean_nm": mean.tolist(),
                        "updated_std_nm": std.tolist(),
                    }
                )
            if self.record_timing_breakdown:
                elite_update_runtime_s += perf_counter() - section_start
        global_stage_runtime_s = perf_counter() - global_stage_start

        accepted = best_sequence is not None
        if accepted:
            assert best_sequence is not None and best_states is not None
            global_objective = float(best_cost)
            local_stage_start = perf_counter()
            best_sequence, refined_evaluation, refinement = (
                self._refine_selected_sequence(
                    best_sequence,
                    (best_cost, best_margin, best_states),
                    evaluate,
                )
            )
            local_stage_runtime_s = perf_counter() - local_stage_start
            best_cost, best_margin, best_states = refined_evaluation
            assert best_states is not None
            self.last_sequence = best_sequence.copy()
            self.last_action = best_sequence[0].copy()
        else:
            global_objective = float("inf")
            local_stage_runtime_s = 0.0
            refinement = {
                "enabled": False,
                "accepted": False,
                "candidate_evaluations": 0,
                "feasible_candidate_evaluations": 0,
                "objective_before": float("inf"),
                "objective_after": float("inf"),
                "objective_improvement": 0.0,
            }
            self.failure_count += 1
            best_sequence = seed.copy()
            best_cost, best_margin, seed_states = evaluate(seed)
            best_states = seed_states
        self.solve_count += 1
        predicted = np.vstack([x0, best_states]) if best_states is not None else self._rollout(x0, seed, human)
        try:
            interaction_terms, selected_allocations = self._interaction_cost_terms(
                x0, best_sequence, predicted[1:], human
            )
            peak_predicted_force = max(
                float(allocation["force_norm_n"])
                for allocation in selected_allocations
            )
        except (ValueError, RuntimeError, FloatingPointError):
            peak_predicted_force = float("inf")
            interaction_terms = {
                "resultant_force_cost": float("nan"),
                "cylindrical_surface_effort_cost": float("nan"),
                "wrench_slew_cost": float("nan"),
            }
        self.last_diagnostics = {
            "accepted": accepted,
            "optimizer_success": accepted,
            "optimizer": (
                "feasible_first_cem_plus_smooth_local_refinement"
                if refinement["enabled"]
                else "feasible_first_cem"
            ),
            "optimizer_iterations": self.config.cem_iterations,
            "implementation": self.implementation,
            "feasible_candidate_evaluations": feasible_candidate_count,
            "global_cem_objective": global_objective,
            "global_stage_runtime_ms": 1000.0 * global_stage_runtime_s,
            "local_stage_runtime_ms": 1000.0 * local_stage_runtime_s,
            "local_refinement": refinement,
            "objective": best_cost,
            "minimum_constraint_margin": best_margin,
            "peak_predicted_force_n": peak_predicted_force,
            "interaction_aware": self.config.interaction_aware,
            "interaction_cost_terms": interaction_terms,
            "objective_contract": self.config.objective_contract(),
            "implementation_timing_ms": {
                "candidate_sampling_generation": 1000.0 * sampling_runtime_s,
                "candidate_population_evaluation": 1000.0 * population_runtime_s,
                "elite_selection_cem_update": 1000.0 * elite_update_runtime_s,
            },
            "predicted_rom_respected": bool(
                np.all(predicted[1:, :2] >= np.asarray(human.q_min_rad) - 1e-9)
                and np.all(predicted[1:, :2] <= np.asarray(human.q_max_rad) + 1e-9)
            ),
        }
        if audit_this_call:
            self.candidate_audit_history.append(
                {
                    "solve_index": self.solve_count - 1,
                    "wall_time_s": float(time_s),
                    "selected_first_generalized_torque_nm": best_sequence[0].tolist(),
                    "candidates": call_audit,
                    "cem_iterations": iteration_audit,
                }
            )
        if self.record_timing_breakdown:
            solve_total_s = perf_counter() - solve_timing_start
            cost_evaluation_s = (
                population_sections_s["cuff_constraint_allocation"]
                + population_sections_s["cost_constraint_evaluation"]
            )
            rollout_overhead_s = max(
                0.0,
                population_runtime_s
                - population_sections_s["dynamics_propagation"]
                - cost_evaluation_s,
            )
            accounted_s = (
                sampling_runtime_s
                + rollout_overhead_s
                + population_sections_s["dynamics_propagation"]
                + cost_evaluation_s
                + elite_update_runtime_s
            )
            self.last_diagnostics["implementation_timing_ms"].update(
                {
                    "candidate_rollout_python_overhead": 1000.0
                    * rollout_overhead_s,
                    "dynamics_propagation": 1000.0
                    * population_sections_s["dynamics_propagation"],
                    "cost_constraint_evaluation": 1000.0 * cost_evaluation_s,
                    "cuff_constraint_allocation_within_cost": 1000.0
                    * population_sections_s["cuff_constraint_allocation"],
                    "other_python_numpy_overhead": 1000.0
                    * max(0.0, solve_total_s - accounted_s),
                    "solve_total": 1000.0 * solve_total_s,
                }
            )
        return best_sequence[0].copy(), dict(self.last_diagnostics)
