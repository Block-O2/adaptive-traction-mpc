"""Offline-only Stage-5 bounded Human-model transition semantics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

import numpy as np

from traction_mpc_stage4.statistical_trust import (
    StatisticalL4Config,
    paired_difference_bounds,
)

from .human_identification_reduced import ReducedIntegralScaleIdentifier


class PostUpdateEvidenceOutcome(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass(frozen=True)
class BoundedHumanModelTransition:
    predecessor_version: str
    candidate_version: str
    successor_version: str
    predecessor_scales: tuple[float, float, float]
    candidate_scales: tuple[float, float, float]
    successor_scales: tuple[float, float, float]
    raw_candidate_displacement: tuple[float, float, float]
    smoothed_displacement: tuple[float, float, float]
    applied_bounded_displacement: tuple[float, float, float]
    smoothing_alpha: float
    maximum_step_fraction_of_span: float
    maximum_step_per_parameter: tuple[float, float, float]
    smoothing_active: tuple[bool, bool, bool]
    step_limit_active: tuple[bool, bool, bool]
    parameter_bound_active: tuple[bool, bool, bool]
    limiting_rule_per_parameter: tuple[str, str, str]
    provisional_only: bool = True
    applied_to_control: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_bounded_human_model_transition(
    identifier: ReducedIntegralScaleIdentifier,
    predecessor_scales: np.ndarray,
    candidate_scales: np.ndarray,
    *,
    predecessor_version: str,
    candidate_version: str,
    successor_version: str,
) -> BoundedHumanModelTransition:
    """Reuse the frozen Stage-4-style Stage-5 smoothing and step bounds."""

    predecessor = np.asarray(predecessor_scales, dtype=float)
    candidate = np.asarray(candidate_scales, dtype=float)
    if predecessor.shape != (3,) or candidate.shape != (3,):
        raise ValueError("predecessor and candidate must be three-scale vectors")
    if not np.all(np.isfinite([*predecessor, *candidate])):
        raise ValueError("transition scales must be finite")
    if not predecessor_version or not candidate_version or not successor_version:
        raise ValueError("all model identities must be explicit")

    raw = candidate - predecessor
    smoothed = identifier.config.smoothing_alpha * raw
    maximum = identifier.config.maximum_update_fraction_of_span * identifier.span
    step_limited = np.clip(smoothed, -maximum, maximum)
    before_parameter_bounds = predecessor + step_limited
    successor = identifier.bounded_smoothed_step(predecessor, candidate)
    smoothing_active = (~np.isclose(raw, 0.0, atol=1.0e-15, rtol=0.0)) & (
        identifier.config.smoothing_alpha < 1.0
    )
    step_active = np.abs(smoothed) > maximum + 1.0e-15
    bound_active = ~np.isclose(
        before_parameter_bounds, successor, atol=1.0e-15, rtol=0.0
    )
    rules = []
    for smooth, step, bound in zip(
        smoothing_active, step_active, bound_active, strict=True
    ):
        active = []
        if smooth:
            active.append("smoothing_alpha")
        if step:
            active.append("maximum_step_fraction_of_span")
        if bound:
            active.append("parameter_bound")
        rules.append("+".join(active) if active else "none")

    return BoundedHumanModelTransition(
        predecessor_version=str(predecessor_version),
        candidate_version=str(candidate_version),
        successor_version=str(successor_version),
        predecessor_scales=tuple(float(v) for v in predecessor),
        candidate_scales=tuple(float(v) for v in candidate),
        successor_scales=tuple(float(v) for v in successor),
        raw_candidate_displacement=tuple(float(v) for v in raw),
        smoothed_displacement=tuple(float(v) for v in smoothed),
        applied_bounded_displacement=tuple(
            float(v) for v in successor - predecessor
        ),
        smoothing_alpha=float(identifier.config.smoothing_alpha),
        maximum_step_fraction_of_span=float(
            identifier.config.maximum_update_fraction_of_span
        ),
        maximum_step_per_parameter=tuple(float(v) for v in maximum),
        smoothing_active=tuple(bool(v) for v in smoothing_active),
        step_limit_active=tuple(bool(v) for v in step_active),
        parameter_bound_active=tuple(bool(v) for v in bound_active),
        limiting_rule_per_parameter=tuple(rules),
    )


def classify_post_update_evidence(
    successor_minus_predecessor_loss: np.ndarray,
    *,
    config: StatisticalL4Config,
    transition_index: int = 0,
) -> dict[str, Any]:
    """Apply the existing sequential future-validation standard to one model pair."""

    differences = np.asarray(successor_minus_predecessor_loss, dtype=float)
    if differences.ndim != 1 or not np.all(np.isfinite(differences)):
        raise ValueError("paired post-update losses must be a finite vector")
    looks: list[dict[str, Any]] = []
    for count in config.scheduled_looks:
        if len(differences) < count:
            break
        evidence = paired_difference_bounds(
            differences[:count],
            config=config,
            challenger_index=transition_index,
            seed_offset=transition_index * 100,
        )
        looks.append(evidence)
        if float(evidence["upper_bound_nms2"]) < 0.0:
            return {
                "outcome": PostUpdateEvidenceOutcome.POSITIVE.value,
                "reason": "successor_future_loss_upper_bound_below_predecessor",
                "decision_block_count": count,
                "looks": looks,
            }
        if float(evidence["lower_bound_nms2"]) > 0.0:
            return {
                "outcome": PostUpdateEvidenceOutcome.NEGATIVE.value,
                "reason": "successor_future_loss_lower_bound_above_predecessor",
                "decision_block_count": count,
                "looks": looks,
            }
    return {
        "outcome": PostUpdateEvidenceOutcome.NEUTRAL.value,
        "reason": (
            "insufficient_genuinely_later_blocks"
            if len(differences) < config.minimum_clean_blocks
            else "paired_future_improvement_inconclusive"
        ),
        "decision_block_count": None,
        "available_block_count": int(len(differences)),
        "looks": looks,
    }


__all__ = [
    "BoundedHumanModelTransition",
    "PostUpdateEvidenceOutcome",
    "build_bounded_human_model_transition",
    "classify_post_update_evidence",
]
