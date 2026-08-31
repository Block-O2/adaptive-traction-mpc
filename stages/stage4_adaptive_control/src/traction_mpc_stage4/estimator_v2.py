"""Population-prior, one-shot Human-V2 geometry and base-dynamics estimator.

The estimator/controller-facing API accepts robot-known cuff pose/twist and a
reconstructed cuff wrench.  MuJoCo Human joint state and parameters are not
accepted by this module; they remain evaluation-only in the rollout driver.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
from scipy.optimize import least_squares, lsq_linear
from scipy.spatial.transform import Rotation

from traction_mpc_stage3.frames import RigidTransform
from traction_mpc_stage3.human import HUMAN, HumanV2Parameters, soft_limit_torque
from traction_mpc_stage3.reference import HIP_HEIGHT_M, _world_from_cuff


DYNAMIC_BASE_PARAMETER_NAMES = (
    "a_inertia_combination",
    "b_distal_inertia_combination",
    "d_mass_length_com_combination",
    "g1_proximal_gravity_combination",
    "g2_distal_gravity_combination",
    "k1_passive_stiffness",
    "k2_passive_stiffness",
    "rho1_stiffness_rest_combination",
    "rho2_stiffness_rest_combination",
    "bv1_viscous_damping",
    "bv2_viscous_damping",
)


def nominal_base_parameters(human: HumanV2Parameters = HUMAN) -> np.ndarray:
    """Return the exact 11-parameter base vector of a Human-V2 prior."""

    b = human.shank_inertia_kg_m2 + human.shank_mass_kg * human.shank_com_m**2
    d = human.shank_mass_kg * human.thigh_length_m * human.shank_com_m
    a = (
        human.thigh_inertia_kg_m2
        + human.thigh_mass_kg * human.thigh_com_m**2
        + b
        + human.shank_mass_kg * human.thigh_length_m**2
    )
    g1 = human.gravity_m_s2 * (
        human.thigh_mass_kg * human.thigh_com_m
        + human.shank_mass_kg * human.thigh_length_m
    )
    g2 = human.gravity_m_s2 * human.shank_mass_kg * human.shank_com_m
    stiffness = np.asarray(human.passive_stiffness_nm_rad, dtype=float)
    rest = np.asarray(human.q_rest_rad, dtype=float)
    damping = np.asarray(human.passive_damping_nms_rad, dtype=float)
    return np.array(
        [
            a,
            b,
            d,
            g1,
            g2,
            stiffness[0],
            stiffness[1],
            stiffness[0] * rest[0],
            stiffness[1] * rest[1],
            damping[0],
            damping[1],
        ],
        dtype=float,
    )


def dynamic_regressor_row(
    q_rad: np.ndarray,
    dq_rad_s: np.ndarray,
    ddq_rad_s2: np.ndarray,
) -> np.ndarray:
    """Exact planar-2R inverse-dynamics regressor excluding soft-limit torque."""

    q1, q2 = np.asarray(q_rad, dtype=float)
    dq1, dq2 = np.asarray(dq_rad_s, dtype=float)
    ddq1, ddq2 = np.asarray(ddq_rad_s2, dtype=float)
    phi = q1 - q2
    cosine = math.cos(q2)
    sine = math.sin(q2)
    regressor = np.zeros((2, len(DYNAMIC_BASE_PARAMETER_NAMES)))
    regressor[0] = [
        ddq1,
        -ddq2,
        2.0 * cosine * ddq1
        - cosine * ddq2
        + sine * (-2.0 * dq1 * dq2 + dq2**2),
        math.cos(q1),
        math.cos(phi),
        q1,
        0.0,
        -1.0,
        0.0,
        dq1,
        0.0,
    ]
    regressor[1] = [
        0.0,
        -ddq1 + ddq2,
        -cosine * ddq1 + sine * dq1**2,
        0.0,
        -math.cos(phi),
        0.0,
        q2,
        0.0,
        -1.0,
        0.0,
        dq2,
    ]
    return regressor


def _rank_diagnostics(matrix: np.ndarray) -> dict[str, Any]:
    raw = np.asarray(matrix, dtype=float)
    if raw.ndim != 2 or raw.shape[1] == 0:
        raise ValueError("rank diagnostic matrix must be two-dimensional")
    norms = np.linalg.norm(raw, axis=0)
    normalized = raw / np.where(norms > 1e-15, norms, 1.0)
    singular = np.linalg.svd(normalized, compute_uv=False)
    tolerance = singular[0] * 1e-10 if len(singular) else 0.0
    rank = int(np.linalg.matrix_rank(normalized, tol=tolerance))
    condition = (
        float(singular[0] / singular[-1])
        if len(singular) and singular[-1] > 1e-15
        else float("inf")
    )
    return {
        "rank": rank,
        "nullity": int(raw.shape[1] - rank),
        "condition_number": condition,
        "singular_values": singular.tolist(),
    }


@dataclass(frozen=True)
class PlanarCuffGeometry:
    """Identifiable planar geometry expressed in a population-prior frame."""

    origin_world_m: np.ndarray
    plane_x_world: np.ndarray
    joint_axis_world: np.ndarray
    plane_z_world: np.ndarray
    hip_plane_m: np.ndarray
    thigh_length_m: float
    knee_to_cuff_in_cuff_m: np.ndarray

    @property
    def cuff_offset_rad(self) -> float:
        vector = np.asarray(self.knee_to_cuff_in_cuff_m, dtype=float)
        return float(math.atan2(vector[1], vector[0]))

    @property
    def cuff_distance_m(self) -> float:
        return float(np.linalg.norm(self.knee_to_cuff_in_cuff_m))

    def _project_position(self, position_world_m: np.ndarray) -> np.ndarray:
        delta = np.asarray(position_world_m, dtype=float) - self.origin_world_m
        return np.array(
            [self.plane_x_world @ delta, self.plane_z_world @ delta],
            dtype=float,
        )

    def _cuff_rotation_2d(self, rotation_world_from_cuff: np.ndarray) -> np.ndarray:
        rotation = np.asarray(rotation_world_from_cuff, dtype=float)
        return np.array(
            [
                [self.plane_x_world @ rotation[:, 0], self.plane_x_world @ rotation[:, 2]],
                [self.plane_z_world @ rotation[:, 0], self.plane_z_world @ rotation[:, 2]],
            ],
            dtype=float,
        )

    def estimate_q(self, position_world_m: np.ndarray, rotation_world_from_cuff: np.ndarray) -> np.ndarray:
        cuff_plane = self._project_position(position_world_m)
        rotation_2d = self._cuff_rotation_2d(rotation_world_from_cuff)
        shank_vector = rotation_2d @ np.asarray(self.knee_to_cuff_in_cuff_m)
        knee_plane = cuff_plane - shank_vector
        thigh_vector = knee_plane - np.asarray(self.hip_plane_m)
        q1 = math.atan2(float(thigh_vector[1]), float(thigh_vector[0]))
        phi = math.atan2(float(shank_vector[1]), float(shank_vector[0]))
        return np.array([q1, q1 - phi], dtype=float)

    def translational_jacobian_world(self, q_rad: np.ndarray) -> np.ndarray:
        q1, q2 = np.asarray(q_rad, dtype=float)
        phi = q1 - q2
        distance = self.cuff_distance_m
        shank_angle = phi
        e1_perp = -math.sin(q1) * self.plane_x_world + math.cos(q1) * self.plane_z_world
        shank_perp = -math.sin(shank_angle) * self.plane_x_world + math.cos(shank_angle) * self.plane_z_world
        # The cuff-frame alignment offset is already included in the fitted
        # vector; its world direction is the physical shank direction.
        first = self.thigh_length_m * e1_perp + distance * shank_perp
        second = -distance * shank_perp
        return np.column_stack([first, second])

    def estimate_state(
        self,
        position_world_m: np.ndarray,
        rotation_world_from_cuff: np.ndarray,
        linear_velocity_world_m_s: np.ndarray,
        angular_velocity_world_rad_s: np.ndarray,
    ) -> np.ndarray:
        q = self.estimate_q(position_world_m, rotation_world_from_cuff)
        linear_j = self.translational_jacobian_world(q)
        angular_j = np.column_stack([-self.joint_axis_world, self.joint_axis_world])
        jacobian = np.vstack([linear_j, angular_j])
        twist = np.concatenate(
            [
                np.asarray(linear_velocity_world_m_s, dtype=float),
                np.asarray(angular_velocity_world_rad_s, dtype=float),
            ]
        )
        dq, _, _, _ = np.linalg.lstsq(jacobian, twist, rcond=None)
        return np.concatenate([q, dq])

    def generalized_input_from_wrench(
        self,
        q_rad: np.ndarray,
        force_world_n: np.ndarray,
        moment_world_nm: np.ndarray,
    ) -> np.ndarray:
        force_tau = self.translational_jacobian_world(q_rad).T @ np.asarray(
            force_world_n, dtype=float
        )
        moment_axis = float(self.joint_axis_world @ np.asarray(moment_world_nm, dtype=float))
        return force_tau + np.array([-moment_axis, moment_axis])

    def cuff_pose(self, q_rad: np.ndarray) -> RigidTransform:
        q1, q2 = np.asarray(q_rad, dtype=float)
        phi = q1 - q2
        delta = self.cuff_offset_rad
        shank = self.cuff_distance_m * np.array([math.cos(phi), math.sin(phi)])
        hip = np.asarray(self.hip_plane_m)
        position_plane = hip + self.thigh_length_m * np.array([math.cos(q1), math.sin(q1)]) + shank
        position_world = (
            self.origin_world_m
            + position_plane[0] * self.plane_x_world
            + position_plane[1] * self.plane_z_world
        )
        cuff_angle = phi - delta
        cuff_x = math.cos(cuff_angle) * self.plane_x_world + math.sin(cuff_angle) * self.plane_z_world
        cuff_z = -math.sin(cuff_angle) * self.plane_x_world + math.cos(cuff_angle) * self.plane_z_world
        rotation = np.column_stack([cuff_x, self.joint_axis_world, cuff_z])
        return RigidTransform(rotation, position_world)

    def cuff_velocity(self, q_rad: np.ndarray, dq_rad_s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        dq = np.asarray(dq_rad_s, dtype=float)
        linear = self.translational_jacobian_world(q_rad) @ dq
        angular = self.joint_axis_world * float(dq[1] - dq[0])
        return linear, angular


@dataclass(frozen=True)
class GeometryEstimatorConfig:
    update_interval_samples: int = 25
    minimum_samples: int = 25
    maximum_condition_number: float = 1.0e6
    minimum_axis_excitation_rad: float = math.radians(3.0)
    residual_acceptance_ratio: float = 1.02
    residual_absolute_allowance_m: float = 5.0e-4
    regularization_weight: float = 1.0e-3
    smoothing_alpha: float = 0.20
    maximum_update_fraction_of_span: float = 0.05
    maximum_residual_rms_m: float = 2.0e-3
    max_nfev: int = 100


class AccumulatedCuffGeometryEstimator:
    """Accumulated-pose geometry fit with a nominal Human-V2 cold-start prior."""

    def __init__(
        self,
        initial_position_world_m: np.ndarray,
        initial_rotation_world_from_cuff: np.ndarray,
        initial_q_prior_rad: np.ndarray,
        config: GeometryEstimatorConfig = GeometryEstimatorConfig(),
    ) -> None:
        self.config = config
        initial_position = np.asarray(initial_position_world_m, dtype=float)
        initial_rotation = np.asarray(initial_rotation_world_from_cuff, dtype=float)
        q0 = np.asarray(initial_q_prior_rad, dtype=float)
        nominal_pose = _world_from_cuff(q0)
        alignment = initial_rotation @ nominal_pose.rotation.T
        prior_axis = alignment[:, 1]
        prior_x = alignment[:, 0]
        prior_z = alignment[:, 2]
        nominal_hip = np.array([0.0, 0.0, HIP_HEIGHT_M])
        translation = initial_position - alignment @ nominal_pose.translation
        origin = alignment @ nominal_hip + translation
        self.prior_axis_world = prior_axis / np.linalg.norm(prior_axis)
        self.prior_plane_x_world = prior_x / np.linalg.norm(prior_x)
        self.prior_plane_z_world = prior_z / np.linalg.norm(prior_z)
        self.origin_world_m = origin
        self.initial_rotation = initial_rotation.copy()
        self.prior = np.array(
            [0.0, 0.0, HUMAN.thigh_length_m, HUMAN.sleeve_center_m, 0.0],
            dtype=float,
        )
        self.lower = np.array(
            [-0.25, -0.25, 0.75 * HUMAN.thigh_length_m, 0.50 * HUMAN.sleeve_center_m, -0.15],
            dtype=float,
        )
        self.upper = np.array(
            [0.25, 0.25, 1.25 * HUMAN.thigh_length_m, 1.50 * HUMAN.sleeve_center_m, 0.15],
            dtype=float,
        )
        self.span = self.upper - self.lower
        self.last_valid = self.prior.copy()
        self.samples: list[tuple[float, np.ndarray, np.ndarray]] = []
        self.total_measurements = 0
        self.rejected_contaminated_samples = 0
        self.accepted_updates = 0
        self.rejected_updates = 0
        self.trustworthy_time_s: float | None = None
        self.last_diagnostics = self._empty_diagnostics("population_prior")
        self.geometry = self._geometry_from_parameters(
            self.last_valid,
            self.prior_axis_world,
            self.prior_plane_x_world,
            self.prior_plane_z_world,
        )

    def _axis_and_basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, int]:
        if not self.samples:
            return (
                self.prior_axis_world.copy(),
                self.prior_plane_x_world.copy(),
                self.prior_plane_z_world.copy(),
                0.0,
                0,
            )
        rotvecs = np.array(
            [
                Rotation.from_matrix(rotation @ self.initial_rotation.T).as_rotvec()
                for _, _, rotation in self.samples
            ]
        )
        excitation = float(np.max(np.linalg.norm(rotvecs, axis=1)))
        singular = np.linalg.svd(rotvecs, compute_uv=False)
        # Rotation-matrix roundoff can create tiny transverse rotvec entries;
        # the common-axis rank test deliberately ignores that numerical dust.
        rank = int(np.linalg.matrix_rank(rotvecs, tol=singular[0] * 1e-6)) if len(singular) and singular[0] > 0.0 else 0
        if rank < 1 or excitation < self.config.minimum_axis_excitation_rad:
            axis = self.prior_axis_world.copy()
        else:
            _, _, vh = np.linalg.svd(rotvecs, full_matrices=False)
            axis = vh[0]
            if axis @ self.prior_axis_world < 0.0:
                axis = -axis
        axis /= np.linalg.norm(axis)
        plane_x = self.prior_plane_x_world - axis * float(axis @ self.prior_plane_x_world)
        plane_x /= np.linalg.norm(plane_x)
        plane_z = np.cross(plane_x, axis)
        plane_z /= np.linalg.norm(plane_z)
        return axis, plane_x, plane_z, excitation, rank

    def _data_arrays(
        self, plane_x: np.ndarray, plane_z: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        positions = []
        rotations = []
        for _, position, rotation in self.samples:
            delta = position - self.origin_world_m
            positions.append([plane_x @ delta, plane_z @ delta])
            rotations.append(
                [
                    [plane_x @ rotation[:, 0], plane_x @ rotation[:, 2]],
                    [plane_z @ rotation[:, 0], plane_z @ rotation[:, 2]],
                ]
            )
        return np.asarray(positions), np.asarray(rotations)

    @staticmethod
    def _radial_residual(
        parameters: np.ndarray, positions: np.ndarray, rotations: np.ndarray
    ) -> np.ndarray:
        hip = parameters[:2]
        thigh_length = float(parameters[2])
        cuff_vector = parameters[3:5]
        knees = positions - np.einsum("nij,j->ni", rotations, cuff_vector)
        return np.linalg.norm(knees - hip, axis=1) - thigh_length

    def _numerical_jacobian(
        self, parameters: np.ndarray, positions: np.ndarray, rotations: np.ndarray
    ) -> np.ndarray:
        columns = []
        for index in range(len(parameters)):
            step = max(1e-8, self.span[index] * 1e-5)
            plus = parameters.copy()
            minus = parameters.copy()
            plus[index] = min(self.upper[index], plus[index] + step)
            minus[index] = max(self.lower[index], minus[index] - step)
            derivative = (
                self._radial_residual(plus, positions, rotations)
                - self._radial_residual(minus, positions, rotations)
            ) / (plus[index] - minus[index])
            columns.append(derivative * self.span[index])
        return np.column_stack(columns)

    def _geometry_from_parameters(
        self,
        parameters: np.ndarray,
        axis: np.ndarray,
        plane_x: np.ndarray,
        plane_z: np.ndarray,
    ) -> PlanarCuffGeometry:
        return PlanarCuffGeometry(
            origin_world_m=self.origin_world_m.copy(),
            plane_x_world=np.asarray(plane_x, dtype=float).copy(),
            joint_axis_world=np.asarray(axis, dtype=float).copy(),
            plane_z_world=np.asarray(plane_z, dtype=float).copy(),
            hip_plane_m=np.asarray(parameters[:2], dtype=float).copy(),
            thigh_length_m=float(parameters[2]),
            knee_to_cuff_in_cuff_m=np.asarray(parameters[3:5], dtype=float).copy(),
        )

    def add_pose(
        self,
        time_s: float,
        position_world_m: np.ndarray,
        rotation_world_from_cuff: np.ndarray,
        *,
        contaminated: bool,
    ) -> dict[str, Any]:
        self.total_measurements += 1
        if contaminated:
            self.rejected_contaminated_samples += 1
            self.last_diagnostics = self._empty_diagnostics("contaminated_sample_excluded")
            return dict(self.last_diagnostics)
        self.samples.append(
            (
                float(time_s),
                np.asarray(position_world_m, dtype=float).copy(),
                np.asarray(rotation_world_from_cuff, dtype=float).copy(),
            )
        )
        if (
            len(self.samples) < self.config.minimum_samples
            or len(self.samples) % self.config.update_interval_samples != 0
        ):
            self.last_diagnostics = self._empty_diagnostics("accumulating_information")
            return dict(self.last_diagnostics)
        self.last_diagnostics = self._attempt_update(float(time_s))
        return dict(self.last_diagnostics)

    def _attempt_update(self, time_s: float) -> dict[str, Any]:
        axis, plane_x, plane_z, excitation, axis_rank = self._axis_and_basis()
        positions, rotations = self._data_arrays(plane_x, plane_z)
        old_residual = self._radial_residual(self.last_valid, positions, rotations)
        prior = self.prior.copy()

        def objective(parameters: np.ndarray) -> np.ndarray:
            data = self._radial_residual(parameters, positions, rotations) / 0.002
            regularization = (
                math.sqrt(self.config.regularization_weight)
                * (parameters - prior)
                / self.span
            )
            return np.concatenate([data, regularization])

        try:
            result = least_squares(
                objective,
                self.last_valid,
                bounds=(self.lower, self.upper),
                loss="huber",
                f_scale=1.345,
                max_nfev=self.config.max_nfev,
            )
        except (ValueError, np.linalg.LinAlgError) as error:
            self.rejected_updates += 1
            diagnostics = self._empty_diagnostics(f"optimizer_exception:{type(error).__name__}")
            diagnostics["attempted"] = True
            return diagnostics
        candidate = np.asarray(result.x, dtype=float)
        candidate_residual = self._radial_residual(candidate, positions, rotations)
        jacobian = self._numerical_jacobian(candidate, positions, rotations)
        rank_diag = _rank_diagnostics(jacobian)
        old_rms = float(np.sqrt(np.mean(old_residual**2)))
        candidate_rms = float(np.sqrt(np.mean(candidate_residual**2)))
        bound_hit = bool(
            np.any(np.isclose(candidate, self.lower, atol=1e-7, rtol=0.0))
            or np.any(np.isclose(candidate, self.upper, atol=1e-7, rtol=0.0))
        )
        reasons = []
        if not result.success or not np.all(np.isfinite(candidate)):
            reasons.append("optimizer_failed")
        if axis_rank < 1 or excitation < self.config.minimum_axis_excitation_rad:
            reasons.append("axis_not_excited")
        if rank_diag["rank"] < 5:
            reasons.append("rank_deficient")
        if not np.isfinite(rank_diag["condition_number"]) or rank_diag["condition_number"] > self.config.maximum_condition_number:
            reasons.append("ill_conditioned")
        if candidate_rms > self.config.residual_acceptance_ratio * old_rms + self.config.residual_absolute_allowance_m:
            reasons.append("residual_not_accepted")
        if candidate_rms > self.config.maximum_residual_rms_m:
            reasons.append("residual_too_large")
        if bound_hit:
            reasons.append("bound_hit")
        accepted = not reasons
        if accepted:
            step = self.config.smoothing_alpha * (candidate - self.last_valid)
            maximum_step = self.config.maximum_update_fraction_of_span * self.span
            self.last_valid = np.clip(
                self.last_valid + np.clip(step, -maximum_step, maximum_step),
                self.lower,
                self.upper,
            )
            self.geometry = self._geometry_from_parameters(
                self.last_valid, axis, plane_x, plane_z
            )
            self.accepted_updates += 1
            if self.trustworthy_time_s is None:
                self.trustworthy_time_s = time_s
        else:
            self.rejected_updates += 1
        return {
            "attempted": True,
            "accepted": accepted,
            "reason": "accepted" if accepted else ",".join(reasons),
            "sample_count": len(self.samples),
            "axis_rank": axis_rank,
            "axis_excitation_deg": math.degrees(excitation),
            **rank_diag,
            "old_residual_rms_m": old_rms,
            "candidate_residual_rms_m": candidate_rms,
            "candidate": candidate.tolist(),
            "applied": self.last_valid.tolist(),
            "bound_hit": bound_hit,
            "last_valid_fallback_used": not accepted,
        }

    def _empty_diagnostics(self, reason: str) -> dict[str, Any]:
        return {
            "attempted": False,
            "accepted": False,
            "reason": reason,
            "sample_count": len(self.samples),
            "rank": 0,
            "nullity": 5,
            "condition_number": float("nan"),
            "axis_rank": 0,
            "axis_excitation_deg": 0.0,
            "applied": self.last_valid.tolist(),
            "last_valid_fallback_used": True,
        }


@dataclass(frozen=True)
class DynamicIdentifierConfig:
    update_interval_measurements: int = 25
    minimum_clean_samples: int = 80
    maximum_condition_number: float = 1.0e5
    residual_acceptance_ratio: float = 1.02
    residual_absolute_allowance_nm: float = 0.05
    regularization_weight: float = 1.0e-3
    smoothing_alpha: float = 0.10
    maximum_update_fraction_of_span: float = 0.03


class AccumulatedBaseDynamicIdentifier:
    """Cumulative 11-base-parameter linear identifier with gated updates."""

    def __init__(self, config: DynamicIdentifierConfig = DynamicIdentifierConfig()) -> None:
        self.config = config
        self.population_prior = nominal_base_parameters()
        lower = 0.50 * self.population_prior
        upper = 1.50 * self.population_prior
        rest_margin = math.radians(10.0)
        for stiffness_index, rho_index, rest_value in (
            (5, 7, HUMAN.q_rest_rad[0]),
            (6, 8, HUMAN.q_rest_rad[1]),
        ):
            lower[rho_index] = lower[stiffness_index] * (rest_value - rest_margin)
            upper[rho_index] = upper[stiffness_index] * (rest_value + rest_margin)
        self.lower = lower
        self.upper = upper
        self.span = self.upper - self.lower
        self.last_valid = self.population_prior.copy()
        self.accepted_updates = 0
        self.rejected_updates = 0
        self.trustworthy_time_s: float | None = None
        self.last_attempt_measurement_count = 0
        self.last_diagnostics = self._empty_diagnostics("population_prior")

    def parameter_estimate(self) -> dict[str, float]:
        return {
            name: float(value)
            for name, value in zip(
                DYNAMIC_BASE_PARAMETER_NAMES, self.last_valid, strict=True
            )
        }

    def attempt_update(
        self,
        raw_history: list[dict[str, Any]],
        geometry: PlanarCuffGeometry,
    ) -> dict[str, Any]:
        if len(raw_history) - self.last_attempt_measurement_count < self.config.update_interval_measurements:
            self.last_diagnostics = self._empty_diagnostics("between_updates")
            return dict(self.last_diagnostics)
        self.last_attempt_measurement_count = len(raw_history)
        clean = [sample for sample in raw_history if not sample["contaminated"]]
        if len(clean) < self.config.minimum_clean_samples:
            self.last_diagnostics = self._empty_diagnostics("insufficient_clean_samples")
            return dict(self.last_diagnostics)
        times = np.array([sample["time_s"] for sample in clean], dtype=float)
        states = np.array(
            [
                geometry.estimate_state(
                    sample["position_world_m"],
                    sample["rotation_world_from_cuff"],
                    sample["linear_velocity_world_m_s"],
                    sample["angular_velocity_world_rad_s"],
                )
                for sample in clean
            ]
        )
        q = states[:, :2]
        dq = states[:, 2:]
        ddq = np.gradient(dq, times, axis=0, edge_order=2)
        tau = np.array(
            [
                geometry.generalized_input_from_wrench(
                    angles, sample["force_world_n"], sample["moment_world_nm"]
                )
                for angles, sample in zip(q, clean, strict=True)
            ]
        )
        keep = np.ones(len(clean), dtype=bool)
        keep[:2] = False
        keep[-2:] = False
        for index, (angles, velocity) in enumerate(zip(q, dq, strict=True)):
            if np.linalg.norm(soft_limit_torque(angles, velocity, HUMAN)) > 1e-8:
                keep[index] = False
        q = q[keep]
        dq = dq[keep]
        ddq = ddq[keep]
        tau = tau[keep]
        if len(q) < self.config.minimum_clean_samples:
            self.last_diagnostics = self._empty_diagnostics("insufficient_clean_derivative_samples")
            return dict(self.last_diagnostics)
        regressor = np.vstack(
            [
                dynamic_regressor_row(angles, velocity, acceleration)
                for angles, velocity, acceleration in zip(q, dq, ddq, strict=True)
            ]
        )
        target = tau.reshape(-1)
        scaled_regressor = regressor * self.span
        rank_diag = _rank_diagnostics(scaled_regressor)
        old_prediction = regressor @ self.last_valid
        old_residual = old_prediction - target
        augmented_a = np.vstack(
            [
                scaled_regressor,
                math.sqrt(self.config.regularization_weight) * np.eye(len(self.last_valid)),
            ]
        )
        augmented_b = np.concatenate(
            [
                target - regressor @ self.population_prior,
                np.zeros(len(self.last_valid)),
            ]
        )
        z_lower = (self.lower - self.population_prior) / self.span
        z_upper = (self.upper - self.population_prior) / self.span
        try:
            result = lsq_linear(
                augmented_a,
                augmented_b,
                bounds=(z_lower, z_upper),
                method="trf",
                lsmr_tol="auto",
            )
        except (ValueError, np.linalg.LinAlgError) as error:
            self.rejected_updates += 1
            diagnostics = self._empty_diagnostics(f"optimizer_exception:{type(error).__name__}")
            diagnostics["attempted"] = True
            return diagnostics
        candidate = self.population_prior + self.span * np.asarray(result.x)
        candidate_residual = regressor @ candidate - target
        old_rms = float(np.sqrt(np.mean(old_residual**2)))
        candidate_rms = float(np.sqrt(np.mean(candidate_residual**2)))
        bound_hit = bool(
            np.any(np.isclose(candidate, self.lower, atol=1e-7, rtol=0.0))
            or np.any(np.isclose(candidate, self.upper, atol=1e-7, rtol=0.0))
        )
        covariance = np.linalg.pinv(scaled_regressor.T @ scaled_regressor, rcond=1e-12)
        std = np.sqrt(np.maximum(np.diag(covariance), 0.0))
        correlation = np.divide(
            covariance,
            np.outer(std, std),
            out=np.full_like(covariance, np.nan),
            where=np.outer(std, std) > 0.0,
        )
        off_diagonal = correlation.copy()
        np.fill_diagonal(off_diagonal, 0.0)
        max_correlation = float(np.nanmax(np.abs(off_diagonal)))
        candidate_model = BaseParameterHumanModel(geometry, candidate)
        positive_definite = candidate_model.minimum_mass_matrix_eigenvalue() > 1e-6
        reasons = []
        if not result.success or not np.all(np.isfinite(candidate)):
            reasons.append("optimizer_failed")
        if rank_diag["rank"] < len(DYNAMIC_BASE_PARAMETER_NAMES):
            reasons.append("rank_deficient")
        if not np.isfinite(rank_diag["condition_number"]) or rank_diag["condition_number"] > self.config.maximum_condition_number:
            reasons.append("ill_conditioned")
        if candidate_rms > self.config.residual_acceptance_ratio * old_rms + self.config.residual_absolute_allowance_nm:
            reasons.append("residual_not_accepted")
        if bound_hit:
            reasons.append("bound_hit")
        if not positive_definite:
            reasons.append("non_positive_definite_mass_matrix")
        accepted = not reasons
        if accepted:
            step = self.config.smoothing_alpha * (candidate - self.last_valid)
            maximum_step = self.config.maximum_update_fraction_of_span * self.span
            self.last_valid = np.clip(
                self.last_valid + np.clip(step, -maximum_step, maximum_step),
                self.lower,
                self.upper,
            )
            self.accepted_updates += 1
            if self.trustworthy_time_s is None:
                self.trustworthy_time_s = float(clean[-1]["time_s"])
        else:
            self.rejected_updates += 1
        self.last_diagnostics = {
            "attempted": True,
            "accepted": accepted,
            "reason": "accepted" if accepted else ",".join(reasons),
            "raw_measurement_count": len(raw_history),
            "clean_dynamic_samples": int(len(q)),
            **rank_diag,
            "old_residual_rms_nm": old_rms,
            "candidate_residual_rms_nm": candidate_rms,
            "maximum_abs_correlation": max_correlation,
            "candidate": candidate.tolist(),
            "applied": self.last_valid.tolist(),
            "bound_hit": bound_hit,
            "positive_definite_mass_matrix": positive_definite,
            "last_valid_fallback_used": not accepted,
        }
        return dict(self.last_diagnostics)

    def _empty_diagnostics(self, reason: str) -> dict[str, Any]:
        return {
            "attempted": False,
            "accepted": False,
            "reason": reason,
            "rank": 0,
            "nullity": len(DYNAMIC_BASE_PARAMETER_NAMES),
            "condition_number": float("nan"),
            "applied": self.last_valid.tolist(),
            "last_valid_fallback_used": True,
        }


@dataclass(frozen=True)
class BaseParameterHumanModel:
    geometry: PlanarCuffGeometry
    beta: np.ndarray
    rom_human: HumanV2Parameters = HUMAN

    @property
    def q_min_rad(self) -> tuple[float, float]:
        return self.rom_human.q_min_rad

    @property
    def q_max_rad(self) -> tuple[float, float]:
        return self.rom_human.q_max_rad

    def mass_matrix(self, q_rad: np.ndarray) -> np.ndarray:
        q2 = float(np.asarray(q_rad)[1])
        a, b, d = np.asarray(self.beta, dtype=float)[:3]
        cosine = math.cos(q2)
        return np.array(
            [
                [a + 2.0 * d * cosine, -(b + d * cosine)],
                [-(b + d * cosine), b],
            ]
        )

    def inverse_dynamics(
        self,
        q_rad: np.ndarray,
        dq_rad_s: np.ndarray,
        ddq_rad_s2: np.ndarray,
    ) -> np.ndarray:
        regressor = dynamic_regressor_row(q_rad, dq_rad_s, ddq_rad_s2)
        torque = regressor @ np.asarray(self.beta, dtype=float)
        return torque - soft_limit_torque(q_rad, dq_rad_s, self.rom_human)

    def continuous_dynamics(self, state: np.ndarray, action_nm: np.ndarray) -> np.ndarray:
        x = np.asarray(state, dtype=float)
        zero_acceleration = self.inverse_dynamics(x[:2], x[2:], np.zeros(2))
        qdd = np.linalg.solve(
            self.mass_matrix(x[:2]), np.asarray(action_nm, dtype=float) - zero_acceleration
        )
        return np.concatenate([x[2:], qdd])

    def step_dynamics(self, state: np.ndarray, action_nm: np.ndarray, dt_s: float) -> np.ndarray:
        x = np.asarray(state, dtype=float)
        u = np.asarray(action_nm, dtype=float)
        dt = float(dt_s)
        k1 = self.continuous_dynamics(x, u)
        k2 = self.continuous_dynamics(x + 0.5 * dt * k1, u)
        k3 = self.continuous_dynamics(x + 0.5 * dt * k2, u)
        k4 = self.continuous_dynamics(x + dt * k3, u)
        return x + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0

    def allocate_generalized_action(self, generalized_action_nm: np.ndarray, q_rad: np.ndarray) -> dict[str, Any]:
        torque = np.asarray(generalized_action_nm, dtype=float)
        force_map = self.geometry.translational_jacobian_world(q_rad).T
        moment_map = np.array([1.0, -1.0])
        moment_orthogonal = np.array([1.0, 1.0]) / math.sqrt(2.0)
        projected_force_map = force_map.T @ moment_orthogonal
        denominator = float(projected_force_map @ projected_force_map)
        if denominator <= 1e-18:
            raise RuntimeError("estimated rigid-cuff allocation is singular")
        force_world = (
            projected_force_map
            * float(moment_orthogonal @ torque)
            / denominator
        )
        my_nm = float(
            moment_map @ (torque - force_map @ force_world)
            / (moment_map @ moment_map)
        )
        moment_world = -self.geometry.joint_axis_world * my_nm
        residual = float(
            np.linalg.norm(force_map @ force_world + moment_map * my_nm - torque)
        )
        return {
            "force_world_n": force_world,
            "force_norm_n": float(np.linalg.norm(force_world)),
            "my_nm": my_nm,
            "wrench_world": np.concatenate([force_world, moment_world]),
            "allocation_residual_nm": residual,
        }

    def minimum_mass_matrix_eigenvalue(self) -> float:
        values = []
        for q2 in np.linspace(self.q_min_rad[1], self.q_max_rad[1], 21):
            values.append(float(np.min(np.linalg.eigvalsh(self.mass_matrix([0.0, q2])))))
        return min(values)


class OneShotHumanEstimatorV2:
    """Coordinates cumulative geometry and dynamic identification online."""

    def __init__(
        self,
        initial_position_world_m: np.ndarray,
        initial_rotation_world_from_cuff: np.ndarray,
        initial_q_prior_rad: np.ndarray,
    ) -> None:
        self.geometry_identifier = AccumulatedCuffGeometryEstimator(
            initial_position_world_m,
            initial_rotation_world_from_cuff,
            initial_q_prior_rad,
        )
        self.dynamic_identifier = AccumulatedBaseDynamicIdentifier()
        self.raw_history: list[dict[str, Any]] = []
        self.last_state = self.geometry_identifier.geometry.estimate_state(
            initial_position_world_m,
            initial_rotation_world_from_cuff,
            np.zeros(3),
            np.zeros(3),
        )
        self.geometry_diagnostics: list[dict[str, Any]] = []
        self.dynamic_diagnostics: list[dict[str, Any]] = []

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
        provisional_state = self.geometry.estimate_state(
            position_world_m,
            rotation_world_from_cuff,
            linear_velocity_world_m_s,
            angular_velocity_world_rad_s,
        )
        soft_limit_contaminated = bool(
            np.linalg.norm(
                soft_limit_torque(provisional_state[:2], provisional_state[2:], HUMAN)
            )
            > 1e-8
        )
        contaminated = bool(bed_contaminated or soft_limit_contaminated)
        raw = {
            "time_s": float(time_s),
            "position_world_m": np.asarray(position_world_m, dtype=float).copy(),
            "rotation_world_from_cuff": np.asarray(rotation_world_from_cuff, dtype=float).copy(),
            "linear_velocity_world_m_s": np.asarray(linear_velocity_world_m_s, dtype=float).copy(),
            "angular_velocity_world_rad_s": np.asarray(angular_velocity_world_rad_s, dtype=float).copy(),
            "force_world_n": np.asarray(force_world_n, dtype=float).copy(),
            "moment_world_nm": np.asarray(moment_world_nm, dtype=float).copy(),
            "bed_contaminated": bool(bed_contaminated),
            "soft_limit_contaminated": soft_limit_contaminated,
            "contaminated": contaminated,
        }
        self.raw_history.append(raw)
        geometry_diag = self.geometry_identifier.add_pose(
            time_s,
            position_world_m,
            rotation_world_from_cuff,
            contaminated=contaminated,
        )
        if geometry_diag["attempted"]:
            self.geometry_diagnostics.append(dict(geometry_diag, time_s=float(time_s)))
        self.last_state = self.geometry.estimate_state(
            position_world_m,
            rotation_world_from_cuff,
            linear_velocity_world_m_s,
            angular_velocity_world_rad_s,
        )
        if self.geometry_identifier.trustworthy_time_s is not None:
            dynamic_diag = self.dynamic_identifier.attempt_update(
                self.raw_history, self.geometry
            )
            if dynamic_diag["attempted"]:
                self.dynamic_diagnostics.append(dict(dynamic_diag, time_s=float(time_s)))
        else:
            dynamic_diag = self.dynamic_identifier._empty_diagnostics(
                "geometry_not_trustworthy"
            )
        return self.last_state.copy(), {
            "geometry": geometry_diag,
            "dynamics": dynamic_diag,
            "bed_contaminated": bool(bed_contaminated),
            "soft_limit_contaminated": soft_limit_contaminated,
        }
