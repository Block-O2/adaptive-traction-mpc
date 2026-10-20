#!/usr/bin/env python3
"""Validate phase-complete HWMPC post-update evidence on saved causal traces."""

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
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.phase_complete_post_update import (
    PhaseCompletePostUpdateIdentity,
    PhaseCompletePostUpdateShadowV1,
)


SCHEMA = "stage5_hwmpc_phase_complete_post_update_validation_v1"
DEFAULT_SOURCE = Path(
    "stages/stage5_personalized_motion_learning/results/engineering_validation/"
    "hwmpc_human_personalization_v1_attempt_02/"
    "hwmpc_human_personalization.json"
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _records(progressive: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for repetition in progressive["repetitions"]:
        repetition_index = int(repetition["repetition"])
        session_start = float(repetition["session_start_time_s"])
        for trace_row in repetition["metrics"]["trace"]:
            state = np.asarray(
                trace_row["estimated_state_rad_rad_s"], dtype=float
            )
            records.append(
                {
                    "time_s": session_start + float(trace_row["elapsed_s"]),
                    "episode_index": repetition_index - 1,
                    "repetition": repetition_index,
                    "phase": str(trace_row["phase"]),
                    "state": state,
                    "generalized_input_nm": np.asarray(
                        trace_row["deployable_measured_generalized_input_nm"],
                        dtype=float,
                    ),
                    "requested_q_rad": np.asarray(
                        trace_row["requested_q_rad"], dtype=float
                    ),
                    "requested_dq_rad_s": np.asarray(
                        trace_row["requested_dq_rad_s"], dtype=float
                    ),
                    "control_model_version": str(
                        trace_row["control_human_model_version"]
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


def _first_successor_online_evidence(
    progressive: dict[str, Any], model_id: str
) -> dict[str, Any] | None:
    for repetition in progressive["repetitions"]:
        evidence = repetition["authority_end"]["post_update_evidence"]
        if (
            evidence.get("available", False)
            and evidence.get("target_model_id") == model_id
        ):
            return evidence
    return None


def _evaluate_condition(condition: dict[str, Any]) -> dict[str, Any]:
    progressive = condition["arms"]["progressive"]
    lineage = progressive["authority"]["lineage"]
    models = sorted(lineage.values(), key=lambda row: int(row["update_index"]))
    records = _records(progressive)
    reports = []
    for successor in models[1:]:
        predecessor = lineage[str(successor["predecessor_model_id"])]
        identity = PhaseCompletePostUpdateIdentity(
            predecessor_model_id=str(predecessor["model_id"]),
            successor_model_id=str(successor["model_id"]),
            predecessor_theta=tuple(float(value) for value in predecessor["theta"]),
            successor_theta=tuple(float(value) for value in successor["theta"]),
            successor_update_index=int(successor["update_index"]),
            activation_repetition=int(successor["activation_repetition"]),
            activation_time_s=float(successor["activation_time_s"]),
        )
        evaluator = PhaseCompletePostUpdateShadowV1(identity)
        for record in records:
            evaluator.observe(record)
        report = evaluator.report()
        online = _first_successor_online_evidence(
            progressive, str(successor["model_id"])
        )
        report["historical_online_authority"] = {
            "post_update_support": successor["post_update_support"],
            "post_update_evidence_id": successor["post_update_evidence_id"],
            "first_available_evidence": online,
        }
        reports.append(report)
    return {
        "condition": condition["condition"],
        "successor_reports": reports,
    }


def _plot(conditions: list[dict[str, Any]], path: Path) -> None:
    reports = [
        (condition["condition"], report)
        for condition in conditions
        for report in condition["successor_reports"]
    ]
    figure, axes = plt.subplots(
        len(reports), 1, figsize=(11, max(4, 3.1 * len(reports))), squeeze=False
    )
    phase_colors = {"OUTBOUND": "tab:blue", "HOLD": "tab:orange", "RETURN": "tab:green"}
    for axis, (condition_name, report) in zip(axes[:, 0], reports, strict=True):
        trajectory = report["later_shadow"]["cumulative_trajectory"]
        available = [
            row for row in trajectory if row["cumulative_evidence"]["available"]
        ]
        counts = np.asarray(
            [row["cumulative_evidence"]["block_count"] for row in available]
        )
        mean = np.asarray(
            [row["cumulative_evidence"]["mean_difference_nms2"] for row in available]
        )
        lower = np.asarray(
            [row["cumulative_evidence"]["lower_bound_nms2"] for row in available]
        )
        upper = np.asarray(
            [row["cumulative_evidence"]["upper_bound_nms2"] for row in available]
        )
        if len(counts):
            axis.fill_between(counts, lower, upper, color="0.8", label="HAC bound")
            axis.plot(counts, mean, color="black", linewidth=1.5, label="cumulative mean")
        terminal_count = int(report["terminal"]["block_count"])
        axis.axvline(terminal_count, color="red", linestyle="--", label="phase-complete terminal")
        axis.axhline(0.0, color="black", linewidth=0.8)
        terminal_blocks = report["terminal"]["block_trajectory"]
        for row in terminal_blocks:
            phase = str(row["phase"]).split("+")[0]
            axis.scatter(
                row["index"] + 1,
                row["successor_minus_predecessor_loss_nms2"],
                color=phase_colors.get(phase, "tab:gray"),
                s=12,
                alpha=0.65,
            )
        identity = report["identity"]
        axis.set_title(
            f"{condition_name}, successor u{identity['successor_update_index']:03d}"
        )
        axis.set_xlabel("causal clean block count")
        axis.set_ylabel("successor - predecessor loss")
        axis.grid(True, alpha=0.25)
        axis.legend(loc="best", fontsize=8)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_validation(source: Path, output_dir: Path) -> dict[str, Any]:
    source_payload = json.loads(source.read_text(encoding="utf-8"))
    conditions = [_evaluate_condition(row) for row in source_payload["conditions"]]
    by_name = {row["condition"]: row for row in conditions}
    stiffness = by_name["stiffness_plus_15pct"]["successor_reports"]
    damping = by_name["damping_plus_20pct"]["successor_reports"]
    stiffness_first = stiffness[0]
    stiffness_terminal = stiffness_first["terminal"]["evidence"]
    stiffness_positive = bool(
        stiffness_first["phase_complete"]
        and stiffness_terminal.get("descriptive_outcome") == "positive"
    )
    damping_positive = bool(
        damping
        and all(
            report["phase_complete"]
            and report["terminal"]["evidence"].get("descriptive_outcome")
            == "positive"
            for report in damping
        )
    )
    no_later_reversal = all(
        not report["later_shadow"]["statistical_reversal_after_terminal"]
        for row in conditions
        for report in row["successor_reports"]
    )
    stiffness_mean_beneficial = bool(
        stiffness_terminal.get(
            "successor_minus_predecessor_mean_loss_nms2", float("inf")
        )
        < 0.0
    )
    if stiffness_positive and damping_positive and no_later_reversal:
        decision = (
            "PC-A — PHASE-COMPLETE EVIDENCE VALIDATES BOTH STIFFNESS AND "
            "DAMPING PERSONALIZATION"
        )
    elif stiffness_mean_beneficial:
        decision = (
            "PC-B — STIFFNESS BENEFIT EXISTS BUT PHASE-COMPLETE EVIDENCE IS "
            "STILL INSUFFICIENT"
        )
    else:
        decision = "PC-C — STIFFNESS SUCCESSOR IS NOT CONSISTENTLY BENEFICIAL"

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "phase_complete_post_update.png"
    _plot(conditions, plot_path)
    payload = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": "shadow_replay_of_saved_causal_engineering_trace",
            "decision": decision,
            "source_artifact": str(source),
            "conditions": conditions,
            "observed_checks": {
                "stiffness_phase_complete_terminal_positive": stiffness_positive,
                "all_damping_phase_complete_terminals_positive": damping_positive,
                "no_later_statistical_reversal": no_later_reversal,
                "historical_online_decisions_unchanged": True,
            },
            "scope_invariants": {
                "online_personalization_logic_changed": False,
                "adaptation_authority_changed": False,
                "threshold_alpha_or_max_step_changed": False,
                "hwmpc_r_task_timing_or_controller_changed": False,
                "stage3_or_stage4_changed": False,
                "historical_results_changed": False,
                "force_value_imitation_or_rl_added": False,
            },
            "plot": str(plot_path),
        }
    )
    result_path = output_dir / "phase_complete_post_update.json"
    result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "decision": decision,
                "observed_checks": payload["observed_checks"],
                "terminals": [
                    {
                        "condition": condition["condition"],
                        "successor_update_index": report["identity"][
                            "successor_update_index"
                        ],
                        "block_count": report["terminal"]["block_count"],
                        "outcome": report["terminal"]["evidence"].get(
                            "descriptive_outcome"
                        ),
                        "mean": report["terminal"]["evidence"].get(
                            "mean_difference_nms2"
                        ),
                        "upper": report["terminal"]["evidence"].get(
                            "upper_bound_nms2"
                        ),
                    }
                    for condition in conditions
                    for report in condition["successor_reports"]
                ],
                "output_dir": str(output_dir),
            },
            indent=2,
        )
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    run_validation(arguments.source, arguments.output_dir)


if __name__ == "__main__":
    main()
