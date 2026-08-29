from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from traction_mpc_stage3.human import (
    HUMAN,
    TRACKING_KD_RAD_S2_PER_RAD_S,
    TRACKING_KP_RAD_S2_PER_RAD,
    mass_matrix,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "stage4_report_validation_matrix.json"
SPEC_PATH = ROOT / "docs" / "research" / "STAGE4_REPORT_VALIDATION_SPEC.md"


def _payload() -> dict[str, object]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_report_validation_sources_are_frozen_and_hash_verified() -> None:
    payload = _payload()
    assert payload["schema_version"] == "stage4_report_validation_matrix_v1"
    assert payload["design_status"] == (
        "preregistered_design_only_no_formal_execution"
    )
    assert payload["frozen_start"] == {
        "tag": "stage4-robustness-final-v1",
        "commit": "cc04765761d08ffaf1914f0236f0201d9c7e1475",
        "authoritative_stage4_mutation_allowed": False,
    }

    for source in payload["source_artifacts"].values():
        source_path = ROOT / source["path"]
        assert source_path.is_file()
        assert _sha256(source_path) == source["sha256"]


def test_selected_patients_and_trajectories_resolve_without_mutating_sources() -> None:
    payload = _payload()
    patient_source = json.loads(
        (ROOT / payload["source_artifacts"]["patient_config"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    existing_patient_ids = {item["case_id"] for item in patient_source["cases"]}
    assert set(payload["patient_cases"]["existing"]) <= existing_patient_ids

    report_only = payload["patient_cases"]["report_only"]
    assert len(report_only) == 1
    assert report_only[0]["case_id"] not in existing_patient_ids
    assert report_only[0]["height_scale"] == 1.03
    assert report_only[0]["stage4_canonical_evidence"] is False

    trajectory_source = json.loads(
        (ROOT / payload["source_artifacts"]["trajectory_config"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    trajectory_ids = {item["trajectory_id"] for item in trajectory_source["cases"]}
    assert set(payload["selected_trajectories"]) <= trajectory_ids
    assert payload["excluded_professor_facing_main_trajectory"] == (
        "two_cycle_moderate_23s"
    )
    assert "two_cycle_moderate_23s" not in payload["selected_trajectories"]


def test_pd_gain_grid_and_physical_base_gain_derivation_are_exact() -> None:
    payload = _payload()
    tuning = payload["gain_tuning"]
    assert tuning["candidate_count"] == len(tuning["kp_scales"]) * len(
        tuning["kd_scales"]
    )
    assert tuning["candidate_count"] == 9

    q0 = np.radians(tuning["initial_q_deg"])
    diagonal_mass = np.diag(mass_matrix(q0, HUMAN))
    np.testing.assert_allclose(
        tuning["base_kp_tau_nm_per_rad"],
        diagonal_mass * TRACKING_KP_RAD_S2_PER_RAD,
        rtol=0.0,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        tuning["base_kd_tau_nms_per_rad"],
        diagonal_mass * TRACKING_KD_RAD_S2_PER_RAD_S,
        rtol=0.0,
        atol=1e-12,
    )
    assert tuning["gains_shared_with"] == "pd_nominal_inverse_dynamics_ff"
    assert tuning["benchmark_runner_requires_frozen_gain_hash"] is True


def test_matrix_counts_are_small_exact_and_evidence_separated() -> None:
    payload = _payload()
    controllers = [item["controller_id"] for item in payload["controllers"]]
    assert controllers == [
        "pd_feedback",
        "pd_nominal_inverse_dynamics_ff",
        "fixed_mpc_prior_only",
        "trusted_adaptive_mpc",
    ]
    assert payload["optional_oracle"]["included_in_any_matrix"] is False

    benchmark = payload["benchmark_matrix"]
    benchmark_product = (
        len(benchmark["controllers"])
        * len(benchmark["patients"])
        * len(benchmark["trajectories"])
        * len(benchmark["measurement_seeds"])
    )
    assert benchmark_product == benchmark["logical_arm_count"] == 16
    assert benchmark["new_rollout_count"] == 16
    assert benchmark["authoritative_result_reuse_count"] == 0

    visualization = payload["visualization_matrix"]
    assert len(visualization["scenes"]) * len(
        visualization["controllers_per_scene"]
    ) == visualization["logical_arm_count"] == 12
    assert sum(item["new_rollout_count"] for item in visualization["scenes"]) == 8
    assert visualization["benchmark_arm_reuse_count"] == 4

    counts = payload["counts_and_cost"]
    assert counts["unique_control_rollouts_total"] == (
        counts["gain_tuning_rollouts"]
        + counts["benchmark_rollouts"]
        + counts["new_demo_rollouts"]
    )
    assert counts["unique_control_rollouts_total"] == 33
    assert payload["evidence_categories"]["existing_authoritative_stage4"][
        "new_rollouts"
    ] == 0


def test_shared_fairness_contract_and_spec_guardrails_are_explicit() -> None:
    payload = _payload()
    invariants = set(payload["shared_contract"]["shared_invariants"])
    assert {
        "same_patient_within_case",
        "same_reference_phase_trace_within_case",
        "same_initial_human_and_robot_state_within_case",
        "same_sensor_case_seed_and_realization_within_case",
        "same_robot_plant_and_cuff_mechanics",
        "same_safety_gates_and_actuator_limits",
        "same_allocator_and_low_level_cartesian_execution",
        "no_controller_specific_trajectory_tuning",
        "no_patient_or_trajectory_specific_gain_tuning",
    } <= invariants
    assert payload["shared_contract"]["reference_clock"][
        "controller_specific_pacing"
    ] is False
    assert payload["visualization"]["render_now"] is False

    spec = " ".join(SPEC_PATH.read_text(encoding="utf-8").lower().split())
    for required_text in (
        "formal v2 gain tuning has not yet been executed",
        "benchmark, demo, and final rendering remain unauthorized",
        "constant nominal-inertia-derived coupled torque pd",
        "not pressure, comfort",
        "33",
        "2 x 2",
    ):
        assert required_text.lower() in spec
