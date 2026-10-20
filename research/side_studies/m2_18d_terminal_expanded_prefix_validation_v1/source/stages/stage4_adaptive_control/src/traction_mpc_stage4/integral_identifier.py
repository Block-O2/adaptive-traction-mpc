"""Causal integral regression for the 11 Human-V2 base parameters.

The regression integrates the existing exact linear inverse-dynamics model
over trailing windows and analytically integrates by parts every acceleration
term.  Its API therefore requires q, dq, and measured generalized input, but
never instantaneous qdd.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
from scipy.linalg import qr
from scipy.optimize import lsq_linear

from traction_mpc_stage3.human import HUMAN

from .estimator_v2 import (
    DYNAMIC_BASE_PARAMETER_NAMES,
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    _rank_diagnostics,
    nominal_base_parameters,
)


def integral_regression_block(
    time_s: np.ndarray,
    state: np.ndarray,
    generalized_input_nm: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return one two-row integral regressor and integrated torque target."""

    time = np.asarray(time_s, dtype=float)
    states = np.asarray(state, dtype=float)
    torque = np.asarray(generalized_input_nm, dtype=float)
    if (
        time.ndim != 1
        or states.shape != (len(time), 4)
        or torque.shape != (len(time), 2)
        or len(time) < 3
        or np.any(np.diff(time) <= 0.0)
    ):
        raise ValueError("integral block requires increasing time and aligned [q,dq,tau]")
    q1, q2, dq1, dq2 = states.T
    cosine = np.cos(q2)
    sine = np.sin(q2)
    phi = q1 - q2
    duration = float(time[-1] - time[0])
    regressor = np.zeros((2, len(DYNAMIC_BASE_PARAMETER_NAMES)))

    # Exact boundary terms after integration by parts.
    regressor[0, 0] = dq1[-1] - dq1[0]
    regressor[0, 1] = -(dq2[-1] - dq2[0])
    regressor[0, 2] = (
        2.0 * cosine[-1] * dq1[-1]
        - cosine[-1] * dq2[-1]
        - 2.0 * cosine[0] * dq1[0]
        + cosine[0] * dq2[0]
    )
    regressor[1, 1] = (-dq1[-1] + dq2[-1]) - (-dq1[0] + dq2[0])
    regressor[1, 2] = (
        -cosine[-1] * dq1[-1]
        + cosine[0] * dq1[0]
        + np.trapezoid(sine * dq1 * (dq1 - dq2), time)
    )

    # Low-bandwidth integral terms.
    regressor[0, 3] = np.trapezoid(np.cos(q1), time)
    regressor[0, 4] = np.trapezoid(np.cos(phi), time)
    regressor[1, 4] = -regressor[0, 4]
    regressor[0, 5] = np.trapezoid(q1, time)
    regressor[1, 6] = np.trapezoid(q2, time)
    regressor[0, 7] = -duration
    regressor[1, 8] = -duration
    regressor[0, 9] = q1[-1] - q1[0]
    regressor[1, 10] = q2[-1] - q2[0]
    target = np.trapezoid(torque, time, axis=0)
    return regressor, target


def _svd_rrqr_diagnostics(matrix: np.ndarray) -> dict[str, Any]:
    raw = np.asarray(matrix, dtype=float)
    svd = _rank_diagnostics(raw)
    norms = np.linalg.norm(raw, axis=0)
    normalized = raw / np.where(norms > 1e-15, norms, 1.0)
    _, r, pivots = qr(normalized, mode="economic", pivoting=True)
    diagonal = np.abs(np.diag(r))
    tolerance = diagonal[0] * 1e-10 if len(diagonal) else 0.0
    rrqr_rank = int(np.sum(diagonal > tolerance))
    return {
        **svd,
        "rrqr_rank": rrqr_rank,
        "rrqr_diagonal": diagonal.tolist(),
        "rrqr_pivots": np.asarray(pivots, dtype=int).tolist(),
    }


@dataclass(frozen=True)
class IntegralDynamicIdentifierConfig:
    update_interval_measurements: int = 25
    integration_window_s: float = 0.50
    block_stride_measurements: int = 5
    minimum_integral_blocks: int = 20
    maximum_condition_number: float = 1.0e5
    residual_acceptance_ratio: float = 1.02
    residual_absolute_allowance_nms: float = 0.025
    regularization_weight: float = 1.0e-3
    smoothing_alpha: float = 0.10
    maximum_update_fraction_of_span: float = 0.03


