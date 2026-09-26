"""Opt-in descriptive timing wrappers; never used as runtime gate evidence."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import sys
from time import perf_counter_ns

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
for relative in ("stages/stage5_personalized_motion_learning/src",
                 "stages/stage4_adaptive_control/src", "stages/stage3_full3d/src"):
    sys.path.insert(0, str(ROOT / relative))
import run_dev_case
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime
from traction_mpc_stage5.full3d_adaptive_integration_v1.wall_physics import WallPhysicsSession
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointMPCShadowContractV1
from traction_mpc_stage5.loaded_supervisor import Stage5LoadedTrackBrakeSupervisor

records = defaultdict(list)
last = {"boundary_end_ns": None, "execute_end_ns": None}


def add(name, started, phase):
    records[f"{phase}/{name}"].append((perf_counter_ns() - started) / 1e6)


orig_capture = WallPhysicsSession.capture
def capture(self, *args, **kwargs):
    t = perf_counter_ns()
    try:
        return orig_capture(self, *args, **kwargs)
    finally:
        add("measurement_state_capture_ms", t, self.phase_records[-1]["phase"])
WallPhysicsSession.capture = capture

orig_boundary = runtime._capture_boundary
def boundary(context):
    phase = context["wall_session"].phase_records[-1]["phase"]
    t = perf_counter_ns()
    if last["execute_end_ns"] is not None:
        records[f"{phase}/execute_end_to_boundary_start_ms"].append(
            (t - last["execute_end_ns"]) / 1e6)
        last["execute_end_ns"] = None
    value = orig_boundary(context)
    add("boundary_total_ms", t, phase)
    last["boundary_end_ns"] = perf_counter_ns()
    return value
runtime._capture_boundary = boundary

orig_execute = runtime._execute_interval
def execute(context, *args, **kwargs):
    phase = context["wall_session"].phase_records[-1]["phase"]
    t = perf_counter_ns()
    if last["boundary_end_ns"] is not None:
        records[f"{phase}/boundary_end_to_execute_start_ms"].append(
            (t - last["boundary_end_ns"]) / 1e6)
        last["boundary_end_ns"] = None
    try:
        return orig_execute(context, *args, **kwargs)
    finally:
        add("execute_total_including_next_tick_ms", t, phase)
        last["execute_end_ns"] = perf_counter_ns()
runtime._execute_interval = execute

orig_tick = WallPhysicsSession.next_control_tick
def tick(self):
    t = perf_counter_ns()
    try:
        return orig_tick(self)
    finally:
        add("next_tick_physics_wait_ms", t, self.phase_records[-1]["phase"])
WallPhysicsSession.next_control_tick = tick

orig_command = HumanWaypointMPCShadowContractV1.command
def command(self, *args, **kwargs):
    t = perf_counter_ns()
    try:
        return orig_command(self, *args, **kwargs)
    finally:
        add("low_level_contract_command_ms", t, "TASK_OR_OTHER")
HumanWaypointMPCShadowContractV1.command = command

orig_supervisor = Stage5LoadedTrackBrakeSupervisor.command
def supervisor(self, *args, **kwargs):
    t = perf_counter_ns()
    try:
        return orig_supervisor(self, *args, **kwargs)
    finally:
        add("supervisor_safety_ms", t, "TASK_OR_OTHER")
Stage5LoadedTrackBrakeSupervisor.command = supervisor


def stats(values):
    a = np.asarray(values, dtype=float)
    return {"count": len(a), "mean": float(np.mean(a)),
            "p95": float(np.percentile(a, 95)), "max": float(np.max(a))}


if __name__ == "__main__":
    try:
        run_dev_case.main()
    finally:
        output = STAGE / "docs/high_rom_runtime_v1/CONTROL_STAGE_INSTRUMENTED.json"
        result = {"schema": "high_rom_control_stage_descriptive_instrumentation_v1",
                  "warning": "in-memory wrappers add overhead; not a frozen runtime benchmark",
                  "metrics": {key: stats(value) for key, value in records.items() if value}}
        output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(f"descriptive stage timing: {output}", flush=True)
