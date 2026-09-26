"""Equation-equivalent native-step evaluation monitor for the runtime path.

The original monitor and its record format remain the reference. This class
only removes temporary NumPy arrays and contact sets from the per-step read.
It is evaluation-only and never supplies planner or controller inputs.
"""
from __future__ import annotations

import math

from ..fresh_qualification_v1.physics_monitor import TruePhysicsMonitor


class FastTruePhysicsMonitor(TruePhysicsMonitor):
    def observe(self, plant: object, *, integrated_step: bool = True) -> None:
        model, data = plant.model, plant.data
        shank_id = int(model.geom("shank_geom").id)
        bed_id = int(plant.bed_geom_id)
        shank_half_length = float(model.geom_size[shank_id, 1])
        shank_radius = float(model.geom_size[shank_id, 0])
        clearance = (float(data.geom_xpos[shank_id, 2])
                     - abs(float(data.geom_xmat[shank_id, 8])) * shank_half_length
                     - shank_radius - float(data.geom_xpos[bed_id, 2]))
        stage = self.stage
        self.minimum_clearance_m[stage] = min(self.minimum_clearance_m[stage], clearance)
        if integrated_step:
            self.step_count[stage] += 1
        else:
            self.boundary_observation_count[stage] += 1
        for i in range(data.ncon):
            contact = data.contact[i]
            if ((int(contact.geom1) == bed_id and int(contact.geom2) == shank_id)
                    or (int(contact.geom1) == shank_id and int(contact.geom2) == bed_id)):
                self.shank_bed_contact_steps[stage] += 1
                break
        q = data.qpos[plant.human_qpos_indices]
        human = plant.human
        if (q[0] < human.q_min_rad[0] - 1e-9 or q[1] < human.q_min_rad[1] - 1e-9
                or q[0] > human.q_max_rad[0] + 1e-9 or q[1] > human.q_max_rad[1] + 1e-9):
            self.rom_violation_steps[stage] += 1
        interface = getattr(plant, "_interface_value", None)
        wrench = getattr(interface, "human_wrench_world", None)
        if (wrench is None or getattr(wrench, "shape", None) != (6,)
                or not all(math.isfinite(float(value)) for value in wrench)):
            self.missing_interface_load_observation_count[stage] += 1
        else:
            force = math.sqrt(sum(float(v) ** 2 for v in wrench[:3]))
            moment = math.sqrt(sum(float(v) ** 2 for v in wrench[3:]))
            self.maximum_interface_force_n[stage] = max(self.maximum_interface_force_n[stage], force)
            self.maximum_interface_moment_nm[stage] = max(self.maximum_interface_moment_nm[stage], moment)
            self.interface_load_observation_count[stage] += 1
