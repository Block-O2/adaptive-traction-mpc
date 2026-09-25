from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from traction_mpc_stage5.baseline_replay import Stage5SensorBoundaryPlant
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.matched_branch import (
    BranchCoordination,
    ShortBranchSpec,
    capture_runtime_snapshot,
    restore_runtime_snapshot,
)
from traction_mpc_stage5.task import TaskPhase


CONFIG = STAGE5_ROOT / "configs" / "stage5_matched_short_branch_v1.json"


def _spec(phase: TaskPhase, branch: BranchCoordination) -> ShortBranchSpec:
    return ShortBranchSpec(
        anchor_name="test",
        phase=phase,
        minimum_progress=0.5,
        duration_s=0.2,
        hip_bias_nm=0.4,
        knee_bias_nm=0.25,
        coordination=branch,
    )


@pytest.mark.parametrize(
    ("phase", "branch", "expected"),
    [
        (TaskPhase.OUTBOUND, BranchCoordination.HIP_LEADING, [0.4, -0.25]),
        (TaskPhase.OUTBOUND, BranchCoordination.BALANCED, [0.0, 0.0]),
        (TaskPhase.OUTBOUND, BranchCoordination.KNEE_LEADING, [-0.4, 0.25]),
        (TaskPhase.RETURN, BranchCoordination.HIP_LEADING, [-0.4, 0.25]),
        (TaskPhase.RETURN, BranchCoordination.KNEE_LEADING, [0.4, -0.25]),
    ],
)
def test_branch_bias_is_phase_relative(phase, branch, expected) -> None:
    assert np.array_equal(_spec(phase, branch).action_bias_nm(), expected)


def test_complete_runtime_snapshot_restores_exact_decision_state() -> None:
    plant = Stage5SensorBoundaryPlant(STAGE5_HUMAN)
    plant.reset(np.radians([5.0, 10.0]))
    graph = {
        "human_estimator": {"history": [np.arange(4.0)]},
        "interface_observer": {"history": [np.arange(12.0)]},
        "mpc": {
            "warm_start": np.arange(16.0).reshape(8, 2),
            "rng": np.random.default_rng(20260917),
        },
        "acceleration_monitor": {"history": [np.array([1.0, 2.0])]},
        "safety": {"previous_status": "TRACK"},
    }
    runtime = {
        "task": {"phase": "OUTBOUND", "hold_elapsed_s": 0.0},
        "current_action": np.array([3.0, 4.0]),
        "support_command": np.array([2.0, 3.0]),
    }
    snapshot = capture_runtime_snapshot(
        plant=plant,
        controller_graph=graph,
        runtime_state=runtime,
        deployable_start={"estimated_state": [0.1, 0.2, 0.0, 0.0]},
    )
    original_integration = snapshot.plant.integration_state.copy()
    plant.data.qpos[:] += 0.1
    plant.last_force[:] = 9.0
    graph["mpc"]["warm_start"][:] = -1.0
    runtime["current_action"][:] = -2.0

    restored_graph, restored_runtime = restore_runtime_snapshot(plant, snapshot)

    assert np.array_equal(
        snapshot.plant.integration_state, original_integration
    )
    assert np.array_equal(
        restored_graph["mpc"]["warm_start"], np.arange(16.0).reshape(8, 2)
    )
    assert np.array_equal(restored_runtime["current_action"], [3.0, 4.0])
    assert restored_graph is not snapshot.controller_graph
    assert restored_runtime is not snapshot.runtime_state


def test_preregistered_contract_freezes_isolation_and_timing() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    condition = config["fixed_condition"]
    assert config["schema"] == "stage5_matched_short_branch_v1"
    assert config["source_personalization_policy"] == {
        "model_update_alpha": 0.25,
        "maximum_per_scale_step": 0.04,
        "frozen_for_this_study": True,
    }
    assert condition["human_model_updates_enabled"] is False
    assert condition["trust_to_gamma_authority"] is False
    assert condition["gamma"] == 0.5
    assert condition["interface"] == "fixed_nominal"
    assert condition["learned_value_or_actor_control"] is False
    assert config["matched_units"]["branches"] == [
        "hip_leading",
        "balanced",
        "knee_leading",
    ]
    assert [row["name"] for row in config["matched_units"]["anchors"]] == [
        "early_outbound",
        "mid_outbound",
        "mid_return",
    ]
    assert (
        config["timing_contract"]["faster_completion_alone_is_path_benefit"]
        is False
    )
    assert config["future_shadow_value_if_br_a"]["control_connection"] is False


def test_snapshot_payload_does_not_require_truth_in_deployable_record() -> None:
    plant = Stage5SensorBoundaryPlant(STAGE5_HUMAN)
    plant.reset(np.radians([5.0, 10.0]))
    deployable = {
        "q_hat": [0.1, 0.2],
        "dq_hat": [0.0, 0.0],
        "plant_truth_in_deployable_record": False,
    }
    snapshot = capture_runtime_snapshot(
        plant=plant,
        controller_graph={"controller": deepcopy(deployable)},
        runtime_state={"task_phase": "OUTBOUND"},
        deployable_start=deployable,
    )
    assert snapshot.deployable_start == deployable
    assert "human_q_rad" not in snapshot.deployable_start
