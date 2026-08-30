from __future__ import annotations

import numpy as np

from traction_mpc_stage4.confidence_execution import ReferenceExecutionLayer
from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.minimal_adaptation import EstimatorConfidence
from traction_mpc_stage4.reference import cold_start_teaching_reference
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case


def _confidence(*, accepted: bool, informative: bool = True) -> EstimatorConfidence:
    names = ("a", "b")
    return EstimatorConfidence(
        parameter_names=names,
        sample_count=20,
        parameter_dimension=2,
        rank=2 if informative else 1,
        condition_number=2.0 if informative else float("inf"),
        residual_rms=0.01,
        covariance=np.eye(2) if informative else np.full((2, 2), np.nan),
        standard_deviation=np.ones(2) if informative else np.full(2, np.nan),
        accepted=accepted,
        reasons=() if accepted else ("rank_deficient",),
    )


def test_model_confidence_is_filtered_before_nominal_speed_recovery() -> None:
    execution = ReferenceExecutionLayer(
        cold_start_teaching_reference, confidence_aware=True
    )
    high = _confidence(accepted=True)
    execution.update_from_confidence(
        1.0,
        high,
        high,
        geometry_model_valid=True,
        dynamic_model_valid=True,
    )
    assert execution.speed_scale == 0.5
    assert execution.execution_confidence_high == 0.0
    execution.update_from_confidence(
        2.0,
        high,
        high,
        geometry_model_valid=True,
        dynamic_model_valid=True,
    )
    assert execution.speed_scale == 0.5
    assert execution.execution_confidence_high == 1.0
    execution.update_from_confidence(
        3.0,
        high,
        high,
        geometry_model_valid=True,
        dynamic_model_valid=True,
    )
    assert execution.speed_scale == 0.75
    execution.update_from_confidence(
        4.0,
        high,
        high,
        geometry_model_valid=True,
        dynamic_model_valid=True,
    )
    assert execution.speed_scale == 1.0


def test_rejected_update_does_not_invalidate_retained_model_or_reduce_speed() -> None:
    execution = ReferenceExecutionLayer(
        cold_start_teaching_reference, confidence_aware=True
    )
    accepted = _confidence(accepted=True)
    rejected = _confidence(accepted=False, informative=True)
    for time_s in (1.0, 2.0, 3.0, 4.0):
        execution.update_from_confidence(
            time_s,
            accepted,
            accepted,
            geometry_model_valid=True,
            dynamic_model_valid=True,
        )
    assert execution.speed_scale == 1.0
    execution.update_from_confidence(
        4.1,
        accepted,
        rejected,
        geometry_model_valid=True,
        dynamic_model_valid=True,
    )
    assert execution.dynamic_information_confidence == 1.0
    assert execution.combined_model_confidence_raw == 1.0
    assert execution.execution_confidence_high == 1.0
    assert execution.speed_scale == 1.0


def test_hysteresis_ignores_short_model_confidence_drop() -> None:
    execution = ReferenceExecutionLayer(
        cold_start_teaching_reference, confidence_aware=True
    )
    high = _confidence(accepted=True)
    for time_s in (1.0, 2.0, 3.0, 4.0):
        execution.update_from_confidence(
            time_s,
            high,
            high,
            geometry_model_valid=True,
            dynamic_model_valid=True,
        )
    execution.update_from_confidence(
        4.1,
        high,
        high,
        geometry_model_valid=False,
        dynamic_model_valid=True,
    )
    assert execution.filtered_model_confidence > 0.25
    assert execution.execution_confidence_high == 1.0
    assert execution.speed_scale == 1.0


def test_reference_time_warp_preserves_pose_and_scales_derivatives() -> None:
    execution = ReferenceExecutionLayer(
        cold_start_teaching_reference, confidence_aware=True
    )
    reference = execution.reference(4.0)
    base = cold_start_teaching_reference(2.0)
    np.testing.assert_allclose(reference.q_rad, base.q_rad)
    np.testing.assert_allclose(reference.dq_rad_s, 0.5 * base.dq_rad_s)
    np.testing.assert_allclose(reference.ddq_rad_s2, 0.25 * base.ddq_rad_s2)


