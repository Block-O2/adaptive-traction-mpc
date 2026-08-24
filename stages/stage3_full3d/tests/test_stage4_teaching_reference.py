from __future__ import annotations

import numpy as np

from traction_mpc_stage4.reference import (
    COLD_START_TEACHING_DURATION_S,
    COLD_START_TEACHING_WAYPOINTS,
    TEACHING_DURATION_S,
    TEACHING_WAYPOINTS,
    cold_start_teaching_reference,
    teaching_reference,
)


def test_teaching_waypoints_and_holds_are_exact() -> None:
    assert TEACHING_DURATION_S == 18.0
    for waypoint in TEACHING_WAYPOINTS:
        reference = teaching_reference(waypoint.time_s)
        np.testing.assert_allclose(np.degrees(reference.q_rad), waypoint.q_deg, atol=1e-10)
        np.testing.assert_allclose(reference.dq_rad_s, 0.0, atol=1e-12)
        np.testing.assert_allclose(reference.ddq_rad_s2, 0.0, atol=1e-10)


def test_teaching_reference_respects_rom_and_varies_joints_independently() -> None:
    times = np.linspace(0.0, TEACHING_DURATION_S, 1801)
    q_deg = np.degrees(np.array([teaching_reference(t).q_rad for t in times]))
    assert np.all(q_deg >= np.array([0.0, 0.0]) - 1e-12)
    assert np.all(q_deg <= np.array([80.0, 100.0]) + 1e-12)
    dq = np.array([teaching_reference(t).dq_rad_s for t in times])
    velocity_ratio = np.divide(dq[:, 0], dq[:, 1], out=np.zeros(len(times)), where=np.abs(dq[:, 1]) > 1e-8)
    ratios = velocity_ratio[np.abs(dq[:, 1]) > 1e-8]
    assert np.ptp(ratios) > 0.5


def test_cold_start_reference_is_one_conservative_to_high_flexion_execution() -> None:
    assert COLD_START_TEACHING_DURATION_S == 23.0
    for waypoint in COLD_START_TEACHING_WAYPOINTS:
        reference = cold_start_teaching_reference(waypoint.time_s)
        np.testing.assert_allclose(
            np.degrees(reference.q_rad), waypoint.q_deg, atol=1e-10
        )
        np.testing.assert_allclose(reference.dq_rad_s, 0.0, atol=1e-12)
    times = np.linspace(0.0, COLD_START_TEACHING_DURATION_S, 2301)
    q_deg = np.degrees(
        np.array([cold_start_teaching_reference(time).q_rad for time in times])
    )
    assert np.max(q_deg[:, 0]) == 75.0
    assert np.max(q_deg[:, 1]) == 90.0
    assert np.all(q_deg >= np.array([0.0, 0.0]) - 1e-12)
    assert np.all(q_deg <= np.array([80.0, 100.0]) + 1e-12)
