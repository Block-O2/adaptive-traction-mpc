"""Versioned High-ROM scenario entry: registered starts are never replaced."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant


CONFIG = Path(__file__).resolve().parents[2] / "configs/high_rom_v1"


@pytest.mark.parametrize("name,start", [
    ("high_rom_matrix_nominal_sync_v1", (5., 10.)),
    ("high_rom_function_fresh_01_v1", (6., 11.)),
    ("high_rom_function_fresh_02_v1", (8., 13.)),
])
def test_registered_start_reaches_task_and_commissioning(name, start):
    case = json.loads((CONFIG / f"{name}.json").read_text())
    _, _, spec, commissioning = hidden_plant(case)
    np.testing.assert_allclose(np.degrees(spec.start_return_target_rad), start)
    np.testing.assert_allclose(np.degrees(commissioning[[0, -1]]), [start, start])
    np.testing.assert_allclose(np.degrees(spec.outbound_goal_target_rad), [120., 120.])


@pytest.mark.parametrize("field,value", [
    ("start_deg", [126., 11.]),
    ("start_deg", [float("nan"), 11.]),
    ("start_deg", [5.]),
    ("start_deg", [-1., 10.]),
    ("commissioning_waypoints_deg", [[0., 0.]] * 5),
])
def test_invalid_registered_start_or_commissioning_rejected(field, value):
    case = json.loads((CONFIG / "high_rom_function_fresh_01_v1.json").read_text())
    case = copy.deepcopy(case)
    case["task"][field] = value
    with pytest.raises(ValueError):
        hidden_plant(case)
