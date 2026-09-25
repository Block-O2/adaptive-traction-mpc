"""Evaluation-side fixed-table assembly contract; never imported by control."""

from .assembly import (
    MIN_PROXIMAL_GAP_M,
    NUMERICAL_PENETRATION_TOLERANCE_M,
    assess_assembly,
    repaired_counterpart,
)

__all__ = [
    "MIN_PROXIMAL_GAP_M",
    "NUMERICAL_PENETRATION_TOLERANCE_M",
    "assess_assembly",
    "repaired_counterpart",
]
