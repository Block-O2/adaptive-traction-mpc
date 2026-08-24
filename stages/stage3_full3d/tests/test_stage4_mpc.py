from __future__ import annotations

import numpy as np

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N, HUMAN
from traction_mpc_stage4.human_model import allocate_generalized_action
from traction_mpc_stage4.mpc import HumanMPCConfig, HumanSpaceMPC
from traction_mpc_stage4.reference import teaching_reference


def test_cuff_allocation_recovers_generalized_action_without_moment_clipping() -> None:
    q = np.radians([30.0, 50.0])
    action = np.array([45.0, -12.0])
    allocation = allocate_generalized_action(action, q, HUMAN)
    assert allocation["allocation_residual_nm"] < 1e-12
    assert allocation["force_norm_n"] < CUFF_TRANSLATIONAL_FORCE_GATE_N


def test_human_space_mpc_returns_feasible_action() -> None:
    controller = HumanSpaceMPC(HumanMPCConfig(horizon_steps=5, candidate_count=32))
    reference = teaching_reference(1.2)
    state = np.concatenate([reference.q_rad + np.radians([0.2, -0.3]), reference.dq_rad_s])
    action, diagnostics = controller.solve(state, 1.2, teaching_reference, HUMAN)
    assert diagnostics["accepted"], diagnostics
    assert diagnostics["predicted_rom_respected"]
    assert diagnostics["peak_predicted_force_n"] <= CUFF_TRANSLATIONAL_FORCE_GATE_N + 1e-7
    assert np.all(np.isfinite(action))