class AccumulatedIntegralBaseDynamicIdentifier:
    """Accumulated, gated 11-base-parameter identifier without qdd input."""

    def __init__(
        self,
        config: IntegralDynamicIdentifierConfig = IntegralDynamicIdentifierConfig(),
    ) -> None:
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
        self.span = upper - lower
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

    def _integral_blocks(
        self,
        raw_history: list[dict[str, Any]],
        geometry: PlanarCuffGeometry,
    ) -> tuple[np.ndarray, np.ndarray, int]:
        times = np.array([item["time_s"] for item in raw_history], dtype=float)
        regressors: list[np.ndarray] = []
        targets: list[np.ndarray] = []
        contaminated_windows = 0
        for end in range(
            self.config.block_stride_measurements,
            len(raw_history),
            self.config.block_stride_measurements,
        ):
            start = int(
                np.searchsorted(
                    times,
                    times[end] - self.config.integration_window_s,
                    side="left",
                )
            )
            if times[end] - times[start] < 0.90 * self.config.integration_window_s:
                continue
            segment = raw_history[start : end + 1]
            if any(bool(item["contaminated"]) for item in segment):
                contaminated_windows += 1
                continue
            block_time = times[start : end + 1]
            block_state = np.array([item["state"] for item in segment], dtype=float)
            block_tau = np.array(
                [
                    geometry.generalized_input_from_wrench(
                        item["state"][:2],
                        item["force_world_n"],
                        item["moment_world_nm"],
                    )
                    for item in segment
                ],
                dtype=float,
            )
            block_regressor, block_target = integral_regression_block(
                block_time, block_state, block_tau
            )
            regressors.append(block_regressor)
            targets.append(block_target)
        if not regressors:
            return (
                np.empty((0, len(DYNAMIC_BASE_PARAMETER_NAMES))),
                np.empty(0),
                contaminated_windows,
            )
        return (
            np.vstack(regressors),
            np.concatenate(targets),
            contaminated_windows,
        )

    def attempt_update(
        self,
        raw_history: list[dict[str, Any]],
        geometry: PlanarCuffGeometry,
    ) -> dict[str, Any]:
        if (
            len(raw_history) - self.last_attempt_measurement_count
            < self.config.update_interval_measurements
        ):
            self.last_diagnostics = self._empty_diagnostics("between_updates")
            return dict(self.last_diagnostics)
        self.last_attempt_measurement_count = len(raw_history)
        regressor, target, contaminated_windows = self._integral_blocks(
            raw_history, geometry
        )
        integral_blocks = len(target) // 2
        if integral_blocks < self.config.minimum_integral_blocks:
            self.last_diagnostics = self._empty_diagnostics(
                "insufficient_clean_integral_blocks"
            )
            self.last_diagnostics.update(
                {
                    "integral_block_count": integral_blocks,
                    "contaminated_integral_windows": contaminated_windows,
                }
            )
            return dict(self.last_diagnostics)

        scaled_regressor = regressor * self.span
        rank_diag = _svd_rrqr_diagnostics(scaled_regressor)
        old_residual = regressor @ self.last_valid - target
        augmented_a = np.vstack(
            [
                scaled_regressor,
                math.sqrt(self.config.regularization_weight)
                * np.eye(len(self.last_valid)),
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
            diagnostics = self._empty_diagnostics(
                f"optimizer_exception:{type(error).__name__}"
            )
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
        covariance = np.linalg.pinv(
            scaled_regressor.T @ scaled_regressor, rcond=1e-12
        )
        std = np.sqrt(np.maximum(np.diag(covariance), 0.0))
        correlation = np.divide(
            covariance,
            np.outer(std, std),
            out=np.full_like(covariance, np.nan),
            where=np.outer(std, std) > 0.0,
        )
        off_diagonal = correlation.copy()
        np.fill_diagonal(off_diagonal, 0.0)
        maximum_abs_correlation = float(np.nanmax(np.abs(off_diagonal)))
        candidate_model = BaseParameterHumanModel(geometry, candidate)
        positive_definite = candidate_model.minimum_mass_matrix_eigenvalue() > 1e-6
        reasons: list[str] = []
        if not result.success or not np.all(np.isfinite(candidate)):
            reasons.append("optimizer_failed")
        if rank_diag["rank"] < len(DYNAMIC_BASE_PARAMETER_NAMES):
            reasons.append("svd_rank_deficient")
        if rank_diag["rrqr_rank"] < len(DYNAMIC_BASE_PARAMETER_NAMES):
            reasons.append("rrqr_rank_deficient")
        if (
            not np.isfinite(rank_diag["condition_number"])
            or rank_diag["condition_number"] > self.config.maximum_condition_number
        ):
            reasons.append("ill_conditioned")
        if (
            candidate_rms
            > self.config.residual_acceptance_ratio * old_rms
            + self.config.residual_absolute_allowance_nms
        ):
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
                self.trustworthy_time_s = float(raw_history[-1]["time_s"])
        else:
            self.rejected_updates += 1
        self.last_diagnostics = {
            "attempted": True,
            "accepted": accepted,
            "reason": "accepted" if accepted else ",".join(reasons),
            "raw_measurement_count": len(raw_history),
            "integral_block_count": integral_blocks,
            "contaminated_integral_windows": contaminated_windows,
            "integration_window_s": self.config.integration_window_s,
            **rank_diag,
            "old_residual_rms_nms": old_rms,
            "candidate_residual_rms_nms": candidate_rms,
            "maximum_abs_correlation": maximum_abs_correlation,
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
            "rrqr_rank": 0,
            "nullity": len(DYNAMIC_BASE_PARAMETER_NAMES),
            "condition_number": float("nan"),
            "applied": self.last_valid.tolist(),
            "last_valid_fallback_used": True,
        }
