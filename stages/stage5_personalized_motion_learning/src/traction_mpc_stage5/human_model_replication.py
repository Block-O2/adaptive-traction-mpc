"""Frozen-successor paired replication semantics for Stage 5."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

import numpy as np

from traction_mpc_stage3.human import soft_limit_torque
from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    nominal_base_parameters,
)
from traction_mpc_stage4.integral_identifier import integral_regression_block
from traction_mpc_stage4.minimal_adaptation import (
    dynamic_scale_projection,
    effective_base_parameters,
)

from .goal_mpc_smoke import FIXED_HUMAN_MODEL_VERSION
from .human import STAGE5_HUMAN
from .human_model_update import classify_post_update_evidence
from .human_identification_reduced import Stage5ReducedHumanIDConfig


FROZEN_THETA_0 = (1.0, 1.0, 1.0)
FROZEN_THETA_1 = (
    1.0000584390985465,
    1.0010424686528112,
    1.0193479803467633,
)
FROZEN_THETA_1_VERSION = "stage5_control_human_scale3_v1"


class FrozenSuccessorArm(str, Enum):
    PREDECESSOR = "predecessor_theta_0"
    FROZEN_SUCCESSOR = "frozen_successor_theta_1"


@dataclass(frozen=True)
class FrozenSuccessorReplicationSpec:
    trigger_time_s: float = 3.045
    post_transition_embargo_s: float = 0.2
    integration_window_s: float = 0.2

    def __post_init__(self) -> None:
        if self.trigger_time_s <= 0.0:
            raise ValueError("replication trigger must be positive")
        if self.post_transition_embargo_s < self.integration_window_s:
            raise ValueError("transition embargo must cover one integral window")


def _model(geometry: Any, scales: tuple[float, float, float]):
    return BaseParameterHumanModel(
        geometry,
        effective_base_parameters(
            np.asarray(scales, dtype=float),
            nominal_base_parameters(STAGE5_HUMAN),
        ),
        STAGE5_HUMAN,
    )


class FrozenSuccessorReplicationAuthority:
    """Collect deployable data and apply one predeclared frozen model switch."""

    def __init__(
        self,
        geometry: Any,
        arm: FrozenSuccessorArm | str,
        *,
        replication_id: str,
        cem_seed: int,
        spec: FrozenSuccessorReplicationSpec = FrozenSuccessorReplicationSpec(),
    ) -> None:
        self.geometry = geometry
        self.arm = FrozenSuccessorArm(arm)
        self.replication_id = str(replication_id)
        self.cem_seed = int(cem_seed)
        self.spec = spec
        if not self.replication_id or self.cem_seed < 0:
            raise ValueError("replication id and seed must be explicit")
        self.raw_history: list[dict[str, Any]] = []
        self.last_time_s: float | None = None
        self.application_count = 0
        self.transition_time_s: float | None = None
        self.active_model_version = FIXED_HUMAN_MODEL_VERSION
        self.theta_1_model = _model(geometry, FROZEN_THETA_1)

    def _record(self, payload: dict[str, Any]) -> None:
        timestamp = float(payload["episode_time_s"])
        if self.last_time_s is not None and timestamp <= self.last_time_s + 1.0e-12:
            return
        state = np.asarray(
            payload["estimated_human_state_rad_rad_s"], dtype=float
        )
        generalized_input = np.asarray(
            payload["measured_generalized_human_input_nm"], dtype=float
        )
        if state.shape != (4,) or generalized_input.shape != (2,):
            raise ValueError("replication deployable state/input shape changed")
        self.raw_history.append(
            {
                "time_s": timestamp,
                "state": state.copy(),
                "generalized_input_nm": generalized_input.copy(),
                "task_phase": str(payload["task_phase"]),
                "contaminated": bool(
                    np.linalg.norm(
                        soft_limit_torque(state[:2], state[2:], STAGE5_HUMAN)
                    )
                    > 1.0e-8
                ),
                "source_index": len(self.raw_history),
            }
        )
        self.last_time_s = timestamp

    def observe(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._record(payload)
        result: dict[str, Any] = {
            "apply_update": False,
            "replication_id": self.replication_id,
            "cem_seed": self.cem_seed,
            "human_identification_active": False,
            "successor_refit": False,
            "truth_consumed": False,
            "gamma_authority": False,
        }
        if self.arm is FrozenSuccessorArm.PREDECESSOR or self.application_count:
            return result
        timestamp = float(payload["episode_time_s"])
        if timestamp + 1.0e-12 < self.spec.trigger_time_s:
            return result
        if str(payload["task_phase"]) != "OUTBOUND":
            raise RuntimeError("frozen transition trigger reached outside OUTBOUND")
        if str(payload["current_control_model_version"]) != FIXED_HUMAN_MODEL_VERSION:
            raise RuntimeError("frozen successor requires theta_0 predecessor")
        self.application_count = 1
        self.transition_time_s = timestamp
        self.active_model_version = FROZEN_THETA_1_VERSION
        return {
            **result,
            "apply_update": True,
            "human_model": self.theta_1_model,
            "model_version": FROZEN_THETA_1_VERSION,
            "transition": {
                "source": "frozen_C_B_successor_no_refit",
                "replication_id": self.replication_id,
                "cem_seed": self.cem_seed,
                "predecessor_version": FIXED_HUMAN_MODEL_VERSION,
                "successor_version": FROZEN_THETA_1_VERSION,
                "predecessor_scales": list(FROZEN_THETA_0),
                "successor_scales": list(FROZEN_THETA_1),
                "trigger_time_s": self.spec.trigger_time_s,
                "actual_causal_transition_time_s": timestamp,
                "successor_refit": False,
                "second_update_allowed": False,
            },
        }

    def prediction_evidence(self) -> dict[str, Any]:
        if self.arm is not FrozenSuccessorArm.FROZEN_SUCCESSOR:
            return {
                "available": False,
                "reason": "predecessor_arm_has_no_model_transition",
                "blocks": [],
                "classification": None,
            }
        if self.transition_time_s is None:
            return {
                "available": False,
                "reason": "frozen_transition_not_reached",
                "blocks": [],
                "classification": None,
            }
        earliest = self.transition_time_s + self.spec.post_transition_embargo_s
        later = [
            item
            for item in self.raw_history
            if float(item["time_s"]) > earliest + 1.0e-12
        ]
        projection = dynamic_scale_projection(
            nominal_base_parameters(STAGE5_HUMAN)
        )
        theta_0 = np.asarray(FROZEN_THETA_0, dtype=float)
        theta_1 = np.asarray(FROZEN_THETA_1, dtype=float)
        blocks: list[dict[str, Any]] = []
        if later:
            start = float(later[0]["time_s"])
            final = float(later[-1]["time_s"])
            while start + self.spec.integration_window_s <= final + 1.0e-12:
                end = start + self.spec.integration_window_s
                segment = [
                    item
                    for item in later
                    if start - 1.0e-12 <= float(item["time_s"]) <= end + 1.0e-12
                ]
                start = end
                duration = (
                    0.0
                    if len(segment) < 2
                    else float(segment[-1]["time_s"] - segment[0]["time_s"])
                )
                valid = bool(
                    len(segment) >= 3
                    and duration >= 0.90 * self.spec.integration_window_s
                    and not any(bool(item["contaminated"]) for item in segment)
                )
                phases = {str(item["task_phase"]) for item in segment}
                block: dict[str, Any] = {
                    "start_time_s": (
                        None if not segment else float(segment[0]["time_s"])
                    ),
                    "end_time_s": (
                        None if not segment else float(segment[-1]["time_s"])
                    ),
                    "task_phase": (
                        "UNAVAILABLE"
                        if not phases
                        else next(iter(phases)) if len(phases) == 1 else "MIXED"
                    ),
                    "valid": valid,
                    "transition_region_overlap": bool(
                        segment
                        and float(segment[0]["time_s"])
                        <= earliest + 1.0e-12
                    ),
                    "future_information_used_online": False,
                    "same_block_for_predecessor_and_successor": True,
                    "source_index_range": (
                        None
                        if not segment
                        else [
                            int(segment[0]["source_index"]),
                            int(segment[-1]["source_index"]),
                        ]
                    ),
                }
                if valid:
                    time = np.asarray(
                        [item["time_s"] for item in segment], dtype=float
                    )
                    state = np.asarray(
                        [item["state"] for item in segment], dtype=float
                    )
                    torque = np.asarray(
                        [item["generalized_input_nm"] for item in segment],
                        dtype=float,
                    )
                    full_regressor, target = integral_regression_block(
                        time, state, torque
                    )
                    regressor = full_regressor @ projection
                    predecessor_loss = float(
                        np.mean((regressor @ theta_0 - target) ** 2)
                    )
                    successor_loss = float(
                        np.mean((regressor @ theta_1 - target) ** 2)
                    )
                    block.update(
                        {
                            "predecessor_loss_nms2": predecessor_loss,
                            "successor_loss_nms2": successor_loss,
                            "successor_minus_predecessor_loss_nms2": (
                                successor_loss - predecessor_loss
                            ),
                        }
                    )
                blocks.append(block)
        valid_blocks = [item for item in blocks if item["valid"]]
        differences = np.asarray(
            [item["successor_minus_predecessor_loss_nms2"] for item in valid_blocks],
            dtype=float,
        )
        classification = classify_post_update_evidence(
            differences,
            config=Stage5ReducedHumanIDConfig().trust,
            transition_index=0,
        )
        phase_summary: dict[str, Any] = {}
        for phase in ("OUTBOUND", "HOLD", "RETURN", "MIXED"):
            selected = [item for item in valid_blocks if item["task_phase"] == phase]
            if not selected:
                continue
            phase_differences = np.asarray(
                [item["successor_minus_predecessor_loss_nms2"] for item in selected]
            )
            phase_summary[phase] = {
                "block_count": len(selected),
                "mean_paired_difference_nms2": float(np.mean(phase_differences)),
                "favorable_block_count": int(np.count_nonzero(phase_differences < 0.0)),
            }
        return {
            "available": True,
            "replication_id": self.replication_id,
            "cem_seed": self.cem_seed,
            "transition_time_s": self.transition_time_s,
            "transition_embargo_end_s": earliest,
            "blocks": blocks,
            "valid_block_count": len(valid_blocks),
            "mean_paired_difference_nms2": (
                None if not len(differences) else float(np.mean(differences))
            ),
            "favorable_block_fraction": (
                None
                if not len(differences)
                else float(np.mean(differences < 0.0))
            ),
            "phase_summary": phase_summary,
            "classification": classification,
            "block_level_values_not_independent_replication_units": True,
        }


def aggregate_replication_units(units: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize one scalar direction per rollout without pooling blocks."""

    records = list(units)
    ids = [str(item["replication_id"]) for item in records]
    seeds = [int(item["cem_seed"]) for item in records]
    if len(records) != len(set(ids)) or len(records) != len(set(seeds)):
        raise ValueError("replication ids and seeds must be unique")
    means = np.asarray(
        [float(item["mean_paired_difference_nms2"]) for item in records],
        dtype=float,
    )
    return {
        "replication_unit_count": len(records),
        "replication_ids": ids,
        "cem_seeds": seeds,
        "rollout_mean_paired_differences_nms2": means.tolist(),
        "favorable_rollout_count": int(np.count_nonzero(means < 0.0)),
        "unfavorable_rollout_count": int(np.count_nonzero(means >= 0.0)),
        "within_rollout_blocks_pooled_as_independent": False,
        "top_level_sample_size": len(records),
    }


__all__ = [
    "FROZEN_THETA_0",
    "FROZEN_THETA_1",
    "FROZEN_THETA_1_VERSION",
    "FrozenSuccessorArm",
    "FrozenSuccessorReplicationAuthority",
    "FrozenSuccessorReplicationSpec",
    "aggregate_replication_units",
]
