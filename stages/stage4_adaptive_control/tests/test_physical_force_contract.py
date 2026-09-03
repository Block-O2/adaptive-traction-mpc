from __future__ import annotations

import numpy as np
import pytest

from traction_mpc_stage4.physical_force_contract import (
    FINE_REPLAY_CONFIRMED,
    HARD_PHYSICAL_VIOLATION,
    RULE_CONTIGUOUS_DURATION,
    RULE_EXCESS_IMPULSE,
    RULE_ROLLING_DURATION,
    RULE_STRICT_SAMPLE,
    RULE_TRAILING_MEAN,
    RULE_TRANSIENT_CEILING,
    SIMULATION_ENGINEERING_TRANSIENT_V1,
    STRICT_PASS,
    STRICT_PHYSICAL_FORCE_V1,
    TRANSIENT_ENGINEERING_QUALIFIED,
    PhysicalForceSupervisor,
    evaluate_physical_force_trace,
)


def _vector_force(norms: np.ndarray) -> np.ndarray:
    result = np.zeros((len(norms), 3))
    result[:, 0] = norms
    return result


def _evaluate(time: np.ndarray, force: np.ndarray):
    return evaluate_physical_force_trace(
        time,
        _vector_force(force),
        policy_id=SIMULATION_ENGINEERING_TRANSIENT_V1,
        numerical_confirmation=FINE_REPLAY_CONFIRMED,
    )


def test_never_exceeds_200_is_strict_pass() -> None:
    time = np.array([0.0, 0.001, 0.003, 0.009, 0.021])
    report = _evaluate(time, np.array([10.0, 100.0, 199.0, 200.0, 190.0]))
    assert report.classification == STRICT_PASS
    assert report.event_count == 0


def test_one_short_transient_is_engineering_qualified() -> None:
    time = np.arange(0.0, 0.031, 0.001)
    force = np.full_like(time, 190.0)
    force[10:14] = 210.0
    report = _evaluate(time, force)
    assert report.classification == TRANSIENT_ENGINEERING_QUALIFIED
    assert report.maximum_contiguous_exceedance_duration_s == pytest.approx(0.004)
    assert report.maximum_rolling_excess_impulse_ns == pytest.approx(0.035)


def test_peak_above_220_is_hard_violation() -> None:
    time = np.arange(0.0, 0.031, 0.001)
    force = np.full_like(time, 190.0)
    force[10] = 220.1
    report = _evaluate(time, force)
    assert report.classification == HARD_PHYSICAL_VIOLATION
    assert RULE_TRANSIENT_CEILING in report.violated_rules


def test_contiguous_duration_violation() -> None:
    time = np.arange(0.0, 0.031, 0.001)
    force = np.full_like(time, 190.0)
    force[10:16] = 205.0
    report = _evaluate(time, force)
    assert report.classification == HARD_PHYSICAL_VIOLATION
    assert RULE_CONTIGUOUS_DURATION in report.violated_rules


def test_repeated_transients_violate_rolling_duration() -> None:
    time = np.arange(0.0, 0.081, 0.001)
    force = np.full_like(time, 190.0)
    force[9] = 200.0
    force[10:12] = 201.0
    force[12] = 200.0
    force[39] = 200.0
    force[40:42] = 201.0
    force[42] = 200.0
    report = _evaluate(time, force)
    assert report.classification == HARD_PHYSICAL_VIOLATION
    assert RULE_ROLLING_DURATION in report.violated_rules
    assert RULE_CONTIGUOUS_DURATION not in report.violated_rules


def test_excess_impulse_violation_is_reported() -> None:
    # Under the frozen 220 N ceiling and 5 ms rolling-duration limit, an excess
    # impulse above 0.10 N*s cannot be isolated mathematically.  This waveform
    # therefore also violates rolling duration, while deterministically proving
    # that the independent impulse rule is evaluated and reported.
    time = np.arange(0.0, 0.081, 0.001)
    force = np.full_like(time, 190.0)
    force[10:14] = 219.0
    force[40:44] = 219.0
    report = _evaluate(time, force)
    assert report.maximum_rolling_excess_impulse_ns > 0.10
    assert RULE_EXCESS_IMPULSE in report.violated_rules


def test_trailing_20ms_mean_violation() -> None:
    time = np.arange(0.0, 0.041, 0.001)
    force = np.full_like(time, 200.0)
    force[10:14] = 210.0
    report = _evaluate(time, force)
    assert report.classification == HARD_PHYSICAL_VIOLATION
    assert RULE_TRAILING_MEAN in report.violated_rules


def test_irregular_timestamps_drive_duration_and_impulse() -> None:
    time = np.array([0.0, 0.002, 0.0031, 0.0047, 0.0060, 0.021, 0.027])
    force = np.array([190.0, 200.0, 210.0, 210.0, 200.0, 190.0, 190.0])
    report = _evaluate(time, force)
    assert report.classification == TRANSIENT_ENGINEERING_QUALIFIED
    assert report.maximum_contiguous_exceedance_duration_s == pytest.approx(0.004)
    assert report.maximum_rolling_excess_impulse_ns == pytest.approx(0.028)


def test_strict_default_policy_is_unchanged() -> None:
    supervisor = PhysicalForceSupervisor()
    assert supervisor.policy_id == STRICT_PHYSICAL_FORCE_V1
    assert not supervisor.update(0.0, np.array([200.0, 0.0, 0.0]))
    assert not supervisor.update(0.001, np.array([200.0 + 0.5e-9, 0.0, 0.0]))
    assert supervisor.update(0.002, np.array([200.0 + 2.0e-9, 0.0, 0.0]))
    report = supervisor.report(numerical_confirmation=FINE_REPLAY_CONFIRMED)
    assert report.classification == HARD_PHYSICAL_VIOLATION
    assert report.violated_rule == RULE_STRICT_SAMPLE


def test_opt_in_runtime_and_offline_evaluator_are_identical() -> None:
    time = np.array([0.0, 0.001, 0.0027, 0.004, 0.006, 0.021, 0.027])
    force = np.array([190.0, 200.0, 207.0, 207.0, 200.0, 190.0, 190.0])
    vectors = _vector_force(force)
    offline = evaluate_physical_force_trace(
        time,
        vectors,
        policy_id=SIMULATION_ENGINEERING_TRANSIENT_V1,
        numerical_confirmation=FINE_REPLAY_CONFIRMED,
    )
    runtime = PhysicalForceSupervisor(SIMULATION_ENGINEERING_TRANSIENT_V1)
    for timestamp, vector in zip(time, vectors, strict=True):
        runtime.update(timestamp, vector)
    online = runtime.report(numerical_confirmation=FINE_REPLAY_CONFIRMED)
    assert online.as_dict() == offline.as_dict()
