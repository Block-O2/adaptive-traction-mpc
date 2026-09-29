from __future__ import annotations

from concurrent.futures import Future
from types import SimpleNamespace

import numpy as np
import pytest

from traction_mpc_stage5.full3d_adaptive_integration_v1.execution_policy import (
    ScientificPlanLifecycle, SimulationVersion,
)
from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import PlanLifecycle
from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import (
    snapshot_task_call, execute_task_snapshot,
)
from traction_mpc_stage5.full3d_adaptive_integration_v1.scientific_scheduler import ScientificPhysicsSession


def fake_session():
    session = object.__new__(ScientificPhysicsSession)
    session.plant = SimpleNamespace(data=SimpleNamespace(time=0.0, ctrl=np.zeros(1)))
    session.steps = 0
    session.sensor_steps = 20
    session.active = True
    session.samples = []
    session.applied_commands = []
    session.active_receipt_index = None
    session.clock = lambda: 1_000_000_000
    session.stop_check = None
    def step():
        session.steps += 1
        session.plant.data.time = session.steps * .00025
    session._step = step
    return session


def version(session):
    return SimulationVersion("episode", session.steps, session.steps,
                             session.plant.data.time, 0, "model0", "reference0")


@pytest.mark.parametrize("host_delay_s", [0.0, .1, .2, .5])
def test_worker_delay_cannot_advance_frozen_epoch(monkeypatch, host_delay_s):
    session = fake_session()
    waits = []
    lifecycle = ScientificPlanLifecycle(session, version_provider=lambda: version(session),
                                        host_delay_s=host_delay_s, sleeper=waits.append)
    lifecycle.capture(0.0, 1_000_000_000)
    request = lifecycle.request("TASK", 0.0, asynchronous=True)
    future = Future()
    future.set_result("decision")
    monkeypatch.setattr(PlanLifecycle, "submit", lambda self, request, payload: future)
    assert lifecycle.submit(request, b"immutable") is future
    assert session.steps == 0 and session.plant.data.time == 0.0
    assert waits == ([] if not host_delay_s else [host_delay_s])
    assert lifecycle.receipt_versions[request.request_id] == version(session)
    assert not lifecycle.expired(request)
    lifecycle.close()


def test_epoch_mutation_during_worker_is_rejected(monkeypatch):
    session = fake_session()
    future = Future()
    future.set_result(None)
    monkeypatch.setattr(PlanLifecycle, "submit", lambda self, request, payload: future)
    lifecycle = ScientificPlanLifecycle(session, version_provider=lambda: version(session),
                                        host_delay_s=.1, sleeper=lambda _: session._step())
    lifecycle.capture(0.0, 1_000_000_000)
    request = lifecycle.request("TASK", 0.0, asynchronous=True)
    with pytest.raises(RuntimeError, match="SCIENTIFIC_EPOCH_CHANGED_DURING_WORKER"):
        lifecycle.submit(request, b"immutable")
    lifecycle.close()


@pytest.mark.parametrize("changed", ["episode_epoch", "state_version", "phase_version",
                                       "human_model_version", "reference_version"])
def test_nonphysical_version_change_during_worker_is_rejected(monkeypatch, changed):
    session = fake_session()
    current = [version(session)]
    future = Future()
    future.set_result(None)
    monkeypatch.setattr(PlanLifecycle, "submit", lambda self, request, payload: future)
    def mutate(_):
        fields = vars(current[0]).copy()
        fields[changed] = fields[changed] + 1 if isinstance(fields[changed], int) else "changed"
        current[0] = SimulationVersion(**fields)
    lifecycle = ScientificPlanLifecycle(session, version_provider=lambda: current[0],
                                        host_delay_s=.002, sleeper=mutate)
    lifecycle.capture(0.0, 1_000_000_000)
    request = lifecycle.request("TASK", 0.0, asynchronous=True)
    with pytest.raises(RuntimeError, match="SCIENTIFIC_EPOCH_CHANGED_DURING_WORKER"):
        lifecycle.submit(request, b"immutable")
    assert session.steps == 0
    lifecycle.close()


def test_activation_uses_physical_age_and_records_versions(monkeypatch):
    session = fake_session()
    future = Future()
    future.set_result(None)
    monkeypatch.setattr(PlanLifecycle, "submit", lambda self, request, payload: future)
    lifecycle = ScientificPlanLifecycle(session, version_provider=lambda: version(session),
                                        host_delay_s=.5, sleeper=lambda _: None)
    lifecycle.capture(0.0, 1_000_000_000)
    request = lifecycle.request("TASK", 0.0, asynchronous=True)
    lifecycle.submit(request, b"immutable")
    session.next_control_tick()
    applied = []
    lifecycle.activate(request, lambda: applied.append(True))
    assert applied
    row = lifecycle.records()[0]
    assert row["execution_mode"] == "SCIENTIFIC_SIMULATION"
    assert row["source_simulation_version"]["physics_step"] == 0
    assert row["activation_simulation_version"]["physics_step"] == 20
    lifecycle.close()


def test_scientific_source_rejected_at_exact_100ms(monkeypatch):
    session = fake_session()
    future = Future()
    future.set_result(None)
    monkeypatch.setattr(PlanLifecycle, "submit", lambda self, request, payload: future)
    lifecycle = ScientificPlanLifecycle(session, version_provider=lambda: version(session))
    lifecycle.capture(0.0, 1_000_000_000)
    request = lifecycle.request("TASK", 0.0, asynchronous=True)
    lifecycle.submit(request, b"immutable")
    for _ in range(20):
        session.next_control_tick()
    assert lifecycle.expired(request)
    with pytest.raises(RuntimeError, match="SCIENTIFIC_SOURCE_OR_EPOCH_STALE"):
        lifecycle.activate(request, lambda: None)
    lifecycle.close()


def test_command_ready_precedes_exact_twenty_native_steps():
    session = fake_session()
    command = SimpleNamespace(joint_torque_command_nm=np.zeros(1))
    receipt = session.prepare_apply(command, source_sample_time_s=0.0)
    assert session.steps == 0 and session.plant.data.time == 0.0
    session.apply(command, lambda: None, source_sample_time_s=0.0, prepared=receipt)
    assert session.steps == 0 and receipt["applied"]
    session.next_control_tick()
    assert session.steps == 20
    assert session.plant.data.time == .005


class SnapshotPlanner:
    def __init__(self):
        self.planner = SimpleNamespace(decisions=[])
        self.belief_sequences_used = []

    def decide(self, **arguments):
        return arguments["state"].copy()


def test_worker_payload_is_by_value_and_sees_no_future_state():
    original = np.array([1.0, 2.0])
    payload = snapshot_task_call(SnapshotPlanner(), {"state": original})
    original[:] = [9.0, 10.0]
    np.testing.assert_array_equal(execute_task_snapshot(payload), [1.0, 2.0])
