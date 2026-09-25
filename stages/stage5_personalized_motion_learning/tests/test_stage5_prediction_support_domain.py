from __future__ import annotations

import numpy as np

from traction_mpc_stage5.prediction_support_domain import (
    feature_block_indices,
    fit_prediction_support_domain_v1,
)


FEATURE_NAMES = (
    "robot_q_0",
    "robot_dq_0",
    "human_0",
    "cuff_position_0",
    "cuff_rotvec_0",
    "cuff_linear_velocity_0",
    "cuff_angular_velocity_0",
    "interface_displacement_0",
    "interface_velocity_0",
    "interface_rotation_0",
    "interface_angular_velocity_0",
    "measured_force_0",
    "measured_moment_0",
    "previous_action_0",
    "previous_action_delta_0",
    "shank_clearance_0",
    "robot_identity_cr12_0",
    "candidate_action_0",
    "candidate_minus_previous_0",
)


def _domain():
    development = np.asarray(
        [
            np.linspace(0.0, 1.8, len(FEATURE_NAMES)),
            np.linspace(0.1, 1.9, len(FEATURE_NAMES)),
            np.linspace(0.2, 2.0, len(FEATURE_NAMES)),
            np.linspace(0.3, 2.1, len(FEATURE_NAMES)),
        ]
    )
    development[:, FEATURE_NAMES.index("shank_clearance_0")] = 0.01
    development[:2, FEATURE_NAMES.index("robot_identity_cr12_0")] = 0.0
    development[2:, FEATURE_NAMES.index("robot_identity_cr12_0")] = 1.0
    calibration = development.copy()
    calibration[:, 0] += 0.02
    return fit_prediction_support_domain_v1(
        feature_names=FEATURE_NAMES,
        development_features=development,
        calibration_features=calibration,
        development_group_ids=("d0", "d1"),
        calibration_group_ids=("c0", "c1"),
    ), calibration


def test_feature_contract_assigns_every_nonidentity_feature() -> None:
    blocks = feature_block_indices(FEATURE_NAMES)
    assigned = set(np.concatenate(list(blocks.values())).tolist())
    identity = FEATURE_NAMES.index("robot_identity_cr12_0")
    assert assigned == set(range(len(FEATURE_NAMES))) - {identity}


def test_calibration_like_point_is_supported() -> None:
    domain, calibration = _domain()
    decision = domain.evaluate(calibration[0], causal_history_valid=True)
    assert decision.supported
    assert decision.label == "SUPPORTED"
    assert not decision.reasons


def test_contact_and_invalid_history_have_explicit_reasons() -> None:
    domain, calibration = _domain()
    feature = calibration[0].copy()
    feature[FEATURE_NAMES.index("shank_clearance_0")] = -1.0e-6
    decision = domain.evaluate(feature, causal_history_valid=False)
    assert not decision.supported
    assert "CAUSAL_HISTORY_INVALID" in decision.reasons
    assert "GEOMETRIC_CONTACT_OR_PENETRATION" in decision.reasons


def test_far_joint_context_is_unsupported_with_block_reason() -> None:
    domain, calibration = _domain()
    feature = calibration[0].copy()
    feature[FEATURE_NAMES.index("measured_force_0")] += 100.0
    decision = domain.evaluate(feature, causal_history_valid=True)
    assert not decision.supported
    assert "OUTSIDE_JOINT_DEPLOYABLE_SUPPORT" in decision.reasons
    assert "OUTSIDE_INTERFACE_LOAD_SUPPORT" in decision.reasons
