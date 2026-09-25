#!/usr/bin/env python3
"""Audit the Stage-5 posture/interaction landscape from formal saved traces."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.posture_landscape import (
    build_supported_grid,
    concatenate_reference_samples,
    decide_landscape,
    load_deployable_trace,
    matched_local_row,
    representative_state_rows,
    summarize_matched_groups,
)


CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_posture_force_landscape_v1.json"
DEFAULT_OUTPUT = STAGE5_ROOT / "results" / "posture_force_landscape_v1_offline_audit"


def _load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != "stage5_posture_force_landscape_v1":
        raise ValueError("unexpected posture-landscape config schema")
    condition = config["frozen_condition"]
    if (
        float(condition["gamma"]) != 0.5
        or condition["interface"] != "fixed_nominal"
        or condition["human_model_updates_enabled"]
        or condition["trust_to_gamma_authority"]
        or condition["value_or_rl_control"]
    ):
        raise ValueError("posture-landscape frozen condition changed")
    return config


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty table: {path.name}")
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (list, dict))
                    else value
                    for key, value in row.items()
                }
            )


def _strict_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _strict_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return _strict_jsonable(value.tolist())
    if isinstance(value, np.generic):
        return _strict_jsonable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _trace_path(source_root: Path, artifact: str) -> Path:
    path = source_root / artifact
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _validate_trace_condition(
    trace: dict[str, np.ndarray], *, gamma: float, model_version: str
) -> bool:
    return bool(
        np.all(np.asarray(trace["progress_pacing_gamma"], dtype=float) == gamma)
        and np.all(
            np.asarray(trace["control_human_model_version"], dtype=str)
            == model_version
        )
    )


def _aggregate_representatives(
    rows: list[dict[str, Any]], specifications: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for spec in specifications:
        selected = [row for row in rows if row["state_name"] == spec["name"]]
        summary.append(
            {
                "state_name": spec["name"],
                "task_phase": selected[0]["task_phase"],
                "seed_count": len(selected),
                "mean_q_deg": np.mean([row["q_deg"] for row in selected], axis=0),
                "mean_dq_deg_s": np.mean(
                    [row["dq_deg_s"] for row in selected], axis=0
                ),
                "mean_force_norm_n": np.mean(
                    [row["measured_cuff_force_norm_n"] for row in selected]
                ),
                "force_seed_range_n": np.ptp(
                    [row["measured_cuff_force_norm_n"] for row in selected]
                ),
                "mean_moment_norm_nm": np.mean(
                    [row["measured_cuff_moment_norm_nm"] for row in selected]
                ),
                "mean_generalized_human_input_norm_nm": np.mean(
                    [
                        row["measured_generalized_human_input_norm_nm"]
                        for row in selected
                    ]
                ),
                "mean_support_norm_nm": np.mean(
                    [row["support_norm_nm"] for row in selected]
                ),
                "mean_motion_increment_norm_nm": np.mean(
                    [row["motion_increment_norm_nm"] for row in selected]
                ),
            }
        )
    return summary


def _grid_summary(grid: dict[str, np.ndarray]) -> dict[str, Any]:
    supported = np.isfinite(grid["force_norm_n"])
    summary: dict[str, Any] = {
        "supported_cell_count": int(np.count_nonzero(supported)),
        "total_cell_count": int(supported.size),
        "supported_fraction": float(np.mean(supported)),
        "maximum_samples_per_cell": int(np.max(grid["sample_count"])),
    }
    for name in (
        "force_norm_n",
        "moment_norm_nm",
        "generalized_input_norm_nm",
        "support_norm_nm",
        "motion_norm_nm",
    ):
        values = grid[name][supported]
        summary[name] = {
            "minimum": float(np.min(values)),
            "median": float(np.median(values)),
            "maximum": float(np.max(values)),
        }
    return summary


def _plot_grid(
    path: Path,
    grid: dict[str, np.ndarray],
    samples: dict[str, np.ndarray],
) -> None:
    panels = (
        ("force_norm_n", "Measured cuff force norm [N]"),
        ("moment_norm_nm", "Measured cuff moment norm [N m]"),
        ("generalized_input_norm_nm", "Generalized Human input norm [N m]"),
        ("support_norm_nm", "Support component norm [N m]"),
        ("motion_norm_nm", "Motion-related component norm [N m]"),
        ("sample_count", "High-level samples per cell"),
    )
    fig, axes = plt.subplots(2, 3, figsize=(15.0, 8.5), constrained_layout=True)
    q_deg = np.degrees(samples["q_rad"])
    for axis, (name, title) in zip(axes.flat, panels):
        values = np.asarray(grid[name], dtype=float)
        if name == "sample_count":
            values = np.where(np.isfinite(grid["force_norm_n"]), values, np.nan)
        mesh = axis.pcolormesh(
            grid["q1_edges_deg"],
            grid["q2_edges_deg"],
            values.T,
            shading="flat",
            cmap="viridis",
        )
        axis.plot(q_deg[:, 0], q_deg[:, 1], ".", color="white", alpha=0.12, ms=1)
        axis.set_title(title)
        axis.set_xlabel("q1 [deg]")
        axis.set_ylabel("q2 [deg]")
        fig.colorbar(mesh, ax=axis)
    fig.suptitle("Stage-5 deployable-only posture/interaction audit")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_local_branches(path: Path, rows: list[dict[str, Any]]) -> None:
    branch_order = ["hip_leading", "balanced", "knee_leading"]
    anchors = ["early_outbound", "mid_outbound", "mid_return"]
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.4), sharey=True, constrained_layout=True)
    for axis, anchor in zip(axes, anchors):
        for branch in branch_order:
            selected = [
                row
                for row in rows
                if row["anchor_name"] == anchor and row["branch"] == branch
            ]
            values = np.asarray([row["mean_measured_force_n"] for row in selected])
            x = branch_order.index(branch)
            axis.scatter(np.full(len(values), x), values, s=40, label=branch)
            axis.hlines(np.mean(values), x - 0.22, x + 0.22, linewidth=2)
        axis.set_title(anchor.replace("_", " "))
        axis.set_xticks(range(3), ["hip", "balanced", "knee"])
        axis.set_xlabel("0.20 s coordination branch")
        axis.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("Mean measured cuff force [N]")
    fig.suptitle("Matched local force under exactly equal duration")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run(config_path: Path, output: Path) -> dict[str, Any]:
    config = _load_config(config_path)
    source_result = STAGE5_ROOT / config["source"]["matched_branch_result"]
    source_root = source_result.parent
    source = json.loads(source_result.read_text(encoding="utf-8"))
    rows = source["rows"]
    condition = config["frozen_condition"]
    expected_count = int(config["source"]["required_rollouts"])
    expected_model = str(condition["human_model_version"])

    output.mkdir(parents=True, exist_ok=False)
    reference_traces: list[tuple[int, dict[str, np.ndarray]]] = []
    reference_condition_valid = True
    for reference in config["source"]["reference_map_rollouts"]:
        parts = reference.split("/")
        seed = int(parts[1].removeprefix("seed_"))
        trace = load_deployable_trace(source_root / reference / "trace.npz")
        reference_condition_valid &= _validate_trace_condition(
            trace, gamma=float(condition["gamma"]), model_version=expected_model
        )
        reference_traces.append((seed, trace))

    representative_rows = representative_state_rows(
        reference_traces,
        config["representative_states"],
        sample_period_s=float(config["source"]["sample_period_s"]),
    )
    representative_summary = _aggregate_representatives(
        representative_rows, config["representative_states"]
    )
    samples = concatenate_reference_samples(
        reference_traces,
        sample_period_s=float(config["source"]["sample_period_s"]),
    )
    q_deg = np.degrees(samples["q_rad"])
    map_config = config["map"]
    q1_edges = np.linspace(
        float(np.min(q_deg[:, 0])) - 1.0e-9,
        float(np.max(q_deg[:, 0])) + 1.0e-9,
        int(map_config["q1_bins"]) + 1,
    )
    q2_edges = np.linspace(
        float(np.min(q_deg[:, 1])) - 1.0e-9,
        float(np.max(q_deg[:, 1])) + 1.0e-9,
        int(map_config["q2_bins"]) + 1,
    )
    grid = build_supported_grid(
        samples,
        q1_edges_deg=q1_edges,
        q2_edges_deg=q2_edges,
        minimum_samples=int(map_config["minimum_samples_per_cell"]),
        minimum_unique_seeds=int(map_config["minimum_unique_seeds_per_cell"]),
    )

    matched_rows: list[dict[str, Any]] = []
    all_trace_conditions_valid = True
    for source_row in rows:
        trace = load_deployable_trace(
            _trace_path(source_root, source_row["complete_q1_q2_path"]["artifact"])
        )
        all_trace_conditions_valid &= _validate_trace_condition(
            trace, gamma=float(condition["gamma"]), model_version=expected_model
        )
        matched_rows.append(
            matched_local_row(
                trace,
                source_row,
                duration_s=float(config["matched_local_audit"]["duration_s"]),
                start_rad=np.radians([5.0, 10.0]),
                goal_rad=np.radians([20.0, 35.0]),
            )
        )
    group_summaries = summarize_matched_groups(
        matched_rows, branch_order=config["matched_local_audit"]["branches"]
    )

    source_valid = bool(
        len(rows) == expected_count
        and not source["execution_failures"]
        and all(row["fixed_condition_valid"] for row in rows)
        and all(row["truth_used_for_controller_or_branch_decision"] is False for row in rows)
        and all(row["task_complete"] and row["safety_valid"] for row in rows)
        and all(group["same_start_digest"] for group in group_summaries)
        and all(group["branch_count"] == 3 for group in group_summaries)
        and len(group_summaries) == int(config["matched_local_audit"]["groups"])
        and reference_condition_valid
        and all_trace_conditions_valid
        and np.count_nonzero(np.isfinite(grid["force_norm_n"])) > 0
    )
    rules = config["decision_rules"]
    decision = decide_landscape(
        group_summaries,
        validity=source_valid,
        meaningful_fraction=float(rules["meaningful_force_separation_fraction"]),
        flat_fraction=float(rules["essentially_flat_force_separation_fraction"]),
        repeat_count=int(
            rules["minimum_repetitions_with_same_low_force_branch_per_anchor"]
        ),
    )

    np.savez_compressed(output / "posture_landscape_grid.npz", **grid)
    _write_csv(output / "representative_states.csv", representative_rows)
    _write_csv(output / "representative_state_summary.csv", representative_summary)
    _write_csv(output / "matched_local_branches.csv", matched_rows)
    _write_csv(output / "matched_local_group_summary.csv", group_summaries)
    _plot_grid(output / "q1_q2_interaction_landscape.png", grid, samples)
    _plot_local_branches(output / "matched_local_force.png", matched_rows)

    result = {
        "schema": "stage5_posture_force_landscape_v1_results",
        "evidence_category": config["evidence_category"],
        "config": str(config_path.relative_to(STAGE5_ROOT)),
        "source_result": str(source_result.relative_to(STAGE5_ROOT)),
        "deployable_only_controller_side_quantities": True,
        "mujoco_truth_used_for_controller_or_branch_decision": False,
        "fixed_condition": condition,
        "validity": {
            "source_rollout_count": len(rows),
            "expected_rollout_count": expected_count,
            "source_execution_failure_count": len(source["execution_failures"]),
            "matched_group_count": len(group_summaries),
            "same_start_identity_all_groups": all(
                group["same_start_digest"] for group in group_summaries
            ),
            "reference_trace_condition_valid": reference_condition_valid,
            "all_trace_conditions_valid": all_trace_conditions_valid,
            "all_source_rollouts_complete_safe": all(
                row["task_complete"] and row["safety_valid"] for row in rows
            ),
            "validity_gate_passed": source_valid,
        },
        "representative_state_summary": representative_summary,
        "grid_summary": _grid_summary(grid),
        "matched_local_group_summary": group_summaries,
        "decision": decision,
        "stronger_matched_branch_study_run": False,
        "stronger_branch_reason": (
            "not run because the preregistered LF-A gate was not met"
            if decision["decision"] != "LF-A"
            else "LF-A met; a separately preregistered study is required"
        ),
        "value_model_trained": False,
        "value_or_rl_connected_to_control": False,
        "stage3_or_stage4_modified_by_this_audit": False,
        "artifacts": [
            "posture_force_landscape_results.json",
            "posture_landscape_grid.npz",
            "representative_states.csv",
            "representative_state_summary.csv",
            "matched_local_branches.csv",
            "matched_local_group_summary.csv",
            "q1_q2_interaction_landscape.png",
            "matched_local_force.png",
        ],
    }
    (output / "posture_force_landscape_results.json").write_text(
        json.dumps(_strict_jsonable(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.config.resolve(), args.output.resolve())
    decision = result["decision"]
    print(f"{decision['decision']} — {decision['decision_label']}")
    print(f"output={args.output.resolve()}")


if __name__ == "__main__":
    main()
