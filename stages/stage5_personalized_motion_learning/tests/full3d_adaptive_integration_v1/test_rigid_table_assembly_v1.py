"""Focused generation/evaluation checks for the new rigid-table contract."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from traction_mpc_stage5.rigid_table_assembly_v1 import (
    MIN_PROXIMAL_GAP_M, assess_assembly, repaired_counterpart,
)


STAGE = Path(__file__).resolve().parents[2]
OLD_CASES = STAGE / "results/full3d_adaptive_integration_v1/fresh_qualification_v1/formal_case_bundle_v1/cases"


def _case(key: str) -> dict:
    return json.loads((OLD_CASES / f"{key}.json").read_text(encoding="utf-8"))


def test_negative_fixed_overlap_caught_before_robot_initialization():
    case = _case("balanced_near_upper_current_rom_r01")
    result = assess_assembly(case)
    assert result["category"] == "INVALID_FIXED_GEOMETRY"
    assert result["proximal_gap_m"] < -0.004
    assert "initial" not in result


def test_repair_changes_only_illegal_hip_height_and_preserves_hidden_patient():
    original = _case("balanced_near_upper_current_rom_r01")
    repaired, record = repaired_counterpart(original)
    assert record["rule"] == "reflect_illegal_downward_installation"
    assert record["new_proximal_gap_m"] == pytest.approx(-record["old_proximal_gap_m"])
    expected = deepcopy(original)
    expected["physical"]["hip_translation_xz_m"][1] = repaired["physical"]["hip_translation_xz_m"][1]
    assert repaired == expected
    assert original["physical"]["hip_translation_xz_m"][1] < 0


def test_valid_old_assembly_remains_identical():
    case = _case("balanced_ordinary_r01")
    revised, record = repaired_counterpart(case)
    assert record["rule"] == "unchanged_legal_placement"
    assert revised == case


def test_nominal_tangency_receives_minimal_positive_gap():
    case = _case("balanced_ordinary_r01")
    case["physical"]["hip_translation_xz_m"][1] = 0.0
    revised, record = repaired_counterpart(case)
    assert record["new_proximal_gap_m"] == pytest.approx(MIN_PROXIMAL_GAP_M)
    assert assess_assembly(revised, verify_robot=False)["valid"]
