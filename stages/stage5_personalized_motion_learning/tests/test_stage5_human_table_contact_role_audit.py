from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/audit_stage5_human_table_contact_role.py"
)
SPEC = importlib.util.spec_from_file_location("contact_role_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_registered_start_goal_path_is_contact_free() -> None:
    result = MODULE._registered_path_check()
    assert result["contact_free"]
    assert result["start_clearance_mm"] > 0.0
    assert result["goal_clearance_mm"] > result["start_clearance_mm"]
    assert np.isclose(
        result["minimum_clearance_mm"], result["start_clearance_mm"]
    )


def test_shank_clearance_accepts_scalar_and_batch() -> None:
    start = np.asarray(
        MODULE.PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad
    )
    scalar = MODULE.shank_clearance_m(start)
    batch = MODULE.shank_clearance_m(np.vstack([start, start]))
    assert np.asarray(scalar).shape == ()
    assert batch.shape == (2,)
    assert np.allclose(batch, scalar)


def test_interval_extraction_keeps_disjoint_contact_windows() -> None:
    time = 0.005 * np.arange(7)
    intervals = MODULE._intervals(
        time, np.asarray([False, True, True, False, True, False, False])
    )
    assert len(intervals) == 2
    assert intervals[0]["onset_s"] == 0.005
    assert intervals[0]["sample_count"] == 2
    assert intervals[1]["onset_s"] == 0.020
