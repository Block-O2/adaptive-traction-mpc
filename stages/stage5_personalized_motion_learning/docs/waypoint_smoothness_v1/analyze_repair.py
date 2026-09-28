"""Development comparison of frozen C08 and one saved pass-through rollout.

Reads saved 5 ms trace and plan ledgers only. No controller execution.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
BASE = Path("/Users/hankli/Desktop/coding/adaptive-traction-mpc-high-rom-runtime-v1/stages/stage5_personalized_motion_learning/results/high_rom_runtime_v1/candidate08_final26/high_rom_matrix_nominal_sync_v1")
NEW = STAGE / "results/motion_smoothness_v1/local_case_06_high_120_lead45"
OUT = Path(__file__).resolve().parent


def intervals(mask, t):
    edges = np.flatnonzero(np.diff(np.r_[False, mask, False]))
    return [{"start_s": float(t[i]), "end_s": float(t[j-1]),
             "duration_s": float(t[j-1]-t[i]+np.median(np.diff(t)))}
            for i, j in edges.reshape(-1, 2) if j-i >= 2]


def inspect(path):
    a = np.load(path / "trace.npz")
    s = json.loads((path / "summary.json").read_text())
    k = np.flatnonzero(a["stage"] == "TASK")
    t = a["time_s"][k]
    phase = a["task_phase"][k].astype(str)
    dqref = np.degrees(a["reference_dq_rad_s"][k])
    dqhuman = np.degrees(a["evaluation_only_human_state_rad_rad_s"][k, 2:])
    dqrobot = np.degrees(a["cr12_dq_rad_s"][k])
    force = a["physical_cuff_force_world_n"][k]
    decisions = [d for d in s["decisions"] if d["plan_activated"]]
    switches = [float(d["activation_timestamp_s"]) for d in decisions]
    # The last activated OUTBOUND and RETURN schedules are terminal braking.
    # Exclude only their active windows; retain commissioning/task-start pause.
    terminal = np.zeros(len(t), dtype=bool)
    for name in ("OUTBOUND", "RETURN"):
        ds = [d for d in decisions if d["phase"] == name]
        if ds:
            terminal |= (phase == name) & (t >= float(ds[-1]["activation_timestamp_s"]))
    moving = np.isin(phase, ["OUTBOUND", "RETURN"])
    rs = np.max(np.abs(dqref), axis=1)
    hs = np.max(np.abs(dqhuman), axis=1)
    rv = np.max(np.abs(dqrobot), axis=1)
    reference_stops = intervals(moving & ~terminal & (rs < 1.), t)
    actual_stops = intervals(moving & ~terminal & (hs < 1.), t)
    jumps = [d["reference_boundary_continuity"] for d in decisions]
    max_jump = lambda key: float(max((np.max(np.abs(np.degrees(x[key]))) for x in jumps), default=0.))
    valleys = []
    for x in switches[1:]:
        window = (t >= x-.1) & (t <= x+.1)
        if np.any(window): valleys.append(float(np.min(rv[window])))
    target_speeds = []
    for d in decisions:
        e = next(e for e in d["evaluations"] if e["label"] == d["executed_label"])
        target_speeds.append({"phase": d["phase"], "activation_s": d["activation_timestamp_s"],
                              "target_dq_deg_s": np.degrees(e["schedule"]["target_dq_rad_s"]).tolist()})
    slew = np.linalg.norm(np.diff(force, axis=0), axis=1) / np.diff(t)
    metrics = {
        "path": str(path), "trace_sample_dt_s": float(np.median(np.diff(t))),
        "task_duration_s": float(t[-1]-t[0]), "plan_activations": len(decisions),
        "plan_switches_per_minute": float(max(0, len(decisions)-1)/(t[-1]-t[0])*60),
        "target_velocities": target_speeds,
        "near_stop_rule": "max absolute hip/knee velocity <1 deg/s on 5ms TASK samples, OUTBOUND/RETURN, excluding last activated schedule of each moving phase (terminal braking)",
        "non_task_reference_near_stop_intervals": reference_stops,
        "non_task_actual_near_stop_intervals": actual_stops,
        "non_task_reference_near_stop_longest_s": max((x["duration_s"] for x in reference_stops), default=0.),
        "non_task_actual_near_stop_longest_s": max((x["duration_s"] for x in actual_stops), default=0.),
        "exact_switch_max_q_jump_deg": max_jump("q_boundary_jump_rad"),
        "exact_switch_max_dq_jump_deg_s": max_jump("dq_boundary_jump_rad_s"),
        "exact_switch_max_ddq_jump_deg_s2": max_jump("ddq_boundary_jump_rad_s2"),
        "switch_robot_speed_valley_deg_s": {"min": min(valleys) if valleys else None,
                                             "median": float(np.median(valleys)) if valleys else None},
        "cuff_vector_force_slew_n_s_5ms": {"p95": float(np.percentile(slew, 95)),
                                             "max": float(np.max(slew))},
        "status": s["status"], "abort_reason": s["abort_reason"],
    }
    return metrics, (t-t[0], rs, hs, rv, np.linalg.norm(force, axis=1),
                     [x-t[0] for x in switches])


def main():
    old, old_series = inspect(BASE)
    new, new_series = inspect(NEW)
    fig, axs = plt.subplots(2, 2, figsize=(13, 8), sharex="row")
    for row, (title, series) in enumerate((("Frozen C08", old_series), ("Pass-through development candidate", new_series))):
        t, rs, hs, rv, fn, switches = series
        axs[row, 0].plot(t, rs, label="human reference speed")
        axs[row, 0].plot(t, hs, label="actual human speed", alpha=.8)
        axs[row, 0].axhline(1., color="black", linestyle=":", linewidth=.8)
        axs[row, 1].plot(t, rv, label="CR12 max joint speed", color="#2a628f")
        ax2 = axs[row, 1].twinx()
        ax2.plot(t, fn, color="#ae6830", alpha=.6, label="cuff resultant force")
        ax2.set_ylabel("force (N)")
        for ax in axs[row]:
            for x in switches: ax.axvline(x, color="gray", alpha=.2, linewidth=.7)
            ax.set_xlabel("task simulation time (s)")
            ax.set_title(title)
        axs[row, 0].set_ylabel("max |hip/knee dq| (deg/s)")
        axs[row, 1].set_ylabel("max |CR12 dq| (deg/s)")
        axs[row, 0].legend(loc="upper right", fontsize=8)
        axs[row, 1].legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    plot = OUT / "c08_vs_pass_through_speed_force.png"
    fig.savefig(plot, dpi=150)
    plt.close(fig)
    result = {"baseline": old, "candidate": new, "plot": str(plot)}
    (OUT / "SMOOTHNESS_COMPARISON.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps({"baseline_ref_s":old["non_task_reference_near_stop_longest_s"],
                      "candidate_ref_s":new["non_task_reference_near_stop_longest_s"],
                      "baseline_actual_s":old["non_task_actual_near_stop_longest_s"],
                      "candidate_actual_s":new["non_task_actual_near_stop_longest_s"],
                      "plot":str(plot)}, indent=2))


if __name__ == "__main__": main()