def test_accelerating_time_warp_is_phase_consistent_and_includes_sdot() -> None:
    execution = ReferenceExecutionLayer(
        cold_start_teaching_reference, confidence_aware=True
    )
    high = _confidence(accepted=True)
    for time_s in (1.0, 2.0):
        execution.update_from_confidence(
            time_s,
            high,
            high,
            geometry_model_valid=True,
            dynamic_model_valid=True,
        )

    wall_time_s = 2.4
    status = execution.status(wall_time_s)
    phase = status["reference_phase_time_s"]
    speed = status["speed_scale"]
    speed_rate = status["speed_scale_rate_per_s"]
    assert speed == 0.6
    assert speed_rate == 0.25
    base = cold_start_teaching_reference(phase)
    reference = execution.reference(wall_time_s)
    np.testing.assert_allclose(reference.q_rad, base.q_rad)
    np.testing.assert_allclose(reference.dq_rad_s, base.dq_rad_s * speed)
    np.testing.assert_allclose(
        reference.ddq_rad_s2,
        base.ddq_rad_s2 * speed**2 + base.dq_rad_s * speed_rate,
    )

    step = 1e-5
    phase_before = execution.phase_time_s(wall_time_s - step)
    phase_after = execution.phase_time_s(wall_time_s + step)
    np.testing.assert_allclose(
        (phase_after - phase_before) / (2.0 * step), speed, rtol=1e-9
    )
    reference_before = execution.reference(wall_time_s - step)
    reference_after = execution.reference(wall_time_s + step)
    np.testing.assert_allclose(
        (reference_after.q_rad - reference_before.q_rad) / (2.0 * step),
        reference.dq_rad_s,
        rtol=2e-8,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        (reference_after.dq_rad_s - reference_before.dq_rad_s) / (2.0 * step),
        reference.ddq_rad_s2,
        rtol=2e-7,
        atol=1e-9,
    )


def test_fixed_speed_ignores_low_confidence_and_never_exceeds_nominal() -> None:
    execution = ReferenceExecutionLayer(
        cold_start_teaching_reference, confidence_aware=False
    )
    low = _confidence(accepted=False)
    execution.update_from_confidence(
        1.0,
        low,
        low,
        geometry_model_valid=False,
        dynamic_model_valid=False,
    )
    assert execution.speed_scale == 1.0
    assert execution.phase_time_s(2.0) == 2.0


def test_short_rollout_logs_confidence_speed_tracking_and_wrench() -> None:
    execution = ReferenceExecutionLayer(
        cold_start_teaching_reference, confidence_aware=True
    )
    summary, trace = run_sensor_realism_case(
        sensor_realism_cases()[0],
        duration_s=0.10,
        estimator_architecture="integral_minimal",
        result_case_name="confidence_execution_short_smoke",
        reference_execution=execution,
    )
    assert summary["mechanically_completed_requested_duration"]
    assert summary["force_gate_n"] == 200.0
    assert summary["reference_execution"]["safety_limits_modified"] is False
    assert np.all(trace["reference_speed_scale"] == 0.5)
    assert np.all(trace["reference_speed_scale_rate_per_s"] == 0.0)
    assert trace["combined_confidence_level"].shape == trace["time_s"].shape
    assert trace["combined_model_confidence_raw"].shape == trace["time_s"].shape
    assert trace["combined_information_confidence"].shape == trace["time_s"].shape
    assert trace["filtered_model_confidence"].shape == trace["time_s"].shape
    assert trace["tracking_error_deg_god_view"].shape[1] == 2
    assert trace["cuff_wrench_local_god_view"].shape[1] == 6
