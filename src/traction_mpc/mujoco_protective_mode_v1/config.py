"""Frozen M1 model and actuator assumptions.

All values here are engineering simulation assumptions unless they are copied
verbatim from Human Model V2.  They are not clinical or hardware limits.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class HumanV2Parameters:
    """Nominal Human V2 values copied from the validated MATLAB constructor."""

    height_m: float = 1.72
    body_mass_kg: float = 75.0
    gravity_m_s2: float = 9.81

    @property
    def thigh_length_m(self) -> float:
        return 0.254 * self.height_m

    @property
    def shank_length_m(self) -> float:
        return 0.233 * self.height_m

    @property
    def thigh_mass_kg(self) -> float:
        return 0.099 * self.body_mass_kg

    @property
    def shank_mass_kg(self) -> float:
        return (0.046 + 0.014) * self.body_mass_kg

    @property
    def thigh_com_m(self) -> float:
        return 0.433 * self.thigh_length_m

    @property
    def shank_com_m(self) -> float:
        return 0.430 * self.shank_length_m

    @property
    def thigh_inertia_kg_m2(self) -> float:
        return self.thigh_mass_kg * (0.30 * self.thigh_length_m) ** 2

    @property
    def shank_inertia_kg_m2(self) -> float:
        return self.shank_mass_kg * (0.30 * self.shank_length_m) ** 2

    @property
    def cuff_location_m(self) -> float:
        return 0.90 * self.shank_length_m

    q_rest_rad: tuple[float, float] = (math.radians(5), math.radians(10))
    passive_stiffness_nm_rad: tuple[float, float] = (10.0, 10.0)
    passive_damping_nms_rad: tuple[float, float] = (5.0, 5.0)
    q_min_rad: tuple[float, float] = (0.0, 0.0)
    q_max_rad: tuple[float, float] = (math.radians(80), math.radians(100))


@dataclass(frozen=True)
class ProtectiveModeConfig:
    """M1 simulation, contact, servo, and validation assumptions."""

    q_switch_deg: float = 30.0
    q_terminal_deg: float = 2.0
    simulation_dt_s: float = 0.001
    control_dt_s: float = 0.005
    bed_start_duration_s: float = 0.50
    transition_duration_s: float = 4.0
    terminal_hold_duration_s: float = 1.0

    # Abstract x/z servo. These are M1 assumptions, not a real robot API.
    servo_kp_n_m: float = 1800.0
    servo_kd_ns_m: float = 90.0
    actuator_force_limit_n: float = 200.0
    force_veto_limit_n: float = 200.0

    # Bilateral cuff is approximated by a tension-only compliant strap.
    cuff_rest_length_m: float = 0.015
    cuff_working_extension_m: float = 0.010
    cuff_stiffness_n_m: float = 1800.0
    cuff_damping_ns_m: float = 35.0
    cuff_loss_force_n: float = 1.0
    cuff_loss_extension_m: float = 0.001

    # MuJoCo unilateral bed-contact assumptions.
    # Places the terminal thigh tangent to the bed at reset: bed + radius.
    hip_height_m: float = 0.062
    bed_height_m: float = 0.012
    thigh_radius_m: float = 0.050
    shank_radius_m: float = 0.045
    bed_friction: float = 0.70
    bed_solref_timeconst_s: float = 0.020
    bed_solref_dampratio: float = 1.0
    bed_solimp_width_m: float = 0.003

    # Engineering completeness metrics; not clinical limits.
    terminal_position_tolerance_deg: float = 1.0
    terminal_velocity_tolerance_deg_s: float = 1.0
    stable_bed_force_n: float = 2.0
    chatter_transition_limit: int = 8
    command_jump_tolerance_m: float = 1e-9
    command_velocity_jump_tolerance_m_s: float = 1e-8

    @property
    def control_substeps(self) -> int:
        ratio = self.control_dt_s / self.simulation_dt_s
        rounded = int(round(ratio))
        if abs(ratio - rounded) > 1e-12 or rounded < 1:
            raise ValueError("control_dt_s must be a positive integer multiple of simulation_dt_s")
        return rounded

    def with_switch(self, q_switch_deg: float) -> "ProtectiveModeConfig":
        from dataclasses import replace

        return replace(self, q_switch_deg=float(q_switch_deg))
