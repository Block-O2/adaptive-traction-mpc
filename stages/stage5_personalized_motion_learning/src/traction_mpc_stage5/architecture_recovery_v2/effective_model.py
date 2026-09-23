"""Causal control-effective geometry and dynamics estimation for V2.

The geometry state intentionally contains the cuff-observable distance from the
knee to the cuff, not full shank length and cuff fraction separately.  Hidden
plant parameters are never accepted by these estimator APIs.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
from scipy.optimize import least_squares, lsq_linear

from traction_mpc_stage4.estimator_v2 import (
    DYNAMIC_BASE_PARAMETER_NAMES,
    PlanarCuffGeometry,
    dynamic_regressor_row,
    nominal_base_parameters,
)


@dataclass(frozen=True)
class EffectiveGeometryFit:
    """Control-effective planar fit and diagnostics."""

    hip_xz_m: np.ndarray
    thigh_length_m: float
    knee_to_cuff_m: float
    residual_rms_m: float
    maximum_residual_m: float
    condition_number: float
    sample_count: int
    angular_span_rad: float
    accepted: bool
    reason: str

    def __post_init__(self) -> None:
        hip = np.asarray(self.hip_xz_m, dtype=float)
        if hip.shape != (2,) or not np.all(np.isfinite(hip)):
            raise ValueError("hip_xz_m must be a finite two-vector")
        object.__setattr__(self, "hip_xz_m", hip.copy())

    def record(self) -> dict[str, Any]:
        return {
            "representation": (
                "control_effective_[hip_x,hip_z,L1,knee_to_cuff]; "
                "full_L2_and_cuff_fraction_not_reconstructed"
            ),
            "hip_xz_m": self.hip_xz_m.tolist(),
            "thigh_length_m": self.thigh_length_m,
            "knee_to_cuff_m": self.knee_to_cuff_m,
            "residual_rms_m": self.residual_rms_m,
            "maximum_residual_m": self.maximum_residual_m,
            "condition_number": self.condition_number,
            "sample_count": self.sample_count,
            "angular_span_rad": self.angular_span_rad,
            "accepted": self.accepted,
            "reason": self.reason,
        }


def _unwrap_span(values: np.ndarray) -> float:
    unwrapped = np.unwrap(np.asarray(values, dtype=float))
    return float(np.max(unwrapped) - np.min(unwrapped)) if len(unwrapped) else 0.0


def fit_effective_geometry(
    cuff_position_xz_m: np.ndarray,
    shank_angle_rad: np.ndarray,
    *,
    prior_hip_xz_m: np.ndarray = np.array([0.0, 0.062]),
    prior_thigh_length_m: float = 0.437,
    prior_knee_to_cuff_m: float = 0.288,
    minimum_samples: int = 30,
    minimum_angular_span_rad: float = math.radians(4.0),
    maximum_residual_rms_m: float = 0.003,
    maximum_condition_number: float = 2.0e5,
) -> EffectiveGeometryFit:
    """Fit a circle after removing an unknown shank-direction cuff lever arm.

    For observation ``p = hip + L1 e(q1) + sc e(phi)``, a candidate ``sc``
    maps every cuff point to a knee point.  The correct knee points lie on a
    circle with center ``hip`` and radius ``L1``.  This fit recovers only the
    control-effective tuple ``(hip, L1, sc)`` and never attempts to split
    ``sc=f*L2``.
    """

    position = np.asarray(cuff_position_xz_m, dtype=float)
    angle = np.asarray(shank_angle_rad, dtype=float)
    if position.ndim != 2 or position.shape[1] != 2:
        raise ValueError("cuff_position_xz_m must be Nx2")
    if angle.shape != (len(position),):
        raise ValueError("shank_angle_rad must match position samples")
    if not np.all(np.isfinite(position)) or not np.all(np.isfinite(angle)):
        raise ValueError("geometry observations must be finite")
    if len(position) < minimum_samples:
        return EffectiveGeometryFit(
            np.asarray(prior_hip_xz_m, dtype=float),
            prior_thigh_length_m,
            prior_knee_to_cuff_m,
            float("inf"),
            float("inf"),
            float("inf"),
            len(position),
            _unwrap_span(angle),
            False,
            "insufficient_samples",
        )
    angular_span = _unwrap_span(angle)
    if angular_span < minimum_angular_span_rad:
        return EffectiveGeometryFit(
            np.asarray(prior_hip_xz_m, dtype=float),
            prior_thigh_length_m,
            prior_knee_to_cuff_m,
            float("inf"),
            float("inf"),
            float("inf"),
            len(position),
            angular_span,
            False,
            "insufficient_shank_angle_excitation",
        )

    direction = np.column_stack([np.cos(angle), np.sin(angle)])
    regularization_weight = (
        1.0e-3 if angular_span < math.radians(20.0) else 1.0e-5
    )
    prior = np.array(
        [
            float(prior_hip_xz_m[0]),
            float(prior_hip_xz_m[1]),
            float(prior_thigh_length_m),
            float(prior_knee_to_cuff_m),
        ]
    )
    scale = np.array([0.25, 0.20, 0.12, 0.14])
    lower = np.array([-0.35, -0.05, 0.30, 0.14])
    upper = np.array([0.35, 0.30, 0.56, 0.48])

    def residual(value: np.ndarray, *, include_regularization: bool) -> np.ndarray:
        hip = value[:2]
        knee = position - value[3] * direction
        radius_error = np.linalg.norm(knee - hip, axis=1) - value[2]
        if not include_regularization:
            return radius_error
        # MAP-scaled population prior resolves the hip/L1 compensation branch
        # of a short commissioning arc.  Once the observed shank rotation is
        # broad, reduce the prior by two orders so informative data dominate.
        regularization = regularization_weight * (value - prior) / scale
        return np.concatenate([radius_error, regularization])

    solved = least_squares(
        lambda value: residual(value, include_regularization=True),
        np.clip(prior, lower, upper),
        bounds=(lower, upper),
        max_nfev=500,
        x_scale=scale,
    )
    value = np.asarray(solved.x, dtype=float)
    data_residual = residual(value, include_regularization=False)
    singular = np.linalg.svd(np.asarray(solved.jac, dtype=float), compute_uv=False)
    condition = (
        float(singular[0] / singular[-1])
        if len(singular) and singular[-1] > 1.0e-14
        else float("inf")
    )
    rms = float(np.sqrt(np.mean(data_residual**2)))
    maximum = float(np.max(np.abs(data_residual)))
    reasons: list[str] = []
    if not solved.success or not np.all(np.isfinite(value)):
        reasons.append("optimizer_failed")
    if rms > maximum_residual_rms_m:
        reasons.append("residual_too_large")
    if not np.isfinite(condition) or condition > maximum_condition_number:
        reasons.append("ill_conditioned")
    if np.any(np.isclose(value, lower, atol=1.0e-6, rtol=0.0)) or np.any(
        np.isclose(value, upper, atol=1.0e-6, rtol=0.0)
    ):
        reasons.append("bound_hit")
    return EffectiveGeometryFit(
        value[:2],
        float(value[2]),
        float(value[3]),
        rms,
        maximum,
        condition,
        len(position),
        angular_span,
        not reasons,
        "accepted" if not reasons else ",".join(reasons),
    )


def build_planar_geometry(fit: EffectiveGeometryFit) -> PlanarCuffGeometry:
    """Embed a 2-D effective fit in the Stage-4 WORLD X/Z convention."""

    if not fit.accepted:
        raise ValueError("cannot build control geometry from a rejected fit")
    return PlanarCuffGeometry(
        origin_world_m=np.zeros(3),
        plane_x_world=np.array([1.0, 0.0, 0.0]),
        joint_axis_world=np.array([0.0, 1.0, 0.0]),
        plane_z_world=np.array([0.0, 0.0, 1.0]),
        hip_plane_m=fit.hip_xz_m.copy(),
        thigh_length_m=fit.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([fit.knee_to_cuff_m, 0.0]),
    )


class CausalEffectiveGeometryEstimator:
    """Append-only pose history with explicit causal fit activation."""

    def __init__(self) -> None:
        self.positions: list[np.ndarray] = []
        self.angles: list[float] = []
        self.fit: EffectiveGeometryFit | None = None
        self.activation_sample_count: int | None = None

    def observe(self, position_xz_m: np.ndarray, shank_angle_rad: float) -> None:
        position = np.asarray(position_xz_m, dtype=float)
        if position.shape != (2,) or not np.all(np.isfinite(position)):
            raise ValueError("position_xz_m must be a finite two-vector")
        if not math.isfinite(shank_angle_rad):
            raise ValueError("shank_angle_rad must be finite")
        self.positions.append(position.copy())
        self.angles.append(float(shank_angle_rad))

    def attempt_fit(self, **kwargs: Any) -> EffectiveGeometryFit:
        proposed = fit_effective_geometry(
            np.asarray(self.positions), np.asarray(self.angles), **kwargs
        )
        if proposed.accepted:
            self.fit = proposed
            if self.activation_sample_count is None:
                self.activation_sample_count = len(self.positions)
        return proposed


class OnlineEffectiveDynamicsIdentifier:
    """Causal bounded batch identifier for the 11 Human-V2 base parameters."""

    def __init__(
        self,
        *,
        minimum_samples: int = 80,
        update_interval: int = 25,
        ridge_weight: float = 1.0e-3,
        smoothing_alpha: float = 0.10,
        maximum_update_fraction_of_span: float = 0.03,
        minimum_mass_matrix_eigenvalue: float = 0.03,
    ) -> None:
        self.minimum_samples = int(minimum_samples)
        self.update_interval = int(update_interval)
        self.ridge_weight = float(ridge_weight)
        self.smoothing_alpha = float(smoothing_alpha)
        self.maximum_update_fraction_of_span = float(
            maximum_update_fraction_of_span
        )
        self.minimum_mass_matrix_eigenvalue = float(
            minimum_mass_matrix_eigenvalue
        )
        if self.minimum_mass_matrix_eigenvalue <= 0.0:
            raise ValueError("minimum_mass_matrix_eigenvalue must be positive")
        self.prior = nominal_base_parameters()
        self.lower = 0.45 * self.prior
        self.upper = 1.65 * self.prior
        # rho=k*q_rest may be near zero or sign-changing; use physical ranges.
        self.lower[7:9] = -0.30 * self.prior[5:7]
        self.upper[7:9] = 0.60 * self.prior[5:7]
        self.span = self.upper - self.lower
        self.beta = self.prior.copy()
        self.rows: list[np.ndarray] = []
        self.targets: list[np.ndarray] = []
        self.maximum_history_samples: int | None = None
        self._recency_samples_since_update = 0
        self.last_update_count = 0
        self.accepted_updates = 0
        self.rejected_updates = 0
        self.rejection_reason_counts: dict[str, int] = {}
        self.last_diagnostics: dict[str, Any] = {
            "attempted": False,
            "accepted": False,
            "reason": "population_prior",
        }
        self.last_attempt_diagnostics: dict[str, Any] = dict(self.last_diagnostics)

    def enable_recency_window(self, maximum_history_samples: int) -> None:
        """Bound future refits to recent causal data without resetting beta.

        Commissioning establishes the initial control-effective model.  When
        the effective parameterization must also absorb geometry mismatch, a
        bounded task-phase history lets newly visited operating regions replace
        old probe rows instead of being diluted by an ever-growing batch.
        """

        maximum = int(maximum_history_samples)
        if maximum < self.minimum_samples:
            raise ValueError(
                "maximum_history_samples must be at least minimum_samples"
            )
        self.maximum_history_samples = maximum
        if len(self.rows) > maximum:
            self.rows = self.rows[-maximum:]
            self.targets = self.targets[-maximum:]
        self._recency_samples_since_update = 0

    def observe(
        self,
        q_rad: np.ndarray,
        dq_rad_s: np.ndarray,
        ddq_rad_s2: np.ndarray,
        applied_generalized_torque_nm: np.ndarray,
    ) -> dict[str, Any]:
        row = dynamic_regressor_row(q_rad, dq_rad_s, ddq_rad_s2)
        target = np.asarray(applied_generalized_torque_nm, dtype=float)
        if target.shape != (2,) or not np.all(np.isfinite(target)):
            raise ValueError("applied_generalized_torque_nm must be finite")
        self.rows.append(row)
        self.targets.append(target.copy())
        if self.maximum_history_samples is not None:
            if len(self.rows) > self.maximum_history_samples:
                excess = len(self.rows) - self.maximum_history_samples
                del self.rows[:excess]
                del self.targets[:excess]
            self._recency_samples_since_update += 1
        if len(self.rows) < self.minimum_samples:
            self.last_diagnostics = {
                "attempted": False,
                "accepted": False,
                "reason": "insufficient_samples",
                "sample_count": len(self.rows),
            }
            return dict(self.last_diagnostics)
        between_updates = (
            self._recency_samples_since_update < self.update_interval
            if self.maximum_history_samples is not None
            else len(self.rows) - self.last_update_count < self.update_interval
        )
        if between_updates:
            self.last_diagnostics = {
                "attempted": False,
                "accepted": False,
                "reason": "between_updates",
                "sample_count": len(self.rows),
            }
            return dict(self.last_diagnostics)
        self.last_update_count = len(self.rows)
        if self.maximum_history_samples is not None:
            self._recency_samples_since_update = 0
        matrix = np.vstack(self.rows)
        target = np.concatenate(self.targets)
        scaled = matrix * self.span
        column_norm = np.linalg.norm(scaled, axis=0)
        normalized = scaled / np.where(column_norm > 1.0e-12, column_norm, 1.0)
        singular = np.linalg.svd(normalized, compute_uv=False)
        rank = int(np.linalg.matrix_rank(normalized, tol=singular[0] * 1.0e-9))
        condition = (
            float(singular[0] / singular[-1])
            if singular[-1] > 1.0e-14
            else float("inf")
        )
        augmented_a = np.vstack(
            [scaled, math.sqrt(self.ridge_weight) * np.eye(len(self.prior))]
        )
        augmented_b = np.concatenate(
            [target - matrix @ self.prior, np.zeros(len(self.prior))]
        )
        lower_z = (self.lower - self.prior) / self.span
        upper_z = (self.upper - self.prior) / self.span
        solved = lsq_linear(
            augmented_a,
            augmented_b,
            bounds=(lower_z, upper_z),
            method="trf",
            lsmr_tol="auto",
        )
        candidate = self.prior + self.span * np.asarray(solved.x)
        old_rms = float(np.sqrt(np.mean((matrix @ self.beta - target) ** 2)))
        raw_candidate_rms = float(
            np.sqrt(np.mean((matrix @ candidate - target) ** 2))
        )
        reasons: list[str] = []
        raw_bound_mask = np.isclose(
            candidate, self.lower, atol=1.0e-7, rtol=0.0
        ) | np.isclose(candidate, self.upper, atol=1.0e-7, rtol=0.0)
        bound_hit = bool(np.any(raw_bound_mask))
        # A boundary solution is evidence that the corresponding individual
        # component is not trustworthy, not evidence that every interior
        # component must be discarded.  Freezing boundary dimensions after a
        # joint fit, however, invalidates the other coefficients because the
        # regressor columns are correlated. Refit the remaining dimensions
        # conditionally with every boundary-limited coefficient held at its
        # last-valid value. Repeat if the conditional solution exposes another
        # boundary dimension.
        def conditional_refit(
            initial_frozen_mask: np.ndarray,
        ) -> tuple[np.ndarray, bool, np.ndarray]:
            frozen = initial_frozen_mask.copy()
            trusted = self.beta.copy()
            success = True
            while np.any(~frozen):
                free = np.flatnonzero(~frozen)
                fixed = np.flatnonzero(frozen)
                fixed_z = (self.beta[fixed] - self.prior[fixed]) / self.span[fixed]
                data_target = target - matrix @ self.prior
                if len(fixed):
                    data_target = data_target - scaled[:, fixed] @ fixed_z
                conditional_a = np.vstack(
                    [
                        scaled[:, free],
                        math.sqrt(self.ridge_weight) * np.eye(len(free)),
                    ]
                )
                conditional_b = np.concatenate(
                    [data_target, np.zeros(len(free))]
                )
                conditional = lsq_linear(
                    conditional_a,
                    conditional_b,
                    bounds=(lower_z[free], upper_z[free]),
                    method="trf",
                    lsmr_tol="auto",
                )
                if not conditional.success or not np.all(
                    np.isfinite(conditional.x)
                ):
                    success = False
                    break
                proposal = self.prior[free] + self.span[free] * np.asarray(
                    conditional.x
                )
                newly_frozen_local = np.isclose(
                    proposal, self.lower[free], atol=1.0e-7, rtol=0.0
                ) | np.isclose(
                    proposal, self.upper[free], atol=1.0e-7, rtol=0.0
                )
                if np.any(newly_frozen_local):
                    frozen[free[newly_frozen_local]] = True
                    continue
                trusted[free] = proposal
                break
            return trusted, success, frozen

        def mass_margin(beta: np.ndarray) -> float:
            return min(
                float(
                    np.min(
                        np.linalg.eigvalsh(
                            np.array(
                                [
                                    [
                                        beta[0] + 2.0 * beta[2] * math.cos(q2),
                                        -(beta[1] + beta[2] * math.cos(q2)),
                                    ],
                                    [
                                        -(beta[1] + beta[2] * math.cos(q2)),
                                        beta[1],
                                    ],
                                ]
                            )
                        )
                    )
                )
                for q2 in np.linspace(0.0, math.radians(100.0), 21)
            )

        trusted_candidate, conditional_refit_success, frozen_mask = (
            conditional_refit(raw_bound_mask)
        )
        minimum_mass_eigenvalue = mass_margin(trusted_candidate)
        mass_margin_frozen_mask = np.zeros_like(frozen_mask)
        if minimum_mass_eigenvalue < self.minimum_mass_matrix_eigenvalue:
            mass_margin_frozen_mask[:3] = True
            trusted_candidate, mass_refit_success, frozen_mask = conditional_refit(
                frozen_mask | mass_margin_frozen_mask
            )
            conditional_refit_success &= mass_refit_success
            minimum_mass_eigenvalue = mass_margin(trusted_candidate)
        trusted_rms = float(
            np.sqrt(np.mean((matrix @ trusted_candidate - target) ** 2))
        )
        if not solved.success or not np.all(np.isfinite(candidate)):
            reasons.append("optimizer_failed")
        if not conditional_refit_success:
            reasons.append("conditional_refit_failed")
        if rank < len(DYNAMIC_BASE_PARAMETER_NAMES):
            reasons.append("rank_deficient")
        if not np.isfinite(condition) or condition > 2.0e5:
            reasons.append("ill_conditioned")
        if trusted_rms > old_rms + 0.02:
            reasons.append("residual_not_improved")
        if np.all(frozen_mask):
            reasons.append("all_parameters_bound_limited")
        if minimum_mass_eigenvalue < self.minimum_mass_matrix_eigenvalue:
            reasons.append("insufficient_mass_matrix_margin")
        if reasons:
            self.rejected_updates += 1
            for reason in reasons:
                self.rejection_reason_counts[reason] = (
                    self.rejection_reason_counts.get(reason, 0) + 1
                )
        else:
            step = self.smoothing_alpha * (trusted_candidate - self.beta)
            maximum_step = self.maximum_update_fraction_of_span * self.span
            self.beta = np.clip(
                self.beta + np.clip(step, -maximum_step, maximum_step),
                self.lower,
                self.upper,
            )
            self.accepted_updates += 1
        self.last_diagnostics = {
            "attempted": True,
            "accepted": not reasons,
            "reason": "accepted" if not reasons else ",".join(reasons),
            "sample_count": len(self.rows),
            "maximum_history_samples": self.maximum_history_samples,
            "rank": rank,
            "condition_number": condition,
            "old_residual_rms_nm": old_rms,
            "raw_candidate_residual_rms_nm": raw_candidate_rms,
            "trusted_candidate_residual_rms_nm": trusted_rms,
            "bound_hit": bound_hit,
            "frozen_bound_parameter_names": [
                name
                for name, frozen in zip(
                    DYNAMIC_BASE_PARAMETER_NAMES, raw_bound_mask, strict=True
                )
                if frozen
            ],
            "frozen_mass_margin_parameter_names": [
                name
                for name, frozen in zip(
                    DYNAMIC_BASE_PARAMETER_NAMES,
                    mass_margin_frozen_mask,
                    strict=True,
                )
                if frozen
            ],
            "frozen_conditional_parameter_names": [
                name
                for name, frozen in zip(
                    DYNAMIC_BASE_PARAMETER_NAMES,
                    frozen_mask,
                    strict=True,
                )
                if frozen
            ],
            "minimum_mass_matrix_eigenvalue": minimum_mass_eigenvalue,
            "candidate": candidate.tolist(),
            "trusted_candidate": trusted_candidate.tolist(),
            "applied": self.beta.tolist(),
            "truth_consumed": False,
        }
        self.last_attempt_diagnostics = dict(self.last_diagnostics)
        return dict(self.last_diagnostics)

    def record(self) -> dict[str, Any]:
        return {
            "representation": "11_dimensional_control_effective_base_beta",
            "parameter_names": list(DYNAMIC_BASE_PARAMETER_NAMES),
            "beta": self.beta.tolist(),
            "sample_count": len(self.rows),
            "maximum_history_samples": self.maximum_history_samples,
            "accepted_updates": self.accepted_updates,
            "rejected_updates": self.rejected_updates,
            "rejection_reason_counts": dict(self.rejection_reason_counts),
            "truth_consumed": False,
            "minimum_mass_matrix_eigenvalue_required": (
                self.minimum_mass_matrix_eigenvalue
            ),
            "last_diagnostics": dict(self.last_diagnostics),
            "last_attempt_diagnostics": dict(self.last_attempt_diagnostics),
        }
