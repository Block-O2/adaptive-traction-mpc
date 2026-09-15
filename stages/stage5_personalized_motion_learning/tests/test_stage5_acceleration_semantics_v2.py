from __future__ import annotations

import inspect

import numpy as np

from traction_mpc_stage5.acceleration_semantics import (
    screen_cumulative_prefix_acceleration,
)
from traction_mpc_stage5.controller_interface import (
    InterfaceAwareFirstActionBatchPreview,
)
from traction_mpc_stage5.task import (
    PROVISIONAL_LOW_MODERATE_GOAL_TASK,
    task_limit_violation,
)


PREFIX_TIMES_S = np.asarray([0.005, 0.010, 0.015, 0.020])
LIMITS = np.radians([300.0, 600.0])


def _prefix_dq(acceleration_deg_s2: np.ndarray) -> np.ndarray:
    return np.radians(np.asarray(acceleration_deg_s2)) * PREFIX_TIMES_S[:, None]


def test_v2_rejects_20ms_legal_but_short_prefix_illegal_sequence() -> None:
    # q2 is 630 deg/s2 at 5 ms and decays to 500 deg/s2 cumulatively at 20 ms.
    prefix_dq = _prefix_dq(
        [[100.0, 630.0], [90.0, 590.0], [80.0, 540.0], [70.0, 500.0]]
    )
    screen = screen_cumulative_prefix_acceleration(
        np.zeros(2), prefix_dq, PREFIX_TIMES_S, LIMITS
    )
    assert np.all(np.abs(screen.acceleration_rad_s2[-1]) <= LIMITS)
    assert screen.margin_rad_s2[0, 1] < 0.0
    assert not bool(screen.feasible)


def test_v2_accepts_sequence_legal_at_all_four_prefixes() -> None:
    prefix_dq = _prefix_dq(
        [[250.0, 590.0], [220.0, 560.0], [180.0, 520.0], [150.0, 480.0]]
    )
    screen = screen_cumulative_prefix_acceleration(
        np.zeros(2), prefix_dq, PREFIX_TIMES_S, LIMITS
    )
    assert np.all(screen.margin_rad_s2 >= 0.0)
    assert bool(screen.feasible)


def test_exact_limit_threshold_matches_online_task_monitor_decision() -> None:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    exact = np.asarray(spec.task_joint_acceleration_limit_rad_s2)
    at_threshold = screen_cumulative_prefix_acceleration(
        np.zeros(2), exact[None, :] * PREFIX_TIMES_S[:, None], PREFIX_TIMES_S, exact
    )
    assert bool(at_threshold.feasible)
    assert task_limit_violation(
        spec, spec.start_return_target_rad, (0.0, 0.0), exact
    ) is None

    above = exact.copy()
    above[1] = np.nextafter(above[1], np.inf)
    above_threshold = screen_cumulative_prefix_acceleration(
        np.zeros(2), above[None, :] * PREFIX_TIMES_S[:, None], PREFIX_TIMES_S, exact
    )
    assert not bool(above_threshold.feasible)
    assert task_limit_violation(
        spec, spec.start_return_target_rad, (0.0, 0.0), above
    ) == "TASK_ACCELERATION_LIMIT"


def test_v2_online_screen_has_no_truth_or_mujoco_input() -> None:
    signature = inspect.signature(InterfaceAwareFirstActionBatchPreview.__init__)
    assert "plant" not in signature.parameters
    assert "truth" not in signature.parameters
    source = inspect.getsource(
        InterfaceAwareFirstActionBatchPreview._apply_v2_prefix_acceleration_screen
    ).lower()
    assert "mujoco" not in source
    assert "truth" not in source
