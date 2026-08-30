from __future__ import annotations

import numpy as np

from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage4.hierarchical_trust import (
    _selection_comparison,
    _validation_blocks,
    measurement_validity,
    state_geometry_validity,
)
from traction_mpc_stage4.measurement import sensor_realism_cases


def _geometry() -> PlanarCuffGeometry:
    return PlanarCuffGeometry(
        origin_world_m=np.zeros(3),
        plane_x_world=np.array([1.0, 0.0, 0.0]),
        joint_axis_world=np.array([0.0, 1.0, 0.0]),
        plane_z_world=np.array([0.0, 0.0, 1.0]),
        hip_plane_m=np.zeros(2),
        thigh_length_m=0.40,
        knee_to_cuff_in_cuff_m=np.array([0.30, 0.0]),
    )


def test_l1_uses_integrity_not_wrench_magnitude_or_parameter_outcome() -> None:
    noise = sensor_realism_cases()[1]
    huge_but_finite_wrench = np.array([1.0e8, -1.0e8, 5.0e7])
    warmup = measurement_validity(
        arrival_time_s=0.10,
        sample_time_s=0.10,
        previous_arrival_time_s=0.08,
        previous_ingested_sample_time_s=0.08,
        new_sample=True,
        case=noise,
        stream_start_sample_time_s=0.0,
        values=(huge_but_finite_wrench,),
    )
    assert not warmup["valid"]
    assert warmup["reasons"] == ["preprocessing_warmup"]

    ready = measurement_validity(
        arrival_time_s=0.12,
        sample_time_s=0.12,
        previous_arrival_time_s=0.10,
        previous_ingested_sample_time_s=0.10,
        new_sample=True,
        case=noise,
        stream_start_sample_time_s=0.0,
        values=(huge_but_finite_wrench,),
    )
    assert ready["valid"]
    assert not ready["sensor_saturation_status_available"]


def test_l1_rejects_timestamp_contract_and_duplicate_zoh() -> None:
    case = sensor_realism_cases()[-1]
    result = measurement_validity(
        arrival_time_s=1.0,
        sample_time_s=0.95,
        previous_arrival_time_s=0.98,
        previous_ingested_sample_time_s=0.95,
        new_sample=False,
        case=case,
        stream_start_sample_time_s=0.0,
        values=(np.ones(3),),
    )
    assert "sample_age_exceeds_registered_timing_contract" in result["reasons"]
    assert "duplicate_or_stale_zoh_sample" in result["reasons"]


def test_l2_records_closure_error_without_rejecting_poor_fit() -> None:
    geometry = _geometry()
    state = np.array([0.2, 0.4, 0.1, -0.2])
    pose = geometry.cuff_pose(state[:2])
    linear, angular = geometry.cuff_velocity(state[:2], state[2:])
    result = state_geometry_validity(
        geometry=geometry,
        state=state,
        measured_position_m=pose.translation + np.array([0.03, 0.0, 0.0]),
        measured_rotation=pose.rotation,
        measured_linear_velocity_m_s=linear + np.array([0.5, 0.0, 0.0]),
        measured_angular_velocity_rad_s=angular,
    )
    assert result["valid"]
    assert result["position_closure_error_m"] > 0.02
    assert result["linear_velocity_closure_error_m_s"] > 0.4


def test_validation_windows_are_future_embargoed_and_nonoverlap_training() -> None:
    history = []
    for source_index, time_s in enumerate(np.arange(0.0, 2.01, 0.02)):
        history.append(
            {
                "time_s": float(time_s),
                "state": np.array([time_s, 0.2 * time_s, 0.1, -0.1]),
                "generalized_input_nm": np.array([1.0, -0.5]),
                "contaminated": False,
                "source_index": source_index,
            }
        )
    blocks = _validation_blocks(
        history,
        fit_end_time_s=0.50,
        window_s=0.50,
        embargo_windows=1,
        count=2,
    )
    assert len(blocks) == 2
    assert blocks[0]["start_time_s"] >= 1.0
    assert min(blocks[0]["source_indices"]) > 25
    assert blocks[-1]["end_time_s"] >= 2.0 - 1e-12


def test_validation_skips_contaminated_window_without_failing_candidate() -> None:
    history = []
    for source_index, time_s in enumerate(np.arange(0.0, 3.01, 0.02)):
        history.append(
            {
                "time_s": float(time_s),
                "state": np.array([time_s, 0.2 * time_s, 0.1, -0.1]),
                "generalized_input_nm": np.array([1.0, -0.5]),
                "contaminated": bool(1.0 <= time_s <= 1.5),
                "source_index": source_index,
            }
        )
    blocks = _validation_blocks(
        history,
        fit_end_time_s=0.50,
        window_s=0.50,
        embargo_windows=1,
        count=2,
    )
    assert len(blocks) == 2
    assert blocks[0]["start_time_s"] >= 1.5


def test_selection_audit_reports_when_nonpromoted_oracle_error_is_better() -> None:
    def record(error: float, active: bool) -> dict[str, object]:
        return {
            "oracle_proposed_model_error_nm": error,
            "oracle_improvement_vs_last_valid_nm": 2.0 - error,
            "oracle_improvement_vs_prior_nm": 2.0 - error,
            "proposed_model_distance_to_truth_span_l2": error,
            "truth_distance_change_from_last_valid_span_l2": error - 1.0,
            "proposed_model_distance_to_prior_span_l2": 0.1,
            "l3": {"active_bound_count": int(active)},
        }

    comparison = _selection_comparison(
        [record(2.0, False)],
        [record(1.0, True), record(1.5, False)],
    )
    assert comparison[
        "cross_pair_probability_nonpromoted_has_greater_phase_matched_oracle_improvement"
    ] == 1.0
    assert comparison[
        "cross_pair_probability_nonpromoted_is_closer_to_true_beta"
    ] == 1.0
