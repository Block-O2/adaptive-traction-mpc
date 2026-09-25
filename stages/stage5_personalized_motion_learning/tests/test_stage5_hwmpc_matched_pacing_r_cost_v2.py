import json

from traction_mpc_stage5.config import STAGE5_ROOT
from validate_stage5_hwmpc_matched_pacing_r_cost_v2 import classify_conclusion


CONFIG_PATH = STAGE5_ROOT / "configs" / "stage5_hwmpc_matched_pacing_r_cost_v2.json"
DOMAIN_PATH = STAGE5_ROOT / "configs" / "stage5_hwmpc_matched_pacing_r_domain_v1.json"


def _classify(**overrides) -> str:
    values = {
        "contract_valid": True,
        "relative_range": 0.06,
        "useful_relative_range": 0.05,
        "path_distance_deg": 2.0,
        "minimum_path_distance_deg": 1.0,
        "repeatability_passed": True,
        "numerical_separation": True,
        "absolute_spearman_rho": 1.0,
        "minimum_absolute_spearman_rho": 0.9,
    }
    values.update(overrides)
    return classify_conclusion(**values)


def test_clean_cost_config_matches_frozen_domain_and_analysis_order() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    domain = json.loads(DOMAIN_PATH.read_text(encoding="utf-8"))

    assert config["status"] == "PREREGISTERED_BEFORE_CLEAN_COST_EXECUTION"
    assert config["frozen_domain_source"]["matched_pacing_interval"] == [-0.24, 0.51]
    assert config["coordination"]["preregistered_r_values"] == domain[
        "next_clean_cost_study"
    ]["representative_r_values"]
    assert config["matched_pacing"]["outbound_duration_s"] == 2.2
    assert config["matched_pacing"]["hold_duration_s"] == 0.5
    assert config["matched_pacing"]["return_duration_s"] == 2.2
    assert config["analysis_contract"]["minimum_relative_J_F_range_for_RC2_A"] == 0.05
    assert config["coordination"]["force_used_for_selection_or_adaptation"] is False
    assert all(value is False for value in config["scope"].values())


def test_conclusion_prioritizes_invalid_execution_contract() -> None:
    assert _classify(contract_valid=False).startswith("RC2-D")


def test_conclusion_separates_useful_small_and_absent_effects() -> None:
    assert _classify(relative_range=0.06).startswith("RC2-A")
    assert _classify(relative_range=0.02).startswith("RC2-B")
    assert _classify(relative_range=0.02, absolute_spearman_rho=0.5).startswith(
        "RC2-C"
    )
    assert _classify(relative_range=0.02, path_distance_deg=0.5).startswith("RC2-C")
