from __future__ import annotations

import numpy as np

from traction_mpc_stage4.confidence_execution import (
    ReferenceExecutionLayer,
    UnifiedReferenceManager,
)
from traction_mpc_stage4.minimal_adaptation import EstimatorConfidence
from traction_mpc_stage4.measurement import sensor_realism_cases
from traction_mpc_stage4.reference import cold_start_teaching_reference
from traction_mpc_stage4.safety_filter import (
    FILTER_INFEASIBLE,
    SAFE_FILTERED,
    SAFE_UNCHANGED,
)
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case
from traction_mpc_stage4.track_brake import TRACK, TrackBrakeSupervisor


def _confidence(*, accepted: bool = True) -> EstimatorConfidence:
    names = ("a", "b")
    return EstimatorConfidence(
        parameter_names=names,
        sample_count=20,
        parameter_dimension=2,
        rank=2,
        condition_number=2.0,
        residual_rms=0.01,
        covariance=np.eye(2),
        standard_deviation=np.ones(2),
        accepted=accepted,
        reasons=() if accepted else ("rejected",),
    )


def _filter_metadata(
    status: str,
    *,
    force_intervention_n: float = 0.0,
    moment_intervention_nm: float = 0.0,
    rho: float = 0.0,
    margin_n: float = 100.0,
) -> dict[str, float | str]:
    return {
        "status": status,
        "force_intervention_norm_n": force_intervention_n,
        "moment_intervention_norm_nm": moment_intervention_nm,
        "intervention_coordinate_norm": rho,
        "executable_force_margin_n": margin_n,
    }


def test_legacy_name_is_alias_of_the_single_reference_manager() -> None:
    assert ReferenceExecutionLayer is UnifiedReferenceManager


def test_nominal_force_identity_reproduces_original_reference_exactly() -> None:
    manager = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=False,
    )
    for time_s in np.arange(0.0, 1.005, 0.005):
        decision = manager.update_from_safety_filter(
            time_s,
            _filter_metadata(SAFE_UNCHANGED),
        )
        assert not decision.brake_required
        assert decision.alpha_force == 1.0
        managed = manager.reference(time_s)
        nominal = cold_start_teaching_reference(time_s)
        np.testing.assert_array_equal(managed.q_rad, nominal.q_rad)
        np.testing.assert_array_equal(managed.dq_rad_s, nominal.dq_rad_s)
        np.testing.assert_array_equal(managed.ddq_rad_s2, nominal.ddq_rad_s2)
    assert manager.phase_time_s(1.0) == 1.0
    assert manager.speed_scale == 1.0


def test_safe_unchanged_force_input_preserves_confidence_only_clock() -> None:
    baseline = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=True,
    )
    unified = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=True,
    )
    confidence = _confidence()
    for time_s in (1.0, 2.0, 3.0, 4.0):
        for manager in (baseline, unified):
            manager.update_from_confidence(
                time_s,
                confidence,
                confidence,
                geometry_model_valid=True,
                dynamic_model_valid=True,
            )
        unified.update_from_safety_filter(
            time_s,
            _filter_metadata(SAFE_UNCHANGED),
        )
        for sample_time_s in (time_s, time_s + 0.25):
            assert unified.status(sample_time_s)["speed_scale"] == (
                baseline.status(sample_time_s)["speed_scale"]
            )
            assert unified.phase_time_s(sample_time_s) == baseline.phase_time_s(
                sample_time_s
            )
            expected = baseline.reference(sample_time_s)
            actual = unified.reference(sample_time_s)
            np.testing.assert_array_equal(actual.q_rad, expected.q_rad)
            np.testing.assert_array_equal(actual.dq_rad_s, expected.dq_rad_s)
            np.testing.assert_array_equal(actual.ddq_rad_s2, expected.ddq_rad_s2)


def test_200hz_force_updates_do_not_change_slow_trust_mathematics() -> None:
    baseline = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=True,
    )
    unified = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=True,
    )
    confidence = _confidence()
    trust_update_times = {1.0, 2.0, 3.0, 4.0}
    for time_s in np.arange(0.0, 4.005, 0.005):
        rounded_time_s = round(float(time_s), 3)
        unified.update_from_safety_filter(
            rounded_time_s,
            _filter_metadata(SAFE_UNCHANGED),
        )
        if rounded_time_s in trust_update_times:
            for manager in (baseline, unified):
                manager.update_from_confidence(
                    rounded_time_s,
                    confidence,
                    confidence,
                    geometry_model_valid=True,
                    dynamic_model_valid=True,
                )
            expected = baseline.status(rounded_time_s)
            actual = unified.status(rounded_time_s)
            assert actual["filtered_model_confidence"] == (
                expected["filtered_model_confidence"]
            )
            assert actual["execution_confidence_high"] == (
                expected["execution_confidence_high"]
            )
            assert actual["alpha_trust"] == expected["alpha_trust"]
        expected_status = baseline.status(rounded_time_s)
        actual_status = unified.status(rounded_time_s)
        np.testing.assert_allclose(
            actual_status["reference_phase_time_s"],
            expected_status["reference_phase_time_s"],
            rtol=0.0,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            actual_status["speed_scale"],
            expected_status["speed_scale"],
            rtol=0.0,
            atol=1e-12,
        )
        expected_reference = baseline.reference(rounded_time_s)
        actual_reference = unified.reference(rounded_time_s)
        np.testing.assert_allclose(
            actual_reference.q_rad,
            expected_reference.q_rad,
            rtol=0.0,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            actual_reference.dq_rad_s,
            expected_reference.dq_rad_s,
            rtol=0.0,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            actual_reference.ddq_rad_s2,
            expected_reference.ddq_rad_s2,
            rtol=0.0,
            atol=1e-12,
        )


