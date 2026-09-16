import numpy as np

from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_identification_reduced import (
    ReducedIntegralScaleIdentifier,
    ReducedShadowHumanIdentificationService,
    _session_validation_blocks,
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


def _episode(
    episode_index: int, start_time_s: float, duration_s: float, source_start: int
):
    geometry = _geometry()
    model = BaseParameterHumanModel(
        geometry, nominal_base_parameters(STAGE5_HUMAN), STAGE5_HUMAN
    )
    output = []
    local_times = np.arange(0.0, duration_s + 1.0e-12, 0.005)
    for offset, local_time in enumerate(local_times):
        q = np.radians(
            [
                15.0 + 5.0 * np.sin(3.0 * local_time),
                25.0 + 7.0 * np.sin(2.0 * local_time + 0.3),
            ]
        )
        dq = np.radians(
            [15.0 * np.cos(3.0 * local_time), 14.0 * np.cos(2.0 * local_time + 0.3)]
        )
        ddq = np.radians(
            [-45.0 * np.sin(3.0 * local_time), -28.0 * np.sin(2.0 * local_time + 0.3)]
        )
        tau = model.inverse_dynamics(q, dq, ddq)
        wrench = model.allocate_generalized_action(tau, q)["wrench_world"]
        output.append(
            {
                "time_s": float(start_time_s + local_time),
                "state": np.concatenate([q, dq]),
                "force_world_n": wrench[:3],
                "moment_world_nm": wrench[3:],
                "generalized_input_nm": tau,
                "contaminated": False,
                "source_index": source_start + offset,
                "task_phase": "OUTBOUND",
                "episode_index": episode_index,
            }
        )
    return output


def test_integral_windows_never_cross_physical_reset() -> None:
    first = _episode(0, 0.0, 0.30, 0)
    second = _episode(1, 1.0, 0.30, len(first))
    identifier = ReducedIntegralScaleIdentifier()
    combined, target, _ = identifier.integral_blocks(first + second, _geometry())
    first_matrix, first_target, _ = identifier.integral_blocks(first, _geometry())
    second_matrix, second_target, _ = identifier.integral_blocks(second, _geometry())
    np.testing.assert_allclose(combined, np.vstack([first_matrix, second_matrix]))
    np.testing.assert_allclose(target, np.concatenate([first_target, second_target]))


def test_future_validation_can_use_later_episode_without_crossing_reset() -> None:
    first = _episode(0, 0.0, 0.80, 0)
    second = _episode(1, 1.25, 0.80, len(first))
    blocks = _session_validation_blocks(
        first + second,
        fit_end_time_s=0.40,
        window_s=0.20,
        embargo_windows=1,
        count=8,
    )
    assert blocks
    assert {block["episode_index"] for block in blocks} == {0, 1}
    for block in blocks:
        source_episodes = {
            item["episode_index"]
            for item in first + second
            if item["source_index"] in block["source_indices"]
        }
        assert source_episodes == {block["episode_index"]}


def test_begin_episode_preserves_shadow_lifecycle_state() -> None:
    service = ReducedShadowHumanIdentificationService(_geometry())
    service.attempts.append({"status": "pending_future_validation"})
    service.active_challenger = service.attempts[0]
    service.begin_episode(1, 1.0)
    assert service.active_challenger is service.attempts[0]
    assert service.retained_scales.tolist() == [1.0, 1.0, 1.0]
    assert service.summary()["episode_count"] == 2
    assert service.summary()["reset_boundary_windows_forbidden"] is True


def test_episode_indices_and_session_times_must_increase() -> None:
    service = ReducedShadowHumanIdentificationService(_geometry())
    service.begin_episode(0, 0.0)
    service.last_sample_time_s = 0.5
    try:
        service.begin_episode(1, 0.4)
    except ValueError as error:
        assert "follow prior samples" in str(error)
    else:
        raise AssertionError("nonmonotonic session boundary was accepted")
