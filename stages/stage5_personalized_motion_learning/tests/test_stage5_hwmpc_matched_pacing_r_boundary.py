import json

from traction_mpc_stage5.config import STAGE5_ROOT
from validate_stage5_hwmpc_matched_pacing_r_boundary import (
    _clean_cost_design,
    _coarse_bracket,
    refinement_grid,
)


CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_hwmpc_matched_pacing_r_boundary_v1.json"
DOMAIN_PATH = STAGE5_ROOT / "configs" / "stage5_hwmpc_matched_pacing_r_domain_v1.json"


def _case(r_value: float, valid: bool) -> dict:
    return {
        "coordination_r": r_value,
        "completed": valid,
        "matched_pacing_contract_passed": valid,
        "safety_contract_passed": valid,
    }


def test_boundary_config_preregisters_force_independent_two_level_grid() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["status"] == "PREREGISTERED_BEFORE_BOUNDARY_EXECUTION"
    assert config["older_free_pacing_support_interval"] == [-0.24, 0.55]
    assert config["search"]["lower_bound_reconfirmation"] == [-0.24]
    assert config["search"]["positive_coarse_grid"] == [
        0.4,
        0.425,
        0.45,
        0.475,
        0.5,
        0.525,
        0.55,
    ]
    assert config["search"]["refinement_step"] == 0.005
    assert config["search"]["boundary_total_repeat_count"] == 2
    assert config["search"]["classification_uses_force"] is False
    assert all(value is False for value in config["scope"].values())


def test_refinement_grid_and_coarse_bracket_are_deterministic() -> None:
    coarse = [
        _case(0.4, True),
        _case(0.425, False),
        _case(0.45, False),
        _case(0.475, False),
    ]

    lower, upper, nonmonotonic = _coarse_bracket(coarse)

    assert (lower, upper) == (0.4, 0.425)
    assert nonmonotonic is False
    assert refinement_grid(lower, upper, 0.005) == [0.405, 0.41, 0.415, 0.42]


def test_clean_cost_design_includes_both_frozen_bounds_and_balanced_path() -> None:
    design = _clean_cost_design(-0.24, 0.41)

    assert design["status"] == "DESIGNED_NOT_EXECUTED"
    assert design["matched_pacing_interval"] == [-0.24, 0.41]
    assert design["representative_r_values"][0] == -0.24
    assert design["representative_r_values"][-1] == 0.41
    assert 0.0 in design["representative_r_values"]
    assert design["force_based_control_or_selection"] is False
    assert design["value_imitation_or_rl"] is False


def test_frozen_domain_distinguishes_matched_from_free_pacing_and_stays_force_neutral() -> None:
    domain = json.loads(DOMAIN_PATH.read_text(encoding="utf-8"))

    assert domain["status"] == "FROZEN_FROM_RB_A_BOUNDARY_VALIDATION"
    assert domain["older_free_pacing_support_interval"] == [-0.24, 0.55]
    assert domain["frozen_matched_pacing_interval"] == [-0.24, 0.51]
    assert domain["boundary_evidence"]["first_failing_grid_point"] == 0.515
    study = domain["next_clean_cost_study"]
    assert study["representative_r_values"] == [
        -0.24,
        -0.09,
        0.0,
        0.06,
        0.21,
        0.36,
        0.51,
    ]
    assert study["force_used_for_waypoint_or_r_selection"] is False
    assert study["value_learning"] is False
    assert study["imitation_learning"] is False
    assert study["rl"] is False
