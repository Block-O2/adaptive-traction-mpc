from __future__ import annotations

import json
from pathlib import Path

import pytest

from validate_stage5_human_waypoint_r_support import (
    _geometry_scan,
    _widest_passing_segment,
)


CONFIG = Path(
    "stages/stage5_personalized_motion_learning/configs/"
    "stage5_human_waypoint_r_support_v1.json"
)


def test_geometry_scan_finds_balanced_component_without_added_margin() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    result = _geometry_scan(config)
    component = result["component_containing_balanced"]

    assert component["lower_r"] == pytest.approx(-0.27, abs=0.0011)
    assert component["upper_r"] == pytest.approx(1.0)
    assert component["lower_minimum_clearance_mm"] >= 0.0
    assert config["geometry_scan"]["feasibility_contract"].endswith(
        "no added margin"
    )


def test_widest_passing_segment_excludes_failed_boundary_points() -> None:
    cases = [
        {"coordination_preference_r": -0.27, "support_contract_passed": False},
        {"coordination_preference_r": -0.25, "support_contract_passed": False},
        {"coordination_preference_r": -0.245, "support_contract_passed": True},
        {"coordination_preference_r": 0.0, "support_contract_passed": True},
        {"coordination_preference_r": 1.0, "support_contract_passed": True},
    ]

    segment = _widest_passing_segment(cases, -0.27, 1.0)

    assert [case["coordination_preference_r"] for case in segment] == [
        -0.245,
        0.0,
        1.0,
    ]
