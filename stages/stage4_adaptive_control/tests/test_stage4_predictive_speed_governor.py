from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from traction_mpc_stage3.reference import CuffPoseReference, _world_from_cuff
from traction_mpc_stage4.predictive_speed_governor import (
    PredictiveSpeedGovernor,
    PredictiveSpeedGovernorConfig,
)


def _quadratic_reference(time_s: float) -> CuffPoseReference:
    time = float(time_s)
    q = np.array([time**2, 0.0])
    dq = np.array([2.0 * time, 0.0])
    ddq = np.array([2.0, 0.0])
    return CuffPoseReference(q, dq, ddq, _world_from_cuff(q))


def test_time_warp_preserves_velocity_and_acceleration_chain_rule() -> None:
    governor = PredictiveSpeedGovernor(_quadratic_reference)
    governor._set_speed_target(0.0, 0.5)
    reference = governor.reference(0.2)
    phase, speed, speed_rate = governor._clock_state(0.2)
    base = _quadratic_reference(phase)
    np.testing.assert_allclose(reference.dq_rad_s, speed * base.dq_rad_s)
    np.testing.assert_allclose(
        reference.ddq_rad_s2,
        speed**2 * base.ddq_rad_s2 + speed_rate * base.dq_rad_s,
    )
    assert phase > 0.0
    assert speed == pytest.approx(0.8)
    assert speed_rate == pytest.approx(-1.0)


class _MappedPredictionGovernor(PredictiveSpeedGovernor):
    def _predict_peak_command_force(
        self, wall_time_s, target, state, human, mpc, cuff_allocator
    ) -> float:
        del wall_time_s, state, human, mpc, cuff_allocator
        return {1.0: 205.0, 0.9: 197.0, 0.8: 194.0, 0.5: 20.0}[target]


def test_governor_selects_largest_predicted_safe_candidate() -> None:
    config = PredictiveSpeedGovernorConfig(
        candidate_speed_scales=(1.0, 0.9, 0.8, 0.5)
    )
    governor = _MappedPredictionGovernor(_quadratic_reference, config=config)
    governor.update_from_prediction(0.0, np.zeros(4), object(), object(), object())
    assert governor.speed_target_scale == pytest.approx(0.8)
    assert governor.predicted_peak_command_force_n == pytest.approx(194.0)
    assert governor.slowdown_selection_count == 1
    assert governor.no_safe_candidate_count == 0


class _LinearGeometry:
    @staticmethod
    def cuff_pose(q_rad: np.ndarray) -> SimpleNamespace:
        return SimpleNamespace(
            translation=np.array([q_rad[0], q_rad[1], 0.0]),
            rotation=np.eye(3),
        )

    @staticmethod
    def cuff_velocity(
        q_rad: np.ndarray, dq_rad_s: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        del q_rad
        return np.array([dq_rad_s[0], dq_rad_s[1], 0.0]), np.zeros(3)


class _OneStepMPC:
    config = SimpleNamespace(horizon_steps=1, prediction_dt_s=0.1)

    @staticmethod
    def _reference_arrays(time_s, reference_fn):
        reference = reference_fn(time_s + 0.1)
        return (
            np.array([reference.q_rad]),
            np.array([reference.dq_rad_s]),
            np.array([reference.ddq_rad_s2]),
        )

    @staticmethod
    def _seed_sequence(state, q_ref, dq_ref, ddq_ref, human):
        del state, q_ref, dq_ref, ddq_ref, human
        return np.zeros((1, 2))

    @staticmethod
    def _rollout(state, sequence, human):
        del sequence, human
        return np.array([state, state])


class _FixedAllocator:
    @staticmethod
    def allocate(action, q_rad, human):
        del action, q_rad, human
        return {"wrench_world": np.array([3.0, 4.0, 0.0, 0.0, 0.0, 0.0])}


def _linear_reference(time_s: float) -> CuffPoseReference:
    q = np.array([float(time_s), 0.0])
    dq = np.array([1.0, 0.0])
    ddq = np.zeros(2)
    return CuffPoseReference(q, dq, ddq, _world_from_cuff(q))


def test_prediction_matches_existing_feedback_plus_feedforward_force_law() -> None:
    governor = PredictiveSpeedGovernor(_linear_reference)
    human = SimpleNamespace(geometry=_LinearGeometry())
    peak = governor._predict_peak_command_force(
        0.0,
        1.0,
        np.zeros(4),
        human,
        _OneStepMPC(),
        _FixedAllocator(),
    )
    # 3000*0.1 + 140*1 clips to 200 N on x before [3,4,0] N FF.
    assert peak == pytest.approx(np.linalg.norm([203.0, 4.0, 0.0]))


def test_planning_limit_leaves_margin_without_changing_hard_gate() -> None:
    payload = PredictiveSpeedGovernorConfig().as_dict()
    assert payload["planning_force_limit_n"] == pytest.approx(195.0)
    assert payload["hard_force_gate_n_unchanged"] == pytest.approx(200.0)
    assert payload["planning_margin_n"] == pytest.approx(5.0)
