"""Frozen engineering assumptions for the MuJoCo sleeve/robot plant V2."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class HumanV2Parameters:
    """Nominal Human V2 parameters copied from the MATLAB constructor."""

    height_m: float = 1.72
    body_mass_kg: float = 75.0
    gravity_m_s2: float = 9.81
    q_rest_rad: tuple[float, float] = (math.radians(5.0), math.radians(10.0))
    passive_stiffness_nm_rad: tuple[float, float] = (10.0, 10.0)
    passive_damping_nms_rad: tuple[float, float] = (5.0, 5.0)
    q_min_rad: tuple[float, float] = (0.0, 0.0)
    q_max_rad: tuple[float, float] = (math.radians(80.0), math.radians(100.0))

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
    def sleeve_center_m(self) -> float:
        return 0.90 * self.shank_length_m


@dataclass(frozen=True)
class RobotV2Parameters:
    """CR12-like geometry; none of these are claimed CR12 specifications."""

    model_label: str = "CR12-like-6DoF-engineering-hypothesis"
    provenance_asset: str = "assets/robots/cr12_12_pending/urdf/CR12-12.urdf"
    provenance_reusable_for_kinematics: bool = False
    base_position_m: tuple[float, float, float] = (1.10, -0.62, 0.04)
    base_column_height_m: float = 0.32
    link_lengths_m: tuple[float, float, float, float, float] = (
        0.40,
        0.38,
        0.18,
        0.12,
        0.08,
    )
    link_masses_kg: tuple[float, float, float, float, float, float] = (
        5.0,
        8.0,
        6.0,
        3.0,
        2.0,
        1.2,
    )
    joint_ranges_deg: tuple[tuple[float, float], ...] = (
        (-170.0, 170.0),
        (-125.0, 125.0),
        (-150.0, 150.0),
        (-180.0, 180.0),
        (-120.0, 120.0),
        (-180.0, 180.0),
    )
    joint_torque_limits_nm: tuple[float, float, float, float, float, float] = (
        300.0,
        300.0,
        220.0,
        100.0,
        80.0,
        60.0,
    )
    joint_damping_nms_rad: tuple[float, float, float, float, float, float] = (
        4.0,
        4.0,
        3.0,
        1.5,
        1.0,
        0.8,
    )

    @property
    def nominal_reach_m(self) -> float:
        return self.base_column_height_m + sum(self.link_lengths_m)


@dataclass(frozen=True)
class PlantV2Config:
    """Simulation, bed, sleeve, controller, and validation assumptions."""

    q_terminal_deg: float = 2.0
    q_switch_deg: float = 30.0
    actuator_cartesian_force_bound_n: float = 200.0
    force_veto_bound_n: float = 200.0
    simulation_dt_s: float = 0.001
    control_dt_s: float = 0.005

    hip_height_m: float = 0.062
    bed_height_m: float = 0.012
    thigh_radius_m: float = 0.050
    shank_radius_m: float = 0.045
    bed_friction: float = 0.70
    bed_solref_timeconst_s: float = 0.020
    bed_solref_dampratio: float = 1.0
    bed_solimp_width_m: float = 0.003

    sleeve_half_length_m: float = 0.040
    sleeve_outer_radius_m: float = 0.058
    sleeve_stiffness_n_m: float = 6000.0
    sleeve_damping_ns_m: float = 120.0
    sleeve_solimp_min: float = 0.97
    sleeve_solimp_max: float = 0.995
    sleeve_solimp_width_m: float = 0.0005

    cartesian_kp_n_m: float = 3000.0
    cartesian_kd_ns_m: float = 140.0
    nullspace_kp_nm_rad: float = 12.0
    nullspace_kd_nms_rad: float = 3.0
    jacobian_damping: float = 1e-4

    settle_max_time_s: float = 4.0
    settle_min_time_s: float = 1.0
    settle_window_s: float = 0.5
    stable_joint_speed_deg_s: float = 0.1
    stable_ee_speed_mm_s: float = 0.2
    stable_force_range_n: float = 0.5
    terminal_position_tolerance_deg: float = 1.0
    fixture_probe_displacement_m: float = 0.002
    fixture_probe_duration_s: float = 1.0
    dynamic_probe_displacement_m: float = 0.001
    dynamic_probe_duration_s: float = 1.0
    release_observation_s: float = 2.0
    preload_max_function_evaluations: int = 30
    preload_settle_s: float = 0.6
    fixture_reaction_tolerance_nm: float = 1.0

    @property
    def control_substeps(self) -> int:
        ratio = self.control_dt_s / self.simulation_dt_s
        rounded = int(round(ratio))
        if rounded < 1 or abs(ratio - rounded) > 1e-12:
            raise ValueError("control_dt_s must be an integer multiple of simulation_dt_s")
        return rounded
