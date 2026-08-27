from __future__ import annotations

import xml.etree.ElementTree as ET

import numpy as np

from traction_mpc_stage4.distributed_cuff import (
    DistributedCuffConfig,
    DistributedCuffStage4Plant,
    build_distributed_cuff_model_xml,
    cuff_length_is_geometrically_supported,
)
from traction_mpc_stage4.human_model import registered_cold_start_perturbed_human
from traction_mpc_stage4.measurement import architecture_comparison_sensor_cases
from traction_mpc_stage4.reference import (
    CONTINUOUS_TEACHING_WAYPOINTS,
    continuous_teaching_reference,
)
from traction_mpc_stage4.sensor_realism import run_sensor_realism_case


def test_distributed_model_has_four_station_pairs_and_no_equality_constraints() -> None:
    config = DistributedCuffConfig(cuff_length_m=0.080)
    root = ET.fromstring(build_distributed_cuff_model_xml(config=config))
    equality = root.find("equality")
    assert equality is not None
    assert equality.findall("weld") == []
    assert equality.findall("connect") == []
    for index in range(4):
        assert root.find(f".//site[@name='cuff_station_{index}']") is not None
        assert root.find(f".//site[@name='shank_station_{index}']") is not None
    visual = root.find(".//geom[@name='distributed_cuff_visual']")
    assert visual is not None
    assert visual.get("fromto") == "-0.04 0 0 0.04 0 0"
    assert visual.get("contype") == "0"
    assert visual.get("conaffinity") == "0"


def test_length_weighting_and_supported_sweep_are_consistent() -> None:
    config_80 = DistributedCuffConfig(cuff_length_m=0.080)
    config_120 = DistributedCuffConfig(cuff_length_m=0.120)
    np.testing.assert_allclose(config_80.station_offsets_m, [-0.03, -0.01, 0.01, 0.03])
    np.testing.assert_allclose(config_120.station_offsets_m, [-0.045, -0.015, 0.015, 0.045])
    assert config_120.station_stiffness_n_m == 1.5 * config_80.station_stiffness_n_m
    assert config_120.station_damping_ns_m == 1.5 * config_80.station_damping_ns_m
    human, _ = registered_cold_start_perturbed_human()
    for length in (0.060, 0.080, 0.100, 0.120):
        assert cuff_length_is_geometrically_supported(human, length)
    assert not cuff_length_is_geometrically_supported(human, 0.160)


def test_resultant_wrench_is_sum_of_station_forces_and_lever_arms() -> None:
    plant = DistributedCuffStage4Plant()
    observation = plant.reset(np.radians([5.0, 10.0]))
    for _ in range(5):
        observation = plant.step()
    np.testing.assert_allclose(
        observation.cuff_force_vector_n,
        np.sum(observation.station_force_world_n, axis=0),
        atol=1e-10,
    )
    shank_positions = plant.data.site_xpos[plant.shank_station_site_ids]
    cuff_center = observation.attachment_position_m
    expected_moment = np.sum(
        np.cross(shank_positions - cuff_center, observation.station_force_world_n),
        axis=0,
    )
    np.testing.assert_allclose(
        observation.cuff_moment_vector_nm, expected_moment, atol=1e-10
    )
    assert observation.cuff_wrench_reconstruction_residual_nm < 1e-9
    expected_generalized_force = np.zeros(plant.model.nv)
    for force, cuff_id, shank_id in zip(
        observation.station_force_world_n,
        plant.cuff_station_site_ids,
        plant.shank_station_site_ids,
        strict=True,
    ):
        expected_generalized_force += (
            plant._site_pose_jacobian(int(shank_id))[:3]
            - plant._site_pose_jacobian(int(cuff_id))[:3]
        ).T @ force
    plant._apply_soft_limit()
    np.testing.assert_allclose(
        plant.data.qfrc_applied[plant.robot_dof_indices],
        expected_generalized_force[plant.robot_dof_indices],
        atol=1e-9,
    )


def test_short_distributed_cuff_architecture_a_rollout_is_finite() -> None:
    summary, trace = run_sensor_realism_case(
        architecture_comparison_sensor_cases()[0],
        duration_s=0.005,
        estimator_architecture="integral_minimal",
        reference_fn=continuous_teaching_reference,
        trajectory_label="distributed_cuff_short_smoke",
        trajectory_waypoints=CONTINUOUS_TEACHING_WAYPOINTS,
        plant_factory=lambda human: DistributedCuffStage4Plant(human),
    )
    assert summary["mechanically_completed_requested_duration"]
    assert summary["cuff_plant"]["station_direct_moments"] is False
    assert summary["cuff_plant"]["resultant_wrench_only_to_estimator_controller"] is True
    assert summary["events"]["force_gate_events"] == 0
    assert all(np.all(np.isfinite(value)) for value in trace.values())
