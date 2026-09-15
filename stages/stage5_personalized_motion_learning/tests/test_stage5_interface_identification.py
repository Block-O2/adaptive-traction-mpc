from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from traction_mpc_stage5.interface_identification import (
    InactiveInterfaceIdentificationTrust,
    InterfaceFitResult,
    InterfaceIdentificationMeasurement,
    InterfaceIdentificationSeries,
    InterfaceIdentifiabilityDiagnostics,
    InterfaceParameterScales,
    ShadowInterfaceIdentificationService,
    WindowedInterfacePredictionErrorIdentifier,
    fixed_stage5_human_model,
    load_interface_identification_config,
)


def _synthetic_series(sample_count: int = 81) -> tuple[
    InterfaceIdentificationSeries,
    np.ndarray,
]:
    time = 0.005 * np.arange(sample_count)
    human_model = fixed_stage5_human_model()
    human_state = np.radians([5.0, 10.0, 0.0, 0.0])
    interface_state = np.r_[
        [0.001, 0.0, -0.0015],
        np.zeros(3),
        [0.0, 0.02, 0.0],
        np.zeros(3),
    ]
    command = np.zeros((sample_count, 6))
    command[:, 0] = 15.0 + 4.0 * np.sin(2.0 * np.pi * 2.0 * time)
    command[:, 2] = -20.0 + 3.0 * np.cos(2.0 * np.pi * 1.5 * time)
    command[:, 4] = 6.0 + 1.5 * np.sin(2.0 * np.pi * 2.5 * time)
    base_force = np.tile(np.array([15.0, 0.0, -20.0]), (sample_count, 1))
    base_moment = np.tile(np.array([0.0, 6.0, 0.0]), (sample_count, 1))
    arrival_human = np.tile(human_state, (sample_count, 1))
    arrival_interface = np.tile(interface_state, (sample_count, 1))
    placeholder = InterfaceIdentificationSeries(
        time_s=time,
        phase=np.full(sample_count, "OUTBOUND"),
        robot_measurement=np.zeros((sample_count, 12)),
        measured_wrench_world=np.zeros((sample_count, 6)),
        executed_wrench_world=command,
        base_drive_world_n=base_force,
        base_angular_drive_world_nm=base_moment,
        arrival_human_state=arrival_human,
        arrival_interface_state=arrival_interface,
        source="synthetic_deployable_measurements",
        legacy_measurement_reconstruction=False,
        reconstruction_closure_max_abs=0.0,
    )
    identifier = WindowedInterfacePredictionErrorIdentifier(human_model=human_model)
    true_parameters = InterfaceParameterScales(0.75, 1.20, 0.85)
    predicted = identifier.predict_measurements(
        placeholder,
        0,
        sample_count - 1,
        true_parameters,
        np.r_[human_state, interface_state],
    )
    series = replace(
        placeholder,
        robot_measurement=np.vstack([predicted[0, :12], predicted[:, :12]]),
        measured_wrench_world=np.vstack([predicted[0, 12:], predicted[:, 12:]]),
    )
    return series, np.r_[human_state, interface_state]


def _diagnostics(rank: int = 3, condition: float = 10.0):
    return InterfaceIdentifiabilityDiagnostics(
        singular_values=np.ones(3),
        rank=rank,
        condition_number=condition,
        correlation=np.eye(3),
        maximum_abs_parameter_correlation=0.0,
        parameter_information_retained_after_latent_projection=np.ones(3),
    )


def _fit_result(**updates):
    base = InterfaceFitResult(
        success=True,
        reason="test",
        parameter_scales=InterfaceParameterScales(0.9, 1.1, 0.9),
        initial_state=np.zeros(16),
        fit_normalized_rmse=0.2,
        validation_normalized_rmse=0.4,
        nominal_validation_normalized_rmse=0.5,
        validation_relative_improvement=0.2,
        validation_component_normalized_rmse={},
        nominal_validation_component_normalized_rmse={},
        optimizer_nfev=10,
        optimizer_cost=1.0,
        bound_hit=False,
        fit_start_time_s=0.0,
        fit_end_time_s=0.2,
        validation_start_time_s=0.25,
        validation_end_time_s=0.35,
        validation_sample_count=20,
        identifiability=_diagnostics(),
        multistart_solutions=(),
        last_valid_fallback_used=False,
    )
    return replace(base, **updates)


def test_config_is_truth_free_and_control_inactive() -> None:
    config = load_interface_identification_config()
    assert not config.active_in_control
    assert not config.truth_available_to_service
    assert not config.inactive_trust.control_publication_enabled
    assert tuple(config.lower) == (0.5, 0.5, 0.5)
    assert tuple(config.upper) == (1.5, 1.5, 1.5)


def test_service_measurement_has_deployable_boundary_and_no_truth_field() -> None:
    measurement = InterfaceIdentificationMeasurement(
        sample_timestamp_s=1.0,
        arrival_timestamp_s=1.01,
        robot_cuff_position_world_m=np.zeros(3),
        robot_cuff_rotation_world=np.eye(3),
        robot_cuff_linear_velocity_world_m_s=np.zeros(3),
        robot_cuff_angular_velocity_world_rad_s=np.zeros(3),
        measured_cuff_force_world_n=np.zeros(3),
        measured_cuff_moment_world_nm=np.zeros(3),
        executed_command_wrench_world=np.zeros(6),
        previous_executed_command_wrench_world=np.zeros(6),
        prediction_base_drive_world_n=np.zeros(3),
        prediction_base_angular_drive_world_nm=np.zeros(3),
        fixed_human_model_version="fixed-test",
    )
    assert not any("truth" in name for name in measurement.__dataclass_fields__)
    with pytest.raises(ValueError, match="arrival timestamp"):
        replace(measurement, arrival_timestamp_s=0.9)


