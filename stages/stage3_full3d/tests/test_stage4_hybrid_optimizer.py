from __future__ import annotations

import numpy as np

from traction_mpc_stage3.human import HUMAN
from traction_mpc_stage4.hybrid_optimizer import (
    HybridHumanSpaceMPC,
    SmoothTemporalLocalRefiner,
    SmoothTemporalRefinementConfig,
    smooth_temporal_residuals,
)
from traction_mpc_stage4.mpc import HumanMPCConfig, HumanSpaceMPC
from traction_mpc_stage4.reference import teaching_reference


def test_smooth_stencil_uses_fixed_half_cem_floor_box() -> None:
    mpc_config = HumanMPCConfig(horizon_steps=7)
    refinement = SmoothTemporalRefinementConfig()
    residuals = smooth_temporal_residuals(mpc_config, refinement)
    assert len(residuals) == 32
    assert {item["name"] for item in residuals} == {
        f"{joint}_{basis}"
        for joint in ("hip", "knee")
        for basis in ("constant", "linear", "quadratic", "cubic")
    }
    for item in residuals:
        maximum = np.max(np.abs(item["delta_u_nm"]), axis=0)
        assert maximum[0] <= 0.5 + 1e-12
        assert maximum[1] <= 0.25 + 1e-12
        assert np.count_nonzero(maximum > 0.0) == 1


def test_refiner_rejects_infeasible_and_accepts_only_strict_improvement() -> None:
    config = HumanMPCConfig(horizon_steps=3)
    refiner = SmoothTemporalLocalRefiner(config)
    baseline = np.zeros((3, 2))
    baseline_evaluation = (10.0, 1.0, np.zeros((3, 4)))

    def evaluate(sequence: np.ndarray) -> tuple[float, float, np.ndarray | None]:
        hip_mean = float(np.mean(sequence[:, 0]))
        knee_mean = float(np.mean(sequence[:, 1]))
        if knee_mean > 0.0:
            return 1.0, -0.1, np.zeros((3, 4))
        cost = 10.0 + (hip_mean + 0.25) ** 2 - 0.25**2
        return cost, 0.5, np.zeros((3, 4))

    sequence, evaluation, diagnostics = refiner.refine(
        baseline, baseline_evaluation, evaluate
    )
    assert diagnostics["accepted"]
    assert diagnostics["feasible_candidate_evaluations"] < 32
    assert evaluation[0] < baseline_evaluation[0]
    np.testing.assert_allclose(sequence[:, 0], -0.25)


def test_refiner_returns_original_sequence_when_no_feasible_improvement() -> None:
    config = HumanMPCConfig(horizon_steps=3)
    refiner = SmoothTemporalLocalRefiner(config)
    baseline = np.arange(6, dtype=float).reshape(3, 2)
    baseline_evaluation = (4.0, 0.2, np.zeros((3, 4)))

    def evaluate(sequence: np.ndarray) -> tuple[float, float, np.ndarray | None]:
        return 4.0, 0.2, np.zeros((3, 4))

    sequence, evaluation, diagnostics = refiner.refine(
        baseline, baseline_evaluation, evaluate
    )
    np.testing.assert_array_equal(sequence, baseline)
    assert evaluation is baseline_evaluation
    assert not diagnostics["accepted"]
    assert diagnostics["objective_improvement"] == 0.0


def test_hybrid_preserves_global_cem_and_never_worsens_its_objective() -> None:
    config = HumanMPCConfig(horizon_steps=5, candidate_count=16)
    baseline = HumanSpaceMPC(config)
    hybrid = HybridHumanSpaceMPC(config)
    reference = teaching_reference(1.2)
    state = np.concatenate(
        [reference.q_rad + np.radians([0.2, -0.3]), reference.dq_rad_s]
    )
    baseline_action, baseline_diagnostics = baseline.solve(
        state, 1.2, teaching_reference, HUMAN
    )
    hybrid_action, hybrid_diagnostics = hybrid.solve(
        state, 1.2, teaching_reference, HUMAN
    )
    np.testing.assert_allclose(
        hybrid_diagnostics["global_cem_objective"],
        baseline_diagnostics["objective"],
    )
    assert hybrid_diagnostics["objective"] <= baseline_diagnostics["objective"]
    assert hybrid_diagnostics["local_refinement"]["candidate_evaluations"] == 32
    assert hybrid_diagnostics["local_refinement"]["enabled"]
    assert np.all(np.isfinite(baseline_action))
    assert np.all(np.isfinite(hybrid_action))


def test_hybrid_can_use_existing_dynamics_trust_as_eligibility_gate() -> None:
    config = HumanMPCConfig(horizon_steps=5, candidate_count=16)
    trust = {"dynamics": False}
    hybrid = HybridHumanSpaceMPC(
        config,
        refinement_eligibility=lambda: trust["dynamics"],
    )
    reference = teaching_reference(1.2)
    state = np.concatenate(
        [reference.q_rad + np.radians([0.2, -0.3]), reference.dq_rad_s]
    )
    _, before = hybrid.solve(state, 1.2, teaching_reference, HUMAN)
    assert not before["local_refinement"]["eligible"]
    assert before["local_refinement"]["candidate_evaluations"] == 0
    assert before["objective"] == before["global_cem_objective"]

    trust["dynamics"] = True
    _, after = hybrid.solve(state, 1.22, teaching_reference, HUMAN)
    assert after["local_refinement"]["eligible"]
    assert after["local_refinement"]["candidate_evaluations"] == 32
    assert after["objective"] <= after["global_cem_objective"]
