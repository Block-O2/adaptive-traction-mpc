import json

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT
from validate_stage5_hwmpc_matched_pacing_r_cost import (
    _effect_analysis,
    _observed_phase_durations,
)


CONFIG_PATH = (
    STAGE5_ROOT
    / "configs"
    / "stage5_hwmpc_matched_pacing_r_cost_v1.json"
)


def test_matched_pacing_cost_config_freezes_scope_before_outcomes() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["status"] == "PREREGISTERED_BEFORE_MATCHED_PACING_COST_OUTCOMES"
    assert config["coordination"]["frozen_support_interval"] == [-0.24, 0.55]
    assert [row["r"] for row in config["coordination"]["representative_profiles"]] == [
        -0.24,
        -0.125,
        0.0,
        0.25,
        0.4,
        0.55,
    ]
    assert config["matched_pacing"]["outbound_duration_s"] == 2.2
    assert config["matched_pacing"]["hold_duration_s"] == 0.5
    assert config["matched_pacing"]["return_duration_s"] == 2.2
    assert config["fixed_human"]["support_outcome"] == "positive"
    assert config["fixed_human"]["updates_enabled"] is False
    assert config["coordination"]["selection_uses_force"] is False
    assert config["scope"]["value_learning"] is False
    assert config["scope"]["imitation_learning"] is False
    assert config["scope"]["rl"] is False


def test_observed_phase_duration_uses_control_period_coverage() -> None:
    trace = [
        *[
            {"phase": "OUTBOUND", "elapsed_s": index * 0.005}
            for index in range(440)
        ],
        *[
            {"phase": "HOLD", "elapsed_s": 2.2 + index * 0.005}
            for index in range(100)
        ],
        *[
            {"phase": "RETURN", "elapsed_s": 2.7 + index * 0.005}
            for index in range(441)
        ],
    ]

    assert _observed_phase_durations(trace) == {
        "OUTBOUND": 2.2,
        "HOLD": 0.5,
        "RETURN": 2.2,
    }


def _trajectory(offset: float) -> dict:
    base = np.column_stack((np.linspace(0.0, 0.3, 101), np.linspace(0.0, 0.5, 101)))
    path = {"q_rad": base + np.array([offset, -offset])}
    return {"realized_paths": {"OUTBOUND": path, "RETURN": path}}


def test_effect_analysis_separates_between_r_effect_from_repeatability() -> None:
    summaries = [
        {
            "coordination_r": -0.24,
            "force_integral_mean_n_s": 100.0,
            "force_integral_range_n_s": 0.2,
            "representative_trajectory": _trajectory(-0.02),
        },
        {
            "coordination_r": 0.0,
            "force_integral_mean_n_s": 95.0,
            "force_integral_range_n_s": 0.1,
            "representative_trajectory": _trajectory(0.0),
        },
        {
            "coordination_r": 0.55,
            "force_integral_mean_n_s": 85.0,
            "force_integral_range_n_s": 0.2,
            "representative_trajectory": _trajectory(0.03),
        },
    ]
    cases = [{"completion_time_s": 4.9} for _ in range(9)]

    result = _effect_analysis(summaries, cases)

    assert np.isclose(result["between_r_force_integral_range_n_s"], 15.0)
    assert result["within_to_between_range_ratio"] < 0.02
    assert result["linear_slope_n_s_per_r"] < 0.0
    assert np.isclose(result["completion_time_range_s"], 0.0)
    assert result["completed_case_count"] == 9
    assert result["incomplete_case_count"] == 0
    assert result["mean_phase_rms_path_distance_deg"] > 1.0
