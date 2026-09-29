"""Fast three-epoch exercise of the production session glue and its APIs."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime as rt
from traction_mpc_stage5.full3d_adaptive_integration_v1.applied_reference_history import (
    AppliedReferenceMotionHistory,
)


START = np.radians([5.0, 10.0])


class FakeBelief:
    def __init__(self, sequence):
        self.sequence = sequence

    def human_model(self):
        return SimpleNamespace(sequence=self.sequence)


class FakeUpdater:
    def __init__(self):
        self.sequence = 351

    def snapshot(self):
        return FakeBelief(self.sequence)


class FakeSession:
    def __init__(self, runtime, *, stop_check=None):
        self.runtime = runtime
        self.active = True
        self.steps = 0
        self.samples = []
        self.phase_records = [{}]
        self.applied_commands = []
        self.capture_flags = []

    def capture(self, *, initial=False):
        self.capture_flags.append(initial)
        self.samples.append(object())


class FakeLifecycle:
    def __init__(self, session, *, version_provider, process_worker, host_delay_s):
        self.session = session
        self.version_provider = version_provider
        self._outstanding = None
        self.closed = False

    def close(self, reason):
        self._outstanding = None
        self.closed = True


def contract(*args):
    original = SimpleNamespace(last_reference=lambda: (
        START.copy(), np.zeros(2), np.full(2, 7.0)))
    return SimpleNamespace(reference_motion_history=original)


class SessionLifecycleV3Tests(unittest.TestCase):
    def initial_runtime(self):
        plant = SimpleNamespace(data=SimpleNamespace(time=15.0))
        return {
            "plant": plant,
            "measurement_layer": object(),
            "observer": object(),
            "allocator": object(),
            "last_command": object(),
            "last_command_robot_position_m": np.zeros(3),
            "last_command_source_sample_s": 15.0,
            "last_command_receipt_physics_s": 15.0,
            "command_response_history": object(),
            "contract": contract(),
            "autonomous_recovery_options": {"planner_process_worker": True},
            "model_sequence": 351,
        }

    def test_reference_history_api_uses_q_dq_and_time_only(self):
        runtime = self.initial_runtime()
        first = rt._start_applied_reference_history(runtime, START, resumed=False)
        second = rt._start_applied_reference_history(runtime, START, resumed=True)
        self.assertIsInstance(first, AppliedReferenceMotionHistory)
        self.assertIsInstance(second, AppliedReferenceMotionHistory)
        np.testing.assert_array_equal(second.last_reference()[0], START)
        np.testing.assert_array_equal(second.last_reference()[1], np.zeros(2))
        self.assertEqual(len(second.last_reference()), 2)

    def test_three_repetition_initialize_finalize_boundary(self):
        runtime = self.initial_runtime()
        updater = FakeUpdater()
        fit = object()
        spec = SimpleNamespace(task_joint_acceleration_limit_rad_s2=np.ones(2))
        context = {}
        old = None
        versions = []
        with (patch.object(rt, "ScientificPhysicsSession", FakeSession),
              patch.object(rt, "ScientificPlanLifecycle", FakeLifecycle),
              patch.object(rt, "HumanWaypointMPCShadowContractV1", contract),
              patch.object(rt, "Stage5LoadedTrackBrakeSupervisor", lambda: object()),
              patch.object(rt, "SplitAccelerationMonitorV1", lambda: object()),
              patch.object(rt, "HumanMotionAccelerationAuthorityV1", lambda _: object())):
            for repetition in (1, 2, 3):
                if repetition > 1:
                    runtime = rt._resume_session_runtime(context, spec)
                    self.assertIs(runtime["plant"], old["plant"])
                    self.assertIs(runtime["observer"], old["observer"])
                    self.assertIs(runtime["measurement_layer"], old["measurement_layer"])
                    self.assertIs(runtime["command_response_history"],
                                  old["command_response_history"])
                    for key in ("task_decisions", "trace", "true_physics_monitor",
                                "return_projection_finalization", "terminal_capture_hook"):
                        self.assertNotIn(key, runtime)
                    self.assertIsNot(runtime["contract"], old["contract"])
                runtime["autonomous_recovery_options"] = {"planner_process_worker": True}
                epoch = Path(f"/tmp/zero_value_lifecycle_v3/rep_{repetition:02d}")
                lifecycle = rt._start_scientific_session_epoch(
                    runtime, epoch, None, 0.0, START, resumed=repetition > 1)
                self.assertIsInstance(runtime["contract"].reference_motion_history,
                                      AppliedReferenceMotionHistory)
                self.assertEqual(runtime["wall_session"].capture_flags,
                                 [repetition == 1])
                self.assertEqual(lifecycle.version_provider().episode_epoch,
                                 str(epoch.resolve()))
                if old is not None:
                    self.assertIsNot(runtime["wall_session"], old["wall_session"])
                    self.assertIsNot(lifecycle, old["plan_lifecycle"])
                    self.assertIsNot(runtime["contract"].reference_motion_history,
                                     old["contract"].reference_motion_history)
                runtime["task_decisions"] = []
                runtime["trace"] = []
                runtime["true_physics_monitor"] = object()
                runtime["return_projection_finalization"] = {"accepted": True}
                runtime["terminal_capture_hook"] = object()
                versions.append(updater.sequence)
                # The production terminal closes the lifecycle and physics epoch
                # before it publishes this context for the next repetition.
                lifecycle.close("COMPLETE")
                runtime["wall_session"].active = False
                runtime["plant"].data.time += 5.0
                updater.sequence += 1
                context.update(runtime=runtime, updater=updater, fit=fit,
                               end_time_s=runtime["plant"].data.time,
                               final_belief=updater.snapshot())
                old = runtime
        self.assertEqual(versions, [351, 352, 353])
        self.assertEqual(updater.sequence, 354)

    def test_resume_rejects_unfinalized_or_changed_physical_time(self):
        previous = self.initial_runtime()
        previous["wall_session"] = SimpleNamespace(active=True)
        previous["plan_lifecycle"] = SimpleNamespace(_outstanding=None)
        context = {"runtime": previous, "updater": FakeUpdater(),
                   "end_time_s": previous["plant"].data.time}
        spec = SimpleNamespace(task_joint_acceleration_limit_rad_s2=np.ones(2))
        with self.assertRaisesRegex(RuntimeError, "not fully finalized"):
            rt._resume_session_runtime(context, spec)
        previous["wall_session"].active = False
        previous["plant"].data.time += 0.005
        with self.assertRaisesRegex(RuntimeError, "plant time changed"):
            rt._resume_session_runtime(context, spec)


if __name__ == "__main__":
    unittest.main()
