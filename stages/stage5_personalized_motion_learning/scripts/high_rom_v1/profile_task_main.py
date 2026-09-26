"""Opt-in first-200-TASK-poll cProfile; diagnostic overhead is not benchmark data."""
from __future__ import annotations

import cProfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stages/stage5_personalized_motion_learning"
sys.path.insert(0, str(STAGE / "src"))
sys.path.insert(0, str(ROOT / "stages/stage4_adaptive_control/src"))
sys.path.insert(0, str(ROOT / "stages/stage3_full3d/src"))

from traction_mpc_stage5.full3d_adaptive_integration_v1.wall_physics import WallPhysicsSession
import run_dev_case

profiler = cProfile.Profile()
state = {"started": False, "finished": False, "task_polls": 0}
original_set_phase = WallPhysicsSession.set_phase
original_boundary = WallPhysicsSession.boundary
original_release = WallPhysicsSession.release_runtime_maintenance
profile_path = STAGE / "docs/high_rom_runtime_v1/TASK_MAIN_200_POLLS.pstats"


def finish():
    if state["started"] and not state["finished"]:
        profiler.disable()
        profiler.dump_stats(str(profile_path))
        state["finished"] = True


def set_phase(self, name, limit_s):
    value = original_set_phase(self, name, limit_s)
    if name == "TASK" and not state["started"]:
        state["started"] = True
        profiler.enable()
    return value


def boundary(self):
    value = original_boundary(self)
    if state["started"] and not state["finished"]:
        state["task_polls"] += 1
        if state["task_polls"] >= 200:
            finish()
    return value


def release(self):
    finish()
    return original_release(self)


WallPhysicsSession.set_phase = set_phase
WallPhysicsSession.boundary = boundary
WallPhysicsSession.release_runtime_maintenance = release

if __name__ == "__main__":
    try:
        run_dev_case.main()
    finally:
        finish()
        print(f"profiled TASK polls: {state['task_polls']}; profile: {profile_path}", flush=True)
