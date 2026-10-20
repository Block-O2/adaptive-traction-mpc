"""Read-only descriptive control timing from the frozen ABBA audit."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
RAW = STAGE / "results/high_rom_runtime_v1/paired_root_cause"
OUT = STAGE / "docs/high_rom_runtime_v1/PAIRED_ROOT_CAUSE_TIMING.json"


def stats(values):
    if not values:
        return {"count": 0, "mean": None, "p95": None, "max": None}
    a = np.asarray(values, dtype=float)
    return {"count": len(a), "mean": float(a.mean()),
            "p95": float(np.percentile(a, 95)), "max": float(a.max())}


def stage_at(t, phases):
    for row in phases:
        if row["start_physics_s"] - 1e-9 <= t <= row["end_physics_s"] + 1e-9:
            return row["phase"]
    return "UNATTRIBUTED"


def read_run(path):
    summary = json.loads((path / "summary.json").read_text())
    wall = json.loads((path / "runtime_artifacts.json").read_text())["wall_physics"]
    phases = wall["phase_boundaries"]
    stage = defaultdict(lambda: defaultdict(list))
    events = wall["catchup_intervals"]
    polls = [x for x in events if x["reason"] == "control_poll"]
    last_grid = -1
    longest = (0, None)
    for i, event in enumerate(polls):
        name = stage_at(event["end_physics_s"], phases)
        grid = round((event["end_physics_s"] - wall["origin_physics_s"])
                     / wall["native_dt_s"]) // 20
        miss = max(0, grid - last_grid - 1)
        if miss > longest[0]:
            longest = (miss, event["end_physics_s"])
        stage[name]["missed_grids"].append(miss)
        stage[name]["control_poll_catchup_ms"].append(
            (event["host_end_ns"] - event["host_start_ns"]) / 1e6)
        if i + 1 < len(polls):
            stage[name]["poll_to_next_poll_ms"].append(
                (polls[i+1]["host_start_ns"] - event["host_start_ns"]) / 1e6)
        last_grid = grid
    next_tick = [None] * len(events)
    upcoming = None
    for i in range(len(events) - 1, -1, -1):
        next_tick[i] = upcoming
        if events[i]["reason"] == "next_control_tick":
            upcoming = events[i]
    for i, event in enumerate(events):
        if event["reason"] != "control_poll":
            continue
        name = stage_at(event["end_physics_s"], phases)
        later = next_tick[i]
        if later is not None:
            stage[name]["poll_end_to_next_tick_start_ms"].append(
                (later["host_start_ns"] - event["host_end_ns"]) / 1e6)
    for event in events:
        if event["reason"] == "next_control_tick":
            name = stage_at(event["end_physics_s"], phases)
            stage[name]["next_tick_catchup_ms"].append(
                (event["host_end_ns"] - event["host_start_ns"]) / 1e6)
    for sample in wall["sensor_samples"]:
        name = stage_at(sample["sample_time_s"], phases)
        stage[name]["sample_materialization_age_ms"].append(
            (sample["host_materialized_ns"] - sample["source_capture_ns"]) / 1e6)
    for native in wall["native_states_evaluation_only"]:
        name = stage_at(native["time_s"], phases)
        stage[name]["native_step_record_ms"].append(
            (native["host_step_finish_ns"] - native["host_step_start_ns"]) / 1e6)
    stage_out = {}
    for name, values in stage.items():
        stage_out[name] = {key: stats(value) for key, value in values.items()}
        stage_out[name]["miss_count"] = sum(values["missed_grids"])
        bounds = next((x for x in phases if x["phase"] == name), None)
        grids = round((bounds["end_physics_s"]-bounds["start_physics_s"])/.005) if bounds else None
        stage_out[name]["physical_grid_count"] = grids
        stage_out[name]["miss_ratio"] = (stage_out[name]["miss_count"] / grids if grids else None)
    requests = summary["timing"]["requests"]
    components = ("acquisition_to_request_ms", "snapshot_ms", "queue_ms",
                  "queue_and_snapshot_ms", "worker_to_main_scheduling_ms", "compute_ms",
                  "validation_scheduling_ms", "validation_and_command_construction_ms",
                  "activation_age_ms")
    request_times = {key: stats([float(x[key]) for x in requests if x.get(key) is not None])
                     for key in components}
    return {"case": path.name, "status": summary["status"],
            "control_cycle_misses": wall["control_cycle_misses"],
            "control_grids": round(wall["physics_elapsed_s"] / .005),
            "control_miss_ratio": wall["control_cycle_misses"] / round(wall["physics_elapsed_s"] / .005),
            "longest_consecutive_misses": longest[0],
            "longest_miss_duration_ms": longest[0] * 5.,
            "longest_miss_end_physics_s": longest[1],
            "maximum_backlog_ms": wall["maximum_backlog_s"] * 1000.,
            "gc_events_during_epoch": len(wall["gc_events"]),
            "gc_deferred_during_epoch": wall["gc_deferred_during_finite_active_session"],
            "io_during_epoch_observed": None,
            "lock_wait_during_epoch_observed": None,
            "planner_worker_backend": summary["timing"].get("classification"),
            "request_outcomes": dict(Counter(x["outcome"] for x in requests)),
            "request_timing": request_times, "stage_timing": stage_out,
            "elapsed_host_s": json.loads((path / "HIGH_ROM_CASE_RESULT.json").read_text())["elapsed_host_s"]}


def main():
    names = ([f"high120_{i:02d}_{kind}" for i, kind in enumerate(
        ("baseline", "candidate", "candidate", "baseline"), 1)] +
        [f"low_{i:02d}_{kind}" for i, kind in enumerate(
        ("baseline", "candidate", "candidate", "baseline"), 1)])
    rows = [read_run(RAW/name) for name in names]
    result = {"schema": "high_rom_runtime_paired_root_cause_timing_v1",
              "order": names, "rows": rows,
              "definitions": {
                  "longest_miss_duration_ms": "consecutive missed 5ms grids times 5; not a separately measured actuator outage",
                  "native_step_record_ms": "plant step plus native evidence record through host_step_finish; excludes later safety monitor and 5ms capture",
                  "poll_end_to_next_tick_start_ms": "main-loop wall gap containing task/reference/control/safety/log work and possible OS pauses; not isolated CPU cost",
                  "poll_to_next_poll_ms": "wall interval including main work, catchup, sleep and scheduling",
                  "sample_materialization_age_ms": "host materialization minus scheduled source capture",
                  "io_lock_limit": "active-epoch I/O and lock durations are not directly instrumented; request queue/wait and GC callbacks are observed"}}
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    for row in rows:
        print(row["case"], round(row["control_miss_ratio"], 4),
              row["longest_consecutive_misses"],
              {k: round(v["miss_ratio"], 3) for k,v in row["stage_timing"].items()})


if __name__ == "__main__":
    main()
