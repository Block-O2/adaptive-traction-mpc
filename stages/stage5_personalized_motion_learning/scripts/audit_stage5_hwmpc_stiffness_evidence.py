#!/usr/bin/env python3
"""Offline causal audit of stiffness post-update evidence under HWMPC."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage3.human import soft_limit_torque
from traction_mpc_stage4.estimator_v2 import nominal_base_parameters
from traction_mpc_stage4.integral_identifier import integral_regression_block
from traction_mpc_stage4.minimal_adaptation import (
    dynamic_scale_projection,
    effective_base_parameters,
)
from traction_mpc_stage4.statistical_trust import _hac_bounds
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_identification_reduced import (
    Stage5ReducedHumanIDConfig,
    reduced_information,
)


SCHEMA = "stage5_hwmpc_stiffness_evidence_audit_v1"
DEFAULT_SOURCE = Path(
    "stages/stage5_personalized_motion_learning/results/engineering_validation/"
    "hwmpc_human_personalization_v1_attempt_02/"
    "hwmpc_human_personalization.json"
)
PHASES = ("OUTBOUND", "HOLD", "RETURN")


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    return value


def _condition(payload: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [item for item in payload["conditions"] if item["condition"] == name]
    if len(matches) != 1:
        raise ValueError(f"expected one condition named {name}")
    return matches[0]


def _session_records(arm: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for repetition_row in arm["repetitions"]:
        repetition = int(repetition_row["repetition"])
        start = float(repetition_row["session_start_time_s"])
        for trace_row in repetition_row["metrics"]["trace"]:
            state = np.asarray(trace_row["estimated_state_rad_rad_s"], dtype=float)
            records.append(
                {
                    "time_s": start + float(trace_row["elapsed_s"]),
                    "episode_index": repetition - 1,
                    "repetition": repetition,
                    "phase": str(trace_row["phase"]),
                    "state": state,
                    "requested_q_rad": np.asarray(
                        trace_row["requested_q_rad"], dtype=float
                    ),
                    "requested_dq_rad_s": np.asarray(
                        trace_row["requested_dq_rad_s"], dtype=float
                    ),
                    "generalized_input_nm": np.asarray(
                        trace_row["deployable_measured_generalized_input_nm"],
                        dtype=float,
                    ),
                    "contaminated": bool(
                        np.linalg.norm(
                            soft_limit_torque(state[:2], state[2:], STAGE5_HUMAN)
                        )
                        > 1.0e-8
                    ),
                    "source_index": len(records),
                }
            )
    return records


def _future_blocks(
    records: list[dict[str, Any]], activation_time_s: float, window_s: float = 0.20
) -> list[dict[str, Any]]:
    projection = dynamic_scale_projection(nominal_base_parameters(STAGE5_HUMAN))
    later = [
        item
        for item in records
        if float(item["time_s"]) > activation_time_s + 1.0e-12
    ]
    blocks: list[dict[str, Any]] = []
    for episode_index in sorted({int(item["episode_index"]) for item in later}):
        episode = [
            item for item in later if int(item["episode_index"]) == episode_index
        ]
        if not episode:
            continue
        block_start = max(activation_time_s, float(episode[0]["time_s"]))
        final_time = float(episode[-1]["time_s"])
        while block_start + window_s <= final_time + 1.0e-12:
            block_end = block_start + window_s
            segment = [
                item
                for item in episode
                if block_start - 1.0e-12
                <= float(item["time_s"])
                <= block_end + 1.0e-12
            ]
            block_start = block_end
            if (
                len(segment) < 3
                or float(segment[-1]["time_s"])
                - float(segment[0]["time_s"])
                < 0.90 * window_s
                or any(bool(item["contaminated"]) for item in segment)
            ):
                continue
            time = np.asarray([item["time_s"] for item in segment], dtype=float)
            state = np.asarray([item["state"] for item in segment], dtype=float)
            torque = np.asarray(
                [item["generalized_input_nm"] for item in segment], dtype=float
            )
            full_regressor, target = integral_regression_block(time, state, torque)
            phases = sorted({str(item["phase"]) for item in segment})
            blocks.append(
                {
                    "index": len(blocks),
                    "episode_index": episode_index,
                    "repetition": int(segment[0]["repetition"]),
                    "start_time_s": float(time[0]),
                    "end_time_s": float(time[-1]),
                    "phase": phases[0] if len(phases) == 1 else "+".join(phases),
                    "sample_count": len(segment),
                    "regressor": full_regressor @ projection,
                    "target": target,
                }
            )
    return blocks


def _losses(blocks: list[dict[str, Any]], scales: Any) -> np.ndarray:
    values = np.asarray(scales, dtype=float)
    return np.asarray(
        [
            float(np.mean((block["regressor"] @ values - block["target"]) ** 2))
            for block in blocks
        ],
        dtype=float,
    )


def _information_summary(
    blocks: list[dict[str, Any]], predecessor: Any, successor: Any
) -> dict[str, Any]:
    if not blocks:
        return {"block_count": 0}
    matrix = np.vstack([block["regressor"] for block in blocks])
    delta = np.asarray(successor, dtype=float) - np.asarray(predecessor, dtype=float)
    information = reduced_information(matrix)
    effect_by_parameter = np.abs(delta) * np.asarray(
        information["column_norms"], dtype=float
    )
    return {
        "block_count": len(blocks),
        "sample_count": int(sum(block["sample_count"] for block in blocks)),
        "duration_s": float(sum(block["end_time_s"] - block["start_time_s"] for block in blocks)),
        "information": information,
        "successor_step": delta,
        "step_effect_l2_by_parameter": effect_by_parameter,
        "total_step_effect_rms": float(np.sqrt(np.mean((matrix @ delta) ** 2))),
    }


def _phase_evidence(
    blocks: list[dict[str, Any]], predecessor: Any, successor: Any
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for phase in (*PHASES, "MIXED", "ALL"):
        if phase == "ALL":
            selected = blocks
        elif phase == "MIXED":
            selected = [block for block in blocks if "+" in block["phase"]]
        else:
            selected = [block for block in blocks if block["phase"] == phase]
        if not selected:
            result[phase] = {"block_count": 0}
            continue
        predecessor_loss = _losses(selected, predecessor)
        successor_loss = _losses(selected, successor)
        difference = successor_loss - predecessor_loss
        result[phase] = {
            **_information_summary(selected, predecessor, successor),
            "predecessor_mean_loss_nms2": float(np.mean(predecessor_loss)),
            "successor_mean_loss_nms2": float(np.mean(successor_loss)),
            "successor_minus_predecessor_mean_loss_nms2": float(
                np.mean(difference)
            ),
            "successor_better_block_fraction": float(np.mean(difference < 0.0)),
            "difference_minimum_nms2": float(np.min(difference)),
            "difference_maximum_nms2": float(np.max(difference)),
        }
    return result


def _tracking_by_phase(arm: dict[str, Any], first_repetition: int = 2) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for repetition_row in arm["repetitions"]:
        repetition = int(repetition_row["repetition"])
        if repetition < first_repetition:
            continue
        phase_result: dict[str, Any] = {}
        for phase in PHASES:
            rows = [
                row
                for row in repetition_row["metrics"]["trace"]
                if row["phase"] == phase
            ]
            q_error = np.asarray(
                [
                    np.asarray(row["estimated_state_rad_rad_s"][:2], dtype=float)
                    - np.asarray(row["requested_q_rad"], dtype=float)
                    for row in rows
                ]
            )
            dq_error = np.asarray(
                [
                    np.asarray(row["estimated_state_rad_rad_s"][2:], dtype=float)
                    - np.asarray(row["requested_dq_rad_s"], dtype=float)
                    for row in rows
                ]
            )
            phase_result[phase] = {
                "sample_count": len(rows),
                "q_rmse_deg": np.rad2deg(np.sqrt(np.mean(q_error**2, axis=0))),
                "dq_rmse_deg_s": np.rad2deg(
                    np.sqrt(np.mean(dq_error**2, axis=0))
                ),
            }
        result[str(repetition)] = phase_result
    return result


def _phase_at(arm: dict[str, Any], session_time_s: float) -> dict[str, Any]:
    candidates: list[tuple[float, int, str, float]] = []
    for row in arm["repetitions"]:
        start = float(row["session_start_time_s"])
        for sample in row["metrics"]["trace"]:
            timestamp = start + float(sample["elapsed_s"])
            candidates.append(
                (
                    abs(timestamp - session_time_s),
                    int(row["repetition"]),
                    str(sample["phase"]),
                    timestamp,
                )
            )
    _, repetition, phase, timestamp = min(candidates)
    return {
        "query_time_s": session_time_s,
        "nearest_sample_time_s": timestamp,
        "repetition": repetition,
        "phase": phase,
    }


def _lifecycle(condition: dict[str, Any]) -> dict[str, Any]:
    arm = condition["arms"]["progressive"]
    first = arm["repetitions"][0]
    second = arm["repetitions"][1]
    attempt = first["new_identifier_attempts"][0]
    queued = first["authority_end"]["queued_update"]
    activation = second["activation"]
    successor_model_id = str(queued["successor_model_id"])
    evidence_rows = [
        row["authority_end"]["post_update_evidence"]
        for row in arm["repetitions"]
        if row["active_model_id"] == successor_model_id
        and row["authority_end"]["post_update_evidence"].get("available", False)
        and row["authority_end"]["post_update_evidence"].get("target_model_id")
        == successor_model_id
    ]
    if not evidence_rows:
        raise RuntimeError("first successor has no post-update evidence record")
    final_evidence = evidence_rows[0]
    return {
        "population_prior": {
            "repetition": 1,
            "session_start_time_s": first["session_start_time_s"],
            "model_id": first["active_model_id"],
            "theta": first["active_theta"],
        },
        "candidate_formation": {
            "fit_end_time_s": attempt["fit_end_time_s"],
            "context": _phase_at(arm, float(attempt["fit_end_time_s"])),
            "training_diagnostics": attempt["training_diagnostics"],
            "candidate_scales": attempt["candidate_scales"],
            "bounded_successor_scales": attempt["proposed_model_scales"],
        },
        "candidate_qualification": {
            "decision_time_s": attempt["decision_time_s"],
            "context": _phase_at(arm, float(attempt["decision_time_s"])),
            "decision_block_count": attempt["decision_block_count"],
            "evidence": attempt["evidence_history"][-1],
            "queued_update": queued,
        },
        "activation": activation,
        "post_update_evaluation": {
            "online_maximum_block_count": 12,
            "blocks": final_evidence["blocks"],
            "classification": final_evidence["classification"],
        },
    }


def _extended_prefix_evidence(
    blocks: list[dict[str, Any]], predecessor: Any, successor: Any, transition_index: int
) -> dict[str, Any]:
    config = Stage5ReducedHumanIDConfig().trust
    difference = _losses(blocks, successor) - _losses(blocks, predecessor)
    alpha = config.per_reference_per_look_alpha(transition_index)
    counts = sorted(
        set(
            [count for count in config.scheduled_looks if count <= len(blocks)]
            + list(range(16, len(blocks) + 1, 4))
            + ([len(blocks)] if len(blocks) >= config.minimum_clean_blocks else [])
        )
    )
    rows = []
    first_crossing = None
    for count in counts:
        bounds = _hac_bounds(
            difference[:count], alpha=alpha, lag_blocks=config.hac_lag_blocks
        )
        row = {
            "block_count": count,
            "last_repetition": int(blocks[count - 1]["repetition"]),
            "last_phase": blocks[count - 1]["phase"],
            "registered_online_look": count in config.scheduled_looks,
            **bounds,
        }
        rows.append(row)
        if first_crossing is None and row["upper_bound_nms2"] < 0.0:
            first_crossing = row
    by_repetition = []
    for repetition in sorted({int(block["repetition"]) for block in blocks}):
        count = sum(int(block["repetition"]) <= repetition for block in blocks)
        if count < config.minimum_clean_blocks:
            continue
        bounds = _hac_bounds(
            difference[:count], alpha=alpha, lag_blocks=config.hac_lag_blocks
        )
        by_repetition.append(
            {"through_repetition": repetition, "block_count": count, **bounds}
        )
    return {
        "semantics": (
            "offline diagnostic extension using the unchanged HAC lag and the "
            "unchanged transition-index alpha; counts above 12 are not registered "
            "online looks and do not alter the historical decision"
        ),
        "per_reference_per_look_alpha": alpha,
        "prefixes": rows,
        "through_repetition": by_repetition,
        "first_offline_upper_bound_below_zero": first_crossing,
        "all_future_block_count": len(blocks),
    }


def _analyze(condition: dict[str, Any]) -> dict[str, Any]:
    progressive = condition["arms"]["progressive"]
    fixed = condition["arms"]["fixed_population_prior"]
    lineage = sorted(
        progressive["authority"]["lineage"].values(),
        key=lambda model: int(model["update_index"]),
    )
    predecessor = lineage[0]
    successor = lineage[1]
    activation_time_s = float(successor["activation_time_s"])
    blocks = _future_blocks(_session_records(progressive), activation_time_s)
    phase = _phase_evidence(blocks, predecessor["theta"], successor["theta"])
    repetition_evidence = {
        str(repetition): _phase_evidence(
            [block for block in blocks if int(block["repetition"]) == repetition],
            predecessor["theta"],
            successor["theta"],
        )
        for repetition in sorted({int(block["repetition"]) for block in blocks})
    }
    block_rows = []
    predecessor_losses = _losses(blocks, predecessor["theta"])
    successor_losses = _losses(blocks, successor["theta"])
    for block, old, new in zip(
        blocks, predecessor_losses, successor_losses, strict=True
    ):
        block_rows.append(
            {
                "index": block["index"],
                "repetition": block["repetition"],
                "phase": block["phase"],
                "start_time_s": block["start_time_s"],
                "end_time_s": block["end_time_s"],
                "predecessor_loss_nms2": old,
                "successor_loss_nms2": new,
                "successor_minus_predecessor_loss_nms2": new - old,
            }
        )
    return {
        "condition": condition["condition"],
        "predecessor": predecessor,
        "first_successor": successor,
        "lifecycle": _lifecycle(condition),
        "future_blocks": block_rows,
        "phase_evidence": phase,
        "repetition_evidence": repetition_evidence,
        "matched_tracking": {
            "fixed_population_prior": _tracking_by_phase(fixed),
            "progressive_successor": _tracking_by_phase(progressive),
        },
        "extended_counterfactual": _extended_prefix_evidence(
            blocks,
            predecessor["theta"],
            successor["theta"],
            int(successor["update_index"]),
        ),
    }


def _plot(analyses: list[dict[str, Any]], path: Path) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(14, 9))
    colors = {"OUTBOUND": "tab:blue", "HOLD": "tab:orange", "RETURN": "tab:green"}
    for row, analysis in enumerate(analyses):
        blocks = analysis["future_blocks"]
        x = np.arange(1, len(blocks) + 1)
        difference = np.asarray(
            [item["successor_minus_predecessor_loss_nms2"] for item in blocks]
        )
        phase_colors = [colors.get(item["phase"], "tab:gray") for item in blocks]
        axes[row, 0].scatter(x, difference, c=phase_colors, s=18)
        axes[row, 0].axhline(0.0, color="black", linewidth=1)
        axes[row, 0].axvline(12.5, color="red", linestyle="--", label="online cap")
        axes[row, 0].set_title(f"{analysis['condition']}: block loss difference")
        axes[row, 0].set_xlabel("causal future block")
        axes[row, 0].set_ylabel("successor - predecessor loss")
        axes[row, 0].grid(True, alpha=0.25)
        axes[row, 0].legend()

        prefixes = analysis["extended_counterfactual"]["prefixes"]
        count = np.asarray([item["block_count"] for item in prefixes])
        mean = np.asarray([item["mean_difference_nms2"] for item in prefixes])
        upper = np.asarray([item["upper_bound_nms2"] for item in prefixes])
        lower = np.asarray([item["lower_bound_nms2"] for item in prefixes])
        axes[row, 1].plot(count, mean, marker="o", label="cumulative mean")
        axes[row, 1].plot(count, upper, marker=".", label="one-sided upper")
        axes[row, 1].plot(count, lower, marker=".", label="one-sided lower")
        axes[row, 1].axhline(0.0, color="black", linewidth=1)
        axes[row, 1].axvline(12, color="red", linestyle="--", label="online cap")
        axes[row, 1].set_title(f"{analysis['condition']}: offline prefix evidence")
        axes[row, 1].set_xlabel("causal future blocks")
        axes[row, 1].grid(True, alpha=0.25)
        axes[row, 1].legend()
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_audit(source: Path, output_dir: Path) -> dict[str, Any]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema") != "stage5_hwmpc_human_personalization_validation_v1":
        raise ValueError("unexpected HWMPC personalization source schema")
    analyses = [
        _analyze(_condition(payload, "stiffness_plus_15pct")),
        _analyze(_condition(payload, "damping_plus_20pct")),
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "stiffness_evidence_lifecycle.png"
    _plot(analyses, plot_path)
    result = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": "offline_diagnostic_from_saved_causal_traces",
            "source": str(source),
            "analyses": analyses,
            "plot": str(plot_path),
            "scope_invariants": {
                "online_decision_changed": False,
                "future_data_used_online": False,
                "personalization_parameter_or_threshold_changed": False,
                "r_task_hwmpc_cost_or_timing_changed": False,
                "simulation_rerun": False,
                "historical_result_modified": False,
            },
        }
    )
    result_path = output_dir / "stiffness_evidence_lifecycle.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(result_path),
                "summary": [
                    {
                        "condition": analysis["condition"],
                        "online": analysis["lifecycle"]["post_update_evaluation"][
                            "classification"
                        ],
                        "future_block_count": analysis["extended_counterfactual"][
                            "all_future_block_count"
                        ],
                        "first_offline_crossing": analysis[
                            "extended_counterfactual"
                        ]["first_offline_upper_bound_below_zero"],
                    }
                    for analysis in analyses
                ],
            },
            indent=2,
        )
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    run_audit(arguments.source, arguments.output_dir)


if __name__ == "__main__":
    main()
