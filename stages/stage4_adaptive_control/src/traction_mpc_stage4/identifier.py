"""Quality-gated Windowed NLS for the selected Human-V2 parameter subspace."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from .human_model import PARAMETER_BOUNDS, nominal_parameter_vector, parameterized_human, step_dynamics


ESTIMATED_PARAMETER_NAMES = (
    "mass_scale",
    "stiffness_scale",
    "rest_common_offset_rad",
)


@dataclass(frozen=True)
class IdentifierConfig:
    sample_dt_s: float = 0.02
    window_size: int = 100
    update_interval: int = 10
    minimum_samples: int = 40
    smoothing_alpha: float = 0.25
    maximum_update_fraction_of_span: float = 0.05
    maximum_condition_number: float = 1.0e6
    maximum_abs_correlation: float = 0.98
    residual_acceptance_ratio: float = 1.02
    regularization_weight: float = 1.0e-3
    max_nfev: int = 80
    maximum_bed_contact_fraction: float = 0.05
    state_residual_scale: tuple[float, float, float, float] = (
        np.radians(0.05),
        np.radians(0.05),
        np.radians(0.5),
        np.radians(0.5),
    )


class WindowedHumanNLS:
    """Exact-discrete NLS with bounded updates and last-valid-model fallback."""

    def __init__(self, config: IdentifierConfig = IdentifierConfig()) -> None:
        self.config = config
        self.names = ESTIMATED_PARAMETER_NAMES
        self.lower = np.array([PARAMETER_BOUNDS[name][0] for name in self.names])
        self.upper = np.array([PARAMETER_BOUNDS[name][1] for name in self.names])
        self.span = self.upper - self.lower
        self.theta_hat = nominal_parameter_vector(self.names)
        self.last_valid_theta = self.theta_hat.copy()
        self.transitions: deque[tuple[np.ndarray, np.ndarray, np.ndarray, float]] = deque(maxlen=config.window_size)
        self.transition_count = 0
        self.accepted_updates = 0
        self.rejected_updates = 0
        self.last_diagnostics = self._empty_diagnostics("not_attempted")

    @property
    def human_model(self):
        return parameterized_human(self.last_valid_theta, self.names)

    def parameter_estimate(self) -> dict[str, float]:
        return {name: float(value) for name, value in zip(self.names, self.last_valid_theta, strict=True)}

    def add_transition(
        self,
        state: np.ndarray,
        action_nm: np.ndarray,
        next_state: np.ndarray,
        *,
        bed_contact_fraction: float = 0.0,
    ) -> dict[str, Any]:
        x = np.asarray(state, dtype=float)
        u = np.asarray(action_nm, dtype=float)
        xn = np.asarray(next_state, dtype=float)
        if x.shape != (4,) or xn.shape != (4,) or (u.ndim == 1 and u.shape != (2,)) or (u.ndim == 2 and u.shape[1:] != (2,)):
            raise ValueError("Human NLS transition requires state (4), action (2) or (N,2), next_state (4)")
        if not (np.all(np.isfinite(x)) and np.all(np.isfinite(u)) and np.all(np.isfinite(xn))):
            raise ValueError("Human NLS transition values must be finite")
        contamination = float(bed_contact_fraction)
        if not np.isfinite(contamination) or not 0.0 <= contamination <= 1.0:
            raise ValueError("bed_contact_fraction must be finite and within [0,1]")
        self.transitions.append((x.copy(), u.copy(), xn.copy(), contamination))
        self.transition_count += 1
        if (
            len(self.transitions) < self.config.minimum_samples
            or self.transition_count % self.config.update_interval != 0
        ):
            self.last_diagnostics = self._empty_diagnostics("insufficient_or_between_updates")
            return dict(self.last_diagnostics)
        self.last_diagnostics = self._attempt_update()
        return dict(self.last_diagnostics)

    def _clean_transitions(self) -> list[tuple[np.ndarray, np.ndarray, np.ndarray, float]]:
        return [transition for transition in self.transitions if transition[3] <= 0.0]

    def _predict_next(self, state: np.ndarray, action_profile: np.ndarray, human: Any) -> np.ndarray:
        actions = np.asarray(action_profile, dtype=float)
        if actions.ndim == 1:
            return step_dynamics(state, actions, self.config.sample_dt_s, human)
        predicted = np.asarray(state, dtype=float)
        substep_dt = self.config.sample_dt_s / len(actions)
        for action in actions:
            predicted = step_dynamics(predicted, action, substep_dt, human)
        return predicted

    def _data_residual(self, theta: np.ndarray) -> np.ndarray:
        human = parameterized_human(theta, self.names)
        scale = np.asarray(self.config.state_residual_scale)
        rows = [
            (self._predict_next(x, u, human) - xn) / scale
            for x, u, xn, _ in self._clean_transitions()
        ]
        return np.asarray(rows).reshape(-1)

    def _optimizer_residual(self, theta: np.ndarray, prior: np.ndarray) -> np.ndarray:
        regularization = np.sqrt(self.config.regularization_weight) * (theta - prior) / self.span
        return np.concatenate([self._data_residual(theta), regularization])

    def _numerical_jacobian(self, theta: np.ndarray) -> np.ndarray:
        columns = []
        for index in range(len(theta)):
            step = max(1e-8, self.span[index] * 1e-5)
            plus = theta.copy(); minus = theta.copy()
            plus[index] = min(self.upper[index], plus[index] + step)
            minus[index] = max(self.lower[index], minus[index] - step)
            derivative = (self._data_residual(plus) - self._data_residual(minus)) / (plus[index] - minus[index])
            columns.append(derivative * self.span[index])
        return np.column_stack(columns)

    def _attempt_update(self) -> dict[str, Any]:
        bed_contact_fraction = float(np.mean([transition[3] for transition in self.transitions]))
        clean_sample_count = len(self._clean_transitions())
        if bed_contact_fraction > self.config.maximum_bed_contact_fraction:
            self.rejected_updates += 1
            diagnostics = self._empty_diagnostics("bed_contact_contaminated_window")
            diagnostics.update(
                {
                    "attempted": True,
                    "bed_contact_fraction": bed_contact_fraction,
                    "clean_samples": clean_sample_count,
                    "last_valid_fallback_used": True,
                }
            )
            return diagnostics
        if clean_sample_count < self.config.minimum_samples:
            self.rejected_updates += 1
            diagnostics = self._empty_diagnostics("insufficient_clean_samples")
            diagnostics.update(
                {
                    "attempted": True,
                    "bed_contact_fraction": bed_contact_fraction,
                    "clean_samples": clean_sample_count,
                    "last_valid_fallback_used": True,
                }
            )
            return diagnostics
        prior = self.last_valid_theta.copy()
        old_residual = self._data_residual(prior)
        try:
            result = least_squares(
                lambda theta: self._optimizer_residual(theta, prior),
                prior,
                bounds=(self.lower, self.upper),
                loss="huber",
                f_scale=1.345,
                max_nfev=self.config.max_nfev,
            )
        except (ValueError, np.linalg.LinAlgError) as error:
            self.rejected_updates += 1
            return self._empty_diagnostics(f"optimizer_exception:{type(error).__name__}")
        candidate = np.asarray(result.x, dtype=float)
        candidate_residual = self._data_residual(candidate)
        jacobian = self._numerical_jacobian(candidate)
        singular_values = np.linalg.svd(jacobian, compute_uv=False)
        rank = int(np.linalg.matrix_rank(jacobian, tol=singular_values[0] * 1e-10)) if len(singular_values) else 0
        info = jacobian.T @ jacobian
        condition = float(np.linalg.cond(info))
        covariance = np.linalg.pinv(info, rcond=1e-12)
        std = np.sqrt(np.maximum(np.diag(covariance), 0.0))
        denom = np.outer(std, std)
        correlation = np.divide(covariance, denom, out=np.full_like(covariance, np.nan), where=denom > 0.0)
        off_diagonal = correlation.copy()
        np.fill_diagonal(off_diagonal, 0.0)
        max_correlation = float(np.nanmax(np.abs(off_diagonal)))
        old_rms = float(np.sqrt(np.mean(old_residual**2)))
        candidate_rms = float(np.sqrt(np.mean(candidate_residual**2)))
        bound_hit = bool(
            np.any(np.isclose(candidate, self.lower, atol=1e-7, rtol=0.0))
            or np.any(np.isclose(candidate, self.upper, atol=1e-7, rtol=0.0))
        )
        reasons = []
        if not result.success or not np.all(np.isfinite(candidate)):
            reasons.append("optimizer_failed")
        if rank < len(self.names):
            reasons.append("rank_deficient")
        if not np.isfinite(condition) or condition > self.config.maximum_condition_number:
            reasons.append("ill_conditioned")
        if not np.isfinite(max_correlation) or max_correlation > self.config.maximum_abs_correlation:
            reasons.append("correlated")
        if candidate_rms > self.config.residual_acceptance_ratio * old_rms:
            reasons.append("residual_not_improved")
        if bound_hit:
            reasons.append("bound_hit")
        accepted = not reasons
        applied = prior.copy()
        if accepted:
            raw_step = self.config.smoothing_alpha * (candidate - prior)
            maximum_step = self.config.maximum_update_fraction_of_span * self.span
            applied = np.clip(prior + np.clip(raw_step, -maximum_step, maximum_step), self.lower, self.upper)
            self.theta_hat = candidate.copy()
            self.last_valid_theta = applied.copy()
            self.accepted_updates += 1
        else:
            self.rejected_updates += 1
        return {
            "attempted": True,
            "accepted": accepted,
            "reason": "accepted" if accepted else ",".join(reasons),
            "valid_samples": len(self.transitions),
            "clean_samples": clean_sample_count,
            "bed_contact_fraction": bed_contact_fraction,
            "rank": rank,
            "condition_number": condition,
            "singular_values": singular_values.tolist(),
            "correlation": correlation.tolist(),
            "maximum_abs_correlation": max_correlation,
            "old_normalized_residual_rms": old_rms,
            "candidate_normalized_residual_rms": candidate_rms,
            "candidate": {name: float(value) for name, value in zip(self.names, candidate, strict=True)},
            "applied": self.parameter_estimate(),
            "bound_hit": bound_hit,
            "optimizer_success": bool(result.success),
            "optimizer_nfev": int(result.nfev),
            "last_valid_fallback_used": not accepted,
        }

    def _empty_diagnostics(self, reason: str) -> dict[str, Any]:
        return {
            "attempted": False,
            "accepted": False,
            "reason": reason,
            "valid_samples": len(self.transitions),
            "clean_samples": len(self._clean_transitions()),
            "bed_contact_fraction": (
                float(np.mean([transition[3] for transition in self.transitions]))
                if self.transitions
                else 0.0
            ),
            "rank": 0,
            "condition_number": float("nan"),
            "maximum_abs_correlation": float("nan"),
            "applied": self.parameter_estimate(),
            "last_valid_fallback_used": True,
        }
