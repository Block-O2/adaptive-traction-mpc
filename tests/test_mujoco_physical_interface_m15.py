"""Contracts for the M1.5 physical-interface engineering diagnostics."""

from __future__ import annotations

import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")

from traction_mpc.mujoco_protective_mode_v1.config import (
    HumanV2Parameters,
    ProtectiveModeConfig,
)
from traction_mpc.mujoco_protective_mode_v1.model import build_mjcf
from traction_mpc.mujoco_protective_mode_v1.physical_interface_m15 import (
    INTERFACES,
    PROBE_POSTURES_DEG,
    PhysicalInterfaceEnvironment,
    run_authority_probe,
    run_bed_start_equilibrium,
)


def test_interface_topologies_keep_common_robot_and_scientific_bounds() -> None:
    parameters = HumanV2Parameters()
    config = ProtectiveModeConfig()
    tension = mujoco.MjModel.from_xml_string(build_mjcf(parameters, config, "tension_only"))
    bilateral = mujoco.MjModel.from_xml_string(
        build_mjcf(parameters, config, "bilateral_point")
    )
    assert tension.nu == bilateral.nu == 2
    assert tension.neq == 0
    assert bilateral.neq == 1
    assert tension.tendon_stiffness[0] == pytest.approx(config.cuff_stiffness_n_m)
    assert bilateral.tendon_stiffness[0] == 0.0
    assert bilateral.eq_solref[0] == pytest.approx(
        [-config.cuff_stiffness_n_m, -config.cuff_damping_ns_m]
    )
    np.testing.assert_allclose(
        tension.actuator_ctrlrange,
        [[-200.0, 200.0], [-200.0, 200.0]],
    )
    np.testing.assert_allclose(bilateral.actuator_ctrlrange, tension.actuator_ctrlrange)


def test_unknown_interface_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported cuff interface"):
        build_mjcf(HumanV2Parameters(), ProtectiveModeConfig(), "invented_hardware")
    with pytest.raises(ValueError, match="unsupported cuff interface"):
        PhysicalInterfaceEnvironment("invented_hardware")


def test_bed_start_settles_but_not_at_requested_terminal() -> None:
    result = run_bed_start_equilibrium()
    metrics = result.metrics
    assert metrics["classification"] == "SETTLED_OFF_REQUESTED_TERMINAL"
    assert metrics["dynamics_settled"] is True
    assert metrics["terminal_held"] is False
    assert metrics["settled_q_deg"][1] == pytest.approx(0.713896, abs=1e-4)
    assert metrics["peak_bed_force_n"] > 400.0
    assert metrics["first_half_second_contact_count_transitions"] > 0
    assert metrics["last_half_second_contact_count_transitions"] == 0
    assert metrics["generalized_force_balance"]["residual_norm_nm"] < 1e-10


@pytest.mark.parametrize("interface", INTERFACES)
@pytest.mark.parametrize("q2_deg", PROBE_POSTURES_DEG)
@pytest.mark.parametrize("direction_sign", (-1, 1))
def test_local_probe_keeps_force_bound_and_reports_paired_authority(
    interface: str,
    q2_deg: float,
    direction_sign: int,
) -> None:
    result = run_authority_probe(interface, q2_deg, direction_sign)
    metrics = result.metrics
    assert metrics["peak_actuator_axis_force_n"] <= 200.0 + 1e-9
    assert metrics["force_veto_triggered"] is False
    assert np.isfinite(metrics["effective_delta_q2_deg_per_mm"])
    assert np.isfinite(metrics["effective_force_per_displacement_n_per_mm"])
    assert metrics["initial_posture_not_equilibrium"] is True


def test_tension_only_and_bilateral_probes_do_not_yet_show_correct_signed_authority() -> None:
    for interface in INTERFACES:
        results = [
            run_authority_probe(interface, q2_deg, direction)
            for q2_deg in PROBE_POSTURES_DEG
            for direction in (-1, 1)
        ]
        assert all(
            result.metrics["effective_delta_q2_deg_per_mm"] < 0.0
            for result in results
        )
