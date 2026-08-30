from __future__ import annotations

import numpy as np

from traction_mpc_stage3.human import HUMAN, nominal_tracking_wrench
from traction_mpc_stage3.reference import CuffPoseReference, _world_from_cuff
from traction_mpc_stage4.human_model import inverse_dynamics, step_dynamics


def test_inverse_dynamics_matches_frozen_nominal_allocation_requirement() -> None:
    q = np.radians([27.0, 43.0])
    dq = np.radians([4.0, -7.0])
    qdd = np.radians([11.0, 17.0])
    reference = CuffPoseReference(q, dq, qdd, _world_from_cuff(q))
    expected = nominal_tracking_wrench(q, dq, reference, HUMAN)["tau_required_nm"]
    np.testing.assert_allclose(inverse_dynamics(q, dq, qdd, HUMAN), expected, atol=1e-12)


def test_rk4_transition_inverts_constant_acceleration_locally() -> None:
    q = np.radians([30.0, 50.0])
    dq = np.radians([2.0, -3.0])
    qdd = np.radians([8.0, -5.0])
    tau = inverse_dynamics(q, dq, qdd, HUMAN)
    next_state = step_dynamics(np.concatenate([q, dq]), tau, 1e-5, HUMAN)
    np.testing.assert_allclose((next_state[2:] - dq) / 1e-5, qdd, atol=2e-4)
