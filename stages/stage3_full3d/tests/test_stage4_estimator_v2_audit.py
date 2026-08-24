from __future__ import annotations

import numpy as np

from traction_mpc_stage4.estimator_v2_audit import (
    AUDIT_WAYPOINTS,
    DYNAMIC_BASE_PARAMETER_NAMES,
    audit_joint_reference,
    run_estimator_v2_observability_audit,
)


def test_high_flexion_audit_trajectory_is_smooth_independent_and_inside_rom() -> None:
    times = np.linspace(0.0, 18.0, 1801)
    q = np.array([audit_joint_reference(float(time))[0] for time in times])
    dq = np.array([audit_joint_reference(float(time))[1] for time in times])
    np.testing.assert_allclose(np.degrees(np.max(q, axis=0)), [75.0, 90.0], atol=1e-10)
    assert np.max(np.degrees(q[:, 0])) < 80.0
    ratios = np.divide(
        dq[:, 0],
        dq[:, 1],
        out=np.zeros(len(times)),
        where=np.abs(dq[:, 1]) > 1e-8,
    )
    assert np.ptp(ratios[np.abs(dq[:, 1]) > 1e-8]) > 1.0
    for time, q_deg, _ in AUDIT_WAYPOINTS:
        reference = audit_joint_reference(time)
        np.testing.assert_allclose(np.degrees(reference[0]), q_deg, atol=1e-10)
        np.testing.assert_allclose(reference[1], 0.0, atol=1e-12)


def test_estimator_v2_audit_distinguishes_batch_rank_from_causal_readiness() -> None:
    result = run_estimator_v2_observability_audit()
    kinematics = result["kinematic_observability"]["cumulative_rank"]
    assert kinematics["1"]["nullity"] == 4
    assert kinematics["18"]["nullity"] == 0
    dynamics = result["dynamic_base_identifiability"]
    assert dynamics["full_history"]["rank"] == len(DYNAMIC_BASE_PARAMETER_NAMES)
    assessment = result["one_shot_causal_assessment"]
    assert assessment["batch_history_structurally_sufficient"]
    assert not assessment["causal_first_execution_controller_ready"]
    assert not assessment["implementation_or_rollout_authorized_by_audit"]