def test_shadow_service_buffers_raw_targets_and_nominal_arrival_prior_only() -> None:
    model = fixed_stage5_human_model()
    pose = model.geometry.cuff_pose(np.radians([5.0, 10.0]))
    zero_wrench = np.zeros(6)
    first = InterfaceIdentificationMeasurement(
        sample_timestamp_s=0.0,
        arrival_timestamp_s=0.0,
        robot_cuff_position_world_m=pose.translation,
        robot_cuff_rotation_world=pose.rotation,
        robot_cuff_linear_velocity_world_m_s=np.zeros(3),
        robot_cuff_angular_velocity_world_rad_s=np.zeros(3),
        measured_cuff_force_world_n=np.zeros(3),
        measured_cuff_moment_world_nm=np.zeros(3),
        executed_command_wrench_world=zero_wrench,
        previous_executed_command_wrench_world=zero_wrench,
        prediction_base_drive_world_n=np.zeros(3),
        prediction_base_angular_drive_world_nm=np.zeros(3),
        fixed_human_model_version="fixed-test",
    )
    second = replace(first, sample_timestamp_s=0.005, arrival_timestamp_s=0.005)
    service = ShadowInterfaceIdentificationService(model)
    service.ingest(first, phase="OUTBOUND")
    service.ingest(second, phase="OUTBOUND")
    series = service.series()
    np.testing.assert_allclose(series.robot_measurement[0, :3], pose.translation)
    assert series.source == "shadow_interface_identification_service"
    assert not series.legacy_measurement_reconstruction


def test_predictor_scores_subsequent_deployable_measurements() -> None:
    series, initial_state = _synthetic_series()
    identifier = WindowedInterfacePredictionErrorIdentifier()
    prediction = identifier.predict_measurements(
        series,
        0,
        len(series.time_s) - 1,
        InterfaceParameterScales(0.75, 1.20, 0.85),
        initial_state,
    )
    np.testing.assert_allclose(
        prediction,
        series.output_measurement[1:],
        atol=1.0e-12,
        rtol=0.0,
    )


def test_diagnostic_rollout_is_exactly_the_scored_predictor_and_exposes_latents() -> None:
    series, initial_state = _synthetic_series()
    identifier = WindowedInterfacePredictionErrorIdentifier()
    parameters = InterfaceParameterScales(0.75, 1.20, 0.85)
    rollout = identifier.predict_rollout(
        series, 0, len(series.time_s) - 1, parameters, initial_state
    )
    np.testing.assert_allclose(
        rollout.deployable_measurements,
        identifier.predict_measurements(
            series, 0, len(series.time_s) - 1, parameters, initial_state
        ),
        atol=0.0,
        rtol=0.0,
    )
    assert rollout.human_state.shape == (len(series.time_s) - 1, 4)
    assert rollout.interface_state.shape == (len(series.time_s) - 1, 12)
    assert rollout.base_drive_world_n.shape == (len(series.time_s) - 1, 3)


def test_fixed_parameter_latent_fit_is_public_offline_diagnostic_only() -> None:
    series, _ = _synthetic_series()
    config = replace(
        load_interface_identification_config(),
        maximum_function_evaluations=15,
    )
    identifier = WindowedInterfacePredictionErrorIdentifier(config)
    fitted_state = identifier.fit_initial_state_for_fixed_parameters(
        series,
        start_index=0,
        fit_window_s=0.05,
        parameters=InterfaceParameterScales(0.75, 1.20, 0.85),
    )
    assert fitted_state.shape == (16,)
    assert np.all(np.isfinite(fitted_state))


def test_fit_uses_disjoint_future_validation_window() -> None:
    series, _ = _synthetic_series()
    config = load_interface_identification_config()
    config = replace(
        config,
        fit_window_s=0.10,
        validation_embargo_s=0.025,
        validation_window_s=0.05,
        maximum_function_evaluations=30,
        multistart_parameter_scales=((1.0, 1.0, 1.0),),
        multistart_initial_state_offsets_in_prior_scales=((0.0,) * 16,),
    )
    result = WindowedInterfacePredictionErrorIdentifier(config).fit(
        series, start_index=0, multistart=False
    )
    assert result.success
    assert result.validation_start_time_s > result.fit_end_time_s
    assert result.validation_sample_count == 10
    assert not result.identifiability.regularization_included


def test_inactive_trust_publishes_only_to_shadow_and_keeps_single_challenger() -> None:
    trust = InactiveInterfaceIdentificationTrust()
    fit = _fit_result()
    trust.propose(fit)
    with pytest.raises(RuntimeError, match="only one"):
        trust.propose(fit)
    decision = trust.resolve(decision_timestamp_s=0.5)
    assert decision.status == "qualified_and_published_to_shadow_only"
    assert not decision.control_model_changed
    assert decision.shadow_incumbent.version.endswith("0000000500")


def test_inactive_trust_rejects_noninformative_fit_and_retains_last_valid() -> None:
    trust = InactiveInterfaceIdentificationTrust()
    before = trust.shadow_incumbent
    trust.propose(
        _fit_result(
            validation_relative_improvement=0.0,
            identifiability=_diagnostics(rank=2, condition=float("inf")),
        )
    )
    decision = trust.resolve(decision_timestamp_s=0.5)
    assert decision.status == "rejected_shadow_last_valid_retained"
    assert decision.shadow_incumbent == before
    assert "insufficient_future_prediction_improvement" in decision.reasons
    assert "data_rank_deficient_after_latent_projection" in decision.reasons
