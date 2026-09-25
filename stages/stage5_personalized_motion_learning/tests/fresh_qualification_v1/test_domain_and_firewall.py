"""Pre-freeze source guards for physical variation and evaluation-only truth."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from traction_mpc_stage5.cr12_plant import Stage5CR12SensorBoundaryPlant
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.fresh_qualification_v1.domain import (
    _true_static_clearance, draw_proposal, mechanical_screen,
)
from traction_mpc_stage5.fresh_qualification_v1.physics_monitor import TruePhysicsMonitor
from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import nominal_control_model
from traction_mpc_stage5.human import STAGE5_HUMAN


STAGE5 = Path(__file__).resolve().parents[2]
NOMINAL = STAGE5 / "configs/full3d_adaptive_integration_v1/fresh_qualification_v1/development_nominal_case.json"


def test_hidden_physical_coefficients_reach_actual_cr12_mujoco_plant():
    case = json.loads(NOMINAL.read_text())
    case["physical"].update({"thigh_length_scale": 1.02, "shank_length_scale": 0.98,
                             "thigh_mass_scale": 1.09, "thigh_com_fraction": 0.46,
                             "hip_translation_xz_m": [0.005, 0.003]})
    human, geometry, spec, _ = hidden_plant(case)
    plant = Stage5CR12SensorBoundaryPlant(human, geometry=geometry)
    plant.reset(np.asarray(spec.start_return_target_rad))
    assert len(plant.actuator_ids) == 6
    assert not np.isclose(human.thigh_length_m, STAGE5_HUMAN.thigh_length_m)
    assert not np.isclose(human.thigh_mass_kg, STAGE5_HUMAN.thigh_mass_kg)
    assert np.isclose(plant.model.body("hip").mass, human.thigh_mass_kg)
    assert np.isclose(plant.model.body("shank").mass, human.shank_mass_kg)
    assert np.isclose(plant.model.body("shank").ipos[0], human.shank_com_m)
    assert np.isclose(plant.model.body("hip").ipos[0], human.thigh_com_m)
    assert np.isclose(plant.model.body("hip").pos[2], 0.065)
    assert np.isclose(geometry.world_from_human.translation[0],
                      STAGE5_GEOMETRY.world_from_human.translation[0] + 0.005)
    assert np.isclose(geometry.world_from_human.translation[2],
                      STAGE5_GEOMETRY.world_from_human.translation[2] + 0.003)
    controller = nominal_control_model()
    assert controller.geometry.thigh_length_m == STAGE5_HUMAN.thigh_length_m
    assert controller.geometry.thigh_length_m != human.thigh_length_m


def test_generation_is_deterministic_and_screen_is_pre_outcome():
    first = draw_proposal(np.random.default_rng(4711001),
                          family="balanced", range_index=0, replicate=1, proposal_index=1)
    second = draw_proposal(np.random.default_rng(4711001),
                           family="balanced", range_index=0, replicate=1, proposal_index=1)
    assert first == second
    nominal = json.loads(NOMINAL.read_text())
    assert mechanical_screen(nominal)["accepted"]
    human, geometry, spec, _ = hidden_plant(nominal)
    assert _true_static_clearance(np.asarray(spec.start_return_target_rad),
                                  human, geometry) > 0


def test_true_monitor_is_separate_evaluation_record():
    nominal = json.loads(NOMINAL.read_text())
    human, geometry, spec, _ = hidden_plant(nominal)
    plant = Stage5CR12SensorBoundaryPlant(human, geometry=geometry)
    plant.reset(np.asarray(spec.start_return_target_rad))
    monitor = TruePhysicsMonitor()
    monitor.observe(plant)
    record = monitor.record()
    assert record["evaluation_only"]
    assert record["step_count"]["COMMISSIONING"] == 1
    assert record["minimum_clearance_m"]["COMMISSIONING"] is not None
    assert np.isclose(record["minimum_clearance_m"]["COMMISSIONING"],
                      _true_static_clearance(np.asarray(spec.start_return_target_rad),
                                             human, geometry), atol=1e-10)
    monitor.stage = "TASK"
    monitor.observe(plant, integrated_step=False)
    task_record = monitor.record()
    assert task_record["step_count"]["TASK"] == 0
    assert task_record["boundary_observation_count"]["TASK"] == 1
    assert task_record["minimum_clearance_m"]["TASK"] is not None
