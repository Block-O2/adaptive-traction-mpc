"""Stage-5 bounded Human-model transition and one-step control authority."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Any

import numpy as np

from traction_mpc_stage4.statistical_trust import (
    StatisticalL4Config,
    paired_difference_bounds,
)
from traction_mpc_stage4.integral_identifier import integral_regression_block

from .human_identification import Stage5HumanIDMeasurement
from .human_identification_reduced import (
    ReducedIntegralScaleIdentifier,
    ReducedShadowHumanIdentificationService,
)


class PostUpdateEvidenceOutcome(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class OneStepHumanModelArm(str, Enum):
    FIXED = "fixed_model"
    ONE_STEP = "one_step_adaptive_model"


FIXED_ONE_STEP_GAMMA = 0.5


def fixed_one_step_pacing_status(_: dict[str, Any]) -> dict[str, float]:
    """Frozen pacing callback for both one-step A/B arms."""

    return {"gamma": FIXED_ONE_STEP_GAMMA, "gamma_rate_per_s": 0.0}


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


class OneStepHumanModelControlAuthority:
    """Causal one-publication control authority around the frozen shadow ID.

    The service remains the sole fit and future-validation authority.  This
    class may expose its first qualified bounded publication to the runner once;
    it never consumes plant truth and never changes pacing.
    """

    def __init__(
        self,
        geometry: Any,
        arm: OneStepHumanModelArm | str,
        *,
        predecessor_version: str,
    ) -> None:
        self.arm = OneStepHumanModelArm(arm)
        self.predecessor_version = str(predecessor_version)
        if not self.predecessor_version:
            raise ValueError("predecessor model version must be explicit")
        self.service = ReducedShadowHumanIdentificationService(geometry)
        self.applied_transition: BoundedHumanModelTransition | None = None
        self.qualified_transition: BoundedHumanModelTransition | None = None
        self.qualification_attempt: dict[str, Any] | None = None
        self.qualification_time_s: float | None = None
        self.transition_time_s: float | None = None
        self.control_model_version = self.predecessor_version
        self.control_model_scales = np.ones(3)
        self.application_count = 0

    @staticmethod
    def _measurement(payload: dict[str, Any]) -> Stage5HumanIDMeasurement:
        timestamp = float(payload["episode_time_s"])
        return Stage5HumanIDMeasurement(
            arrival_time_s=timestamp,
            sample_time_s=timestamp,
            estimated_human_state_rad_rad_s=np.asarray(
                payload["estimated_human_state_rad_rad_s"], dtype=float
            ),
            measured_human_cuff_force_world_n=np.asarray(
                payload["measured_human_cuff_force_world_n"], dtype=float
            ),
            measured_human_cuff_moment_world_nm=np.asarray(
                payload["measured_human_cuff_moment_world_nm"], dtype=float
            ),
            measured_generalized_human_input_nm=np.asarray(
                payload["measured_generalized_human_input_nm"], dtype=float
            ),
            task_phase=str(payload["task_phase"]),
            interface_model_version=str(payload["interface_model_version"]),
        )

    def _new_publication_attempt(self, timestamp_s: float) -> dict[str, Any]:
        matches = [
            attempt
            for attempt in self.service.attempts
            if attempt.get("status") == "published_to_shadow_incumbent"
            and np.isclose(
                float(attempt.get("decision_time_s", np.nan)),
                timestamp_s,
                atol=1.0e-12,
                rtol=0.0,
            )
        ]
        if len(matches) != 1:
            raise RuntimeError("qualified publication must map to one causal attempt")
        return matches[0]

    def observe(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Ingest one deployable record and optionally authorize one update."""

        publications_before = len(self.service.publication_history)
        self.service.observe(self._measurement(payload))
        result: dict[str, Any] = {
            "apply_update": False,
            "arm": self.arm.value,
            "gamma_authority": False,
            "truth_consumed": False,
        }
        if len(self.service.publication_history) == publications_before:
            return result
        timestamp = float(payload["episode_time_s"])
        attempt = self._new_publication_attempt(timestamp)
        if self.qualified_transition is None:
            transition = build_bounded_human_model_transition(
                self.service.identifier,
                self.control_model_scales,
                np.asarray(attempt["candidate_scales"], dtype=float),
                predecessor_version=self.control_model_version,
                candidate_version=(
                    f"stage5_human_candidate_{int(attempt['challenger_index'])}"
                ),
                successor_version="stage5_control_human_scale3_v1",
            )
            if not np.allclose(
                transition.successor_scales,
                np.asarray(attempt["proposed_model_scales"], dtype=float),
                atol=1.0e-12,
                rtol=0.0,
            ):
                raise RuntimeError("control transition differs from qualified proposal")
            self.qualified_transition = transition
            self.qualification_attempt = attempt
            self.qualification_time_s = timestamp
        if self.arm is OneStepHumanModelArm.FIXED or self.application_count:
            return result

        assert self.qualified_transition is not None
        self.applied_transition = replace(
            self.qualified_transition,
            provisional_only=False,
            applied_to_control=True,
        )
        self.transition_time_s = timestamp
        self.control_model_version = self.applied_transition.successor_version
        self.control_model_scales = np.asarray(
            self.applied_transition.successor_scales, dtype=float
        )
        self.application_count += 1
        return {
            **result,
            "apply_update": True,
            "human_model": self.service.retained_model,
            "model_version": self.control_model_version,
            "transition": self.applied_transition.to_dict(),
            "qualification_attempt_index": int(attempt["challenger_index"]),
            "qualification_decision_time_s": timestamp,
        }

    def post_update_prediction_evidence(self) -> dict[str, Any]:
        """Compare the active successor and rollback predecessor on later blocks."""

        if self.applied_transition is None or self.transition_time_s is None:
            return {
                "available": False,
                "reason": "no_control_model_transition",
                "blocks": [],
                "classification": None,
            }
        assert self.qualification_attempt is not None
        window = self.service.config.identifier.integration_window_s
        training_end = float(self.qualification_attempt["fit_end_time_s"])
        qualification_windows = list(
            self.qualification_attempt["evidence_history"][-1][
                "validation_windows"
            ]
        )
        later = [
            item
            for item in self.service.raw_history
            if float(item["time_s"]) > self.transition_time_s + 1.0e-12
        ]
        blocks: list[dict[str, Any]] = []
        if later:
            block_start = float(later[0]["time_s"])
            final_time = float(later[-1]["time_s"])
            while block_start + window <= final_time + 1.0e-12:
                block_end = block_start + window
                segment = [
                    item
                    for item in later
                    if block_start - 1.0e-12 <= float(item["time_s"])
                    <= block_end + 1.0e-12
                ]
                block_start = block_end
                if (
                    len(segment) < 3
                    or float(segment[-1]["time_s"])
                    - float(segment[0]["time_s"])
                    < 0.90 * window
                    or any(bool(item["contaminated"]) for item in segment)
                ):
                    continue
                time = np.asarray([item["time_s"] for item in segment], dtype=float)
                state = np.asarray([item["state"] for item in segment], dtype=float)
                torque = np.asarray(
                    [item["generalized_input_nm"] for item in segment], dtype=float
                )
                full_regressor, target = integral_regression_block(time, state, torque)
                regressor = full_regressor @ self.service.projection
                predecessor = np.asarray(
                    self.applied_transition.predecessor_scales, dtype=float
                )
                successor = np.asarray(
                    self.applied_transition.successor_scales, dtype=float
                )
                predecessor_loss = float(
                    np.mean((regressor @ predecessor - target) ** 2)
                )
                successor_loss = float(
                    np.mean((regressor @ successor - target) ** 2)
                )
                phases = {str(item["task_phase"]) for item in segment}
                overlaps_prior_evidence = bool(
                    float(time[0]) <= training_end + 1.0e-12
                    or any(
                        float(time[0]) <= float(end) + 1.0e-12
                        and float(time[-1]) >= float(start) - 1.0e-12
                        for start, end in qualification_windows
                    )
                )
                blocks.append(
                    {
                        "start_time_s": float(time[0]),
                        "end_time_s": float(time[-1]),
                        "task_phase": (
                            next(iter(phases)) if len(phases) == 1 else "MIXED"
                        ),
                        "predecessor_loss_nms2": predecessor_loss,
                        "successor_loss_nms2": successor_loss,
                        "successor_minus_predecessor_loss_nms2": (
                            successor_loss - predecessor_loss
                        ),
                        "overlaps_training_or_qualification": (
                            overlaps_prior_evidence
                        ),
                    }
                )
        differences = np.asarray(
            [item["successor_minus_predecessor_loss_nms2"] for item in blocks],
            dtype=float,
        )
        classification = classify_post_update_evidence(
            differences,
            config=self.service.config.trust,
            transition_index=int(
                self.qualification_attempt.get("challenger_index", 0)
            ),
        )
        return {
            "available": True,
            "transition_time_s": self.transition_time_s,
            "embargo_semantics": (
                "first complete nonoverlapping integral block begins at the first "
                "strictly later deployable sample"
            ),
            "training_fit_end_time_s": training_end,
            "qualification_windows": qualification_windows,
            "blocks": blocks,
            "classification": classification,
        }


__all__ = [
    "BoundedHumanModelTransition",
    "PostUpdateEvidenceOutcome",
    "OneStepHumanModelArm",
    "OneStepHumanModelControlAuthority",
    "FIXED_ONE_STEP_GAMMA",
    "build_bounded_human_model_transition",
    "classify_post_update_evidence",
    "fixed_one_step_pacing_status",
]
