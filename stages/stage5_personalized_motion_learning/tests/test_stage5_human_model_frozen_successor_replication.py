import inspect
import json

import numpy as np
import pytest

from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.goal_mpc_smoke import (
    FIXED_HUMAN_MODEL_VERSION,
    run_goal_mpc_smoke,
)
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_model_replication import (
    FROZEN_THETA_0,
    FROZEN_THETA_1,
    FROZEN_THETA_1_VERSION,
    FrozenSuccessorArm,
    FrozenSuccessorReplicationAuthority,
    aggregate_replication_units,
)
from traction_mpc_stage5.human_model_update import fixed_one_step_pacing_status


CONFIG_PATH = (
    STAGE5_ROOT
    / "configs"
    / "stage5_human_model_frozen_successor_replication_v1.json"
)


def _geometry() -> PlanarCuffGeometry:
    rotation = STAGE5_GEOMETRY.world_from_human.rotation
    return PlanarCuffGeometry(
        origin_world_m=STAGE5_GEOMETRY.world_from_human.translation.copy(),
        plane_x_world=rotation[:, 0].copy(),
        joint_axis_world=rotation[:, 1].copy(),
        plane_z_world=rotation[:, 2].copy(),
        hip_plane_m=np.zeros(2),
        thigh_length_m=STAGE5_HUMAN.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([STAGE5_HUMAN.sleeve_center_m, 0.0]),
    )


def _payload(time_s: float, *, phase: str = "OUTBOUND") -> dict:
    return {
        "episode_time_s": time_s,
        "estimated_human_state_rad_rad_s": np.array(
            [
                0.20 + 0.03 * np.sin(time_s),
                0.35 + 0.05 * np.sin(0.7 * time_s),
                0.03 * np.cos(time_s),
                0.035 * np.cos(0.7 * time_s),
            ]
        ),
        "measured_human_cuff_force_world_n": np.zeros(3),
        "measured_human_cuff_moment_world_nm": np.zeros(3),
        "measured_generalized_human_input_nm": np.array([12.0, -3.0]),
        "task_phase": phase,
        "interface_model_version": "stage5_controller_nominal_kelvin_voigt_v1",
        "current_control_model_version": FIXED_HUMAN_MODEL_VERSION,
    }


def _adaptive_authority() -> FrozenSuccessorReplicationAuthority:
    return FrozenSuccessorReplicationAuthority(
        _geometry(),
        FrozenSuccessorArm.FROZEN_SUCCESSOR,
        replication_id="replication_01_seed_20260825",
        cem_seed=20260825,
    )


def _populate_later_history(authority: FrozenSuccessorReplicationAuthority) -> None:
    authority.observe(_payload(3.045))
    for timestamp in np.arange(3.050, 5.506, 0.005):
        phase = "OUTBOUND" if timestamp < 4.0 else "RETURN"
        payload = _payload(float(timestamp), phase=phase)
        payload["current_control_model_version"] = FROZEN_THETA_1_VERSION
        authority.observe(payload)


def test_theta_1_is_frozen_and_replication_forbids_refit() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert tuple(config["model_pair"]["theta_0"]) == FROZEN_THETA_0
    assert tuple(config["model_pair"]["theta_1"]) == FROZEN_THETA_1
    assert config["transition"]["human_identification_active"] is False
    assert "never refit" in config["model_pair"]["theta_1_source"]


def test_predecessor_arm_never_leaves_theta_0() -> None:
    authority = FrozenSuccessorReplicationAuthority(
        _geometry(),
        FrozenSuccessorArm.PREDECESSOR,
        replication_id="fixed",
        cem_seed=20260825,
    )
    for timestamp in (0.0, 3.045, 6.0):
        assert not authority.observe(_payload(timestamp))["apply_update"]
    assert authority.application_count == 0
    assert authority.active_model_version == FIXED_HUMAN_MODEL_VERSION


def test_successor_arm_performs_one_frozen_theta_0_to_theta_1_transition() -> None:
    authority = _adaptive_authority()
    assert not authority.observe(_payload(3.040))["apply_update"]
    update = authority.observe(_payload(3.045))
    assert update["apply_update"]
    assert update["model_version"] == FROZEN_THETA_1_VERSION
    assert tuple(update["transition"]["successor_scales"]) == FROZEN_THETA_1
    assert update["transition"]["successor_refit"] is False


def test_no_second_human_model_update_can_occur() -> None:
    authority = _adaptive_authority()
    assert authority.observe(_payload(3.045))["apply_update"]
    payload = _payload(3.050)
    payload["current_control_model_version"] = FROZEN_THETA_1_VERSION
    assert not authority.observe(payload)["apply_update"]
    assert authority.application_count == 1


def test_replication_gamma_remains_exactly_half() -> None:
    for timestamp in (0.0, 3.045, 9.0):
        assert fixed_one_step_pacing_status({"episode_time_s": timestamp}) == {
            "gamma": 0.5,
            "gamma_rate_per_s": 0.0,
        }


def test_acceleration_monitor_semantics_remain_on_estimation_model() -> None:
    source = inspect.getsource(run_goal_mpc_smoke)
    assert "acceleration_monitor.update(\n                task_observation, interface_state, estimation_model" in source
    authority_source = inspect.getsource(FrozenSuccessorReplicationAuthority)
    assert "acceleration_monitor" not in authority_source


def test_post_transition_evidence_starts_after_full_transition_embargo() -> None:
    authority = _adaptive_authority()
    _populate_later_history(authority)
    evidence = authority.prediction_evidence()
    valid = [item for item in evidence["blocks"] if item["valid"]]
    assert valid
    assert all(item["start_time_s"] > 3.245 for item in valid)
    assert not any(item["transition_region_overlap"] for item in valid)
    assert not any(item["future_information_used_online"] for item in valid)


def test_predecessor_and_successor_use_the_same_valid_blocks() -> None:
    authority = _adaptive_authority()
    _populate_later_history(authority)
    valid = [
        item for item in authority.prediction_evidence()["blocks"] if item["valid"]
    ]
    assert all(item["same_block_for_predecessor_and_successor"] for item in valid)
    assert all(item["predecessor_loss_nms2"] >= 0.0 for item in valid)
    assert all(item["successor_loss_nms2"] >= 0.0 for item in valid)


def test_replication_ids_and_seeds_are_isolated() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["replications"]["fixed_cem_seeds"] == [
        20260825,
        20260826,
        20260827,
    ]
    with pytest.raises(ValueError, match="unique"):
        aggregate_replication_units(
            [
                {
                    "replication_id": "same",
                    "cem_seed": 1,
                    "mean_paired_difference_nms2": -1.0,
                },
                {
                    "replication_id": "same",
                    "cem_seed": 2,
                    "mean_paired_difference_nms2": -2.0,
                },
            ]
        )


def test_aggregate_uses_rollouts_not_within_rollout_blocks_as_units() -> None:
    aggregate = aggregate_replication_units(
        [
            {
                "replication_id": "r1",
                "cem_seed": 11,
                "mean_paired_difference_nms2": -1.0,
                "valid_block_count": 100,
            },
            {
                "replication_id": "r2",
                "cem_seed": 12,
                "mean_paired_difference_nms2": -2.0,
                "valid_block_count": 200,
            },
            {
                "replication_id": "r3",
                "cem_seed": 13,
                "mean_paired_difference_nms2": 0.5,
                "valid_block_count": 300,
            },
        ]
    )
    assert aggregate["top_level_sample_size"] == 3
    assert aggregate["favorable_rollout_count"] == 2
    assert aggregate["within_rollout_blocks_pooled_as_independent"] is False
