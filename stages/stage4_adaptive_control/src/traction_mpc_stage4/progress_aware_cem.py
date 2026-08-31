"""Joint control-and-progress CEM extension for Stage-4 High-ROM execution.

The extension keeps the frozen Human-space MPC horizon, population, elite
count, iterations, base objective, dynamics, and cuff allocator.  Each member
of the existing CEM population gains one scalar alpha over the whole horizon.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Callable

import numpy as np

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage3.reference import CuffPoseReference

from .estimator_v2 import BaseParameterHumanModel
from .mpc import HumanMPCConfig, HumanSpaceMPC


@dataclass(frozen=True)
class ProgressAwareCEMConfig:
    """New-variable bounds and dimensionless pacing normalization only."""

    minimum_alpha: float = 0.50
    maximum_alpha: float = 1.00
    initial_std_fraction_of_domain: float = 0.25
    floor_std_fraction_of_domain: float = 0.02

    def __post_init__(self) -> None:
        if not 0.0 < self.minimum_alpha < self.maximum_alpha <= 1.0:
            raise ValueError("alpha bounds must satisfy 0 < min < max <= 1")
        if self.initial_std_fraction_of_domain <= 0.0:
            raise ValueError("initial alpha spread must be positive")
        if self.floor_std_fraction_of_domain <= 0.0:
            raise ValueError("alpha spread floor must be positive")

    @property
    def alpha_span(self) -> float:
        return self.maximum_alpha - self.minimum_alpha

    @property
    def initial_alpha_std(self) -> float:
        return self.initial_std_fraction_of_domain * self.alpha_span

    @property
    def floor_alpha_std(self) -> float:
        return self.floor_std_fraction_of_domain * self.alpha_span

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.update(
            {
                "initial_alpha_std": self.initial_alpha_std,
                "floor_alpha_std": self.floor_alpha_std,
                "progress_cost": (
                    "H*((1-alpha)/(alpha_max-alpha_min))^2"
                ),
                "alpha_change_cost": (
                    "((alpha-alpha_previous)/(alpha_max-alpha_min))^2"
                ),
                "pacing_weights_tuned": False,
                "pacing_normalization": (
                    "unit dimensionless normalization over the declared alpha domain"
                ),
            }
        )
        return payload


class ProgressAwareReferenceClock:
    """Continuous path phase driven by the alpha selected in each MPC cycle."""

    def __init__(
        self,
        base_reference: Callable[[float], CuffPoseReference],
        batched_path_kinematics: Callable[
            [np.ndarray], tuple[np.ndarray, np.ndarray, np.ndarray]
        ],
        *,
        duration_s: float,
        initial_wall_time_s: float = 0.0,
        initial_alpha: float = 1.0,
    ) -> None:
        self.base_reference = base_reference
        self.batched_path_kinematics = batched_path_kinematics
        self.duration_s = float(duration_s)
        self.wall_anchor_s = float(initial_wall_time_s)
        self.phase_anchor_s = 0.0
        self.alpha = float(initial_alpha)
        self.previous_alpha = float(initial_alpha)
        self.selection_count = 0

    def phase_time_s(self, wall_time_s: float) -> float:
        wall_time = float(wall_time_s)
        if wall_time < self.wall_anchor_s - 1e-12:
            raise ValueError("reference execution time must be monotonic")
        return float(
            np.clip(
                self.phase_anchor_s
                + self.alpha * max(0.0, wall_time - self.wall_anchor_s),
                0.0,
                self.duration_s,
            )
        )

    def candidate_reference_arrays(
        self,
        wall_time_s: float,
        alpha: np.ndarray,
        offsets_s: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        alpha_array = np.asarray(alpha, dtype=float).reshape(-1)
        offsets = np.asarray(offsets_s, dtype=float).reshape(-1)
        phase_now = self.phase_time_s(wall_time_s)
        phase = np.clip(
            phase_now + alpha_array[:, None] * offsets[None, :],
            0.0,
            self.duration_s,
        )
        q, dq_path, ddq_path = self.batched_path_kinematics(phase)
        scale = alpha_array[:, None, None]
        return q, scale * dq_path, scale**2 * ddq_path

    def update_from_mpc_selection(
        self, wall_time_s: float, diagnostics: dict[str, Any]
    ) -> None:
        selected = float(diagnostics["selected_alpha"])
        phase_now = self.phase_time_s(wall_time_s)
        self.phase_anchor_s = phase_now
        self.wall_anchor_s = float(wall_time_s)
        self.previous_alpha = self.alpha
        self.alpha = selected
        self.selection_count += 1

    def reference(self, wall_time_s: float) -> CuffPoseReference:
        base = self.base_reference(self.phase_time_s(wall_time_s))
        return CuffPoseReference(
            q_rad=base.q_rad.copy(),
            dq_rad_s=self.alpha * base.dq_rad_s,
            ddq_rad_s2=self.alpha**2 * base.ddq_rad_s2,
            world_from_cuff=base.world_from_cuff,
        )

    def status(self, wall_time_s: float) -> dict[str, float]:
        return {
            "reference_phase_time_s": self.phase_time_s(wall_time_s),
            "speed_scale": self.alpha,
            "speed_scale_rate_per_s": 0.0,
            "force_speed_scale": self.alpha,
            "force_speed_target_scale": self.alpha,
            "governor_predicted_peak_command_force_n": 0.0,
            "geometry_confidence": 0.0,
            "dynamic_confidence": 0.0,
            "combined_confidence": 0.0,
            "geometry_model_confidence": 0.0,
            "dynamic_model_confidence": 0.0,
            "combined_model_confidence_raw": 0.0,
            "filtered_model_confidence": 0.0,
            "execution_confidence_high": 0.0,
            "geometry_information_confidence": 0.0,
            "dynamic_information_confidence": 0.0,
            "combined_information_confidence": 0.0,
        }

    def summary(self, wall_time_s: float) -> dict[str, Any]:
        return {
            "mode": "joint_cem_progress_clock",
            "final_status": self.status(wall_time_s),
            "selection_count": self.selection_count,
            "alpha_is_piecewise_constant_per_20ms_cycle": True,
            "time_warp_kinematics": (
                "qdot=q_prime*alpha; qddot=q_double_prime*alpha^2 "
                "within each constant-alpha horizon"
            ),
            "trust_confidence_used": False,
            "hard_force_gate_modified": False,
        }


class ProgressAwareCEMMPC(HumanSpaceMPC):
    """Frozen CEM population jointly sampling one alpha per control sequence."""

    def __init__(
        self,
        progress_clock: ProgressAwareReferenceClock,
        config: HumanMPCConfig = HumanMPCConfig(),
        *,
        pacing_config: ProgressAwareCEMConfig = ProgressAwareCEMConfig(),
        cuff_allocator: Any | None = None,
        record_timing_breakdown: bool = True,
    ) -> None:
        super().__init__(
            config,
            cuff_allocator=cuff_allocator,
            implementation="batched",
            record_timing_breakdown=record_timing_breakdown,
        )
        self.progress_clock = progress_clock
        self.pacing_config = pacing_config
        self.last_alpha = float(progress_clock.alpha)

    def reset(self) -> None:
        super().reset()
        self.last_alpha = float(self.progress_clock.alpha)

    @staticmethod
    def _batched_position_velocity(
        q_rad: np.ndarray, dq_rad_s: np.ndarray, human: BaseParameterHumanModel
    ) -> tuple[np.ndarray, np.ndarray]:
        geometry = human.geometry
        q = np.asarray(q_rad, dtype=float)
        dq = np.asarray(dq_rad_s, dtype=float)
        q1 = q[..., 0]
        phi = q1 - q[..., 1]
        plane_x = np.asarray(geometry.plane_x_world, dtype=float)
        plane_z = np.asarray(geometry.plane_z_world, dtype=float)
        hip = np.asarray(geometry.hip_plane_m, dtype=float)
        position_plane_x = (
            hip[0]
            + geometry.thigh_length_m * np.cos(q1)
            + geometry.cuff_distance_m * np.cos(phi)
        )
        position_plane_z = (
            hip[1]
            + geometry.thigh_length_m * np.sin(q1)
            + geometry.cuff_distance_m * np.sin(phi)
        )
        position = (
            np.asarray(geometry.origin_world_m, dtype=float)
            + position_plane_x[..., None] * plane_x
            + position_plane_z[..., None] * plane_z
        )
        e1_perp = -np.sin(q1)[..., None] * plane_x + np.cos(q1)[..., None] * plane_z
        shank_perp = -np.sin(phi)[..., None] * plane_x + np.cos(phi)[..., None] * plane_z
        first = geometry.thigh_length_m * e1_perp + geometry.cuff_distance_m * shank_perp
        second = -geometry.cuff_distance_m * shank_perp
        velocity = first * dq[..., 0, None] + second * dq[..., 1, None]
        return position, velocity

    def _batched_cuff_force_world(
        self,
        action: np.ndarray,
        q_rad: np.ndarray,
        human: BaseParameterHumanModel,
    ) -> np.ndarray:
        """Vectorized equivalent of the unchanged registered allocator."""

        geometry = human.geometry
        q = np.asarray(q_rad, dtype=float)
        q1 = q[..., 0]
        phi = q1 - q[..., 1]
        plane_x = np.asarray(geometry.plane_x_world, dtype=float)
        plane_z = np.asarray(geometry.plane_z_world, dtype=float)
        axis = np.asarray(geometry.joint_axis_world, dtype=float)
        e1_perp = -np.sin(q1)[..., None] * plane_x + np.cos(q1)[..., None] * plane_z
        shank_perp = -np.sin(phi)[..., None] * plane_x + np.cos(phi)[..., None] * plane_z
        first = geometry.thigh_length_m * e1_perp + geometry.cuff_distance_m * shank_perp
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
        cuff_x = np.cos(cuff_angle)[..., None] * plane_x + np.sin(cuff_angle)[..., None] * plane_z
        cuff_z = -np.sin(cuff_angle)[..., None] * plane_x + np.cos(cuff_angle)[..., None] * plane_z
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
        surface_metric = (
            self.cuff_allocator.surface_model.minimum_norm_operator.T
            @ self.cuff_allocator.surface_model.minimum_norm_operator
        )
        hessian = self.cuff_allocator.config.cylindrical_surface_effort_weight * np.einsum(
            "...wi,wv,...vj->...ij", transformed, surface_metric, transformed
        )
        hessian[..., 0, 0] += self.cuff_allocator.config.resultant_force_weight
        hessian[..., 1, 1] += self.cuff_allocator.config.resultant_force_weight
        inverse_hessian_bt = np.linalg.solve(hessian, np.swapaxes(matrix, -1, -2))
        dual = matrix @ inverse_hessian_bt
        dual_solution = np.linalg.solve(
            dual, np.asarray(action, dtype=float)[..., None]
        )[..., 0]
        sagittal = np.einsum("...ij,...j->...i", inverse_hessian_bt, dual_solution)
        wrench_world = np.einsum("wi,...i->...w", world_mapping, sagittal)
        return wrench_world[..., :3]

    def _batched_base_step_dt(
        self,
        state: np.ndarray,
        action: np.ndarray,
        human: BaseParameterHumanModel,
        dt_s: float,
    ) -> np.ndarray:
        """Frozen RK4 dynamics at a low-level substep for force-path alignment."""

        dt = float(dt_s)
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

    def _joint_population(
        self,
        state: np.ndarray,
        actions: np.ndarray,
        alpha: np.ndarray,
        time_s: float,
        human: BaseParameterHumanModel,
    ) -> dict[str, np.ndarray]:
        count = actions.shape[0]
        horizon = self.config.horizon_steps
        dt = self.config.prediction_dt_s
        low_level_dt = 0.005
        substeps_per_action = int(round(dt / low_level_dt))
        if abs(substeps_per_action * low_level_dt - dt) > 1e-12:
            raise RuntimeError("MPC period must contain an integer number of 5 ms substeps")
        path_steps = horizon * substeps_per_action
        section_start = perf_counter()
        command_states = np.empty((count, path_steps, 4), dtype=float)
        substep_states = np.empty((count, path_steps, 4), dtype=float)
        current = np.broadcast_to(
            np.asarray(state, dtype=float), (count, 4)
        ).copy()
        repeated_actions = np.repeat(actions, substeps_per_action, axis=1)
        try:
            with np.errstate(over="raise", invalid="raise"):
                dynamics_start = perf_counter()
                for step in range(path_steps):
                    command_states[:, step, :] = current
                    current = self._batched_base_step_dt(
                        current, repeated_actions[:, step, :], human, low_level_dt
                    )
                    substep_states[:, step, :] = current
                dynamics_s = perf_counter() - dynamics_start
                tracking_offsets = dt * np.arange(1, horizon + 1, dtype=float)
                command_offsets = low_level_dt * np.arange(path_steps, dtype=float)
                q_ref, dq_ref, _ = self.progress_clock.candidate_reference_arrays(
                    time_s, alpha, tracking_offsets
                )
                q_command_ref, dq_command_ref, _ = (
                    self.progress_clock.candidate_reference_arrays(
                        time_s, alpha, command_offsets
                    )
                )
                predicted = substep_states[:, substeps_per_action - 1 :: substeps_per_action, :]
                force_start = perf_counter()
                feedforward = self._batched_cuff_force_world(
                    repeated_actions, command_states[..., :2], human
                )
                actual_position, actual_velocity = self._batched_position_velocity(
                    command_states[..., :2], command_states[..., 2:], human
                )
                target_position, target_velocity = self._batched_position_velocity(
                    q_command_ref, dq_command_ref, human
                )
                feedback = 3000.0 * (target_position - actual_position)
                feedback += 140.0 * (target_velocity - actual_velocity)
                feedback = np.clip(feedback, -200.0, 200.0)
                total_command = feedback + feedforward
                total_force_norm = np.linalg.norm(total_command, axis=-1)
                allocated_force_norm = np.linalg.norm(feedforward, axis=-1)
                force_s = perf_counter() - force_start
        except (ValueError, OverflowError, FloatingPointError, np.linalg.LinAlgError):
            return {
                "valid": np.zeros(count, dtype=bool),
                "cost": np.full(count, 1.0e30),
                "margin": np.full(count, -1.0e6),
                "states": np.zeros((count, horizon, 4)),
                "substep_states": np.zeros((count, path_steps, 4)),
                "total_force_norm": np.full((count, path_steps), np.inf),
                "allocated_force_norm": np.full((count, path_steps), np.inf),
                "base_cost": np.full(count, 1.0e30),
                "progress_cost": np.full(count, 1.0e30),
                "alpha_change_cost": np.full(count, 1.0e30),
                "timing_s": np.array([perf_counter() - section_start, 0.0, 0.0]),
            }

        finite = np.all(np.isfinite(substep_states), axis=(1, 2))
        bounded = np.max(np.abs(substep_states), axis=(1, 2)) <= 1.0e6
        q_cost = np.sum(
            ((predicted[..., :2] - q_ref) / self.q_scale) ** 2,
            axis=(1, 2),
        )
        dq_cost = np.sum(
            ((predicted[..., 2:] - dq_ref) / self.dq_scale) ** 2,
            axis=(1, 2),
        )
        effort = self.config.action_weight * np.sum(
            (actions / self.action_scale) ** 2, axis=(1, 2)
        )
        delta = np.empty_like(actions)
        delta[:, 0, :] = actions[:, 0, :] - self.last_action
        delta[:, 1:, :] = actions[:, 1:, :] - actions[:, :-1, :]
        action_smoothness = self.config.action_rate_weight * np.sum(
            (delta / self.rate_scale) ** 2, axis=(1, 2)
        )
        base_cost = q_cost + dq_cost + effort + action_smoothness
        span = self.pacing_config.alpha_span
        progress_cost = horizon * (
            (self.pacing_config.maximum_alpha - alpha) / span
        ) ** 2
        alpha_change_cost = ((alpha - self.last_alpha) / span) ** 2
        cost = base_cost + progress_cost + alpha_change_cost

        lower = substep_states[..., :2] - np.asarray(human.q_min_rad)
        upper = np.asarray(human.q_max_rad) - substep_states[..., :2]
        allocated_margin = CUFF_TRANSLATIONAL_FORCE_GATE_N - allocated_force_norm
        total_margin = CUFF_TRANSLATIONAL_FORCE_GATE_N - total_force_norm
        margin = np.min(
            np.concatenate(
                [
                    lower.reshape(count, -1),
                    upper.reshape(count, -1),
                    allocated_margin,
                    total_margin,
                ],
                axis=1,
            ),
            axis=1,
        )
        valid = (
            finite
            & bounded
            & np.isfinite(allocated_force_norm).all(axis=1)
            & np.isfinite(total_force_norm).all(axis=1)
        )
        return {
            "valid": valid,
            "cost": np.where(valid, cost, 1.0e30),
            "margin": np.where(valid, margin, -1.0e6),
            "states": predicted,
            "substep_states": substep_states,
            "total_force_norm": total_force_norm,
            "allocated_force_norm": allocated_force_norm,
            "base_cost": base_cost,
            "progress_cost": progress_cost,
            "alpha_change_cost": alpha_change_cost,
            "timing_s": np.array(
                [dynamics_s, force_s, perf_counter() - section_start]
            ),
        }

    def solve(
        self,
        state: np.ndarray,
        time_s: float,
        reference_fn: Callable[[float], CuffPoseReference],
        human: Any,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        del reference_fn
        solve_start = perf_counter()
        if not self._can_use_batched_population(human):
            raise TypeError(
                "progress-aware CEM requires the frozen batched base model and allocator"
            )
        x0 = np.asarray(state, dtype=float)
        horizon = self.config.horizon_steps
        dt = self.config.prediction_dt_s
        previous_alpha = float(self.progress_clock.alpha)
        seed_q, seed_dq, seed_ddq = self.progress_clock.candidate_reference_arrays(
            time_s,
            np.array([previous_alpha]),
            dt * np.arange(1, horizon + 1, dtype=float),
        )
        action_mean = self._seed_sequence(
            x0, seed_q[0], seed_dq[0], seed_ddq[0], human
        )
        action_std = np.broadcast_to(
            np.asarray(self.config.exploration_std_nm), action_mean.shape
        ).copy()
        action_floor = np.broadcast_to(
            np.asarray(self.config.exploration_std_floor_nm), action_mean.shape
        )
        alpha_mean = previous_alpha
        alpha_std = self.pacing_config.initial_alpha_std

        best: dict[str, Any] | None = None
        feasible_evaluations = 0
        population_time_s = 0.0
        sampling_time_s = 0.0
        elite_time_s = 0.0
        dynamics_time_s = 0.0
        force_time_s = 0.0
        for iteration in range(self.config.cem_iterations):
            start = perf_counter()
            actions = self.rng.normal(
                action_mean,
                action_std,
                size=(self.config.candidate_count, horizon, 2),
            )
            alpha = np.clip(
                self.rng.normal(
                    alpha_mean, alpha_std, size=self.config.candidate_count
                ),
                self.pacing_config.minimum_alpha,
                self.pacing_config.maximum_alpha,
            )
            actions[0] = action_mean
            alpha[0] = alpha_mean
            if self.config.candidate_count > 1:
                alpha[1] = self.pacing_config.minimum_alpha
            sampling_time_s += perf_counter() - start

            start = perf_counter()
            evaluation = self._joint_population(x0, actions, alpha, time_s, human)
            population_time_s += perf_counter() - start
            dynamics_time_s += float(evaluation["timing_s"][0])
            force_time_s += float(evaluation["timing_s"][1])
            feasible = np.flatnonzero(
                evaluation["valid"] & (evaluation["margin"] >= -1e-9)
            )
            feasible_evaluations += len(feasible)
            if not len(feasible):
                continue
            start = perf_counter()
            ordered = feasible[np.argsort(evaluation["cost"][feasible])]
            selected = int(ordered[0])
            if best is None or evaluation["cost"][selected] < best["cost"]:
                best = {
                    "actions": actions[selected].copy(),
                    "alpha": float(alpha[selected]),
                    "cost": float(evaluation["cost"][selected]),
                    "margin": float(evaluation["margin"][selected]),
                    "states": evaluation["states"][selected].copy(),
                    "substep_states": evaluation["substep_states"][selected].copy(),
                    "total_force": evaluation["total_force_norm"][selected].copy(),
                    "allocated_force": evaluation["allocated_force_norm"][selected].copy(),
                    "base_cost": float(evaluation["base_cost"][selected]),
                    "progress_cost": float(evaluation["progress_cost"][selected]),
                    "alpha_change_cost": float(
                        evaluation["alpha_change_cost"][selected]
                    ),
                    "iteration": iteration,
                    "candidate_index": selected,
                }
            elites = ordered[: min(self.config.elite_count, len(ordered))]
            action_mean = np.mean(actions[elites], axis=0)
            action_std = np.maximum(np.std(actions[elites], axis=0), action_floor)
            alpha_mean = float(np.mean(alpha[elites]))
            alpha_std = max(
                float(np.std(alpha[elites])), self.pacing_config.floor_alpha_std
            )
            elite_time_s += perf_counter() - start

        accepted = best is not None
        if best is None:
            fallback_alpha = previous_alpha
            fallback_eval = self._joint_population(
                x0,
                action_mean[None, ...],
                np.array([fallback_alpha]),
                time_s,
                human,
            )
            best = {
                "actions": action_mean.copy(),
                "alpha": fallback_alpha,
                "cost": float(fallback_eval["cost"][0]),
                "margin": float(fallback_eval["margin"][0]),
                "states": fallback_eval["states"][0].copy(),
                "substep_states": fallback_eval["substep_states"][0].copy(),
                "total_force": fallback_eval["total_force_norm"][0].copy(),
                "allocated_force": fallback_eval["allocated_force_norm"][0].copy(),
                "base_cost": float(fallback_eval["base_cost"][0]),
                "progress_cost": float(fallback_eval["progress_cost"][0]),
                "alpha_change_cost": float(
                    fallback_eval["alpha_change_cost"][0]
                ),
                "iteration": None,
                "candidate_index": None,
            }
            self.failure_count += 1

        actions = np.asarray(best["actions"], dtype=float)
        selected_alpha = float(best["alpha"])
        self.last_sequence = actions.copy()
        self.last_action = actions[0].copy()
        self.last_alpha = selected_alpha
        self.solve_count += 1
        solve_elapsed_s = perf_counter() - solve_start
        self.last_diagnostics = {
            "accepted": accepted,
            "optimizer_success": accepted,
            "optimizer": "feasible_first_joint_control_alpha_cem",
            "implementation": "batched",
            "optimizer_iterations": self.config.cem_iterations,
            "candidate_count": self.config.candidate_count,
            "elite_count": self.config.elite_count,
            "joint_population_not_sequential_alpha_solves": True,
            "feasible_candidate_evaluations": feasible_evaluations,
            "selected_alpha": selected_alpha,
            "previous_alpha": previous_alpha,
            "objective": best["cost"],
            "base_mpc_objective": best["base_cost"],
            "pacing_progress_cost": best["progress_cost"],
            "pacing_alpha_change_cost": best["alpha_change_cost"],
            "minimum_constraint_margin": best["margin"],
            "peak_predicted_force_n": float(np.max(best["allocated_force"])),
            "peak_predicted_total_command_force_n": float(
                np.max(best["total_force"])
            ),
            "selected_first_predicted_command_force_n": float(
                best["total_force"][0]
            ),
            "selected_first_control_interval_predicted_command_force_n": (
                np.asarray(best["total_force"][:4], dtype=float).tolist()
            ),
            "selected_first_predicted_allocated_force_n": float(
                best["allocated_force"][0]
            ),
            "selected_iteration": best["iteration"],
            "selected_candidate_index": best["candidate_index"],
            "predicted_rom_respected": bool(
                np.all(best["substep_states"][:, :2] >= np.asarray(human.q_min_rad) - 1e-9)
                and np.all(best["substep_states"][:, :2] <= np.asarray(human.q_max_rad) + 1e-9)
            ),
            "predicted_total_force_gate_respected": bool(
                np.max(best["total_force"])
                <= CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9
            ),
            "predicted_allocated_force_gate_respected": bool(
                np.max(best["allocated_force"])
                <= CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-9
            ),
            "robot_limit_handling": (
                "path-invariant continuous-IK audit plus unchanged runtime robot limit "
                "check; robot dynamics are not part of Human-space MPC state"
            ),
            "objective_contract": {
                "base": self.config.objective_contract(),
                "pacing": self.pacing_config.as_dict(),
                "hard_constraints": [
                    "Human ROM",
                    "allocated cuff translational force <= 200 N",
                    "total low-level translational command force <= 200 N at each 5 ms substep",
                ],
            },
            "implementation_timing_ms": {
                "candidate_sampling_generation": 1000.0 * sampling_time_s,
                "candidate_population_evaluation": 1000.0 * population_time_s,
                "dynamics_propagation": 1000.0 * dynamics_time_s,
                "total_command_force_prediction": 1000.0 * force_time_s,
                "elite_selection_cem_update": 1000.0 * elite_time_s,
                "solve_total": 1000.0 * solve_elapsed_s,
            },
        }
        return actions[0].copy(), dict(self.last_diagnostics)
