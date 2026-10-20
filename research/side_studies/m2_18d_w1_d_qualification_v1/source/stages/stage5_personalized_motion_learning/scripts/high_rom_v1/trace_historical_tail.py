"""Bounded, evaluation-only event trace of the retained slow planner snapshot."""
from __future__ import annotations

from collections import defaultdict
import gc
import hashlib
import json
from pathlib import Path
import pickle
import sys
from time import perf_counter_ns, process_time_ns

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
for relative in ("stages/stage5_personalized_motion_learning/src",
                 "stages/stage4_adaptive_control/src", "stages/stage3_full3d/src"):
    sys.path.insert(0, str(ROOT / relative))
from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedulerV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import (
    CombinedRigidTableClearanceV1, _quintic_sample_powers)

SNAP = STAGE / "results/high_rom_runtime_v1/snapshots_historical_4s/task_00_outbound.pickle"
OUT = STAGE / "docs/high_rom_runtime_v1/HISTORICAL_TAIL_EVENT_TRACE.json"


def main():
    payload = SNAP.read_bytes()
    original_continuous = QuinticHumanWaypointSchedulerV1._continuous_clearance_is_valid
    original_certificate = CombinedRigidTableClearanceV1.certified_minimum
    observations = []
    current = {"label": None}

    def continuous(self, coefficients, duration_s, candidate):
        current["label"] = candidate.label
        try:
            return original_continuous(self, coefficients, duration_s, candidate)
        finally:
            current["label"] = None

    def certificate(self, coefficients, duration_s):
        start = perf_counter_ns()
        lower = original_certificate(self, coefficients, duration_s)
        observations.append((current["label"], duration_s,
                             (perf_counter_ns() - start) / 1e6, lower))
        return lower

    QuinticHumanWaypointSchedulerV1._continuous_clearance_is_valid = continuous
    CombinedRigidTableClearanceV1.certified_minimum = certificate
    rows = []
    try:
        for repetition in (1, 2):
            observations.clear()
            gc_events = []
            def callback(phase, info):
                gc_events.append({"phase": phase, "generation": info.get("generation"),
                                  "time_ns": perf_counter_ns()})
            gc.callbacks.append(callback)
            before_cache = _quintic_sample_powers.cache_info()
            wall_start, cpu_start = perf_counter_ns(), process_time_ns()
            planner, arguments = pickle.loads(payload)
            unpickle_ms = (perf_counter_ns() - wall_start) / 1e6
            decision = planner.decide(**arguments)
            wall_ms = (perf_counter_ns() - wall_start) / 1e6
            cpu_ms = (process_time_ns() - cpu_start) / 1e6
            gc.callbacks.remove(callback)
            labels = defaultdict(list)
            for label, duration, ms, lower in observations:
                labels[str(label)].append((duration, ms, lower))
            rows.append({"repetition": repetition, "wall_ms": wall_ms,
                         "cpu_ms": cpu_ms, "unpickle_ms": unpickle_ms,
                         "gc_events": gc_events,
                         "certificate_calls": len(observations),
                         "certificate_wall_ms_sum": sum(x[2] for x in observations),
                         "certificate_by_label": {
                             label: {"count": len(vals), "wall_ms_sum": sum(x[1] for x in vals),
                                     "first_duration_s": vals[0][0],
                                     "last_duration_s": vals[-1][0],
                                     "minimum_lower_m": min(x[2] for x in vals),
                                     "maximum_lower_m": max(x[2] for x in vals)}
                             for label, vals in labels.items()},
                         "grid_cache_before": str(before_cache),
                         "grid_cache_after": str(_quintic_sample_powers.cache_info()),
                         "chosen_label": decision.record()["executed_label"]})
            print(repetition, round(wall_ms, 1), round(cpu_ms, 1),
                  len(observations), len(gc_events), flush=True)
    finally:
        QuinticHumanWaypointSchedulerV1._continuous_clearance_is_valid = original_continuous
        CombinedRigidTableClearanceV1.certified_minimum = original_certificate
    OUT.write_text(json.dumps({"schema": "high_rom_historical_tail_event_trace_v1",
                               "snapshot_sha256": hashlib.sha256(payload).hexdigest(),
                               "category": "development_diagnostic_not_runtime_benchmark",
                               "rows": rows}, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
