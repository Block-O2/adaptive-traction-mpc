"""Shadow-only phase-complete post-update evidence for HWMPC Human models.

The online progressive-personalization authority intentionally keeps its
registered 8/10/12-block lifecycle.  This module is a separate diagnostic
consumer: it evaluates the same predecessor/successor prediction-loss
difference on causal deployable samples through the first complete
OUTBOUND/HOLD/RETURN cycle.  It never records evidence with the authority and
never changes a control model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from traction_mpc_stage3.human import soft_limit_torque
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.integral_identifier import integral_regression_block
from traction_mpc_stage4.minimal_adaptation import dynamic_scale_projection
from traction_mpc_stage4.statistical_trust import _hac_bounds

from .human import STAGE5_HUMAN
from .human_identification_reduced import (
    Stage5ReducedHumanIDConfig,
    reduced_information,
)


PHASE_ORDER = ("OUTBOUND", "HOLD", "RETURN")


@dataclass(frozen=True)
class PhaseCompletePostUpdateIdentity:
    predecessor_model_id: str
    successor_model_id: str
    predecessor_theta: tuple[float, float, float]
    successor_theta: tuple[float, float, float]
    successor_update_index: int
    activation_repetition: int
    activation_time_s: float

    def __post_init__(self) -> None:
        if not self.predecessor_model_id or not self.successor_model_id:
            raise ValueError("predecessor and successor identities are required")
        if self.successor_update_index < 1 or self.activation_repetition < 1:
            raise ValueError("a non-root activated successor is required")
        predecessor = np.asarray(self.predecessor_theta, dtype=float)
        successor = np.asarray(self.successor_theta, dtype=float)
        if predecessor.shape != (3,) or successor.shape != (3,):
            raise ValueError("Human model theta must have three scales")
        if not np.all(np.isfinite([*predecessor, *successor, self.activation_time_s])):
            raise ValueError("identity parameters must be finite")


class PhaseCompletePostUpdateShadowV1:
    """Causal, authority-isolated phase-complete evidence accumulator."""

    def __init__(
        self,
        identity: PhaseCompletePostUpdateIdentity,
        config: Stage5ReducedHumanIDConfig | None = None,
    ) -> None:
        self.identity = identity
        self.config = Stage5ReducedHumanIDConfig() if config is None else config
        self.records: list[dict[str, Any]] = []
        self._last_time_s: float | None = None

    def observe(self, sample: dict[str, Any]) -> None:
        """Consume one deployable causal sample without producing authority."""

        time_s = float(sample["time_s"])
        if time_s <= self.identity.activation_time_s + 1.0e-12:
            return
        if self._last_time_s is not None and time_s <= self._last_time_s + 1.0e-12:
            raise ValueError("phase-complete shadow samples must be time ordered")
        state = np.asarray(sample["state"], dtype=float)
        generalized_input = np.asarray(sample["generalized_input_nm"], dtype=float)
        if state.shape != (4,) or generalized_input.shape != (2,):
            raise ValueError("shadow state/input dimensions are invalid")
        if not np.all(np.isfinite([*state, *generalized_input])):
            raise ValueError("shadow samples must be finite")
        phase = str(sample["phase"])
        if phase not in PHASE_ORDER:
            raise ValueError(f"unsupported task phase {phase}")
        requested_q = sample.get("requested_q_rad")
        requested_dq = sample.get("requested_dq_rad_s")
        self.records.append(
            {
                "time_s": time_s,
                "episode_index": int(sample["episode_index"]),
                "repetition": int(sample["repetition"]),
                "phase": phase,
                "state": state.copy(),
                "generalized_input_nm": generalized_input.copy(),
                "requested_q_rad": (
                    None
                    if requested_q is None
                    else np.asarray(requested_q, dtype=float).copy()
                ),
                "requested_dq_rad_s": (
                    None
                    if requested_dq is None
                    else np.asarray(requested_dq, dtype=float).copy()
                ),
                "control_model_version": str(
                    sample.get("control_model_version", "unknown")
                ),
                "contaminated": bool(
                    sample.get(
                        "contaminated",
                        np.linalg.norm(
                            soft_limit_torque(state[:2], state[2:], STAGE5_HUMAN)
                        )
                        > 1.0e-8,
                    )
                ),
                "source_index": int(sample.get("source_index", len(self.records))),
            }
        )
        self._last_time_s = time_s

    def _blocks(self) -> list[dict[str, Any]]:
        window_s = float(self.config.identifier.integration_window_s)
        projection = dynamic_scale_projection(nominal_base_parameters(STAGE5_HUMAN))
        blocks: list[dict[str, Any]] = []
        episodes = sorted({int(row["episode_index"]) for row in self.records})
        for episode_index in episodes:
            episode = [
                row
                for row in self.records
                if int(row["episode_index"]) == episode_index
            ]
            if not episode:
                continue
            block_start = max(
                self.identity.activation_time_s, float(episode[0]["time_s"])
            )
            final_time = float(episode[-1]["time_s"])
            while block_start + window_s <= final_time + 1.0e-12:
                block_end = block_start + window_s
                segment = [
                    row
                    for row in episode
                    if block_start - 1.0e-12
                    <= float(row["time_s"])
                    <= block_end + 1.0e-12
                ]
                block_start = block_end
                if (
                    len(segment) < 3
                    or float(segment[-1]["time_s"])
                    - float(segment[0]["time_s"])
                    < 0.90 * window_s
                    or any(bool(row["contaminated"]) for row in segment)
                ):
                    continue
                time = np.asarray([row["time_s"] for row in segment], dtype=float)
                state = np.asarray([row["state"] for row in segment], dtype=float)
                torque = np.asarray(
                    [row["generalized_input_nm"] for row in segment], dtype=float
                )
                full_regressor, target = integral_regression_block(time, state, torque)
                phase_sequence = list(dict.fromkeys(str(row["phase"]) for row in segment))
                model_versions = list(
                    dict.fromkeys(str(row["control_model_version"]) for row in segment)
                )
                blocks.append(
                    {
                        "index": len(blocks),
                        "episode_index": episode_index,
                        "repetition": int(segment[0]["repetition"]),
                        "start_time_s": float(time[0]),
                        "end_time_s": float(time[-1]),
                        "phase": "+".join(phase_sequence),
                        "control_model_versions": model_versions,
                        "sample_count": len(segment),
                        "regressor": full_regressor @ projection,
                        "target": target,
                        "source_indices": [int(row["source_index"]) for row in segment],
                    }
                )
        return blocks

    def _block_rows(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        predecessor = np.asarray(self.identity.predecessor_theta, dtype=float)
        successor = np.asarray(self.identity.successor_theta, dtype=float)
        differences: list[float] = []
        rows: list[dict[str, Any]] = []
        trust = self.config.trust
        alpha = trust.per_reference_per_look_alpha(
            self.identity.successor_update_index
        )
        for block in blocks:
            old = float(
                np.mean((block["regressor"] @ predecessor - block["target"]) ** 2)
            )
            new = float(
                np.mean((block["regressor"] @ successor - block["target"]) ** 2)
            )
            differences.append(new - old)
            cumulative: dict[str, Any] = {
                "available": len(differences) >= trust.minimum_clean_blocks,
                "block_count": len(differences),
                "mean_difference_nms2": float(np.mean(differences)),
                "registered_online_look": len(differences) in trust.scheduled_looks,
            }
            if cumulative["available"]:
                bounds = _hac_bounds(
                    np.asarray(differences, dtype=float),
                    alpha=alpha,
                    lag_blocks=trust.hac_lag_blocks,
                )
                cumulative.update(bounds)
                cumulative["descriptive_outcome"] = self._outcome(bounds)
            else:
                cumulative.update(
                    {
                        "reason": "below_existing_minimum_clean_blocks",
                        "descriptive_outcome": "neutral",
                    }
                )
            rows.append(
                {
                    "index": int(block["index"]),
                    "episode_index": int(block["episode_index"]),
                    "repetition": int(block["repetition"]),
                    "start_time_s": float(block["start_time_s"]),
                    "end_time_s": float(block["end_time_s"]),
                    "phase": str(block["phase"]),
                    "control_model_versions": list(block["control_model_versions"]),
                    "sample_count": int(block["sample_count"]),
                    "predecessor_loss_nms2": old,
                    "successor_loss_nms2": new,
                    "successor_minus_predecessor_loss_nms2": new - old,
                    "cumulative_evidence": cumulative,
                }
            )
        return rows

    @staticmethod
    def _outcome(bounds: dict[str, Any]) -> str:
        if float(bounds["upper_bound_nms2"]) < 0.0:
            return "positive"
        if float(bounds["lower_bound_nms2"]) > 0.0:
            return "negative"
        return "neutral"

    def _evidence_summary(self, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        if not blocks:
            return {"block_count": 0, "bounds_available": False}
        predecessor = np.asarray(self.identity.predecessor_theta, dtype=float)
        successor = np.asarray(self.identity.successor_theta, dtype=float)
        differences = np.asarray(
            [
                np.mean((block["regressor"] @ successor - block["target"]) ** 2)
                - np.mean((block["regressor"] @ predecessor - block["target"]) ** 2)
                for block in blocks
            ],
            dtype=float,
        )
        information = reduced_information(
            np.vstack([block["regressor"] for block in blocks])
        )
        result: dict[str, Any] = {
            "block_count": len(blocks),
            "start_time_s": float(blocks[0]["start_time_s"]),
            "end_time_s": float(blocks[-1]["end_time_s"]),
            "successor_minus_predecessor_mean_loss_nms2": float(
                np.mean(differences)
            ),
            "successor_better_block_fraction": float(np.mean(differences < 0.0)),
            "regressor_information": information,
            "bounds_available": len(blocks) >= self.config.trust.minimum_clean_blocks,
        }
        if result["bounds_available"]:
            bounds = _hac_bounds(
                differences,
                alpha=self.config.trust.per_reference_per_look_alpha(
                    self.identity.successor_update_index
                ),
                lag_blocks=self.config.trust.hac_lag_blocks,
            )
            result.update(bounds)
            result["descriptive_outcome"] = self._outcome(bounds)
        else:
            result["descriptive_outcome"] = "neutral"
        return result

    def _tracking_summary(
        self, episode_records: list[dict[str, Any]], phase: str
    ) -> dict[str, Any]:
        selected = [row for row in episode_records if row["phase"] == phase]
        if not selected:
            return {"sample_count": 0, "available": False}
        if any(
            row["requested_q_rad"] is None or row["requested_dq_rad_s"] is None
            for row in selected
        ):
            return {
                "sample_count": len(selected),
                "available": False,
                "reason": "requested_reference_not_supplied",
            }
        state = np.asarray([row["state"] for row in selected], dtype=float)
        requested_q = np.asarray(
            [row["requested_q_rad"] for row in selected], dtype=float
        )
        requested_dq = np.asarray(
            [row["requested_dq_rad_s"] for row in selected], dtype=float
        )
        return {
            "sample_count": len(selected),
            "available": True,
            "q_rmse_deg": np.rad2deg(
                np.sqrt(np.mean((state[:, :2] - requested_q) ** 2, axis=0))
            ),
            "dq_rmse_deg_s": np.rad2deg(
                np.sqrt(np.mean((state[:, 2:] - requested_dq) ** 2, axis=0))
            ),
        }

    def report(self) -> dict[str, Any]:
        """Return the frozen first-cycle endpoint and later shadow trajectory."""

        activation_episode = self.identity.activation_repetition - 1
        episode_records = [
            row
            for row in self.records
            if int(row["episode_index"]) == activation_episode
        ]
        observed_phase_order = list(
            dict.fromkeys(str(row["phase"]) for row in episode_records)
        )
        phase_complete = observed_phase_order == list(PHASE_ORDER)
        all_blocks = self._blocks()
        terminal_blocks = [
            block
            for block in all_blocks
            if int(block["episode_index"]) == activation_episode
        ]
        terminal_rows = self._block_rows(terminal_blocks)
        phase_summary = {}
        for phase in PHASE_ORDER:
            phase_blocks = [block for block in terminal_blocks if block["phase"] == phase]
            phase_records = [row for row in episode_records if row["phase"] == phase]
            phase_summary[phase] = {
                "prediction_evidence": self._evidence_summary(phase_blocks),
                "tracking": self._tracking_summary(episode_records, phase),
                "control_model_versions": list(
                    dict.fromkeys(
                        str(row["control_model_version"]) for row in phase_records
                    )
                ),
            }
        mixed_blocks = [block for block in terminal_blocks if "+" in block["phase"]]
        terminal_evidence = self._evidence_summary(terminal_blocks)
        later_rows = self._block_rows(all_blocks)
        post_terminal = [
            row
            for row in later_rows
            if int(row["episode_index"]) > activation_episode
        ]
        later_reversal = any(
            row["cumulative_evidence"].get("descriptive_outcome") == "negative"
            for row in post_terminal
        )
        return {
            "schema": "stage5_phase_complete_post_update_shadow_v1",
            "shadow_only": True,
            "authority_effect": "none",
            "historical_online_decision_rewritten": False,
            "identity": {
                "predecessor_model_id": self.identity.predecessor_model_id,
                "successor_model_id": self.identity.successor_model_id,
                "predecessor_theta": list(self.identity.predecessor_theta),
                "successor_theta": list(self.identity.successor_theta),
                "successor_update_index": self.identity.successor_update_index,
                "activation_repetition": self.identity.activation_repetition,
                "activation_time_s": self.identity.activation_time_s,
            },
            "contract": {
                "sample_boundary": "deployable causal samples strictly after activation",
                "block_window_s": self.config.identifier.integration_window_s,
                "phase_order": list(PHASE_ORDER),
                "terminal_rule": (
                    "first activated repetition with complete OUTBOUND/HOLD/RETURN; "
                    "use every clean nonoverlapping block available at its end"
                ),
                "existing_minimum_clean_blocks": self.config.trust.minimum_clean_blocks,
                "existing_online_scheduled_looks": list(
                    self.config.trust.scheduled_looks
                ),
                "existing_hac_lag_blocks": self.config.trust.hac_lag_blocks,
                "unchanged_per_reference_per_look_alpha": (
                    self.config.trust.per_reference_per_look_alpha(
                        self.identity.successor_update_index
                    )
                ),
                "intermediate_bounds_role": "descriptive_shadow_trajectory_only",
            },
            "phase_complete": phase_complete,
            "observed_phase_order": observed_phase_order,
            "phase_cycle_completion_time_s": (
                None if not episode_records else float(episode_records[-1]["time_s"])
            ),
            "terminal": {
                "block_count": len(terminal_blocks),
                "last_block_end_time_s": (
                    None
                    if not terminal_blocks
                    else float(terminal_blocks[-1]["end_time_s"])
                ),
                "evidence": terminal_evidence,
                "block_trajectory": terminal_rows,
                "phase_summary": phase_summary,
                "mixed_phase_prediction_evidence": self._evidence_summary(
                    mixed_blocks
                ),
                "control_model_versions": list(
                    dict.fromkeys(
                        str(row["control_model_version"]) for row in episode_records
                    )
                ),
            },
            "later_shadow": {
                "all_block_count": len(all_blocks),
                "post_terminal_block_count": len(post_terminal),
                "cumulative_trajectory": later_rows,
                "statistical_reversal_after_terminal": later_reversal,
                "final_evidence": self._evidence_summary(all_blocks),
                "interpretation": (
                    "later blocks are causal observations but may have been generated "
                    "under later active model versions; they never alter the frozen terminal"
                ),
            },
        }


__all__ = [
    "PHASE_ORDER",
    "PhaseCompletePostUpdateIdentity",
    "PhaseCompletePostUpdateShadowV1",
]
