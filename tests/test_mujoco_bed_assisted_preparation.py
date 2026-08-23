"""Contracts for the bed-assisted small-angle preparation study."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from traction_mpc.mujoco_sleeve_robot_v2.bed_assisted_preparation import (  # noqa: E402
    PreparationStudyConfig,
    minimum_bed_clearance_q1,
    preparation_target_posture,
    run_staged_preparation,
)
from traction_mpc.mujoco_sleeve_robot_v2.config import (  # noqa: E402
    HumanV2Parameters,
    PlantV2Config,
)
from traction_mpc.mujoco_sleeve_robot_v2.kinematics import (  # noqa: E402
    quintic_boundary_sample,
)


@pytest.fixture(scope="module")
def staged_result():
    return run_staged_preparation()


def test_target_q1_is_derived_from_registered_constraints() -> None:
    human = HumanV2Parameters()
    plant = PlantV2Config()
    study = PreparationStudyConfig()
    clearance = minimum_bed_clearance_q1(np.radians(5.0), human, plant)
    target, basis = preparation_target_posture(5.0, human, plant, study)
    assert np.degrees(clearance) == pytest.approx(2.046, abs=0.01)
    np.testing.assert_allclose(np.degrees(target), [5.0, 5.0], atol=1e-12)
    assert basis["selected_q1_deg"] == pytest.approx(5.0)
    assert basis["bed_clearance_minimum_q1_deg"] < 5.0


def test_preparation_path_starts_at_measured_boundary_and_is_c2() -> None:
    q0 = np.radians([-0.004, 0.713])
    dq0 = np.radians([0.002, -0.003])
    qf = np.radians([5.0, 5.0])
    start = quintic_boundary_sample(0.0, 4.0, q0, dq0, qf)
    finish = quintic_boundary_sample(4.0, 4.0, q0, dq0, qf)
    np.testing.assert_allclose(start.q, q0, atol=1e-14)
    np.testing.assert_allclose(start.dq, dq0, atol=1e-14)
    np.testing.assert_allclose(start.ddq, np.zeros(2), atol=1e-14)
    np.testing.assert_allclose(finish.q, qf, atol=1e-14)
    np.testing.assert_allclose(finish.dq, np.zeros(2), atol=1e-14)
    np.testing.assert_allclose(finish.ddq, np.zeros(2), atol=1e-13)


def test_staged_rule_stops_after_5_degree_failure_or_runs_only_8_and_10(staged_result) -> None:
    summary, _ = staged_result
    tested = summary["tested_candidates_deg"]
    assert tested[0] == 5.0
    if summary["five_degree_pass"]:
        assert tested == [5.0, 8.0, 10.0]
    else:
        assert tested == [5.0]
    assert summary["frozen_values"]["force_bound_n"] == 200.0
    assert summary["frozen_values"]["normal_controller_used"] is False
    assert summary["scientific_variables_changed"] == []


def test_measured_result_respects_force_and_sleeve_contract(staged_result) -> None:
    summary, _ = staged_result
    for row in summary["candidate_rows"]:
        assert row["peak_interaction_force_n"] <= 200.0 + 1e-6
        assert row["maximum_sleeve_deformation_mm"] <= 1.0
        assert row["mapping_jacobian_max_error"] < 1e-8
