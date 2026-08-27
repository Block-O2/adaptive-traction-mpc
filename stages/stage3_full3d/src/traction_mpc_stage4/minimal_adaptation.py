"""Prior-based control-relevant adaptation primitives for Stage 4.

This module deliberately does not identify anatomical Human-V2 parameters.
It restricts the existing integral inverse-dynamics regression to three
dimensionless scales and defines a controller-neutral confidence payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from .estimator_v2 import DYNAMIC_BASE_PARAMETER_NAMES, nominal_base_parameters
from .integral_identifier import integral_regression_block


CONTROL_RELEVANT_DYNAMIC_PARAMETER_NAMES = (
    "effective_mass_scale",
    "effective_stiffness_scale",
    "effective_damping_scale",
)

CONTROL_RELEVANT_GEOMETRY_PARAMETER_NAMES = (
    "effective_leg_length_m",
    "cuff_alignment_x_m",
    "cuff_alignment_z_m",
)


def dynamic_scale_projection(prior: np.ndarray | None = None) -> np.ndarray:
    """Map three effective scales into the frozen 11-base-parameter model.

    Uniform mass scales the five inertial/gravity combinations, uniform
    stiffness scales both stiffness and stiffness-rest combinations, and
    uniform damping scales both viscous coefficients.  At ``[1, 1, 1]`` the
    mapping is exactly the population prior.
    """

    beta = nominal_base_parameters() if prior is None else np.asarray(prior, dtype=float)
    if beta.shape != (len(DYNAMIC_BASE_PARAMETER_NAMES),) or not np.all(np.isfinite(beta)):
        raise ValueError("prior must be a finite 11-base-parameter vector")
    projection = np.zeros((len(beta), 3), dtype=float)
    projection[:5, 0] = beta[:5]
    projection[5:9, 1] = beta[5:9]
    projection[9:11, 2] = beta[9:11]
    return projection


def effective_base_parameters(
    scales: np.ndarray, prior: np.ndarray | None = None
) -> np.ndarray:
    """Return the MPC-compatible 11-vector represented by three scales."""

    values = np.asarray(scales, dtype=float)
    if values.shape != (3,) or not np.all(np.isfinite(values)):
        raise ValueError("scales must be a finite [mass, stiffness, damping] vector")
    return dynamic_scale_projection(prior) @ values


def control_relevant_integral_regression_block(
    time_s: np.ndarray,
    state: np.ndarray,
    generalized_input_nm: np.ndarray,
    prior: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Project the unchanged integral regression into the three-scale subspace."""

    full_regressor, target = integral_regression_block(
        time_s, state, generalized_input_nm
    )
    return full_regressor @ dynamic_scale_projection(prior), target


@dataclass(frozen=True)
class EstimatorConfidence:
    """Estimator evidence for logging and downstream adaptation policy.

    ``accepted`` records the estimator gate outcome; it is not a safety claim.
    The covariance is a local, residual-scaled regression covariance in the
    coordinates named by ``parameter_names``.
    """

    parameter_names: tuple[str, ...]
    sample_count: int
    parameter_dimension: int
    rank: int
    condition_number: float
    residual_rms: float
    covariance: np.ndarray
    standard_deviation: np.ndarray
    accepted: bool
    reasons: tuple[str, ...]

    @property
    def full_rank(self) -> bool:
        return self.rank == self.parameter_dimension

    def to_dict(self) -> dict[str, Any]:
        return {
            "parameter_names": list(self.parameter_names),
            "sample_count": self.sample_count,
            "parameter_dimension": self.parameter_dimension,
            "rank": self.rank,
            "full_rank": self.full_rank,
            "condition_number": self.condition_number,
            "residual_rms": self.residual_rms,
            "covariance": np.asarray(self.covariance).tolist(),
            "standard_deviation": np.asarray(self.standard_deviation).tolist(),
            "accepted": self.accepted,
            "reasons": list(self.reasons),
            "interpretation": "local_estimator_evidence_not_safety_probability",
        }


def regression_confidence(
    regressor: np.ndarray,
    residual: np.ndarray,
    parameter_names: Sequence[str],
    *,
    accepted: bool,
    reasons: Sequence[str] = (),
) -> EstimatorConfidence:
    """Build rank, conditioning, residual, and covariance evidence.

    Rank and condition number use column-normalized regressors so parameter
    units do not dominate the diagnostic.  Covariance is computed in the
    original parameter coordinates using the residual variance and a
    pseudoinverse; rank deficiency remains visible rather than being hidden by
    prior regularization.
    """

    matrix = np.asarray(regressor, dtype=float)
    error = np.asarray(residual, dtype=float).reshape(-1)
    names = tuple(str(name) for name in parameter_names)
    if matrix.ndim != 2 or matrix.shape[1] != len(names):
        raise ValueError("regressor columns must match parameter_names")
    if matrix.shape[0] != len(error) or not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(error)):
        raise ValueError("regressor and residual must be finite and row-aligned")

    norms = np.linalg.norm(matrix, axis=0)
    normalized = matrix / np.where(norms > 1e-15, norms, 1.0)
    singular = np.linalg.svd(normalized, compute_uv=False)
    tolerance = singular[0] * 1e-10 if len(singular) else 0.0
    rank = int(np.linalg.matrix_rank(normalized, tol=tolerance))
    condition = (
        float(singular[0] / singular[-1])
        if len(singular) and singular[-1] > 1e-15
        else float("inf")
    )
    residual_rms = float(np.sqrt(np.mean(error**2))) if len(error) else float("nan")
    degrees_of_freedom = max(matrix.shape[0] - rank, 1)
    residual_variance = float(error @ error / degrees_of_freedom)
    covariance = residual_variance * np.linalg.pinv(matrix.T @ matrix, rcond=1e-12)
    standard_deviation = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    return EstimatorConfidence(
        parameter_names=names,
        sample_count=matrix.shape[0],
        parameter_dimension=matrix.shape[1],
        rank=rank,
        condition_number=condition,
        residual_rms=residual_rms,
        covariance=covariance,
        standard_deviation=standard_deviation,
        accepted=bool(accepted),
        reasons=tuple(str(reason) for reason in reasons),
    )