def test_force_intervention_slows_and_recovers_through_shared_rate_limit() -> None:
    manager = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=False,
    )
    before = manager.reference(1.0)
    filtered = manager.update_from_safety_filter(
        1.0,
        _filter_metadata(
            SAFE_FILTERED,
            force_intervention_n=40.0,
            moment_intervention_nm=8.0,
            rho=41.0,
            margin_n=0.0,
        ),
    )
    after = manager.reference(1.0)
    assert filtered.alpha_force == 0.8
    assert filtered.force_severity == 0.2
    np.testing.assert_array_equal(after.q_rad, before.q_rad)
    np.testing.assert_array_equal(after.dq_rad_s, before.dq_rad_s)
    assert manager.status(1.0)["speed_scale_rate_per_s"] == -1.0
    np.testing.assert_allclose(manager.status(1.1)["speed_scale"], 0.9)
    np.testing.assert_allclose(manager.status(1.2)["speed_scale"], 0.8)

    manager.update_from_safety_filter(
        1.2,
        _filter_metadata(SAFE_UNCHANGED),
    )
    np.testing.assert_allclose(manager.status(1.2)["speed_scale"], 0.8)
    assert manager.status(1.2)["speed_scale_rate_per_s"] == 0.25
    np.testing.assert_allclose(manager.status(1.6)["speed_scale"], 0.9)
    np.testing.assert_allclose(manager.status(2.0)["speed_scale"], 1.0)
    assert manager.phase_time_s(2.0) < 2.0


def test_trust_and_force_caps_share_one_minimum_command() -> None:
    manager = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=True,
    )
    manager.update_from_safety_filter(
        0.0,
        _filter_metadata(SAFE_FILTERED, force_intervention_n=40.0),
    )
    assert manager.alpha_trust == 0.5
    assert manager.alpha_force == 0.8
    assert manager.alpha_cmd == 0.5

    confidence = _confidence()
    manager.update_from_confidence(
        1.0,
        confidence,
        confidence,
        geometry_model_valid=True,
        dynamic_model_valid=True,
    )
    manager.update_from_confidence(
        2.0,
        confidence,
        confidence,
        geometry_model_valid=True,
        dynamic_model_valid=True,
    )
    assert manager.alpha_trust == 1.0
    assert manager.alpha_force == 0.8
    assert manager.alpha_cmd == 0.8


def test_filter_infeasible_requires_brake_without_guessing_alpha() -> None:
    manager = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=False,
    )
    manager.update_from_safety_filter(
        0.5,
        _filter_metadata(SAFE_FILTERED, force_intervention_n=40.0),
    )
    prior_force_cap = manager.alpha_force
    prior_command = manager.alpha_cmd
    decision = manager.update_from_safety_filter(
        0.6,
        _filter_metadata(
            FILTER_INFEASIBLE,
            force_intervention_n=200.0,
            margin_n=-10.0,
        ),
    )
    assert decision.brake_required
    assert decision.alpha_force is None
    assert decision.force_severity is None
    assert manager.alpha_force == prior_force_cap
    assert manager.alpha_cmd == prior_command
    checkpoint = manager.brake_reentry_checkpoint(0.6)
    assert not checkpoint["automatic_return_to_track_implemented"]


def test_short_track_runtime_routes_filter_signal_into_same_manager() -> None:
    manager = UnifiedReferenceManager(
        cold_start_teaching_reference,
        confidence_aware=False,
    )
    supervisor = TrackBrakeSupervisor()
    summary, trace = run_sensor_realism_case(
        sensor_realism_cases()[0],
        duration_s=0.04,
        reference_execution=manager,
        track_brake_supervisor=supervisor,
    )
    assert summary["termination_reason"] == "completed"
    assert supervisor.mode == TRACK
    assert summary["reference_execution"]["single_reference_manager"]
    assert summary["reference_execution"]["force_update_count"] == 8
    assert summary["mpc"]["solve_count"] == 2
    np.testing.assert_array_equal(trace["reference_alpha_cmd"], 1.0)
    np.testing.assert_array_equal(trace["reference_alpha_trust"], 1.0)
    np.testing.assert_array_equal(trace["reference_alpha_force"], 1.0)
