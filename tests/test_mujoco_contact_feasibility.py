"""Contracts for the contact-consistent quasistatic audit."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from traction_mpc.mujoco_sleeve_robot_v2.config import (  # noqa: E402
    HumanV2Parameters,
    PlantV2Config,
)
from traction_mpc.mujoco_sleeve_robot_v2.contact_feasibility import (  # noqa: E402
    ContactAuditConfig,
    audit_posture,
    classify_contacts,
    human_v2_quasistatic_load,
    preparation_q1,
    preparation_q1_derivative,
    run_contact_feasibility_audit,
)


def test_candidate_geometry_keeps_ankle_center_level() -> None:
    human = HumanV2Parameters()
    for q2_deg in (0.0, 0.7, 5.0, 10.0, 20.0):
        q2 = np.radians(q2_deg)
        q1 = preparation_q1(q2, human)
        height = (
            human.thigh_length_m * np.sin(q1)
            + human.shank_length_m * np.sin(q1 - q2)
        )
        assert height == pytest.approx(0.0, abs=1e-13)


def test_contact_velocity_sign_marks_distal_thigh_separating() -> None:
    human = HumanV2Parameters()
    plant = PlantV2Config()
    audit = ContactAuditConfig()
    q = np.zeros(2)
    tangent = np.array([preparation_q1_derivative(0.0, human), 1.0])
    contacts = classify_contacts(q, tangent, human, plant, audit, distributed=True)
    by_name = {row["name"]: row for row in contacts["rows"]}
    assert by_name["thigh_0.00"]["mode"] == "admissible_maintained"
    assert by_name["thigh_1.00"]["mode"] == "separating_lambda_zero"
    assert by_name["shank_1.00"]["mode"] == "geometrically_separated"
    assert contacts["invalid"] is False


def test_full_human_load_includes_registered_soft_limit() -> None:
    human = HumanV2Parameters()
    audit = ContactAuditConfig()
    load = human_v2_quasistatic_load(np.zeros(2), human, audit)
    np.testing.assert_allclose(load["soft_rhs_nm"], [25.0, 25.0], atol=1e-6)
    assert np.all(load["passive_left_nm"] < -25.0)


def test_rank_and_force_are_not_confused() -> None:
    human = HumanV2Parameters()
    plant = PlantV2Config()
    audit = ContactAuditConfig()
    singular = audit_posture(0.0, human, plant, audit)
    low_angle = audit_posture(5.0, human, plant, audit)
    assert singular["robot_only_rank"] == 1
    assert singular["classification"] == "RANK_OR_UNILATERAL_INCOMPATIBLE"
    assert low_angle["robot_only_rank"] == 2
    assert low_angle["classification"] == "FORCE_LIMIT_INFEASIBLE"
    assert low_angle["minimum_robot_force_norm_n"] > 200.0


@pytest.fixture(scope="module")
def audit_summary():
    return run_contact_feasibility_audit()


def test_registered_audit_reports_support_gap_without_parameter_changes(audit_summary) -> None:
    assert audit_summary["global_classification"] == "SUPPORT_AUTHORITY_GAP"
    assert audit_summary["candidate_path"]["contact_kinematically_valid"] is True
    assert audit_summary["contact_assisted_continuous_from_rest"] is False
    intervals = audit_summary["contact_and_robot_force_feasible_intervals_within_scan_deg"]
    assert intervals[0] == pytest.approx([2.1162, 2.6261], abs=1e-3)
    assert intervals[1][0] == pytest.approx(18.7948, abs=1e-3)
    assert audit_summary["robot_only_feasible_entry_deg"] == pytest.approx(
        2.1162, abs=1e-3
    )
    assert audit_summary["robot_only_persistent_entry_deg"] == pytest.approx(
        18.7948, abs=1e-3
    )
    assert audit_summary["scientific_variables_changed"] == []
    assert audit_summary["frozen_values"]["force_bound_n"] == 200.0
    assert audit_summary["distribution_sensitivity_equivalent"] is True
