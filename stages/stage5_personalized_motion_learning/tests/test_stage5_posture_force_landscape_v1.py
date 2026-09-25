from __future__ import annotations

import json

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.posture_landscape import (
    DEPLOYABLE_FIELDS,
    build_supported_grid,
    decide_landscape,
    high_level_indices,
)


CONFIG = STAGE5_ROOT / "configs" / "stage5_posture_force_landscape_v1.json"


def test_contract_freezes_learning_and_controller_authority() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    condition = config["frozen_condition"]
    assert config["schema"] == "stage5_posture_force_landscape_v1"
    assert condition["gamma"] == 0.5
    assert condition["interface"] == "fixed_nominal"
    assert condition["human_model_updates_enabled"] is False
    assert condition["trust_to_gamma_authority"] is False
    assert condition["value_or_rl_control"] is False
    assert config["control_authority"]["value_model_training"] is False
    assert config["control_authority"]["value_or_rl_connected_to_control"] is False
    assert config["control_authority"]["stronger_branch_study_only_if_lf_a"] is True


def test_controller_side_audit_fields_are_deployable_only() -> None:
    assert "estimated_state_rad_rad_s" in DEPLOYABLE_FIELDS
    assert "deployable_measured_cuff_force_world_n" in DEPLOYABLE_FIELDS
    assert "deployable_measured_generalized_input_nm" in DEPLOYABLE_FIELDS
    assert all("truth" not in field and "true_" not in field for field in DEPLOYABLE_FIELDS)


def test_high_level_indices_select_fixed_timing_grid() -> None:
    time = np.arange(0.0, 0.101, 0.005)
    selected = high_level_indices(time, 0.02)
    assert np.allclose(time[selected], [0.0, 0.02, 0.04, 0.06, 0.08, 0.10])


def test_grid_masks_cells_without_seed_support() -> None:
    samples = {
        "q_rad": np.radians([[5.1, 10.1], [5.2, 10.2], [5.3, 10.3], [9.0, 19.0]]),
        "seed": np.array([1, 1, 2, 1]),
        "force_norm_n": np.array([10.0, 12.0, 14.0, 99.0]),
        "moment_norm_nm": np.array([1.0, 1.2, 1.4, 9.9]),
        "generalized_input_norm_nm": np.array([2.0, 2.2, 2.4, 8.0]),
        "support_norm_nm": np.array([3.0, 3.2, 3.4, 7.0]),
        "motion_norm_nm": np.array([4.0, 4.2, 4.4, 6.0]),
    }
    grid = build_supported_grid(
        samples,
        q1_edges_deg=np.array([5.0, 7.0, 10.0]),
        q2_edges_deg=np.array([10.0, 15.0, 20.0]),
        minimum_samples=3,
        minimum_unique_seeds=2,
    )
    assert grid["force_norm_n"][0, 0] == 12.0
    assert np.isnan(grid["force_norm_n"][1, 1])


def _groups(separations: list[float], winners: list[str]) -> list[dict]:
    return [
        {
            "anchor_name": "anchor",
            "seed": index,
            "local_duration_range_s": 0.0,
            "mean_force_separation_fraction": separation,
            "low_force_branch": winner,
        }
        for index, (separation, winner) in enumerate(zip(separations, winners))
    ]


def test_decision_rules_distinguish_meaningful_small_flat_and_invalid() -> None:
    kwargs = dict(meaningful_fraction=0.05, flat_fraction=0.01, repeat_count=2)
    assert decide_landscape(
        _groups([0.06, 0.07, 0.02], ["hip", "hip", "knee"]), validity=True, **kwargs
    )["decision"] == "LF-A"
    assert decide_landscape(
        _groups([0.02, 0.03, 0.01], ["hip", "hip", "knee"]), validity=True, **kwargs
    )["decision"] == "LF-B"
    assert decide_landscape(
        _groups([0.005, 0.004, 0.003], ["hip", "knee", "balanced"]),
        validity=True,
        **kwargs,
    )["decision"] == "LF-C"
    assert decide_landscape(
        _groups([0.06, 0.07, 0.08], ["hip", "hip", "hip"]), validity=False, **kwargs
    )["decision"] == "LF-D"
