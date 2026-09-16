"""Causal session orchestration for the Stage-5 progressive A/B study.

The control model is fixed within each repetition.  This module only connects
the already-frozen reduced identifier, future validation, versioned authority,
and repetition-boundary activation.  It has no plant-truth input boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from traction_mpc_stage4.integral_identifier import integral_regression_block

from .human import STAGE5_HUMAN
from .human_identification import Stage5HumanIDMeasurement
from .human_identification_reduced import (
    _reduced_block_losses,
    _session_validation_blocks,
)
from .human_model_update import classify_post_update_evidence
from .progressive_human_model import (
    ActiveHumanModel,
    PROGRESSIVE_FIXED_GAMMA,
    PostUpdateSupport,
    ProgressiveHumanModelAuthority,
)
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.minimal_adaptation import effective_base_parameters


FROZEN_THETA_1 = (
    1.0000584390985465,
    1.0010424686528112,
    1.0193479803467633,
)
LONGITUDINAL_CEM_SEEDS = (
    20260828,
    20260829,
    20260830,
    20260831,
    20260832,
)


class ProgressiveLongitudinalArm(str, Enum):
    FIXED_THETA_1 = "fixed_theta_1"
    PROGRESSIVE = "progressive"


@dataclass(frozen=True)
class RepetitionAuthoritySnapshot:
    repetition: int
    session_time_s: float
    active_model_id: str
    active_theta: tuple[float, float, float]
    activation: dict[str, Any] | None
    queued_update: dict[str, Any] | None


def initial_theta_1_model(session_id: str) -> ActiveHumanModel:
    """Build the already-supported RPL-A successor as a session root."""

    return ActiveHumanModel.create(
        session_id=session_id,
        update_index=1,
        theta=FROZEN_THETA_1,
        predecessor_model_id="stage5-population-prior:theta_0",
        provenance="RPL-A_frozen_successor_independent_replication",
        activation_repetition=1,
        activation_time_s=0.0,
        rollback_predecessor_id="stage5-population-prior:theta_0",
        candidate_evidence_id="RPL-A-theta-1",
        bounded_transition_delta=np.asarray(FROZEN_THETA_1) - 1.0,
        qualification_repetition=0,
        qualification_time_s=0.0,
        post_update_support=PostUpdateSupport.POSITIVE,
    )


def fixed_progress_pacing_status(_: dict[str, Any]) -> dict[str, float]:
    return {"gamma": PROGRESSIVE_FIXED_GAMMA, "gamma_rate_per_s": 0.0}


class ProgressiveLongitudinalSession:
    """One arm's persistent truth-free Human-ID and model-authority state."""

    def __init__(
        self,
        geometry: Any,
        arm: ProgressiveLongitudinalArm | str,
        *,
        session_id: str,
    ) -> None:
        self.arm = ProgressiveLongitudinalArm(arm)
        self.authority = ProgressiveHumanModelAuthority(
            geometry,
            initial_theta_1_model(session_id),
            updates_enabled=self.arm is ProgressiveLongitudinalArm.PROGRESSIVE,
        )
        self.session_offset_s = 0.0
        self.current_repetition: int | None = None
        self.repetition_active_model_id: str | None = None
        self.repetition_snapshots: list[RepetitionAuthoritySnapshot] = []
        self.post_update_evidence_history: list[dict[str, Any]] = []
        self.blocked_qualified_proposals: list[dict[str, Any]] = []
        self._recorded_blocked_evidence_ids: set[str] = set()

    @property
    def active_model(self) -> ActiveHumanModel:
        return self.authority.active_model

    @property
    def control_human_model(self) -> Any:
        return self.authority.control_human_model

    def begin_repetition(
        self, repetition: int, session_time_s: float
    ) -> RepetitionAuthoritySnapshot:
        result = self.authority.begin_repetition(repetition, session_time_s)
        self.session_offset_s = float(session_time_s)
        self.current_repetition = int(repetition)
        self.repetition_active_model_id = self.active_model.model_id
        snapshot = RepetitionAuthoritySnapshot(
            repetition=int(repetition),
            session_time_s=float(session_time_s),
            active_model_id=self.active_model.model_id,
            active_theta=self.active_model.theta,
            activation=result["activation"],
            queued_update=(
                None
                if self.authority.queued_update is None
                else self.authority.queued_update.to_dict()
            ),
        )
        self.repetition_snapshots.append(snapshot)
        return snapshot

    def _measurement(self, payload: dict[str, Any]) -> Stage5HumanIDMeasurement:
        timestamp = self.session_offset_s + float(payload["episode_time_s"])
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

    def post_update_evidence(self) -> dict[str, Any]:
        """Compare active successor against its immediate predecessor on later data."""

        model = self.active_model
        if model.activation_repetition <= 1 or model.predecessor_model_id is None:
            return {
                "available": False,
                "reason": "initial_theta_1_support_is_frozen_from_RPL-A",
                "classification": None,
                "blocks": [],
            }
        predecessor = self.authority.lineage.get(model.predecessor_model_id)
        if predecessor is None:
            raise RuntimeError("active model rollback predecessor is unavailable")
        config = self.authority.service.config
        strictly_later_history = [
            item
            for item in self.authority.service.raw_history
            if float(item["time_s"]) > float(model.activation_time_s) + 1.0e-12
        ]
        blocks = _session_validation_blocks(
            strictly_later_history,
            fit_end_time_s=float(model.activation_time_s),
            window_s=config.identifier.integration_window_s,
            embargo_windows=0,
            count=config.trust.maximum_clean_blocks,
        )
        projection = self.authority.service.projection
        successor_loss = _reduced_block_losses(
            np.asarray(model.theta), blocks, projection
        )
        predecessor_loss = _reduced_block_losses(
            np.asarray(predecessor.theta), blocks, projection
        )
        differences = successor_loss - predecessor_loss
        classification = classify_post_update_evidence(
            differences,
            config=config.trust,
            transition_index=model.update_index,
        )
        block_rows = [
            {
                "episode_index": int(block["episode_index"]),
                "start_time_s": float(block["start_time_s"]),
                "end_time_s": float(block["end_time_s"]),
                "predecessor_loss_nms2": float(old),
                "successor_loss_nms2": float(new),
                "successor_minus_predecessor_loss_nms2": float(delta),
            }
            for block, old, new, delta in zip(
                blocks,
                predecessor_loss,
                successor_loss,
                differences,
                strict=True,
            )
        ]
        return {
            "available": True,
            "target_model_id": model.model_id,
            "predecessor_model_id": predecessor.model_id,
            "activation_time_s": model.activation_time_s,
            "data_boundary": "deployable samples strictly after activation; blocks never cross a repetition reset",
            "blocks": block_rows,
            "classification": classification,
        }

    def _record_decisive_post_update_evidence(
        self, evidence: dict[str, Any], timestamp_s: float
    ) -> None:
        classification = evidence.get("classification")
        if not evidence.get("available") or classification is None:
            return
        outcome = PostUpdateSupport(str(classification["outcome"]))
        if outcome is PostUpdateSupport.NEUTRAL:
            return
        if self.active_model.post_update_support is not PostUpdateSupport.NEUTRAL:
            return
        assert self.current_repetition is not None
        evidence_id = (
            f"post-update:{self.active_model.model_id}:"
            f"{outcome.value}:rep-{self.current_repetition}"
        )
        self.authority.record_post_update_evidence(
            outcome,
            target_model_id=self.active_model.model_id,
            predecessor_model_id=str(self.active_model.predecessor_model_id),
            evidence_id=evidence_id,
            evidence_repetition=self.current_repetition,
            evidence_time_s=timestamp_s,
        )
        self.post_update_evidence_history.append(
            {**evidence, "recorded_evidence_id": evidence_id}
        )

    def _record_blocked_proposal(self, reason: str) -> None:
        proposal = self.authority.service.queued_publication
        if proposal is None:
            return
        evidence_id = str(proposal["qualification_evidence_id"])
        if evidence_id in self._recorded_blocked_evidence_ids:
            return
        self._recorded_blocked_evidence_ids.add(evidence_id)
        self.blocked_qualified_proposals.append(
            {
                "qualification_evidence_id": evidence_id,
                "predecessor_model_id": str(proposal["predecessor_model_version"]),
                "candidate_theta": list(proposal["candidate_scales"]),
                "bounded_successor_theta": list(proposal["proposed_model_scales"]),
                "qualification_time_s": float(proposal["qualification_time_s"]),
                "blocked_reason": reason,
                "active_model_id": self.active_model.model_id,
                "active_post_update_support": self.active_model.post_update_support.value,
            }
        )

    def observe(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Ingest one deployable sample; never changes the model mid-repetition."""

        if self.current_repetition is None or self.repetition_active_model_id is None:
            raise RuntimeError("session observation requires an active repetition")
        if str(payload["current_control_model_version"]) != self.active_model.model_id:
            raise RuntimeError("Goal-MPC control model disagrees with session authority")
        if self.active_model.model_id != self.repetition_active_model_id:
            raise RuntimeError("active Human model changed within a repetition")
        measurement = self._measurement(payload)
        status = self.authority.service.observe(measurement)
        evidence = self.post_update_evidence()
        self._record_decisive_post_update_evidence(
            evidence, float(measurement.sample_time_s)
        )

        proposal = self.authority.service.queued_publication
        if proposal is not None and self.authority.queued_update is None:
            if self.arm is ProgressiveLongitudinalArm.FIXED_THETA_1:
                self._record_blocked_proposal("fixed_theta_1_arm_has_no_update_authority")
            elif self.authority.can_qualify_next:
                self.authority.queue_service_qualified_successor(
                    transition_source="registered_reduced_human_id",
                    qualification_repetition=self.current_repetition,
                )
            elif self.authority.progression_blocked:
                self._record_blocked_proposal("post_update_negative_blocks_progression")
            else:
                self._record_blocked_proposal(
                    "active_model_lacks_post_update_positive_support"
                )

        return {
            "apply_update": False,
            "arm": self.arm.value,
            "active_model_id": self.active_model.model_id,
            "active_theta": list(self.active_model.theta),
            "human_id_status": status["trust_state"],
            "queued_for_next_repetition": self.authority.queued_update is not None,
            "gamma_authority": False,
            "truth_consumed": False,
        }

    def finalize_repetition(self) -> dict[str, Any]:
        if self.repetition_active_model_id != self.active_model.model_id:
            raise RuntimeError("active model changed before repetition finalization")
        evidence = self.post_update_evidence()
        return {
            "active_model_id": self.active_model.model_id,
            "active_theta": list(self.active_model.theta),
            "post_update_support": self.active_model.post_update_support.value,
            "post_update_evidence": evidence,
            "queued_update": (
                None
                if self.authority.queued_update is None
                else self.authority.queued_update.to_dict()
            ),
            "service_queued_publication": self.authority.service.queued_publication,
            "active_fixed_within_repetition": True,
        }


def deployable_prediction_summary(
    trace: dict[str, np.ndarray], scales: Any
) -> dict[str, Any]:
    """Evaluate one model on causal deployable trace signals, never plant truth."""

    time = np.asarray(trace["time_s"], dtype=float)
    state = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)
    torque = np.asarray(
        trace["deployable_measured_generalized_input_nm"], dtype=float
    )
    phase = np.asarray(trace["task_phase"], dtype=str)
    beta = effective_base_parameters(
        np.asarray(scales, dtype=float), nominal_base_parameters(STAGE5_HUMAN)
    )
    result: dict[str, Any] = {}
    all_residuals: list[float] = []
    for phase_name in ("OUTBOUND", "HOLD", "RETURN"):
        indices = np.flatnonzero(phase == phase_name)
        residuals: list[float] = []
        if len(indices):
            block_start = float(time[indices[0]])
            final_time = float(time[indices[-1]])
            while block_start + 0.20 <= final_time + 1.0e-12:
                selected = indices[
                    (time[indices] >= block_start - 1.0e-12)
                    & (time[indices] <= block_start + 0.20 + 1.0e-12)
                ]
                block_start += 0.20
                if (
                    len(selected) < 3
                    or time[selected[-1]] - time[selected[0]] < 0.18
                ):
                    continue
                regressor, target = integral_regression_block(
                    time[selected], state[selected], torque[selected]
                )
                residuals.extend((regressor @ beta - target).tolist())
        values = np.asarray(residuals, dtype=float)
        if len(values):
            all_residuals.extend(values.tolist())
            result[phase_name] = {
                "block_count": int(len(values) // 2),
                "mean_squared_loss_nms2": float(np.mean(values**2)),
                "rmse_nms": float(np.sqrt(np.mean(values**2))),
                "maximum_abs_nms": float(np.max(np.abs(values))),
            }
        else:
            result[phase_name] = {"block_count": 0}
    combined = np.asarray(all_residuals, dtype=float)
    result["ALL_PHASES"] = (
        {"block_count": 0}
        if not len(combined)
        else {
            "block_count": int(len(combined) // 2),
            "mean_squared_loss_nms2": float(np.mean(combined**2)),
            "rmse_nms": float(np.sqrt(np.mean(combined**2))),
            "maximum_abs_nms": float(np.max(np.abs(combined))),
        }
    )
    return result


def parameter_direction_diagnostics(deltas: Any) -> dict[str, Any]:
    """Report reversals without conflating one settling turn with oscillation."""

    matrix = np.asarray(deltas, dtype=float)
    if matrix.size == 0:
        matrix = np.empty((0, 3), dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != 3 or not np.all(np.isfinite(matrix)):
        raise ValueError("bounded-update deltas must be a finite N-by-3 matrix")
    names = ("alpha_M", "alpha_K", "alpha_D")
    counts = {name: 0 for name in names}
    if len(matrix) >= 2:
        for index, name in enumerate(names):
            signs = np.sign(matrix[:, index])
            signs[np.abs(matrix[:, index]) <= 1.0e-15] = 0.0
            nonzero = signs[signs != 0.0]
            counts[name] = int(np.count_nonzero(nonzero[1:] != nonzero[:-1]))
    return {
        "reversal_count": counts,
        "oscillatory": {name: count >= 2 for name, count in counts.items()},
    }


__all__ = [
    "FROZEN_THETA_1",
    "LONGITUDINAL_CEM_SEEDS",
    "ProgressiveLongitudinalArm",
    "ProgressiveLongitudinalSession",
    "RepetitionAuthoritySnapshot",
    "deployable_prediction_summary",
    "fixed_progress_pacing_status",
    "initial_theta_1_model",
    "parameter_direction_diagnostics",
]
