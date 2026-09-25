"""Frozen-gate analysis and trace plots for preserved DEV-C matched branches."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


GATES = {"human_action_nm": 1.30, "desired_force_n": 2.69,
         "desired_moment_nm": 0.58, "robot_torque_nm": 2.06}


def _vec(record: dict, name: str) -> np.ndarray:
    if name == "human_action_nm":
        return np.asarray(record["generalized_action_nm"], dtype=float)
    if name == "desired_force_n":
        return np.asarray(record["force_total_n"], dtype=float)
    if name == "desired_moment_nm":
        return np.asarray(record["moment_total_nm"], dtype=float)
    return np.asarray(record["robot_torque_nm"], dtype=float)


def _previous(preactivation: dict, name: str) -> np.ndarray:
    if name == "desired_force_n":
        return np.asarray(preactivation["allocated_wrench_world"][:3], dtype=float)
    if name == "desired_moment_nm":
        return np.asarray(preactivation["allocated_wrench_world"][3:], dtype=float)
    key = {"human_action_nm": "generalized_action_nm",
           # The prior row's robot_tau_nm is the command *before* that
           # interval; applied_robot_tau_nm is the actual last command at the
           # matched checkpoint boundary.
           "robot_torque_nm": "applied_robot_tau_nm"}[name]
    return np.asarray(preactivation[key], dtype=float)


def _read_branch(path: Path) -> dict:
    trace = json.loads(path.read_text(encoding="utf-8"))
    predecessor = json.loads((Path(trace["checkpoint"]) / "preactivation_trace.json").read_text(encoding="utf-8"))
    if not trace["records"] or not predecessor:
        raise ValueError(f"incomplete trace {path}")
    prior = predecessor[-1]
    metrics = {}
    for name in GATES:
        vectors = np.stack([_previous(prior, name)]
                           + [_vec(row, name) for row in trace["records"]])
        steps = np.linalg.norm(np.diff(vectors, axis=0), axis=1)
        metrics[name] = {"first_step": float(steps[0]),
                         "max_step": float(np.max(steps)),
                         "max_step_index": int(np.argmax(steps)),
                         "frozen_gate": GATES[name],
                         "gate_pass": bool(np.max(steps) <= GATES[name])}
    physics = trace["physics"]
    early = [row for row in physics if row["time_s"] <= physics[0]["time_s"] + .2000001]
    def peak(rows: list[dict], key: str, first: int | None = None,
             componentwise: bool = False) -> float:
        values = [np.asarray(row[key], dtype=float) for row in rows]
        if first is not None:
            values = [value[:first] for value in values]
        return float(max(np.max(np.abs(value)) if componentwise else np.linalg.norm(value)
                         for value in values))
    metrics["physical"] = {
        "early_200ms_human_acceleration_component_peak_rad_s2": peak(
            early, "ddq_true_rad_s2", componentwise=True),
        "early_200ms_cuff_force_peak_n": peak(early, "human_cuff_wrench_world", 3),
        "full_trace_bed_normal_load_peak_n": max(float(row["bed_normal_load_n"]) for row in physics),
        "full_trace_min_true_clearance_m": min(float(row["true_shank_clearance_m"]) for row in physics),
        "physics_boundaries": len(physics),
    }
    metrics["events"] = trace["model_transfer_events"]
    metrics["fully_realized_version"] = trace["last_fully_realized_version"]
    metrics["abort_reason"] = trace["abort_reason"]
    metrics["direct_dev_b_first_40_max_command_difference_nm"] = trace.get(
        "dev_b_direct_command_max_difference_nm")
    return {"trace": trace, "metrics": metrics}


def _plot(case: str, direct: dict, repaired: dict, path: Path) -> None:
    fig, axes = plt.subplots(6, 1, figsize=(11, 15), sharex=True)
    for label, result, color in (("direct", direct, "#b23a48"),
                                 ("DEV-C", repaired, "#207e8c")):
        rows = result["trace"]["records"]
        origin = float(rows[0]["time_s"])
        x = np.asarray([float(row["time_s"]) - origin for row in rows])
        for ax, key, title in zip(axes[:4],
                                  ("generalized_action_nm", "force_total_n",
                                   "moment_total_nm", "robot_torque_nm"),
                                  ("Human desired action (Nm)", "desired cuff force (N)",
                                   "desired cuff moment (Nm)", "CR12 torque command (Nm)")):
            y = np.asarray([np.linalg.norm(row[key]) for row in rows])
            ax.plot(x, y, label=label, color=color, linewidth=1.5)
            ax.set_ylabel(title)
        phys = result["trace"]["physics"]
        xp = np.asarray([float(row["time_s"]) - origin for row in phys])
        yp = np.asarray([np.linalg.norm(row["ddq_true_rad_s2"]) for row in phys])
        axes[4].plot(xp, yp, label=label, color=color, linewidth=1)
        axes[4].set_ylabel("Human |qdd| (rad/s²)")
        if label == "DEV-C":
            axes[5].plot(x, [row["transfer"]["fraction_new"] for row in rows],
                         color=color, label="new-model fraction")
    axes[5].set_ylabel("new model fraction")
    axes[5].set_xlabel("seconds after matched activation")
    for ax in axes:
        ax.grid(alpha=.2)
        ax.legend(loc="best")
    fig.suptitle(f"DEV-C matched physical branch: {case} (development evidence)")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--repaired-set", default="matched_v2")
    args = parser.parse_args()
    root = args.results
    rows = {}
    for case_dir in sorted((root / args.repaired_set).iterdir()):
        if not case_dir.is_dir():
            continue
        case = case_dir.name
        direct = _read_branch(root / "matched_v1" / case / "direct" / "matched_trace.json")
        repaired = _read_branch(case_dir / "bumpless" / "matched_trace.json")
        plots = root / f"plots_{args.repaired_set}_with_moment"
        plots.mkdir(parents=True, exist_ok=True)
        _plot(case, direct, repaired, plots / f"{case}.png")
        rows[case] = {"direct": direct["metrics"], "dev_c": repaired["metrics"],
                      "dev_c_all_frozen_continuity_gates_pass": all(
                          repaired["metrics"][key]["gate_pass"] for key in GATES)}
    (root / f"matched_summary_{args.repaired_set}_with_moment.json").write_text(json.dumps({
        "schema": "dev_c_matched_analysis_v1",
        "repaired_set": args.repaired_set,
        "evidence_category": "matched_state_development_diagnostic",
        "frozen_5ms_gates": GATES,
        "case_rows": rows,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: {"gates_pass": value["dev_c_all_frozen_continuity_gates_pass"],
                             "max_robot_step_nm": value["dev_c"]["robot_torque_nm"]["max_step"]}
                      for key, value in rows.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
