from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from traction_mpc_stage5.architecture_recovery_v1.provenance import (
    QuantityProvenance,
    SourceClass,
    assert_deployable_session_provenance,
)


STAGE5_ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCRIPT = (
    STAGE5_ROOT
    / "scripts"
    / "architecture_recovery_v1"
    / "run_identifiability_audit.py"
)


def _audit_module():
    spec = importlib.util.spec_from_file_location("architecture_recovery_audit", AUDIT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixed_nominal_and_truth_sources_fail_loudly_for_session_geometry():
    records = (
        QuantityProvenance(
            "human_base",
            SourceClass.FIXED_NOMINAL,
            True,
            "stage5_geometry_v1",
            "provisional config",
        ),
        QuantityProvenance(
            "human_q",
            SourceClass.SIMULATION_TRUTH,
            True,
            "mujoco_state",
            "evaluation state",
        ),
    )
    with pytest.raises(ValueError, match="human_base=FIXED_NOMINAL"):
        assert_deployable_session_provenance(records)


def test_allowed_sources_pass_the_provenance_guard():
    records = tuple(
        QuantityProvenance(
            f"quantity_{source.value}",
            source,
            True,
            "v1",
            "audited evidence",
        )
        for source in (
            SourceClass.MEASURED,
            SourceClass.CALIBRATED,
            SourceClass.ONLINE_ESTIMATED,
            SourceClass.STRUCTURAL_PRIOR,
        )
    )
    assert_deployable_session_provenance(records)


def test_l2_and_cuff_fraction_are_an_exact_observation_equivalence():
    audit = _audit_module()
    l1 = 0.254 * 1.72
    l2_a, fraction_a = 0.233 * 1.72, 0.72
    l2_b = 0.46
    fraction_b = l2_a * fraction_a / l2_b
    wrench = np.array([37.0, -21.0])
    for q_deg in ((5.0, 10.0), (20.0, 35.0), (60.0, 90.0)):
        q = np.radians(q_deg)
        pose_a = audit._cuff_position(q, l1, l2_a, fraction_a)
        pose_b = audit._cuff_position(q, l1, l2_b, fraction_b)
        jac_a = audit._cuff_jacobian(q, l1, l2_a, fraction_a)
        jac_b = audit._cuff_jacobian(q, l1, l2_b, fraction_b)
        np.testing.assert_allclose(pose_a, pose_b, atol=1.0e-14, rtol=0.0)
        np.testing.assert_allclose(jac_a, jac_b, atol=1.0e-14, rtol=0.0)
        np.testing.assert_allclose(
            jac_a.T @ wrench, jac_b.T @ wrench, atol=1.0e-14, rtol=0.0
        )
        assert np.linalg.norm(
            audit._ankle_position(q, l1, l2_a)
            - audit._ankle_position(q, l1, l2_b)
        ) > 0.05


def test_in_plane_basis_and_absolute_q1_have_an_exact_gauge():
    audit = _audit_module()
    gamma = np.radians(17.0)
    basis_b = audit._rotation_2d(gamma)
    l1, l2, fraction = 0.254 * 1.72, 0.233 * 1.72, 0.72
    q = np.radians([40.0, 60.0])
    q_gauge = np.array([q[0] - gamma, q[1]])
    pose_a = audit._cuff_position(q, l1, l2, fraction)
    pose_b = basis_b @ audit._cuff_position(q_gauge, l1, l2, fraction)
    jac_a = audit._cuff_jacobian(q, l1, l2, fraction)
    jac_b = basis_b @ audit._cuff_jacobian(q_gauge, l1, l2, fraction)
    np.testing.assert_allclose(pose_a, pose_b, atol=1.0e-14, rtol=0.0)
    np.testing.assert_allclose(jac_a, jac_b, atol=1.0e-14, rtol=0.0)
