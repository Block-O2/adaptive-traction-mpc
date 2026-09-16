"""Stage-5 confidence-aware progress pacing without a reference clock."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Stage5ConfidencePacingConfig:
    """Historical Stage-4 V1 defaults mapped to a dimensionless gamma."""

    minimum_gamma: float = 0.50
    nominal_gamma: float = 1.00
    recovery_rate_per_s: float = 0.25
    slowdown_rate_per_s: float = 1.00
    model_confidence_filter_time_constant_s: float = 0.75
    high_confidence_enter_threshold: float = 0.75
    high_confidence_exit_threshold: float = 0.25
    provenance: str = (
        "Stage-4 ConfidenceAwareExecutionConfig defaults; semantic mapping only"
    )

    def __post_init__(self) -> None:
        if not 0.0 < self.minimum_gamma <= self.nominal_gamma <= 1.0:
            raise ValueError("gamma bounds must satisfy 0 < minimum <= nominal <= 1")
        if self.recovery_rate_per_s <= 0.0 or self.slowdown_rate_per_s <= 0.0:
            raise ValueError("gamma rates must be positive")
        if self.model_confidence_filter_time_constant_s <= 0.0:
            raise ValueError("confidence filter time constant must be positive")
        if not (
            0.0
            <= self.high_confidence_exit_threshold
            < self.high_confidence_enter_threshold
            <= 1.0
        ):
            raise ValueError("confidence hysteresis thresholds are invalid")


@dataclass(frozen=True)
class Stage5PacingEvidence:
    """Three separate authorities observed at one causal session time."""

    session_time_s: float
    identification_informative: bool
    information_rank: int
    information_condition_number: float
    current_nominal_model_adequate: bool
    current_model_evidence_reason: str
    challenger_status: str
    shadow_publication_count: int


class Stage5ConfidencePacing:
    """Rate-limited gamma controller driven only by current-model trust.

    Information quality and challenger publication are logged but cannot raise
    gamma.  Gamma scales only the Goal-MPC planning-velocity ceiling.
    """

    def __init__(
        self,
        config: Stage5ConfidencePacingConfig = Stage5ConfidencePacingConfig(),
        *,
        initial_session_time_s: float = 0.0,
    ) -> None:
        self.config = config
        self.anchor_time_s = float(initial_session_time_s)
        self.last_update_time_s = float(initial_session_time_s)
        self.gamma_anchor = config.minimum_gamma
        self.gamma_target = config.minimum_gamma
        self.gamma_rate_per_s = 0.0
        self.filtered_current_model_confidence = 0.0
        self.execution_confidence_high = False
        self.update_count = 0
        self.evidence_history: list[dict[str, Any]] = []
        self._last_evidence_signature: tuple[Any, ...] | None = None

    def _state(self, session_time_s: float) -> tuple[float, float]:
        now = float(session_time_s)
        if now < self.anchor_time_s - 1.0e-12:
            raise ValueError("pacing time must be monotonic")
        elapsed = max(0.0, now - self.anchor_time_s)
        rate = self.gamma_rate_per_s
        if abs(rate) <= 1.0e-15:
            return self.gamma_anchor, 0.0
        duration = (self.gamma_target - self.gamma_anchor) / rate
        if duration <= 1.0e-15 or elapsed >= duration:
            return self.gamma_target, 0.0
        return self.gamma_anchor + rate * elapsed, rate

    def _set_target(self, session_time_s: float, target: float) -> None:
        gamma, _ = self._state(session_time_s)
        requested = float(
            np.clip(target, self.config.minimum_gamma, self.config.nominal_gamma)
        )
        if requested > gamma + 1.0e-15:
            rate = self.config.recovery_rate_per_s
        elif requested < gamma - 1.0e-15:
            rate = -self.config.slowdown_rate_per_s
        else:
            rate = 0.0
        self.anchor_time_s = float(session_time_s)
        self.gamma_anchor = float(gamma)
        self.gamma_target = requested
        self.gamma_rate_per_s = float(rate)

    def update(self, evidence: Stage5PacingEvidence) -> dict[str, Any]:
        now = float(evidence.session_time_s)
        if now < self.last_update_time_s - 1.0e-12:
            raise ValueError("pacing evidence time must be monotonic")
        elapsed = max(0.0, now - self.last_update_time_s)
        alpha = -np.expm1(
            -elapsed / self.config.model_confidence_filter_time_constant_s
        )
        raw = float(evidence.current_nominal_model_adequate)
        self.filtered_current_model_confidence += float(alpha) * (
            raw - self.filtered_current_model_confidence
        )
        if (
            not self.execution_confidence_high
            and self.filtered_current_model_confidence
            >= self.config.high_confidence_enter_threshold
        ):
            self.execution_confidence_high = True
        elif (
            self.execution_confidence_high
            and self.filtered_current_model_confidence
            <= self.config.high_confidence_exit_threshold
        ):
            self.execution_confidence_high = False
        target = (
            self.config.nominal_gamma
            if self.execution_confidence_high
            else self.config.minimum_gamma
        )
        self._set_target(now, target)
        self.last_update_time_s = now
        self.update_count += 1
        status = self.status(now)
        record = {
            "evidence": asdict(evidence),
            "pacing": status,
            "information_affects_gamma": False,
            "challenger_publication_affects_gamma": False,
        }
        signature = (
            evidence.identification_informative,
            evidence.information_rank,
            round(float(evidence.information_condition_number), 12)
            if np.isfinite(evidence.information_condition_number)
            else float("inf"),
            evidence.current_nominal_model_adequate,
            evidence.current_model_evidence_reason,
            evidence.challenger_status,
            evidence.shadow_publication_count,
            bool(status["execution_confidence_high"]),
            float(status["gamma_target"]),
        )
        if signature != self._last_evidence_signature:
            self.evidence_history.append(record)
            self._last_evidence_signature = signature
        return record

    def status(self, session_time_s: float) -> dict[str, Any]:
        gamma, rate = self._state(session_time_s)
        return {
            "session_time_s": float(session_time_s),
            "gamma": float(gamma),
            "gamma_target": float(self.gamma_target),
            "gamma_rate_per_s": float(rate),
            "filtered_current_model_confidence": float(
                self.filtered_current_model_confidence
            ),
            "execution_confidence_high": bool(self.execution_confidence_high),
            "planning_semantics": "v_plan_ceiling=gamma*[15,25]deg/s",
            "support_scaled": False,
            "hold_equilibrium_scaled": False,
            "hard_motion_limits_scaled": False,
        }

    def summary(self, session_time_s: float) -> dict[str, Any]:
        return {
            "config": asdict(self.config),
            "final_status": self.status(session_time_s),
            "update_count": self.update_count,
            "evidence_history": list(self.evidence_history),
            "reference_clock_used": False,
            "full_joint_trajectory_created": False,
            "coordination_ratio_or_corridor_created": False,
            "force_intervention_pacing_reused": False,
        }


def current_nominal_model_trust_from_shadow_service(
    service_summary: dict[str, Any],
) -> tuple[bool, str]:
    """Conservatively assess the model actually used by Goal-MPC.

    A fit, full rank, low training residual, pending challenger, or shadow
    publication never raises nominal-model trust.  Trust becomes high only if a
    completed future comparison establishes that the challenger is
    statistically worse than the nominal reference.
    """

    attempts = list(service_summary.get("attempts", []))
    if not attempts:
        return False, "no_future_comparison"
    for attempt in reversed(attempts):
        evidence_history = list(attempt.get("evidence_history", []))
        if attempt.get("status") == "published_to_shadow_incumbent":
            return False, "challenger_outperformed_nominal_but_remains_shadow_only"
        if attempt.get("status") != "rejected_no_future_support":
            continue
        if evidence_history and bool(
            evidence_history[-1].get(
                "statistically_worse_than_at_least_one_reference", False
            )
        ):
            return True, "future_validation_supports_nominal_over_challenger"
        return False, "future_validation_inconclusive_for_nominal_adequacy"
    return False, "challenger_pending_or_training_only"


__all__ = [
    "Stage5ConfidencePacing",
    "Stage5ConfidencePacingConfig",
    "Stage5PacingEvidence",
    "current_nominal_model_trust_from_shadow_service",
]
