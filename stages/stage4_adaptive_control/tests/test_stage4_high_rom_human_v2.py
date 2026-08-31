from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pytest

from traction_mpc_stage3.coupled import CoupledUR10eHumanV2
from traction_mpc_stage3.human import HUMAN, soft_limit_torque
from traction_mpc_stage4.high_rom_human_v2 import (
    HIGH_ROM_HUMAN_V2,
    PRIMARY_ENDPOINT_NAMES,
    audit_passive_model,
    audit_quasistatic_paths,
    high_rom_config_payload,
)
from traction_mpc_stage4.high_rom_dynamic_pilot import (
    PILOT_DURATION_S,
    pilot_trajectories,
)
from traction_mpc_stage4.mpc import HumanSpaceMPC


def test_high_rom_variant_changes_only_the_joint_upper_limits() -> None:
    canonical = asdict(HUMAN)
    variant = asdict(HIGH_ROM_HUMAN_V2)
    assert np.degrees(HUMAN.q_max_rad) == pytest.approx([80.0, 100.0])
    assert np.degrees(HIGH_ROM_HUMAN_V2.q_max_rad) == pytest.approx(
        [125.0, 125.0]
    )
    changed = {name for name in canonical if canonical[name] != variant[name]}
    assert changed == {"q_max_rad"}


def test_endpoint_margins_keep_all_three_paths_out_of_the_new_soft_zone() -> None:
    config = high_rom_config_payload()
    assert config["upper_soft_zone_start_deg"] == pytest.approx([120.0, 120.0])
    for name in PRIMARY_ENDPOINT_NAMES:
        margins = config["trajectory_margins_deg"][name]
        assert min(margins["to_hard_upper_limit_deg"]) >= 5.0
        assert min(margins["to_upper_soft_zone_start_deg"]) >= 0.0
    np.testing.assert_allclose(
        soft_limit_torque(
            np.radians([120.0, 120.0]), np.zeros(2), HIGH_ROM_HUMAN_V2
        ),
        np.zeros(2),
        atol=1e-12,
    )
    np.testing.assert_allclose(
        soft_limit_torque(
            np.radians([125.0, 125.0]), np.zeros(2), HIGH_ROM_HUMAN_V2
        ),
        [-25.0, -25.0],
        atol=1e-9,
    )


def test_high_rom_variant_propagates_to_an_explicit_coupled_plant() -> None:
    high_rom_plant = CoupledUR10eHumanV2(HIGH_ROM_HUMAN_V2)
    canonical_plant = CoupledUR10eHumanV2()
    assert np.degrees(
        high_rom_plant.model.jnt_range[high_rom_plant.human_joint_ids, 1]
    ) == pytest.approx([125.0, 125.0])
    assert np.degrees(
        canonical_plant.model.jnt_range[canonical_plant.human_joint_ids, 1]
    ) == pytest.approx([80.0, 100.0])


def test_high_rom_passive_model_is_continuous_inward_and_dissipative() -> None:
    audit = audit_passive_model(samples_per_joint=101)
    checks = audit["global_checks"]
    assert checks["finite_over_full_rom"]
    assert checks["no_soft_limit_inside_central_region"]
    assert checks["soft_limit_inward_at_hard_boundaries"]
    assert checks["damping_dissipative"]
    assert checks["maximum_soft_boundary_continuity_jump_nm"] < 1e-12
    assert audit["joints"]["hip"][
        "total_passive_left_static_envelope_nm"
    ] == pytest.approx([-25.872664625997164, 45.94395102393195])
    assert audit["joints"]["knee"][
        "total_passive_left_static_envelope_nm"
    ] == pytest.approx([-26.74532925199433, 45.07128657790648])


def test_actual_high_rom_model_passes_three_quasistatic_force_gates() -> None:
    audit = audit_quasistatic_paths(sample_count=31)
    for name in PRIMARY_ENDPOINT_NAMES:
        path = audit["paths"][name]
        assert path["rom_valid_all_samples"]
        assert path["soft_limit_inactive_all_samples"]
        assert path["force_gate_passed"]
        assert path["classification"] == "READY FOR DYNAMIC PILOT"
        assert path["peak_cuff_force"]["n"] < 200.0


def test_high_rom_pilot_reference_uses_one_common_smooth_timing_contract() -> None:
    for trajectory in pilot_trajectories():
        start = trajectory.reference(0.0)
        target = trajectory.reference(13.0)
        final = trajectory.reference(PILOT_DURATION_S)
        np.testing.assert_allclose(np.degrees(start.q_rad), [5.0, 10.0])
        np.testing.assert_allclose(
            np.degrees(target.q_rad), trajectory.endpoint_deg
        )
        np.testing.assert_allclose(np.degrees(final.q_rad), [5.0, 10.0])
        np.testing.assert_allclose(target.dq_rad_s, np.zeros(2))
        np.testing.assert_allclose(target.ddq_rad_s2, np.zeros(2))


def test_batched_mpc_soft_limit_uses_the_explicit_model_envelope() -> None:
    q = np.radians(np.array([[90.0, 110.0], [120.0, 120.0]]))
    dq = np.zeros_like(q)
    canonical = HumanSpaceMPC._batched_soft_limit_torque(q, dq, HUMAN)
    high_rom = HumanSpaceMPC._batched_soft_limit_torque(
        q, dq, HIGH_ROM_HUMAN_V2
    )
    assert abs(canonical[0, 1]) > 25.0
    np.testing.assert_allclose(high_rom, np.zeros_like(q), atol=1e-12)
