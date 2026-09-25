"""Evaluation-only physical clearance/contact audit at every MuJoCo step.

This module is never used by estimation, waypoint planning, or safety control.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math

import numpy as np


@dataclass
class TruePhysicsMonitor:
    stage: str = "COMMISSIONING"
    minimum_clearance_m: dict[str, float] = field(default_factory=lambda: {
        "COMMISSIONING": math.inf, "ACTIVE_RECOVERY": math.inf, "TASK": math.inf})
    shank_bed_contact_steps: dict[str, int] = field(default_factory=lambda: {
        "COMMISSIONING": 0, "ACTIVE_RECOVERY": 0, "TASK": 0})
    rom_violation_steps: dict[str, int] = field(default_factory=lambda: {
        "COMMISSIONING": 0, "ACTIVE_RECOVERY": 0, "TASK": 0})
    step_count: dict[str, int] = field(default_factory=lambda: {
        "COMMISSIONING": 0, "ACTIVE_RECOVERY": 0, "TASK": 0})
    boundary_observation_count: dict[str, int] = field(default_factory=lambda: {
        "COMMISSIONING": 0, "ACTIVE_RECOVERY": 0, "TASK": 0})

    def observe(self, plant: object, *, integrated_step: bool = True) -> None:
        """Read physical truth for scoring only, after a step or at task handoff."""
        model, data = plant.model, plant.data
        shank_id = int(model.geom("shank_geom").id)
        bed_id = int(plant.bed_geom_id)
        shank_center = np.asarray(data.geom_xpos[shank_id], dtype=float)
        shank_axis = np.asarray(data.geom_xmat[shank_id], dtype=float).reshape(3, 3)[:, 2]
        shank_half_length = float(model.geom_size[shank_id, 1])
        shank_radius = float(model.geom_size[shank_id, 0])
        # The registered bed geom is a plane; its size[2] is rendering extent,
        # not a box half-height.  The signed surface is geom_xpos.z.
        bed_top = float(data.geom_xpos[bed_id, 2])
        clearance = (float(shank_center[2])
                     - abs(float(shank_axis[2])) * shank_half_length
                     - shank_radius - bed_top)
        stage = self.stage
        self.minimum_clearance_m[stage] = min(self.minimum_clearance_m[stage], clearance)
        if integrated_step:
            self.step_count[stage] += 1
        else:
            self.boundary_observation_count[stage] += 1
        if any({int(data.contact[i].geom1), int(data.contact[i].geom2)} == {bed_id, shank_id}
               for i in range(data.ncon)):
            self.shank_bed_contact_steps[stage] += 1
        q = np.asarray(data.qpos[plant.human_qpos_indices], dtype=float)
        human = plant.human
        if np.any(q < np.asarray(human.q_min_rad) - 1e-9) or np.any(q > np.asarray(human.q_max_rad) + 1e-9):
            self.rom_violation_steps[stage] += 1

    def record(self) -> dict[str, object]:
        return {
            "evaluation_only": True,
            "clearance_definition": "minimum physical shank capsule bottom minus physical bed plane; MuJoCo world z, meters",
            "contact_and_rom_count_semantics": "post-integration observations plus one task-handoff boundary observation",
            "minimum_clearance_m": {key: None if math.isinf(value) else value
                                    for key, value in self.minimum_clearance_m.items()},
            "shank_bed_contact_steps": dict(self.shank_bed_contact_steps),
            "rom_violation_steps": dict(self.rom_violation_steps),
            "step_count": dict(self.step_count),
            "boundary_observation_count": dict(self.boundary_observation_count),
        }
