"""Deterministic checks for explicit boundary ownership and accounting."""
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime as rt
from traction_mpc_stage5.full3d_adaptive_integration_v1.session_state import PersistentSessionState
from traction_mpc_stage5.full3d_adaptive_integration_v1.terminal_reference import (
    receipt_reference_at_sample,
)


class Plant:
    def __init__(self):
        self.data = SimpleNamespace(time=1.0, qpos=np.arange(8., dtype=float),
                                    qvel=np.zeros(8))
        self.steps = 0

    def observe(self):
        return SimpleNamespace(time_s=self.data.time, human_q_rad=np.array([.1, .2]),
            human_dq_rad_s=np.zeros(2), robot_q_rad=np.arange(6., dtype=float),
            robot_dq_rad_s=np.zeros(6))

    def step_native(self):
        self.data.time += .00025
        self.steps += 1


class Layer:
    def __init__(self):
        self.current = SimpleNamespace(sample_time_s=1.0, robot_dq_rad_s=np.zeros(6))

    def update(self, truth):
        self.current = SimpleNamespace(sample_time_s=truth.time_s,
                                       robot_dq_rad_s=np.zeros(6))
        return self.current


class Observer:
    def update(self, measurement, model, human_model_version):
        observation = SimpleNamespace(
            sample_timestamp_s=measurement.sample_time_s,
            as_array=lambda: np.array([.1, .2, 0., 0.]))
        interface = SimpleNamespace(measured_force_world_n=np.array([2., 0., 0.]),
                                    measured_moment_world_nm=np.array([0., 3., 0.]))
        return observation, interface


class Updater:
    sequence = 4

    def snapshot(self):
        return SimpleNamespace(human_model=lambda: SimpleNamespace(geometry=object()))


def test_three_boundaries_preserve_native_state_and_account_for_hold():
    plant, layer, updater = Plant(), Layer(), Updater()
    runtime = {
        "plant": plant, "wall_session": SimpleNamespace(active=False),
        "plan_lifecycle": SimpleNamespace(_outstanding=None),
        "measurement_layer": layer, "observer": Observer(),
        "autonomous_recovery_options": {},
        "contract": SimpleNamespace(reference_motion_history=SimpleNamespace(
            last_reference=lambda: (np.array([.1, .2]), np.zeros(2)))),
        "trace": [{"ddq_ref_rad_s2": np.zeros(2)}],
    }
    context = {"runtime": runtime, "updater": updater, "spec": object(),
               "config": {"cuff_force_limit_n": 10., "cuff_moment_limit_nm": 10.},
               "repetition_index": 1, "end_time_s": 1.0}
    qpos, qvel = plant.data.qpos.copy(), plant.data.qvel.copy()
    with patch.object(rt, "SessionClearanceContract", lambda geometry: object()), (
         patch.object(rt, "RigidTableReferenceEnvelopeV1", lambda geometry: object())), (
         patch.object(rt, "CombinedRigidTableClearanceV1",
                      lambda *args, **kwargs: SimpleNamespace(evaluate=lambda q: .02))), (
         patch.object(rt, "start_episode", lambda *args, **kwargs: object())):
        first = rt.advance_inter_rep_boundary(context)
        context["repetition_index"] = 2
        second = rt.advance_inter_rep_boundary(context)
    assert plant.steps == 40
    assert first["settle_duration_s"] == second["settle_duration_s"] == 0.
    assert first["hold_duration_s"] == second["hold_duration_s"] == .005
    assert first["cost"]["J_F_n_s"] == pytest.approx(.01)
    assert first["cost"]["moment_integral_nm_s"] == pytest.approx(.015)
    np.testing.assert_array_equal(first["terminal_native_qpos_evaluation_only"], qpos)
    np.testing.assert_array_equal(second["settled_native_qvel_evaluation_only"], qvel)
    assert first["end_time_s"] == second["start_time_s"]
    assert context["end_time_s"] == plant.data.time
    assert context["final_belief"] is not None


def test_receipt_source_is_owned_by_fresh_episode_track():
    old = {"applied": True, "start_physics_s": 1.0, "mode": "TRACK",
           "q_ref_rad": np.zeros(2), "dq_ref_rad_s": np.zeros(2), "apply_ns": 10}
    continuing = {"applied": True, "start_physics_s": 2.0, "mode": "BRAKE"}
    fresh = {"applied": True, "start_physics_s": 2.0, "mode": "TRACK",
             "q_ref_rad": np.array([.1, .2]), "dq_ref_rad_s": np.zeros(2),
             "apply_ns": 20}
    with pytest.raises(ValueError, match="no TRACK"):
        receipt_reference_at_sample([old, continuing], 2.005)
    owner = receipt_reference_at_sample([continuing, fresh], 2.005)
    assert owner["receipt_index"] == 1
    assert owner["source_sample_time_s"] > owner["reference_effective_physics_s"]
    np.testing.assert_array_equal(owner["q_ref_rad"], fresh["q_ref_rad"])


def test_future_learning_state_persists_without_zero_value_effect():
    value = object()
    replay = [{"rep": 1}]
    state = PersistentSessionState("session", value_model_parameters=value,
                                   replay_history=replay, exploration_state={"seed": 17})
    for rep in range(1, 7):
        state.begin_repetition(rep)
    assert state.value_model_parameters is value
    assert state.replay_history is replay
    assert state.exploration_state == {"seed": 17}
    assert state.primary_learned_parameters_frozen
    with pytest.raises(ValueError):
        state.begin_repetition(8)



def test_bootstrap_applies_new_track_before_first_request():
    plant = Plant()
    layer = Layer()
    monitor = SimpleNamespace(latest=None)
    wall = SimpleNamespace(applied_commands=[
        {"applied": True, "start_physics_s": 1.0, "mode": "BRAKE"}],
        active_receipt_index=0)
    def warmup():
        plant.data.time += .005
        layer.update(plant.observe())
        monitor.latest = SimpleNamespace(
            fast_motion_valid=True, sample_timestamp_s=plant.data.time)
    wall.next_control_tick = warmup
    runtime = {"plant": plant, "measurement_layer": layer, "observer": Observer(),
               "model": object(), "model_sequence": 4, "wall_session": wall, "monitor": monitor}
    def apply_new(runtime, **kwargs):
        plant.data.time += .005
        layer.update(plant.observe())
        wall.applied_commands.append({
            "applied": True, "start_physics_s": 1.005,
            "source_sample_time_s": 1.005, "mode": "TRACK",
            "q_ref_rad": np.array([.1, .2]), "dq_ref_rad_s": np.zeros(2),
            "apply_ns": 55})
        wall.active_receipt_index = 1
        return object(), {"safety_mode": "TRACK"}
    with patch.object(rt, "_execute_interval", apply_new):
        result = rt._bootstrap_fresh_track_reference(
            runtime, SimpleNamespace(outbound_goal_target_rad=np.array([.3, .4])), np.array([.1, .2]))
    assert result["receipt_index"] == 1
    assert result["source_sample_time_s"] == pytest.approx(1.01)
    assert result["reference"]["receipt_index"] == 1
    assert result["cost"]["J_F_n_s"] == pytest.approx(.02)
