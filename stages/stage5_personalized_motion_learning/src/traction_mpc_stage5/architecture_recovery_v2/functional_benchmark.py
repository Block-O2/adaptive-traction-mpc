"""Truth-firewalled reduced Human-V2 closed-loop benchmark for V2 development.

This benchmark deliberately uses the verified Human-V2 equations and Stage-4
Human-space CEM MPC while omitting the detailed robot/interface predictor.  It
tests the control-sufficient adaptation boundary before modern Stage-5
integration.  Plant truth is contained in ``HiddenSetup`` and evaluation only;
deployable estimator/controller objects never receive it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
from typing import Any, Callable, Literal

import numpy as np

from traction_mpc_stage3.executable_command import ExecutableCommandPreview
from traction_mpc_stage3.frames import RigidTransform
from traction_mpc_stage3.human import HUMAN, HumanV2Parameters, soft_limit_torque
from traction_mpc_stage3.reference import CuffPoseReference, quintic_progress
from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    dynamic_regressor_row,
    nominal_base_parameters,
)
from traction_mpc_stage4.human_model import ScaledHumanV2
from traction_mpc_stage4.mpc import HumanMPCConfig, HumanSpaceMPC
from traction_mpc_stage5.full3d_adaptive_integration_v1.time_contract import (
    build_boundary_time_grid,
)

from .effective_model import (
    CausalEffectiveGeometryEstimator,
    EffectiveGeometryFit,
    OnlineEffectiveDynamicsIdentifier,
    build_planar_geometry,
)


Arm = Literal[
    "oracle",
    "adaptive",
    "adaptive_state_residual",
    "adaptive_phase_banked_residual",
    "commissioning_beta_residual",
    "commissioning_only_dynamics",
    "fixed_nominal",
    "wrong_geometry_adaptive_dynamics",
    "no_dynamics_adaptation",
]
CONTROLLER_RANDOM_SEED = 20260824
PROBE_TRANSLATION_KP_N_PER_M = 2400.0
PROBE_TRANSLATION_KD_N_S_PER_M = 150.0
PROBE_FORCE_LIMIT_N = 180.0
PROBE_ORIENTATION_KP_NM_PER_RAD = 70.0
PROBE_ORIENTATION_KD_NM_S_PER_RAD = 6.0
PROBE_MOMENT_LIMIT_NM = 30.0
PROBE_SETTLE_TRANSLATION_KD_N_S_PER_M = 75.0
PROBE_SETTLE_ORIENTATION_KD_NM_S_PER_RAD = 3.0
PROBE_INTERIOR_DELTA_DEG = np.array([20.0, 20.0])
COMMISSIONING_CONSISTENCY_MARGIN_DEG = 15.0
# The nominal first-pose construction gives q1=10 deg.  Across the frozen
# initial domain q1 differs by at most 8 deg, and the registered soft-limit
# layer is 5 deg.  A further 2 deg covers pose-noise/IK numerical sensitivity.
# This is a causal consistency envelope, not an exact Human-ROM guarantee.
COMMISSIONING_TARGET_Q_MIN_DEG = np.array([10.0, 2.0])
COMMISSIONING_TARGET_Q_MAX_DEG = np.array([38.0, 59.0])
BOUNDED_KNEE_LEAD_PROFILE = "knee_led_clearance_constrained_v1"
BOUNDED_KNEE_LEAD_MIDPOINT_PROGRESS = np.array([0.65, 0.72])
INTEGRATION_MAX_STEP_S = 0.005
STATE_RESIDUAL_VELOCITY_SCALE_RAD_S = 1.0

DEFAULT_GENERATION_DOMAIN: dict[str, Any] = {
    "patient_height_scale": [0.88, 1.12],
    "patient_mass_scale": [0.78, 1.28],
    "passive_stiffness_scale": [0.65, 1.45],
    "passive_damping_scale": [0.70, 1.35],
    "rest_offset_q_deg": [[-4.0, -5.0], [5.0, 6.0]],
    "thigh_com_scale": [0.88, 1.12],
    "shank_com_scale": [0.86, 1.14],
    "hip_placement_x_m": [-0.12, 0.12],
    "hip_placement_z_m": [0.045, 0.16],
    "cuff_fraction_of_shank": [0.52, 0.88],
    "initial_q_deg": [[6.0, 10.0], [18.0, 28.0]],
    "task_profiles": [
        "coordinated",
        "hip_lead",
        BOUNDED_KNEE_LEAD_PROFILE,
        "two_rate",
    ],
    "standard_goal_q_deg": [[35.0, 48.0], [62.0, 78.0]],
    "high_rom_goal_q_deg": [[66.0, 82.0], [75.0, 95.0]],
    "standard_duration_s": [9.0, 12.0],
    "high_rom_duration_s": [12.0, 15.0],
    "measurement_position_std_m": 1.5e-4,
    "measurement_angle_std_deg": 0.03,
    "measurement_twist_assumption": "ideal_noiseless_simulated_derivative",
    "bed_height_m": 0.012,
    "shank_radius_m": 0.045,
    "minimum_reference_clearance_m": None,
    "generation_static_force_peak_n_maximum": None,
    "generation_static_moment_peak_nm_maximum": None,
    "generation_max_attempts": 1000,
}


@dataclass(frozen=True)
class HiddenSetup:
    """Simulation-only hidden plant setup; never pass this to deployable code."""

    seed: int
    human: HumanV2Parameters
    beta: np.ndarray
    geometry: PlanarCuffGeometry
    full_shank_length_m: float
    cuff_fraction: float
    initial_q_rad: np.ndarray
    measurement_position_std_m: float
    measurement_angle_std_rad: float
    bed_height_m: float
    shank_radius_m: float
    generation_attempt: int
    generator_draw_seed: int
    generation_min_reference_clearance_m: float | None
    generation_static_force_peak_n: float | None
    generation_static_moment_peak_nm: float | None
    generation_dynamic_force_peak_n: float | None
    generation_dynamic_moment_peak_nm: float | None
    generation_rejection_counts: dict[str, int]

    def evaluation_record(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "height_m": self.human.height_m,
            "body_mass_kg": self.human.body_mass_kg,
            "full_shank_length_m": self.full_shank_length_m,
            "cuff_fraction": self.cuff_fraction,
            "effective_knee_to_cuff_m": self.geometry.cuff_distance_m,
            "hip_xz_m": self.geometry.hip_plane_m.tolist(),
            "initial_q_deg": np.degrees(self.initial_q_rad).tolist(),
            "generation_attempt": self.generation_attempt,
            "generator_draw_seed": self.generator_draw_seed,
            "generation_min_reference_clearance_m": (
                self.generation_min_reference_clearance_m
            ),
            "generation_static_force_peak_n": self.generation_static_force_peak_n,
            "generation_static_moment_peak_nm": (
                self.generation_static_moment_peak_nm
            ),
            "generation_dynamic_force_peak_n": (
                self.generation_dynamic_force_peak_n
            ),
            "generation_dynamic_moment_peak_nm": (
                self.generation_dynamic_moment_peak_nm
            ),
            "generation_reference_basis": (
                "pre_probe_hidden_initial_state_evaluation_only"
            ),
            "generation_rejection_counts": dict(self.generation_rejection_counts),
        }


@dataclass(frozen=True)
class TaskSpec:
    """Explicit allowed reference input, separate from hidden plant truth."""

    task_id: str
    goal_q_rad: np.ndarray
    duration_s: float
    high_rom: bool
    generation_seed: int

    def record(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal_q_deg": np.degrees(self.goal_q_rad).tolist(),
            "duration_s": self.duration_s,
            "high_rom": self.high_rom,
            "generation_seed": self.generation_seed,
        }


def make_benchmark_case(
    setup_seed: int,
    *,
    task_seed: int | None = None,
    high_rom: bool = False,
    task_profile: str | None = None,
    domain: dict[str, Any] | None = None,
) -> tuple[HiddenSetup, TaskSpec]:
    """Generate independent hidden plant truth and allowed task input."""

    resolved = {**DEFAULT_GENERATION_DOMAIN, **(domain or {})}
    if task_seed is None:
        task_seed = setup_seed + 1_000_000
    minimum_clearance = resolved.get("minimum_reference_clearance_m")
    static_force_limit = resolved.get("generation_static_force_peak_n_maximum")
    static_moment_limit = resolved.get("generation_static_moment_peak_nm_maximum")
    if (
        minimum_clearance is not None
        or static_force_limit is not None
        or static_moment_limit is not None
    ):
        unconditioned_domain = dict(resolved)
        unconditioned_domain["minimum_reference_clearance_m"] = None
        unconditioned_domain["generation_static_force_peak_n_maximum"] = None
        unconditioned_domain["generation_static_moment_peak_nm_maximum"] = None
        maximum_attempts = int(resolved["generation_max_attempts"])
        rejection_counts = {
            "clearance": 0,
            "static_force": 0,
            "static_moment": 0,
            "combined_rejected_proposal": 0,
        }
        for attempt in range(maximum_attempts):
            draw_seed = (
                setup_seed
                if attempt == 0
                else int(
                    np.random.SeedSequence([setup_seed, attempt]).generate_state(1)[0]
                )
            )
            candidate, candidate_task = make_benchmark_case(
                draw_seed,
                task_seed=task_seed,
                high_rom=high_rom,
                task_profile=task_profile,
                domain=unconditioned_domain,
            )
            clearance = _minimum_hidden_clearance_over_reference(
                candidate, candidate_task
            )
            static_force, static_moment = _maximum_hidden_static_wrench_over_reference(
                candidate, candidate_task
            )
            clearance_ok = (
                minimum_clearance is None or clearance >= float(minimum_clearance)
            )
            force_ok = (
                static_force_limit is None or static_force <= float(static_force_limit)
            )
            moment_ok = (
                static_moment_limit is None
                or static_moment <= float(static_moment_limit)
            )
            if clearance_ok and force_ok and moment_ok:
                dynamic_force, dynamic_moment = (
                    _maximum_hidden_dynamic_wrench_over_reference(
                        candidate, candidate_task
                    )
                )
                return (
                    replace(
                        candidate,
                        seed=setup_seed,
                        generation_attempt=attempt,
                        generator_draw_seed=draw_seed,
                        generation_min_reference_clearance_m=clearance,
                        generation_static_force_peak_n=static_force,
                        generation_static_moment_peak_nm=static_moment,
                        generation_dynamic_force_peak_n=dynamic_force,
                        generation_dynamic_moment_peak_nm=dynamic_moment,
                        generation_rejection_counts=rejection_counts.copy(),
                    ),
                    candidate_task,
                )
            rejection_counts["clearance"] += int(not clearance_ok)
            rejection_counts["static_force"] += int(not force_ok)
            rejection_counts["static_moment"] += int(not moment_ok)
            rejection_counts["combined_rejected_proposal"] += 1
        raise RuntimeError(
            "physics-feasible setup generation exhausted frozen attempt budget"
        )
    setup_rng = np.random.default_rng(setup_seed)
    task_rng = np.random.default_rng(task_seed)
    height_scale = setup_rng.uniform(*resolved["patient_height_scale"])
    mass_scale = setup_rng.uniform(*resolved["patient_mass_scale"])
    height = HUMAN.height_m * height_scale
    body_mass = HUMAN.body_mass_kg * mass_scale
    stiffness_scale = setup_rng.uniform(*resolved["passive_stiffness_scale"])
    damping_scale = setup_rng.uniform(*resolved["passive_damping_scale"])
    rest_offset = np.radians(
        setup_rng.uniform(*np.asarray(resolved["rest_offset_q_deg"], dtype=float))
    )
    human = ScaledHumanV2(
        height_m=height,
        body_mass_kg=body_mass,
        q_rest_rad=tuple(np.asarray(HUMAN.q_rest_rad) + rest_offset),
        passive_stiffness_nm_rad=tuple(
            np.asarray(HUMAN.passive_stiffness_nm_rad) * stiffness_scale
        ),
        passive_damping_nms_rad=tuple(
            np.asarray(HUMAN.passive_damping_nms_rad) * damping_scale
        ),
        thigh_com_scale=setup_rng.uniform(*resolved["thigh_com_scale"]),
        shank_com_scale=setup_rng.uniform(*resolved["shank_com_scale"]),
        sleeve_center_scale=1.0,
    )
    full_shank = human.shank_length_m
    cuff_fraction = setup_rng.uniform(*resolved["cuff_fraction_of_shank"])
    effective_cuff = full_shank * cuff_fraction
    hip = np.array(
        [
            setup_rng.uniform(*resolved["hip_placement_x_m"]),
            setup_rng.uniform(*resolved["hip_placement_z_m"]),
        ]
    )
    geometry = PlanarCuffGeometry(
        origin_world_m=np.zeros(3),
        plane_x_world=np.array([1.0, 0.0, 0.0]),
        joint_axis_world=np.array([0.0, 1.0, 0.0]),
        plane_z_world=np.array([0.0, 0.0, 1.0]),
        hip_plane_m=hip,
        thigh_length_m=human.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([effective_cuff, 0.0]),
    )
    initial_q = np.radians(
        setup_rng.uniform(*np.asarray(resolved["initial_q_deg"], dtype=float))
    )
    task_ids = tuple(str(value) for value in resolved["task_profiles"])
    if task_profile is not None and task_profile not in task_ids:
        raise ValueError(f"task_profile {task_profile!r} is outside the frozen domain")
    task_id = str(task_rng.choice(task_ids) if task_profile is None else task_profile)
    if high_rom:
        goal_deg = task_rng.uniform(
            *np.asarray(resolved["high_rom_goal_q_deg"], dtype=float)
        )
        duration = task_rng.uniform(*resolved["high_rom_duration_s"])
    else:
        goal_deg = task_rng.uniform(
            *np.asarray(resolved["standard_goal_q_deg"], dtype=float)
        )
        duration = task_rng.uniform(*resolved["standard_duration_s"])
    setup = HiddenSetup(
        seed=setup_seed,
        human=human,
        beta=nominal_base_parameters(human),
        geometry=geometry,
        full_shank_length_m=full_shank,
        cuff_fraction=cuff_fraction,
        initial_q_rad=initial_q,
        measurement_position_std_m=float(resolved["measurement_position_std_m"]),
        measurement_angle_std_rad=math.radians(
            float(resolved["measurement_angle_std_deg"])
        ),
        bed_height_m=float(resolved["bed_height_m"]),
        shank_radius_m=float(resolved["shank_radius_m"]),
        generation_attempt=0,
        generator_draw_seed=setup_seed,
        generation_min_reference_clearance_m=None,
        generation_static_force_peak_n=None,
        generation_static_moment_peak_nm=None,
        generation_dynamic_force_peak_n=None,
        generation_dynamic_moment_peak_nm=None,
        generation_rejection_counts={},
    )
    task = TaskSpec(
        task_id=task_id,
        goal_q_rad=np.radians(goal_deg),
        duration_s=duration,
        high_rom=high_rom,
        generation_seed=task_seed,
    )
    return setup, task


def _hidden_shank_clearance_m(setup: HiddenSetup, q_rad: np.ndarray) -> float:
    q1, q2 = np.asarray(q_rad, dtype=float)
    knee_z = (
        float(setup.geometry.hip_plane_m[1])
        + setup.human.thigh_length_m * math.sin(q1)
    )
    ankle_z = knee_z + setup.full_shank_length_m * math.sin(q1 - q2)
    return float(
        min(knee_z, ankle_z) - setup.shank_radius_m - setup.bed_height_m
    )


def _minimum_hidden_clearance_over_reference(
    setup: HiddenSetup,
    task: TaskSpec,
    *,
    sample_count: int = 301,
) -> float:
    reference = make_task_reference(
        setup.initial_q_rad,
        task.goal_q_rad,
        task.task_id,
        task.duration_s,
        setup.geometry,
    )
    return float(
        min(
            _hidden_shank_clearance_m(setup, reference(time_s).q_rad)
            for time_s in np.linspace(0.0, task.duration_s, sample_count)
        )
    )


def _minimum_hidden_clearance_for_constructed_reference_evaluation_only(
    setup: HiddenSetup,
    reference: Callable[[float], CuffPoseReference],
    duration_s: float,
    *,
    sample_count: int = 301,
) -> float:
    """Audit an issued reference without exposing the result to control."""

    return float(
        min(
            _hidden_shank_clearance_m(setup, reference(time_s).q_rad)
            for time_s in np.linspace(0.0, duration_s, sample_count)
        )
    )


def _maximum_hidden_static_wrench_over_reference(
    setup: HiddenSetup,
    task: TaskSpec,
    *,
    sample_count: int = 101,
) -> tuple[float, float]:
    reference = make_task_reference(
        setup.initial_q_rad,
        task.goal_q_rad,
        task.task_id,
        task.duration_s,
        setup.geometry,
    )
    model = BaseParameterHumanModel(setup.geometry, setup.beta, setup.human)
    force_peak = 0.0
    moment_peak = 0.0
    for time_s in np.linspace(0.0, task.duration_s, sample_count):
        q = reference(time_s).q_rad
        tau = model.inverse_dynamics(q, np.zeros(2), np.zeros(2))
        allocation = model.allocate_generalized_action(tau, q)
        force_peak = max(
            force_peak,
            float(np.linalg.norm(np.asarray(allocation["force_world_n"]))),
        )
        moment_peak = max(
            moment_peak,
            float(
                np.linalg.norm(np.asarray(allocation["wrench_world"], dtype=float)[3:])
            ),
        )
    return force_peak, moment_peak


def _maximum_hidden_dynamic_wrench_over_reference(
    setup: HiddenSetup,
    task: TaskSpec,
    *,
    sample_count: int = 301,
) -> tuple[float, float]:
    """Evaluation-only inverse-dynamics demand along the complete reference."""

    reference = make_task_reference(
        setup.initial_q_rad,
        task.goal_q_rad,
        task.task_id,
        task.duration_s,
        setup.geometry,
    )
    model = BaseParameterHumanModel(setup.geometry, setup.beta, setup.human)
    force_peak = 0.0
    moment_peak = 0.0
    for time_s in np.linspace(0.0, task.duration_s, sample_count):
        sample = reference(time_s)
        tau = model.inverse_dynamics(
            sample.q_rad, sample.dq_rad_s, sample.ddq_rad_s2
        )
        allocation = model.allocate_generalized_action(tau, sample.q_rad)
        force_peak = max(
            force_peak,
            float(np.linalg.norm(np.asarray(allocation["force_world_n"]))),
        )
        moment_peak = max(
            moment_peak,
            float(
                np.linalg.norm(
                    np.asarray(allocation["wrench_world"], dtype=float)[3:]
                )
            ),
        )
    return force_peak, moment_peak


def _pose_observation(
    geometry: PlanarCuffGeometry,
    q_rad: np.ndarray,
    dq_rad_s: np.ndarray,
    rng: np.random.Generator,
    position_std_m: float,
    angle_std_rad: float,
) -> tuple[np.ndarray, float, np.ndarray, float]:
    pose = geometry.cuff_pose(q_rad)
    linear, angular = geometry.cuff_velocity(q_rad, dq_rad_s)
    position = pose.translation[[0, 2]] + rng.normal(0.0, position_std_m, size=2)
    phi = float(q_rad[0] - q_rad[1] + rng.normal(0.0, angle_std_rad))
    velocity = linear[[0, 2]]
    phi_dot = float(dq_rad_s[0] - dq_rad_s[1] + angular[1] * 0.0)
    return position, phi, velocity, phi_dot


def _wrench_to_generalized(
    geometry: PlanarCuffGeometry,
    q_rad: np.ndarray,
    force_xz_n: np.ndarray,
    moment_y_nm: float,
) -> np.ndarray:
    return geometry.generalized_input_from_wrench(
        q_rad,
        np.array([force_xz_n[0], 0.0, force_xz_n[1]]),
        np.array([0.0, moment_y_nm, 0.0]),
    )


def _inside_registered_rom(q_rad: np.ndarray) -> bool:
    q = np.asarray(q_rad, dtype=float)
    return bool(
        q.shape == (2,)
        and np.all(np.isfinite(q))
        and np.all(q >= np.asarray(HUMAN.q_min_rad))
        and np.all(q <= np.asarray(HUMAN.q_max_rad))
    )


def _inside_commissioning_consistency_envelope(q_rad: np.ndarray) -> bool:
    q_deg = np.degrees(np.asarray(q_rad, dtype=float))
    return bool(
        q_deg.shape == (2,)
        and np.all(np.isfinite(q_deg))
        and np.all(
            q_deg
            >= COMMISSIONING_TARGET_Q_MIN_DEG
            - COMMISSIONING_CONSISTENCY_MARGIN_DEG
        )
        and np.all(
            q_deg
            <= COMMISSIONING_TARGET_Q_MAX_DEG
            + COMMISSIONING_CONSISTENCY_MARGIN_DEG
        )
    )


def _probe_wrench(
    time_s: float,
    position_xz_m: np.ndarray,
    phi_rad: float,
    velocity_xz_m_s: np.ndarray,
    phi_dot_rad_s: float,
    commissioning_geometry: PlanarCuffGeometry,
    commissioning_start_q_rad: np.ndarray,
    duration_s: float,
) -> tuple[np.ndarray, float]:
    """Bounded, one-sided commissioning motion into the ROM interior.

    The path is constructed from the first measured cuff pose plus a population
    q1 anchor, never the hidden initial state. It first moves both estimated
    joints toward flexion, then applies independent harmonics around that
    interior point. This avoids symmetric excitation toward an unknown nearby
    lower ROM boundary while still conditioning the effective-geometry fit.
    """

    start_q = np.asarray(commissioning_start_q_rad, dtype=float)
    interior_q = start_q + np.radians(PROBE_INTERIOR_DELTA_DEG)
    entry_duration = 0.35 * duration_s
    excitation_duration = 0.45 * duration_s
    excitation_end = entry_duration + excitation_duration
    if time_s < entry_duration:
        progress, progress_velocity, _ = quintic_progress(time_s / entry_duration)
        target_q = start_q + (interior_q - start_q) * progress
        target_dq = (interior_q - start_q) * progress_velocity / entry_duration
    elif time_s < excitation_end:
        normalized = (time_s - entry_duration) / excitation_duration
        phase = 2.0 * math.pi * normalized
        phase_rate = 2.0 * math.pi / excitation_duration
        window = math.sin(math.pi * normalized) ** 2
        window_rate = (
            math.pi
            * math.sin(2.0 * math.pi * normalized)
            / excitation_duration
        )
        hip_shape = math.sin(phase) * window
        knee_shape = math.sin(2.0 * phase) * window
        hip_shape_rate = math.cos(phase) * phase_rate * window + math.sin(
            phase
        ) * window_rate
        knee_shape_rate = (
            math.cos(2.0 * phase) * 2.0 * phase_rate * window
            + math.sin(2.0 * phase) * window_rate
        )
        target_q = interior_q + np.radians(
            [8.0 * hip_shape, 7.0 * knee_shape]
        )
        target_dq = np.radians(
            [8.0 * hip_shape_rate, 7.0 * knee_shape_rate]
        )
    else:
        # End commissioning at the interior target with zero desired velocity;
        # this prevents the identification excitation from handing a large
        # residual velocity directly to the task MPC.
        target_q = interior_q
        target_dq = np.zeros(2)
    target_pose = commissioning_geometry.cuff_pose(target_q)
    target_linear, _ = commissioning_geometry.cuff_velocity(target_q, target_dq)
    target = target_pose.translation[[0, 2]]
    target_velocity = target_linear[[0, 2]]
    target_phi = float(target_q[0] - target_q[1])
    target_phi_dot = float(target_dq[0] - target_dq[1])
    force = PROBE_TRANSLATION_KP_N_PER_M * (
        target - position_xz_m
    ) + PROBE_TRANSLATION_KD_N_S_PER_M * (
        target_velocity - velocity_xz_m_s
    )
    norm = float(np.linalg.norm(force))
    if norm > PROBE_FORCE_LIMIT_N:
        force *= PROBE_FORCE_LIMIT_N / norm
    # ``generalized_input_from_wrench`` maps +My to [-My,+My], so the
    # negative sign is required for positive phi=q1-q2 feedback work.
    moment = float(
        -np.clip(
            PROBE_ORIENTATION_KP_NM_PER_RAD * (target_phi - phi_rad)
            + PROBE_ORIENTATION_KD_NM_S_PER_RAD
            * (target_phi_dot - phi_dot_rad_s),
            -PROBE_MOMENT_LIMIT_NM,
            PROBE_MOMENT_LIMIT_NM,
        )
    )
    return force, moment


def _integrate_substeps(
    model: BaseParameterHumanModel,
    state: np.ndarray,
    action_nm: np.ndarray,
    duration_s: float,
    *,
    evaluation_observer: Callable[[np.ndarray], None] | None = None,
) -> np.ndarray:
    """Keep the verified stiff soft-limit dynamics on a 5 ms integration grid."""

    count = max(1, int(math.ceil(duration_s / INTEGRATION_MAX_STEP_S)))
    dt = duration_s / count
    result = np.asarray(state, dtype=float).copy()
    for _ in range(count):
        result = model.step_dynamics(result, action_nm, dt)
        if evaluation_observer is not None:
            evaluation_observer(result)
    return result


def _nominal_geometry_from_first_pose(
    position_xz_m: np.ndarray, phi_rad: float
) -> PlanarCuffGeometry:
    q1_prior = math.radians(10.0)
    l1 = HUMAN.thigh_length_m
    sc = HUMAN.sleeve_center_m
    hip = (
        np.asarray(position_xz_m)
        - l1 * np.array([math.cos(q1_prior), math.sin(q1_prior)])
        - sc * np.array([math.cos(phi_rad), math.sin(phi_rad)])
    )
    fit = EffectiveGeometryFit(
        hip,
        l1,
        sc,
        0.0,
        0.0,
        1.0,
        1,
        0.0,
        True,
        "fixed_nominal_anchored_to_first_cuff_pose",
    )
    return build_planar_geometry(fit)


def _rotation_from_phi(phi_rad: float) -> np.ndarray:
    cosine, sine = math.cos(phi_rad), math.sin(phi_rad)
    return np.array(
        [[cosine, 0.0, -sine], [0.0, 1.0, 0.0], [sine, 0.0, cosine]]
    )


def _quintic_segment(
    time_s: float, start_s: float, duration_s: float, q0: np.ndarray, q1: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if time_s <= start_s:
        return q0.copy(), np.zeros(2), np.zeros(2)
    if time_s >= start_s + duration_s:
        return q1.copy(), np.zeros(2), np.zeros(2)
    progress, velocity, acceleration = quintic_progress((time_s - start_s) / duration_s)
    delta = q1 - q0
    return (
        q0 + delta * progress,
        delta * velocity / duration_s,
        delta * acceleration / duration_s**2,
    )


def make_task_reference(
    start_q_rad: np.ndarray,
    goal_q_rad: np.ndarray,
    task_id: str,
    duration_s: float,
    geometry: PlanarCuffGeometry,
) -> Callable[[float], CuffPoseReference]:
    """Build a versioned outbound/hold/return profile from task inputs."""

    outbound, hold, returning = _task_phase_durations(task_id, duration_s)

    def reference(time_s: float) -> CuffPoseReference:
        time = float(np.clip(time_s, 0.0, duration_s))
        if task_id == BOUNDED_KNEE_LEAD_PROFILE:
            midpoint = start_q_rad + BOUNDED_KNEE_LEAD_MIDPOINT_PROGRESS * (
                goal_q_rad - start_q_rad
            )
            first = outbound * 0.52
            if time <= first:
                q, dq, ddq = _quintic_segment(
                    time, 0.0, first, start_q_rad, midpoint
                )
            elif time <= outbound:
                q, dq, ddq = _quintic_segment(
                    time, first, outbound - first, midpoint, goal_q_rad
                )
            elif time <= outbound + hold:
                q, dq, ddq = goal_q_rad.copy(), np.zeros(2), np.zeros(2)
            else:
                return_start = outbound + hold
                if time <= return_start + returning * 0.48:
                    q, dq, ddq = _quintic_segment(
                        time,
                        return_start,
                        returning * 0.48,
                        goal_q_rad,
                        midpoint,
                    )
                else:
                    q, dq, ddq = _quintic_segment(
                        time,
                        return_start + returning * 0.48,
                        returning * 0.52,
                        midpoint,
                        start_q_rad,
                    )
        elif task_id in {"hip_lead", "knee_lead"}:
            lead = 0 if task_id == "hip_lead" else 1
            lag = 1 - lead
            midpoint = start_q_rad.copy()
            midpoint[lead] = goal_q_rad[lead]
            half = outbound * 0.52
            if time <= half:
                q, dq, ddq = _quintic_segment(time, 0.0, half, start_q_rad, midpoint)
            elif time <= outbound:
                q, dq, ddq = _quintic_segment(time, half, outbound - half, midpoint, goal_q_rad)
            elif time <= outbound + hold:
                q, dq, ddq = goal_q_rad.copy(), np.zeros(2), np.zeros(2)
            else:
                return_start = outbound + hold
                return_midpoint = goal_q_rad.copy()
                return_midpoint[lag] = start_q_rad[lag]
                if time <= return_start + returning * 0.48:
                    q, dq, ddq = _quintic_segment(
                        time,
                        return_start,
                        returning * 0.48,
                        goal_q_rad,
                        return_midpoint,
                    )
                else:
                    q, dq, ddq = _quintic_segment(
                        time,
                        return_start + returning * 0.48,
                        returning * 0.52,
                        return_midpoint,
                        start_q_rad,
                    )
        else:
            if time <= outbound:
                q, dq, ddq = _quintic_segment(
                    time, 0.0, outbound, start_q_rad, goal_q_rad
                )
            elif time <= outbound + hold:
                q, dq, ddq = goal_q_rad.copy(), np.zeros(2), np.zeros(2)
            else:
                q, dq, ddq = _quintic_segment(
                    time,
                    outbound + hold,
                    returning,
                    goal_q_rad,
                    start_q_rad,
                )
        return CuffPoseReference(q, dq, ddq, geometry.cuff_pose(q))

    return reference


def _task_phase_durations(task_id: str, duration_s: float) -> tuple[float, float, float]:
    """Return the registered known-reference outbound/hold/return durations."""

    if task_id == "two_rate":
        return 0.46 * duration_s, 0.08 * duration_s, 0.38 * duration_s
    return 0.40 * duration_s, 0.12 * duration_s, 0.40 * duration_s


def _task_reference_phase(task_id: str, duration_s: float, time_s: float) -> str:
    """Classify a task sample using only the registered reference clock."""

    outbound, hold, _ = _task_phase_durations(task_id, duration_s)
    if time_s <= outbound:
        return "outbound"
    if time_s <= outbound + hold:
        return "hold"
    return "return"


def _preview(
    action_nm: np.ndarray,
    model: BaseParameterHumanModel,
    current_q_rad: np.ndarray,
    control_dt_s: float,
) -> ExecutableCommandPreview:
    allocation = model.allocate_generalized_action(action_nm, current_q_rad)
    force = np.asarray(allocation["force_world_n"], dtype=float)
    moment = np.asarray(allocation["wrench_world"], dtype=float)[3:]
    norm = float(np.linalg.norm(force))
    feasible = bool(norm <= 200.0 + 1.0e-9 and np.linalg.norm(moment) <= 60.0)
    zeros3 = np.zeros(3)
    zeros6 = np.zeros(6)
    return ExecutableCommandPreview(
        force_position_n=zeros3,
        force_velocity_n=zeros3,
        force_allocator_n=force,
        force_total_n=force,
        raw_force_position_n=zeros3,
        raw_force_velocity_n=zeros3,
        feedback_force_before_clipping_n=zeros3,
        feedback_force_after_clipping_n=zeros3,
        feedback_force_clipping_delta_n=zeros3,
        moment_orientation_nm=zeros3,
        moment_angular_velocity_nm=zeros3,
        moment_allocator_nm=moment,
        moment_total_nm=moment,
        translational_force_norm_n=norm,
        margin_to_force_gate_n=200.0 - norm,
        feasible=feasible,
        robot_attachment_jacobian=np.zeros((6, 6)),
        unclipped_joint_torque_nm=zeros6,
        joint_torque_command_nm=zeros6,
        control_dt_s=control_dt_s,
    )


def _base_model_with_residual_bias(
    geometry: PlanarCuffGeometry,
    beta: np.ndarray,
    residual_bias_nm: np.ndarray,
) -> BaseParameterHumanModel:
    """Encode a task-local constant torque residual in the two rho columns.

    The base regressor contributes ``-rho1`` and ``-rho2`` to inverse
    dynamics, so subtracting the causal residual from those coefficients makes
    the ordinary batched model require exactly that additional commanded
    torque.  The physical beta estimate remains separate and unchanged.
    """

    residual = np.asarray(residual_bias_nm, dtype=float)
    if residual.shape != (2,) or not np.all(np.isfinite(residual)):
        raise ValueError("residual_bias_nm must be a finite two-vector")
    effective_beta = np.asarray(beta, dtype=float).copy()
    effective_beta[7:9] -= residual
    return BaseParameterHumanModel(geometry, effective_beta, HUMAN)


def _state_residual_features(state: np.ndarray) -> np.ndarray:
    """Return fixed bounded deployable features for the V2 state residual.

    Position is normalized by the registered Human-V2 ROM.  Velocity uses the
    parameter-free signed saturation ``v / (1 + abs(v))`` in SI units.  The
    feature map therefore adds no learned threshold and consumes only the same
    estimated state already supplied to MPC.
    """

    x = np.asarray(state, dtype=float)
    if x.shape[-1] != 4 or not np.all(np.isfinite(x)):
        raise ValueError("state must contain finite [q1, q2, dq1, dq2]")
    lower = np.asarray(HUMAN.q_min_rad, dtype=float)
    upper = np.asarray(HUMAN.q_max_rad, dtype=float)
    q_normalized = 2.0 * (x[..., :2] - lower) / (upper - lower) - 1.0
    velocity_scale = STATE_RESIDUAL_VELOCITY_SCALE_RAD_S
    dq_bounded = x[..., 2:] / (velocity_scale + np.abs(x[..., 2:]))
    ones = np.ones(x.shape[:-1] + (1,), dtype=float)
    return np.concatenate([ones, q_normalized, dq_bounded], axis=-1)


def _update_state_residual_weights(
    previous_weights_nm: np.ndarray,
    state: np.ndarray,
    residual_sample_nm: np.ndarray,
    alpha: float,
    limit_nm: float,
) -> tuple[np.ndarray, bool, bool]:
    """Apply one causal normalized-LMS update with a bounded weight projection."""

    previous = np.asarray(previous_weights_nm, dtype=float)
    sample = np.asarray(residual_sample_nm, dtype=float)
    if previous.shape != (2, 5) or not np.all(np.isfinite(previous)):
        raise ValueError("previous_weights_nm must be a finite 2x5 matrix")
    if sample.shape != (2,) or not np.all(np.isfinite(sample)):
        raise ValueError("residual_sample_nm must be a finite two-vector")
    if not math.isfinite(alpha) or not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must be finite and in (0, 1]")
    if not math.isfinite(limit_nm) or limit_nm <= 0.0:
        raise ValueError("limit_nm must be finite and positive")
    features = _state_residual_features(state)
    prediction = np.clip(previous @ features, -limit_nm, limit_nm)
    error = sample - prediction
    candidate = previous + alpha * np.outer(error, features) / float(
        features @ features
    )
    row_norm = np.linalg.norm(candidate, axis=1)
    scale = np.minimum(1.0, limit_nm / np.maximum(row_norm, 1.0e-12))
    projected = candidate * scale[:, None]
    coefficient_projection_hit = bool(np.any(row_norm > limit_nm))
    observed_output_cap_hit = bool(
        np.any(np.abs(projected @ features) > limit_nm)
    )
    return projected, coefficient_projection_hit, observed_output_cap_hit


@dataclass(frozen=True)
class StateResidualHumanModel(BaseParameterHumanModel):
    """Base-parameter model plus a bounded state-conditioned torque residual."""

    residual_weights_nm: np.ndarray = field(
        default_factory=lambda: np.zeros((2, 5))
    )
    residual_limit_nm: float = 12.0

    def __post_init__(self) -> None:
        weights = np.asarray(self.residual_weights_nm, dtype=float)
        if weights.shape != (2, 5) or not np.all(np.isfinite(weights)):
            raise ValueError("residual_weights_nm must be a finite 2x5 matrix")
        if not math.isfinite(self.residual_limit_nm) or self.residual_limit_nm <= 0.0:
            raise ValueError("residual_limit_nm must be finite and positive")

    def state_residual_nm(self, state: np.ndarray) -> np.ndarray:
        prediction = self.raw_state_residual_nm(state)
        return np.clip(
            prediction, -float(self.residual_limit_nm), float(self.residual_limit_nm)
        )

    def raw_state_residual_nm(self, state: np.ndarray) -> np.ndarray:
        features = _state_residual_features(state)
        return np.einsum(
            "ij,...j->...i", np.asarray(self.residual_weights_nm), features
        )

    def inverse_dynamics(
        self,
        q_rad: np.ndarray,
        dq_rad_s: np.ndarray,
        ddq_rad_s2: np.ndarray,
    ) -> np.ndarray:
        base = super().inverse_dynamics(q_rad, dq_rad_s, ddq_rad_s2)
        state = np.concatenate(
            [np.asarray(q_rad, dtype=float), np.asarray(dq_rad_s, dtype=float)]
        )
        return base + self.state_residual_nm(state)


class StateResidualHumanSpaceMPC(HumanSpaceMPC):
    """V2-local batched MPC extension for state-conditioned residual dynamics."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.residual_prediction_dynamics_component_evaluation_count = 0
        self.residual_prediction_dynamics_component_cap_hit_count = 0

    def reset(self) -> None:
        super().reset()
        self.residual_prediction_dynamics_component_evaluation_count = 0
        self.residual_prediction_dynamics_component_cap_hit_count = 0

    def _batched_base_continuous_dynamics(
        self,
        state: np.ndarray,
        action: np.ndarray,
        human: BaseParameterHumanModel,
    ) -> np.ndarray:
        derivative = super()._batched_base_continuous_dynamics(state, action, human)
        if not isinstance(human, StateResidualHumanModel):
            return derivative
        x = np.asarray(state, dtype=float)
        raw_residual = human.raw_state_residual_nm(x)
        self.residual_prediction_dynamics_component_evaluation_count += int(
            raw_residual.size
        )
        self.residual_prediction_dynamics_component_cap_hit_count += int(
            np.sum(np.abs(raw_residual) > human.residual_limit_nm)
        )
        q2 = x[..., 1]
        beta = np.asarray(human.beta, dtype=float)
        cosine = np.cos(q2)
        mass = np.empty(x.shape[:-1] + (2, 2), dtype=float)
        mass[..., 0, 0] = beta[0] + 2.0 * beta[2] * cosine
        mass[..., 0, 1] = -(beta[1] + beta[2] * cosine)
        mass[..., 1, 0] = mass[..., 0, 1]
        mass[..., 1, 1] = beta[1]
        correction = np.linalg.solve(
            mass, np.clip(
                raw_residual,
                -human.residual_limit_nm,
                human.residual_limit_nm,
            )[..., None]
        )[..., 0]
        result = np.asarray(derivative, dtype=float).copy()
        result[..., 2:] -= correction
        return result


def _arm_uses_task_residual(arm: Arm) -> bool:
    """Return whether an arm is allowed to use the deployable residual layer."""

    return arm in {
        "adaptive",
        "adaptive_state_residual",
        "adaptive_phase_banked_residual",
        "commissioning_beta_residual",
        "wrong_geometry_adaptive_dynamics",
    }


def _arm_updates_task_beta(arm: Arm) -> bool:
    """Return whether the task phase may refit the global beta model."""

    return arm in {
        "adaptive",
        "adaptive_state_residual",
        "adaptive_phase_banked_residual",
        "wrong_geometry_adaptive_dynamics",
    }


def _update_task_residual_bias(
    previous_bias_nm: np.ndarray,
    residual_sample_nm: np.ndarray,
    alpha: float,
    limit_nm: float,
) -> tuple[np.ndarray, bool]:
    """Apply one bounded causal EWMA update without mutating either input."""

    previous = np.asarray(previous_bias_nm, dtype=float)
    sample = np.asarray(residual_sample_nm, dtype=float)
    if previous.shape != (2,) or not np.all(np.isfinite(previous)):
        raise ValueError("previous_bias_nm must be a finite two-vector")
    if sample.shape != (2,) or not np.all(np.isfinite(sample)):
        raise ValueError("residual_sample_nm must be a finite two-vector")
    if not math.isfinite(alpha) or not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must be finite and in (0, 1]")
    if not math.isfinite(limit_nm) or limit_nm <= 0.0:
        raise ValueError("limit_nm must be finite and positive")
    candidate = (1.0 - alpha) * previous + alpha * sample
    cap_hit = bool(np.any(np.abs(candidate) > limit_nm))
    return np.clip(candidate, -limit_nm, limit_nm), cap_hit


def run_closed_loop_case(
    setup: HiddenSetup,
    task: TaskSpec,
    arm: Arm,
    *,
    dt_s: float = 0.02,
    probe_duration_s: float = 8.0,
    probe_control_dt_s: float = 0.01,
    commissioning_only: bool = False,
    probe_settle_timeout_s: float = 4.0,
    probe_settle_velocity_deg_s: float = 5.0,
    probe_settle_consecutive_samples: int = 20,
    probe_settle_translation_kd_n_s_per_m: float = PROBE_SETTLE_TRANSLATION_KD_N_S_PER_M,
    probe_settle_orientation_kd_nm_s_per_rad: float = PROBE_SETTLE_ORIENTATION_KD_NM_S_PER_RAD,
    task_dynamics_history_window_samples: int | None = None,
    task_dynamics_smoothing_alpha: float | None = None,
    task_residual_bias_alpha: float | None = None,
    task_residual_bias_limit_nm: float = 12.0,
    evaluation_time_contract: str = "historical_post_state_pre_reference_v1",
) -> dict[str, Any]:
    """Run one arm with a strict truth/deployable object separation."""

    if evaluation_time_contract not in {
        "historical_post_state_pre_reference_v1",
        "boundary_aligned_v2",
    }:
        raise ValueError("unknown evaluation_time_contract")
    boundary_aligned = evaluation_time_contract == "boundary_aligned_v2"
    rng = np.random.default_rng(setup.seed + 170000)
    true_model = BaseParameterHumanModel(setup.geometry, setup.beta, setup.human)
    state_true = np.concatenate([setup.initial_q_rad.copy(), np.zeros(2)])
    geometry_estimator = CausalEffectiveGeometryEstimator()
    first = _pose_observation(
        setup.geometry,
        state_true[:2],
        state_true[2:],
        rng,
        setup.measurement_position_std_m,
        setup.measurement_angle_std_rad,
    )
    first_position, first_phi = first[0], first[1]
    fixed_geometry = _nominal_geometry_from_first_pose(first_position, first_phi)
    commissioning_start_q = fixed_geometry.estimate_q(
        np.array([first_position[0], 0.0, first_position[1]]),
        _rotation_from_phi(first_phi),
    )
    probe_force_peak = 0.0
    probe_moment_peak = 0.0
    probe_rom_violation = False
    clearance_evaluation_enabled = (
        setup.generation_min_reference_clearance_m is not None
    )
    probe_min_clearance_m = (
        _hidden_shank_clearance_m(setup, state_true[:2])
        if clearance_evaluation_enabled
        else None
    )
    probe_clearance_violation = bool(
        probe_min_clearance_m is not None and probe_min_clearance_m < 0.0
    )
    probe_consistency_abort = False
    probe_estimated_q_min = np.full(2, np.inf)
    probe_estimated_q_max = np.full(2, -np.inf)
    probe_abort_time_s: float | None = None
    probe_settle_timeout = False
    probe_settled_sample_count = 0
    probe_actual_duration_s = 0.0
    probe_settle_target_position_xz_m: np.ndarray | None = None
    probe_settle_target_phi_rad: float | None = None
    probe_history: list[dict[str, Any]] = []

    def observe_probe_substep(substep_state: np.ndarray) -> None:
        nonlocal probe_min_clearance_m, probe_clearance_violation
        if not clearance_evaluation_enabled:
            return
        clearance = _hidden_shank_clearance_m(setup, substep_state[:2])
        probe_min_clearance_m = min(float(probe_min_clearance_m), clearance)
        probe_clearance_violation |= clearance < 0.0

    if probe_control_dt_s <= 0.0 or probe_control_dt_s > dt_s:
        raise ValueError("probe_control_dt_s must be in (0, dt_s]")
    if probe_settle_timeout_s <= 0.0:
        raise ValueError("probe_settle_timeout_s must be positive")
    if probe_settle_velocity_deg_s <= 0.0:
        raise ValueError("probe_settle_velocity_deg_s must be positive")
    if probe_settle_consecutive_samples <= 0:
        raise ValueError("probe_settle_consecutive_samples must be positive")
    if probe_settle_translation_kd_n_s_per_m <= 0.0:
        raise ValueError("probe_settle_translation_kd_n_s_per_m must be positive")
    if probe_settle_orientation_kd_nm_s_per_rad <= 0.0:
        raise ValueError("probe_settle_orientation_kd_nm_s_per_rad must be positive")
    probe_steps = int(
        round((probe_duration_s + probe_settle_timeout_s) / probe_control_dt_s)
    ) + 1
    for step in range(probe_steps):
        time_s = step * probe_control_dt_s
        probe_actual_duration_s = time_s
        position, phi, velocity, phi_dot = _pose_observation(
            setup.geometry,
            state_true[:2],
            state_true[2:],
            rng,
            setup.measurement_position_std_m,
            setup.measurement_angle_std_rad,
        )
        probe_q_hat = fixed_geometry.estimate_q(
            np.array([position[0], 0.0, position[1]]),
            _rotation_from_phi(phi),
        )
        probe_estimated_q_min = np.minimum(probe_estimated_q_min, probe_q_hat)
        probe_estimated_q_max = np.maximum(probe_estimated_q_max, probe_q_hat)
        if not _inside_commissioning_consistency_envelope(probe_q_hat):
            probe_consistency_abort = True
            probe_abort_time_s = time_s
            break
        geometry_estimator.observe(position, phi)
        probe_state_hat = fixed_geometry.estimate_state(
            np.array([position[0], 0.0, position[1]]),
            _rotation_from_phi(phi),
            np.array([velocity[0], 0.0, velocity[1]]),
            np.array([0.0, -phi_dot, 0.0]),
        )
        if time_s >= probe_duration_s:
            if np.max(np.abs(np.degrees(probe_state_hat[2:]))) <= (
                probe_settle_velocity_deg_s
            ):
                probe_settled_sample_count += 1
            else:
                probe_settled_sample_count = 0
            if probe_settled_sample_count >= probe_settle_consecutive_samples:
                break
        if time_s >= probe_duration_s:
            if probe_settle_target_position_xz_m is None:
                settle_q = commissioning_start_q + np.radians(
                    PROBE_INTERIOR_DELTA_DEG
                )
                probe_settle_target_position_xz_m = (
                    fixed_geometry.cuff_pose(settle_q).translation[[0, 2]]
                )
                probe_settle_target_phi_rad = float(
                    settle_q[0] - settle_q[1]
                )
            force = PROBE_TRANSLATION_KP_N_PER_M * (
                probe_settle_target_position_xz_m - position
            ) - probe_settle_translation_kd_n_s_per_m * velocity
            force_norm = float(np.linalg.norm(force))
            if force_norm > PROBE_FORCE_LIMIT_N:
                force *= PROBE_FORCE_LIMIT_N / force_norm
            moment = float(
                -np.clip(
                    PROBE_ORIENTATION_KP_NM_PER_RAD
                    * (float(probe_settle_target_phi_rad) - phi)
                    - probe_settle_orientation_kd_nm_s_per_rad * phi_dot,
                    -PROBE_MOMENT_LIMIT_NM,
                    PROBE_MOMENT_LIMIT_NM,
                )
            )
        else:
            force, moment = _probe_wrench(
                time_s,
                position,
                phi,
                velocity,
                phi_dot,
                fixed_geometry,
                commissioning_start_q,
                probe_duration_s,
            )
        probe_history.append(
            {
                "position_xz_m": position.copy(),
                "phi_rad": phi,
                "velocity_xz_m_s": velocity.copy(),
                "phi_dot_rad_s": phi_dot,
                "force_xz_n": force.copy(),
                "moment_y_nm": moment,
            }
        )
        torque = _wrench_to_generalized(
            setup.geometry, state_true[:2], force, moment
        )
        state_true = _integrate_substeps(
            true_model,
            state_true,
            torque,
            probe_control_dt_s,
            evaluation_observer=observe_probe_substep,
        )
        probe_force_peak = max(probe_force_peak, float(np.linalg.norm(force)))
        probe_moment_peak = max(probe_moment_peak, abs(moment))
        probe_rom_violation |= bool(
            np.any(state_true[:2] < np.asarray(setup.human.q_min_rad) - 1.0e-9)
            or np.any(state_true[:2] > np.asarray(setup.human.q_max_rad) + 1.0e-9)
        )
        if probe_rom_violation:
            break
        if probe_clearance_violation:
            break
        if not np.all(np.isfinite(state_true)) or np.max(np.abs(state_true)) > 1.0e3:
            break
    else:
        probe_settle_timeout = True
    probe_force_exposure_n_s = float(
        sum(np.linalg.norm(sample["force_xz_n"]) for sample in probe_history)
        * probe_control_dt_s
    )
    probe_moment_exposure_nm_s = float(
        sum(abs(sample["moment_y_nm"]) for sample in probe_history)
        * probe_control_dt_s
    )
    if probe_consistency_abort:
        return {
            "schema": "architecture_recovery_v2.closed_loop_case.v1",
            "arm": arm,
            "seed": setup.seed,
            "task_seed": task.generation_seed,
            "task_id": task.task_id,
            "completed": False,
            "full_horizon_executed": False,
            "clearance_evaluation_enabled": clearance_evaluation_enabled,
            "probe_control_dt_s": probe_control_dt_s,
            "termination_reason": "probe_consistency_envelope_abort",
            "probe_terminal_state": state_true.tolist(),
            "probe_force_peak_n": probe_force_peak,
            "probe_moment_peak_nm": probe_moment_peak,
            "probe_force_exposure_n_s": probe_force_exposure_n_s,
            "probe_moment_exposure_nm_s": probe_moment_exposure_nm_s,
            "probe_rom_violation": probe_rom_violation,
            "probe_clearance_violation": probe_clearance_violation,
            "probe_min_clearance_m_evaluation_only": probe_min_clearance_m,
            "probe_consistency_abort_count": 1,
            "probe_estimated_q_min_deg": np.degrees(probe_estimated_q_min).tolist(),
            "probe_estimated_q_max_deg": np.degrees(probe_estimated_q_max).tolist(),
            "probe_abort_time_s": probe_abort_time_s,
            "probe_actual_duration_s": probe_actual_duration_s,
            "probe_settle_timeout_count": 0,
            "geometry_fit": {
                "accepted": False,
                "reason": "not_attempted_after_causal_consistency_abort",
            },
            "truth_firewall": {"deployable_truth_consumed": False},
            "setup_evaluation_only": setup.evaluation_record(),
            "task_input": task.record(),
        }
    geometry_fit = geometry_estimator.attempt_fit()
    if (
        probe_rom_violation
        or probe_clearance_violation
        or probe_settle_timeout
        or not np.all(np.isfinite(state_true))
    ):
        if probe_rom_violation:
            probe_termination = "evaluation_probe_hidden_rom_violation"
        elif probe_clearance_violation:
            probe_termination = "evaluation_probe_hidden_table_clearance_violation"
        elif probe_settle_timeout:
            probe_termination = "probe_settle_timeout_abort"
        else:
            probe_termination = "probe_state_became_nonfinite"
        return {
            "schema": "architecture_recovery_v2.closed_loop_case.v1",
            "arm": arm,
            "seed": setup.seed,
            "task_seed": task.generation_seed,
            "task_id": task.task_id,
            "completed": False,
            "full_horizon_executed": False,
            "clearance_evaluation_enabled": clearance_evaluation_enabled,
            "probe_control_dt_s": probe_control_dt_s,
            "termination_reason": probe_termination,
            "probe_terminal_state": state_true.tolist(),
            "probe_force_peak_n": probe_force_peak,
            "probe_moment_peak_nm": probe_moment_peak,
            "probe_force_exposure_n_s": probe_force_exposure_n_s,
            "probe_moment_exposure_nm_s": probe_moment_exposure_nm_s,
            "probe_rom_violation": probe_rom_violation,
            "probe_clearance_violation": probe_clearance_violation,
            "probe_min_clearance_m_evaluation_only": probe_min_clearance_m,
            "probe_consistency_abort_count": int(probe_consistency_abort),
            "probe_estimated_q_min_deg": np.degrees(probe_estimated_q_min).tolist(),
            "probe_estimated_q_max_deg": np.degrees(probe_estimated_q_max).tolist(),
            "probe_abort_time_s": probe_abort_time_s,
            "probe_actual_duration_s": probe_actual_duration_s,
            "probe_settle_timeout_count": int(probe_settle_timeout),
            "geometry_fit": geometry_fit.record(),
            "truth_firewall": {"deployable_truth_consumed": False},
            "setup_evaluation_only": setup.evaluation_record(),
            "task_input": task.record(),
        }
    if arm in {
        "adaptive",
        "adaptive_state_residual",
        "adaptive_phase_banked_residual",
        "commissioning_beta_residual",
        "commissioning_only_dynamics",
        "no_dynamics_adaptation",
    }:
        if not geometry_fit.accepted:
            return {
                "schema": "architecture_recovery_v2.closed_loop_case.v1",
                "arm": arm,
                "seed": setup.seed,
                "task_seed": task.generation_seed,
                "task_id": task.task_id,
                "completed": False,
                "full_horizon_executed": False,
                "clearance_evaluation_enabled": clearance_evaluation_enabled,
                "probe_control_dt_s": probe_control_dt_s,
                "termination_reason": f"geometry_fit_rejected:{geometry_fit.reason}",
                "geometry_fit": geometry_fit.record(),
                "probe_force_peak_n": probe_force_peak,
                "probe_moment_peak_nm": probe_moment_peak,
                "probe_force_exposure_n_s": probe_force_exposure_n_s,
                "probe_moment_exposure_nm_s": probe_moment_exposure_nm_s,
                "probe_rom_violation": probe_rom_violation,
                "probe_clearance_violation": probe_clearance_violation,
                "probe_min_clearance_m_evaluation_only": probe_min_clearance_m,
                "probe_consistency_abort_count": 0,
                "probe_actual_duration_s": probe_actual_duration_s,
                "probe_settle_timeout_count": 0,
                "probe_estimated_q_min_deg": np.degrees(probe_estimated_q_min).tolist(),
                "probe_estimated_q_max_deg": np.degrees(probe_estimated_q_max).tolist(),
                "truth_firewall": {"deployable_truth_consumed": False},
                "setup_evaluation_only": setup.evaluation_record(),
                "task_input": task.record(),
            }
        control_geometry = build_planar_geometry(geometry_fit)
    elif arm == "oracle":
        control_geometry = setup.geometry
    else:
        control_geometry = fixed_geometry

    dynamics = OnlineEffectiveDynamicsIdentifier()
    dynamics_update_trace: list[dict[str, Any]] = []

    def record_dynamics_attempt(
        diagnostics: dict[str, Any], *, phase: str, time_s: float
    ) -> None:
        if not diagnostics.get("attempted", False):
            return
        dynamics_update_trace.append(
            {
                "phase": phase,
                "time_s": float(time_s),
                "accepted": bool(diagnostics.get("accepted", False)),
                "reason": str(diagnostics.get("reason", "unknown")),
                "sample_count": int(diagnostics.get("sample_count", 0)),
                "rank": diagnostics.get("rank"),
                "condition_number": diagnostics.get("condition_number"),
                "minimum_mass_matrix_eigenvalue": diagnostics.get(
                    "minimum_mass_matrix_eigenvalue"
                ),
                "old_residual_rms_nm": diagnostics.get("old_residual_rms_nm"),
                "raw_candidate_residual_rms_nm": diagnostics.get(
                    "raw_candidate_residual_rms_nm"
                ),
                "trusted_candidate_residual_rms_nm": diagnostics.get(
                    "trusted_candidate_residual_rms_nm"
                ),
                "frozen_bound_parameter_names": list(
                    diagnostics.get("frozen_bound_parameter_names", [])
                ),
                "frozen_mass_margin_parameter_names": list(
                    diagnostics.get("frozen_mass_margin_parameter_names", [])
                ),
                "frozen_conditional_parameter_names": list(
                    diagnostics.get("frozen_conditional_parameter_names", [])
                ),
                "applied_beta": list(diagnostics.get("applied", dynamics.beta.tolist())),
            }
        )
    if arm in {
        "adaptive",
        "adaptive_state_residual",
        "adaptive_phase_banked_residual",
        "commissioning_beta_residual",
        "commissioning_only_dynamics",
        "wrong_geometry_adaptive_dynamics",
    }:
        commissioning_states = np.asarray(
            [
                control_geometry.estimate_state(
                    np.array(
                        [
                            sample["position_xz_m"][0],
                            0.0,
                            sample["position_xz_m"][1],
                        ]
                    ),
                    _rotation_from_phi(sample["phi_rad"]),
                    np.array(
                        [
                            sample["velocity_xz_m_s"][0],
                            0.0,
                            sample["velocity_xz_m_s"][1],
                        ]
                    ),
                    np.array([0.0, -sample["phi_dot_rad_s"], 0.0]),
                )
                for sample in probe_history
            ]
        )
        commissioning_ddq = np.gradient(
            commissioning_states[:, 2:],
            probe_control_dt_s,
            axis=0,
            edge_order=2,
        )
        for index in range(2, len(probe_history) - 2):
            q_sample = commissioning_states[index, :2]
            dq_sample = commissioning_states[index, 2:]
            if np.linalg.norm(
                soft_limit_torque(q_sample, dq_sample, HUMAN)
            ) > 1.0e-8:
                continue
            sample = probe_history[index]
            tau_sample = _wrench_to_generalized(
                control_geometry,
                q_sample,
                sample["force_xz_n"],
                sample["moment_y_nm"],
            )
            commissioning_diagnostics = dynamics.observe(
                q_sample,
                dq_sample,
                commissioning_ddq[index],
                tau_sample,
            )
            record_dynamics_attempt(
                commissioning_diagnostics,
                phase="commissioning",
                time_s=index * probe_control_dt_s,
            )
    commissioning_accepted_updates = dynamics.accepted_updates
    beta = (
        setup.beta.copy()
        if arm == "oracle"
        else dynamics.beta.copy()
        if arm
        in {
            "adaptive",
            "adaptive_state_residual",
            "adaptive_phase_banked_residual",
            "commissioning_beta_residual",
            "commissioning_only_dynamics",
            "wrong_geometry_adaptive_dynamics",
        }
        else nominal_base_parameters()
    )
    # The deployable model receives the registered ROM contract, not the
    # hidden plant instance. Session-varying dynamics enter only through beta.
    model = BaseParameterHumanModel(control_geometry, beta, HUMAN)
    if commissioning_only:
        geometry_error = {
            "hip_position_m": float(
                np.linalg.norm(
                    control_geometry.hip_plane_m - setup.geometry.hip_plane_m
                )
            ),
            "thigh_length_m": float(
                abs(
                    control_geometry.thigh_length_m
                    - setup.geometry.thigh_length_m
                )
            ),
            "knee_to_cuff_m": float(
                abs(
                    control_geometry.cuff_distance_m
                    - setup.geometry.cuff_distance_m
                )
            ),
            "full_shank_length_and_fraction_individually_estimated": False,
        }
        return {
            "schema": "architecture_recovery_v2.commissioning_case.v1",
            "arm": arm,
            "seed": setup.seed,
            "task_seed": task.generation_seed,
            "task_id": task.task_id,
            "high_rom_case": task.high_rom,
            "completed": True,
            "termination_reason": "commissioning_completed",
            "clearance_evaluation_enabled": clearance_evaluation_enabled,
            "clearance_evaluation_step_s_maximum": INTEGRATION_MAX_STEP_S,
            "probe_control_dt_s": probe_control_dt_s,
            "probe_force_peak_n": probe_force_peak,
            "probe_moment_peak_nm": probe_moment_peak,
            "probe_force_exposure_n_s": probe_force_exposure_n_s,
            "probe_moment_exposure_nm_s": probe_moment_exposure_nm_s,
            "probe_rom_violation": probe_rom_violation,
            "probe_clearance_violation": probe_clearance_violation,
            "probe_min_clearance_m_evaluation_only": probe_min_clearance_m,
            "probe_consistency_abort_count": 0,
            "probe_actual_duration_s": probe_actual_duration_s,
            "probe_settle_timeout_count": 0,
            "probe_estimated_q_min_deg": np.degrees(
                probe_estimated_q_min
            ).tolist(),
            "probe_estimated_q_max_deg": np.degrees(
                probe_estimated_q_max
            ).tolist(),
            "handoff_true_q_deg_evaluation_only": np.degrees(
                state_true[:2]
            ).tolist(),
            "handoff_true_dq_deg_s_evaluation_only": np.degrees(
                state_true[2:]
            ).tolist(),
            "geometry_fit": geometry_fit.record(),
            "geometry_error_evaluation_only": geometry_error,
            "dynamics_adaptation": dynamics.record(),
            "dynamics_update_trace": dynamics_update_trace,
            "commissioning_accepted_dynamic_updates": (
                commissioning_accepted_updates
            ),
            "beta_error_span_l2_evaluation_only": float(
                np.linalg.norm((model.beta - setup.beta) / dynamics.span)
            ),
            "truth_firewall": {
                "deployable_truth_consumed": False,
                "hidden_setup_used_only_by_plant_generator_and_evaluation": True,
                "oracle_arm_explicitly_non_deployable": arm == "oracle",
            },
            "setup_evaluation_only": setup.evaluation_record(),
            "task_input": task.record(),
        }
    mpc_class = (
        StateResidualHumanSpaceMPC
        if arm == "adaptive_state_residual"
        else HumanSpaceMPC
    )
    mpc = mpc_class(
        HumanMPCConfig(
            prediction_dt_s=dt_s,
            horizon_steps=8,
            candidate_count=24,
            elite_count=5,
            cem_iterations=2,
            exploration_std_nm=(8.0, 4.0),
            exploration_std_floor_nm=(0.8, 0.4),
            # Fixed controller randomness is independent of the hidden case
            # generation seed and is shared across comparison arms.
            random_seed=CONTROLLER_RANDOM_SEED,
        ),
        implementation="batched",
    )

    if (
        task_dynamics_history_window_samples is not None
        and _arm_updates_task_beta(arm)
    ):
        dynamics.enable_recency_window(task_dynamics_history_window_samples)
    if (
        task_dynamics_smoothing_alpha is not None
        and _arm_updates_task_beta(arm)
    ):
        alpha = float(task_dynamics_smoothing_alpha)
        if not 0.0 < alpha <= 1.0:
            raise ValueError("task_dynamics_smoothing_alpha must be in (0, 1]")
        dynamics.smoothing_alpha = alpha
    residual_bias = np.zeros(2)
    residual_bias_peak_abs_nm = 0.0
    residual_bias_cap_hit_count = 0
    residual_bias_update_count = 0
    residual_bias_max_step_nm = 0.0
    residual_bias_total_variation_nm = 0.0
    residual_bias_sign_reversal_count = 0
    state_residual = arm == "adaptive_state_residual"
    state_residual_weights = np.zeros((2, 5))
    state_residual_weight_peak_norm_nm = 0.0
    state_residual_weight_max_step_nm = 0.0
    state_residual_weight_total_variation_nm = 0.0
    state_residual_coefficient_projection_hit_count = 0
    state_residual_observed_output_cap_hit_count = 0
    state_residual_chosen_rollout_component_evaluation_count = 0
    state_residual_chosen_rollout_component_cap_hit_count = 0
    phase_banked_residual = arm == "adaptive_phase_banked_residual"
    residual_bias_banks = {
        phase: np.zeros(2) for phase in ("outbound", "hold", "return")
    }
    residual_layer_enabled = (
        task_residual_bias_alpha is not None and _arm_uses_task_residual(arm)
    )
    if residual_layer_enabled:
        residual_alpha = float(task_residual_bias_alpha)
        residual_limit = float(task_residual_bias_limit_nm)
        if not 0.0 < residual_alpha <= 1.0:
            raise ValueError("task_residual_bias_alpha must be in (0, 1]")
        if not math.isfinite(residual_limit) or residual_limit <= 0.0:
            raise ValueError("task_residual_bias_limit_nm must be positive")

    task_start_true = state_true[:2].copy()
    task_start_observed_position, task_start_phi, _, _ = _pose_observation(
        setup.geometry,
        state_true[:2],
        state_true[2:],
        rng,
        setup.measurement_position_std_m,
        setup.measurement_angle_std_rad,
    )
    rotation = _rotation_from_phi(task_start_phi)
    if arm == "oracle":
        state_hat = state_true.copy()
    else:
        q_hat = control_geometry.estimate_q(
            np.array([task_start_observed_position[0], 0.0, task_start_observed_position[1]]),
            rotation,
        )
        state_hat = np.concatenate([q_hat, np.zeros(2)])
    reference = make_task_reference(
        state_hat[:2].copy(),
        task.goal_q_rad,
        task.task_id,
        task.duration_s,
        control_geometry,
    )
    previous_residual_phase = _task_reference_phase(
        task.task_id, task.duration_s, 0.0
    )
    task_initial_reference = reference(0.0)
    # Evaluation-only audit of the exact arm-specific reference constructed
    # after commissioning. Hidden geometry is not returned to the deployable
    # controller and this value does not change generation or action selection.
    post_probe_reference_min_clearance_m = (
        _minimum_hidden_clearance_for_constructed_reference_evaluation_only(
            setup,
            reference,
            task.duration_s,
        )
        if clearance_evaluation_enabled
        else None
    )
    post_probe_reference_clearance_violation = bool(
        post_probe_reference_min_clearance_m is not None
        and post_probe_reference_min_clearance_m < 0.0
    )

    true_states: list[np.ndarray] = []
    estimated_states: list[np.ndarray] = []
    references: list[np.ndarray] = []
    actions: list[np.ndarray] = []
    forces: list[float] = []
    moments: list[float] = []
    executed_interval_durations_s: list[float] = []
    solve_failures = 0
    safety_abort_count = 0
    rom_violations = 0
    table_clearance_violation_samples = 0
    task_min_clearance_m: float | None = None
    accepted_update_times: list[float] = []
    previous_q_hat: np.ndarray | None = None
    filtered_dq = np.zeros(2)
    previous_filtered_dq = np.zeros(2)
    previous_wrench: tuple[np.ndarray, float] | None = None
    termination_reason = "task_horizon_reached"
    diagnostics: dict[str, Any] = {"status": "NOT_RUN"}
    corrected_grid = (
        build_boundary_time_grid(task.duration_s, dt_s)
        if boundary_aligned
        else None
    )
    task_steps = (
        corrected_grid.interval_count
        if corrected_grid is not None
        else int(round(task.duration_s / dt_s)) + 1
    )
    estimated_rom_supervisor_abort_count = 0
    previous_observation_time_s: float | None = None

    def observe_task_substep(substep_state: np.ndarray) -> None:
        nonlocal task_min_clearance_m, table_clearance_violation_samples
        if not clearance_evaluation_enabled:
            return
        clearance = _hidden_shank_clearance_m(setup, substep_state[:2])
        task_min_clearance_m = (
            clearance
            if task_min_clearance_m is None
            else min(task_min_clearance_m, clearance)
        )
        table_clearance_violation_samples += int(clearance < 0.0)

    for step in range(task_steps):
        time_s = (
            float(corrected_grid.boundary_times_s[step])
            if corrected_grid is not None
            else step * dt_s
        )
        interval_dt_s = (
            float(corrected_grid.interval_durations_s[step])
            if corrected_grid is not None
            else dt_s
        )
        current_residual_phase = _task_reference_phase(
            task.task_id, task.duration_s, time_s
        )
        ref = reference(time_s)
        position, phi, velocity, phi_dot = _pose_observation(
            setup.geometry,
            state_true[:2],
            state_true[2:],
            rng,
            setup.measurement_position_std_m,
            setup.measurement_angle_std_rad,
        )
        if arm == "oracle":
            state_hat = state_true.copy()
        else:
            measured_state = control_geometry.estimate_state(
                np.array([position[0], 0.0, position[1]]),
                _rotation_from_phi(phi),
                np.array([velocity[0], 0.0, velocity[1]]),
                np.array([0.0, -phi_dot, 0.0]),
            )
            q_hat = measured_state[:2]
            raw_dq = measured_state[2:]
            # Cuff twist is already the measured velocity channel used by the
            # historical estimator. Extra lag here breaks the inverse-
            # dynamics time alignment and makes beta absorb filter phase.
            filtered_dq = raw_dq.copy()
            state_hat = np.concatenate([q_hat, filtered_dq])
            if previous_q_hat is not None and previous_wrench is not None:
                observation_dt_s = (
                    time_s - previous_observation_time_s
                    if boundary_aligned and previous_observation_time_s is not None
                    else dt_s
                )
                ddq = (filtered_dq - previous_filtered_dq) / observation_dt_s
                force_prev, moment_prev = previous_wrench
                tau_est = _wrench_to_generalized(
                    control_geometry, previous_q_hat, force_prev, moment_prev
                )
                # The 11-beta regressor excludes the nonlinear soft-limit
                # torque. Samples in that layer therefore cannot be treated as
                # ordinary dynamics evidence.
                if (
                    _arm_updates_task_beta(arm) or residual_layer_enabled
                ) and np.linalg.norm(
                    soft_limit_torque(
                        previous_q_hat, previous_filtered_dq, HUMAN
                    )
                ) <= 1.0e-8:
                    if _arm_updates_task_beta(arm):
                        diagnostics = dynamics.observe(
                            previous_q_hat,
                            previous_filtered_dq,
                            ddq,
                            tau_est,
                        )
                        record_dynamics_attempt(
                            diagnostics, phase="task", time_s=time_s
                        )
                        if diagnostics.get("accepted"):
                            accepted_update_times.append(time_s)
                    base_model = BaseParameterHumanModel(
                        control_geometry, dynamics.beta.copy(), HUMAN
                    )
                    if residual_layer_enabled:
                        residual_sample = tau_est - (
                            dynamic_regressor_row(
                                previous_q_hat,
                                previous_filtered_dq,
                                ddq,
                            )
                            @ dynamics.beta
                        )
                        if state_residual:
                            previous_weights = state_residual_weights.copy()
                            features = _state_residual_features(
                                np.concatenate(
                                    [previous_q_hat, previous_filtered_dq]
                                )
                            )
                            previous_residual_bias = np.clip(
                                previous_weights @ features,
                                -residual_limit,
                                residual_limit,
                            )
                            (
                                state_residual_weights,
                                coefficient_projection_hit,
                                observed_output_cap_hit,
                            ) = (
                                _update_state_residual_weights(
                                    previous_weights,
                                    np.concatenate(
                                        [previous_q_hat, previous_filtered_dq]
                                    ),
                                    residual_sample,
                                    residual_alpha,
                                    residual_limit,
                                )
                            )
                            cap_hit = bool(
                                coefficient_projection_hit
                                or observed_output_cap_hit
                            )
                            updated_residual_bias = np.clip(
                                state_residual_weights @ features,
                                -residual_limit,
                                residual_limit,
                            )
                            residual_bias = updated_residual_bias
                            state_residual_weight_peak_norm_nm = max(
                                state_residual_weight_peak_norm_nm,
                                float(
                                    np.max(
                                        np.linalg.norm(
                                            state_residual_weights, axis=1
                                        )
                                    )
                                ),
                            )
                            state_residual_weight_max_step_nm = max(
                                state_residual_weight_max_step_nm,
                                float(
                                    np.max(
                                        np.abs(
                                            state_residual_weights
                                            - previous_weights
                                        )
                                    )
                                ),
                            )
                            state_residual_weight_total_variation_nm += float(
                                np.sum(
                                    np.abs(
                                        state_residual_weights - previous_weights
                                    )
                                )
                            )
                            state_residual_coefficient_projection_hit_count += int(
                                coefficient_projection_hit
                            )
                            state_residual_observed_output_cap_hit_count += int(
                                observed_output_cap_hit
                            )
                        else:
                            residual_bank_key = (
                                previous_residual_phase
                                if phase_banked_residual
                                else "global"
                            )
                            previous_residual_bias = (
                                residual_bias_banks[residual_bank_key].copy()
                                if phase_banked_residual
                                else residual_bias.copy()
                            )
                            updated_residual_bias, cap_hit = _update_task_residual_bias(
                                previous_residual_bias,
                                residual_sample,
                                residual_alpha,
                                residual_limit,
                            )
                            if phase_banked_residual:
                                residual_bias_banks[residual_bank_key] = (
                                    updated_residual_bias
                                )
                            else:
                                residual_bias = updated_residual_bias
                        residual_delta = updated_residual_bias - previous_residual_bias
                        residual_bias_cap_hit_count += int(cap_hit)
                        residual_bias_update_count += 1
                        residual_bias_max_step_nm = max(
                            residual_bias_max_step_nm,
                            float(np.max(np.abs(residual_delta))),
                        )
                        residual_bias_total_variation_nm += float(
                            np.sum(np.abs(residual_delta))
                        )
                        residual_bias_sign_reversal_count += int(
                            np.sum(
                                previous_residual_bias
                                * updated_residual_bias
                                < 0.0
                            )
                        )
                        residual_bias_peak_abs_nm = max(
                            residual_bias_peak_abs_nm,
                            float(np.max(np.abs(updated_residual_bias))),
                        )
                        if state_residual:
                            model = StateResidualHumanModel(
                                control_geometry,
                                dynamics.beta.copy(),
                                HUMAN,
                                state_residual_weights.copy(),
                                residual_limit,
                            )
                        elif not phase_banked_residual:
                            model = _base_model_with_residual_bias(
                                control_geometry,
                                dynamics.beta.copy(),
                                residual_bias,
                            )
                    else:
                        model = base_model
            previous_filtered_dq = filtered_dq.copy()
            previous_q_hat = q_hat.copy()
            previous_observation_time_s = time_s

        if phase_banked_residual and residual_layer_enabled:
            residual_bias = residual_bias_banks[current_residual_phase].copy()
            model = _base_model_with_residual_bias(
                control_geometry,
                dynamics.beta.copy(),
                residual_bias,
            )
        previous_residual_phase = current_residual_phase

        if not np.all(np.isfinite(state_hat)) or not _inside_registered_rom(
            state_hat[:2]
        ):
            safety_abort_count += 1
            estimated_rom_supervisor_abort_count += 1
            termination_reason = "estimated_rom_supervisor_abort"
            break

        try:
            action, diagnostics = mpc.solve(
                state_hat,
                time_s,
                reference,
                model,
                first_action_preview=lambda candidate, active=model, q=state_hat[:2].copy(): _preview(
                    candidate, active, q, interval_dt_s
                ),
            )
        except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError):
            action = None
            diagnostics = {"status": "SOLVE_EXCEPTION"}
        if action is None:
            solve_failures += 1
            termination_reason = "solver_no_safe_action_abort"
            break
        if state_residual and isinstance(model, StateResidualHumanModel):
            predicted_state = state_hat.copy()
            for predicted_action in np.asarray(mpc.last_sequence):
                raw_prediction = model.raw_state_residual_nm(predicted_state)
                state_residual_chosen_rollout_component_evaluation_count += int(
                    raw_prediction.size
                )
                state_residual_chosen_rollout_component_cap_hit_count += int(
                    np.sum(np.abs(raw_prediction) > residual_limit)
                )
                predicted_state = model.step_dynamics(
                    predicted_state, predicted_action, dt_s
                )
        try:
            allocation = model.allocate_generalized_action(action, state_hat[:2])
        except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError):
            safety_abort_count += 1
            termination_reason = "allocation_error_abort"
            break
        force_world = np.asarray(allocation["force_world_n"], dtype=float)
        moment_world = np.asarray(allocation["wrench_world"], dtype=float)[3:]
        force_xz = force_world[[0, 2]]
        moment_y = float(moment_world[1])
        if (
            not np.all(np.isfinite(force_xz))
            or not math.isfinite(moment_y)
            or float(np.linalg.norm(force_xz)) > 200.0 + 1.0e-6
            or abs(moment_y) > 60.0 + 1.0e-6
        ):
            safety_abort_count += 1
            termination_reason = "wrench_gate_abort"
            break
        true_torque = _wrench_to_generalized(
            setup.geometry, state_true[:2], force_xz, moment_y
        )
        clearance_violations_before = table_clearance_violation_samples
        pre_interval_true_state = state_true.copy()
        state_true = _integrate_substeps(
            true_model,
            state_true,
            true_torque,
            interval_dt_s,
            evaluation_observer=observe_task_substep,
        )
        previous_wrench = (force_xz.copy(), moment_y)
        rom_violation = bool(
            np.any(state_true[:2] < np.asarray(setup.human.q_min_rad) - 1.0e-8)
            or np.any(state_true[:2] > np.asarray(setup.human.q_max_rad) + 1.0e-8)
        )
        rom_violations += int(rom_violation)
        clearance_violation = (
            table_clearance_violation_samples > clearance_violations_before
        )
        true_states.append(
            pre_interval_true_state.copy() if boundary_aligned else state_true.copy()
        )
        estimated_states.append(state_hat.copy())
        references.append(np.concatenate([ref.q_rad, ref.dq_rad_s]))
        actions.append(np.asarray(action, dtype=float))
        forces.append(float(np.linalg.norm(force_xz)))
        moments.append(abs(moment_y))
        executed_interval_durations_s.append(interval_dt_s)
        if rom_violation:
            termination_reason = "evaluation_hidden_rom_violation"
            break
        if clearance_violation:
            termination_reason = "evaluation_hidden_table_clearance_violation"
            break
        if not np.all(np.isfinite(state_true)) or np.max(np.abs(state_true)) > 1.0e4:
            safety_abort_count += 1
            termination_reason = "state_nonfinite_abort"
            break

    if boundary_aligned and len(true_states) == len(executed_interval_durations_s):
        # Whether the run reaches T or aborts at an intermediate boundary, an
        # integrated interval must always have both of its boundary states.
        final_time_s = float(sum(executed_interval_durations_s))
        final_ref = reference(final_time_s)
        if arm == "oracle":
            final_state_hat = state_true.copy()
        else:
            final_position, final_phi, final_velocity, final_phi_dot = _pose_observation(
                setup.geometry,
                state_true[:2],
                state_true[2:],
                rng,
                setup.measurement_position_std_m,
                setup.measurement_angle_std_rad,
            )
            final_state_hat = control_geometry.estimate_state(
                np.array([final_position[0], 0.0, final_position[1]]),
                _rotation_from_phi(final_phi),
                np.array([final_velocity[0], 0.0, final_velocity[1]]),
                np.array([0.0, -final_phi_dot, 0.0]),
            )
        true_states.append(state_true.copy())
        estimated_states.append(final_state_hat.copy())
        references.append(
            np.concatenate([final_ref.q_rad, final_ref.dq_rad_s])
        )

    true_array = np.asarray(true_states)
    estimated_array = np.asarray(estimated_states)
    reference_array = np.asarray(references)
    if len(true_array) == 0:
        return {
            "schema": "architecture_recovery_v2.closed_loop_case.v1",
            "arm": arm,
            "seed": setup.seed,
            "task_seed": task.generation_seed,
            "task_id": task.task_id,
            "high_rom_case": task.high_rom,
            "completed": False,
            "full_horizon_executed": False,
            "clearance_evaluation_enabled": clearance_evaluation_enabled,
            "probe_control_dt_s": probe_control_dt_s,
            "termination_reason": termination_reason,
            "sample_count": 0,
            "evaluation_time_contract": evaluation_time_contract,
            "integration_interval_count": len(executed_interval_durations_s),
            "boundary_sample_count": 0,
            "task_start_true_state_evaluation_only": state_true.tolist(),
            "task_start_estimated_state": state_hat.tolist(),
            "task_initial_reference_q_deg": np.degrees(
                task_initial_reference.q_rad
            ).tolist(),
            "task_initial_reference_dq_deg_s": np.degrees(
                task_initial_reference.dq_rad_s
            ).tolist(),
            "terminal_solver_diagnostics": diagnostics,
            "probe_force_peak_n": probe_force_peak,
            "probe_moment_peak_nm": probe_moment_peak,
            "probe_force_exposure_n_s": probe_force_exposure_n_s,
            "probe_moment_exposure_nm_s": probe_moment_exposure_nm_s,
            "task_force_exposure_n_s": 0.0,
            "task_moment_exposure_nm_s": 0.0,
            "full_episode_force_exposure_n_s": probe_force_exposure_n_s,
            "full_episode_moment_exposure_nm_s": probe_moment_exposure_nm_s,
            "probe_rom_violation": probe_rom_violation,
            "probe_clearance_violation": probe_clearance_violation,
            "probe_min_clearance_m_evaluation_only": probe_min_clearance_m,
            "probe_consistency_abort_count": 0,
            "probe_actual_duration_s": probe_actual_duration_s,
            "probe_settle_timeout_count": 0,
            "probe_estimated_q_min_deg": np.degrees(probe_estimated_q_min).tolist(),
            "probe_estimated_q_max_deg": np.degrees(probe_estimated_q_max).tolist(),
            "rom_violation_samples": rom_violations,
            "table_clearance_violation_samples": table_clearance_violation_samples,
            "task_min_clearance_m_evaluation_only": task_min_clearance_m,
            "post_probe_constructed_reference_min_clearance_m_evaluation_only": (
                post_probe_reference_min_clearance_m
            ),
            "post_probe_constructed_reference_clearance_violation_evaluation_only": (
                post_probe_reference_clearance_violation
            ),
            "solver_failure_count": solve_failures,
            "safety_abort_count": safety_abort_count,
            "estimated_rom_supervisor_abort_count": (
                estimated_rom_supervisor_abort_count
            ),
            "geometry_fit": geometry_fit.record(),
            "dynamics_adaptation": dynamics.record(),
            "dynamics_update_trace": dynamics_update_trace,
            "truth_firewall": {
                "deployable_truth_consumed": False,
                "hidden_setup_used_only_by_plant_generator_and_evaluation": True,
                "oracle_arm_explicitly_non_deployable": arm == "oracle",
            },
            "setup_evaluation_only": setup.evaluation_record(),
            "task_input": task.record(),
        }
    error_deg = np.degrees(true_array[:, :2] - reference_array[:, :2])
    dq_error_deg_s = np.degrees(true_array[:, 2:] - reference_array[:, 2:])
    sample_times_s = (
        corrected_grid.boundary_times_s[: len(error_deg)]
        if boundary_aligned
        else np.arange(len(error_deg), dtype=float) * dt_s
    )
    outbound_duration_s, hold_duration_s, _ = _task_phase_durations(
        task.task_id, task.duration_s
    )

    def phase_entry_window_rmse(entry_s: float) -> float | None:
        selected = (
            (sample_times_s >= entry_s)
            & (sample_times_s < min(entry_s + 0.5, task.duration_s + dt_s))
        )
        if not np.any(selected):
            return None
        return float(np.sqrt(np.mean(error_deg[selected] ** 2)))

    final_q_error = np.abs(error_deg[-1])
    final_dq = np.abs(np.degrees(true_array[-1, 2:]))
    expected_boundary_sample_count = task_steps + 1 if boundary_aligned else task_steps
    completed = bool(
        len(true_array) == expected_boundary_sample_count
        and np.all(final_q_error <= 2.0)
        and np.all(final_dq <= 5.0)
        and rom_violations == 0
        and table_clearance_violation_samples == 0
        and max(forces, default=float("inf")) <= 200.0 + 1.0e-6
        and max(moments, default=float("inf")) <= 60.0 + 1.0e-6
        and solve_failures == 0
        and safety_abort_count == 0
    )
    if termination_reason == "task_horizon_reached":
        termination_reason = "completed" if completed else "closed_loop_gate_failed"
    fit_geometry = control_geometry
    geometry_error = {
        "hip_position_m": float(
            np.linalg.norm(fit_geometry.hip_plane_m - setup.geometry.hip_plane_m)
        ),
        "thigh_length_m": float(
            abs(fit_geometry.thigh_length_m - setup.geometry.thigh_length_m)
        ),
        "knee_to_cuff_m": float(
            abs(fit_geometry.cuff_distance_m - setup.geometry.cuff_distance_m)
        ),
        "full_shank_length_and_fraction_individually_estimated": False,
    }
    return {
        "schema": "architecture_recovery_v2.closed_loop_case.v1",
        "arm": arm,
        "seed": setup.seed,
        "task_seed": task.generation_seed,
        "task_id": task.task_id,
        "high_rom_case": task.high_rom,
        "completed": completed,
        "full_horizon_executed": len(true_array) == expected_boundary_sample_count,
        "clearance_evaluation_enabled": clearance_evaluation_enabled,
        "probe_control_dt_s": probe_control_dt_s,
        "termination_reason": termination_reason,
        "sample_count": len(true_array),
        "evaluation_time_contract": evaluation_time_contract,
        "integration_interval_count": len(executed_interval_durations_s),
        "boundary_sample_count": len(true_array),
        "requested_task_duration_s": task.duration_s,
        "executed_task_duration_s": float(sum(executed_interval_durations_s)),
        "boundary_interval_relation_holds": bool(
            not boundary_aligned
            or len(true_array) == len(executed_interval_durations_s) + 1
        ),
        "task_start_true_q_evaluation_only": task_start_true.tolist(),
        "task_start_estimated_state": estimated_array[0].tolist(),
        "task_initial_reference_q_deg": np.degrees(
            task_initial_reference.q_rad
        ).tolist(),
        "task_initial_reference_dq_deg_s": np.degrees(
            task_initial_reference.dq_rad_s
        ).tolist(),
        "terminal_solver_diagnostics": diagnostics,
        "q_tracking_rmse_deg": float(np.sqrt(np.mean(error_deg**2))),
        "q_tracking_max_abs_deg": float(np.max(np.abs(error_deg))),
        "dq_tracking_rmse_deg_s": float(np.sqrt(np.mean(dq_error_deg_s**2))),
        "hold_entry_0p5s_q_tracking_rmse_deg": phase_entry_window_rmse(
            outbound_duration_s
        ),
        "return_entry_0p5s_q_tracking_rmse_deg": phase_entry_window_rmse(
            outbound_duration_s + hold_duration_s
        ),
        "final_q_error_deg": final_q_error.tolist(),
        "final_dq_deg_s": final_dq.tolist(),
        "force_peak_n": max(forces, default=float("nan")),
        "moment_peak_nm": max(moments, default=float("nan")),
        "probe_force_peak_n": probe_force_peak,
        "probe_moment_peak_nm": probe_moment_peak,
        "probe_force_exposure_n_s": probe_force_exposure_n_s,
        "probe_moment_exposure_nm_s": probe_moment_exposure_nm_s,
        "task_force_exposure_n_s": float(
            np.dot(forces, executed_interval_durations_s)
        ),
        "task_moment_exposure_nm_s": float(
            np.dot(moments, executed_interval_durations_s)
        ),
        "full_episode_force_exposure_n_s": float(
            probe_force_exposure_n_s
            + np.dot(forces, executed_interval_durations_s)
        ),
        "full_episode_moment_exposure_nm_s": float(
            probe_moment_exposure_nm_s
            + np.dot(moments, executed_interval_durations_s)
        ),
        "probe_rom_violation": probe_rom_violation,
        "probe_clearance_violation": probe_clearance_violation,
        "probe_min_clearance_m_evaluation_only": probe_min_clearance_m,
        "probe_consistency_abort_count": 0,
        "probe_actual_duration_s": probe_actual_duration_s,
        "probe_settle_timeout_count": 0,
        "probe_estimated_q_min_deg": np.degrees(probe_estimated_q_min).tolist(),
        "probe_estimated_q_max_deg": np.degrees(probe_estimated_q_max).tolist(),
        "rom_violation_samples": rom_violations,
        "table_clearance_violation_samples": table_clearance_violation_samples,
        "task_min_clearance_m_evaluation_only": task_min_clearance_m,
        "post_probe_constructed_reference_min_clearance_m_evaluation_only": (
            post_probe_reference_min_clearance_m
        ),
        "post_probe_constructed_reference_clearance_violation_evaluation_only": (
            post_probe_reference_clearance_violation
        ),
        "solver_failure_count": solve_failures,
        "safety_abort_count": safety_abort_count,
        "estimated_rom_supervisor_abort_count": estimated_rom_supervisor_abort_count,
        "geometry_fit": geometry_fit.record(),
        "geometry_error_evaluation_only": geometry_error,
        "dynamics_adaptation": dynamics.record(),
        "dynamics_update_trace": dynamics_update_trace,
        "commissioning_accepted_dynamic_updates": commissioning_accepted_updates,
        "beta_error_span_l2_evaluation_only": float(
            np.linalg.norm((dynamics.beta - setup.beta) / dynamics.span)
        ),
        "state_estimation_rmse_deg_evaluation_only": float(
            np.sqrt(np.mean(np.degrees(estimated_array[:, :2] - true_array[:, :2]) ** 2))
        ),
        "accepted_dynamic_update_times_s": accepted_update_times,
        "task_beta_updates_enabled_for_arm": _arm_updates_task_beta(arm),
        "task_beta_update_attempt_count": sum(
            item["phase"] == "task" for item in dynamics_update_trace
        ),
        "task_beta_accepted_update_count": sum(
            item["phase"] == "task" and item["accepted"]
            for item in dynamics_update_trace
        ),
        "task_dynamics_history_window_samples": (
            task_dynamics_history_window_samples
        ),
        "task_dynamics_smoothing_alpha": task_dynamics_smoothing_alpha,
        "task_residual_bias_alpha": task_residual_bias_alpha,
        "task_residual_bias_limit_nm": task_residual_bias_limit_nm,
        "task_residual_bias_enabled_for_arm": residual_layer_enabled,
        "task_residual_bias_representation": (
            "bounded_linear_state_nlms_v1"
            if state_residual
            else "known_reference_phase_banks_v1"
            if phase_banked_residual
            else "single_task_wide_bias_v1"
        ),
        "task_residual_bias_final_nm": residual_bias.tolist(),
        "task_residual_bias_phase_banks_final_nm": {
            phase: value.tolist()
            for phase, value in residual_bias_banks.items()
        } if phase_banked_residual else None,
        "task_residual_bias_peak_abs_nm": residual_bias_peak_abs_nm,
        "task_residual_bias_cap_hit_count": residual_bias_cap_hit_count,
        "task_residual_bias_update_count": residual_bias_update_count,
        "task_residual_bias_max_step_nm": residual_bias_max_step_nm,
        "task_residual_bias_total_variation_l1_nm": (
            residual_bias_total_variation_nm
        ),
        "task_residual_bias_sign_reversal_count": (
            residual_bias_sign_reversal_count
        ),
        "task_state_residual_feature_names": (
            ["constant", "q1_rom", "q2_rom", "dq1_bounded", "dq2_bounded"]
            if state_residual
            else None
        ),
        "task_state_residual_weights_final_nm": (
            state_residual_weights.tolist() if state_residual else None
        ),
        "task_state_residual_weights_finite": (
            bool(np.all(np.isfinite(state_residual_weights)))
            if state_residual
            else None
        ),
        "task_state_residual_weights_within_l2_projection_limit": (
            bool(
                np.all(
                    np.linalg.norm(state_residual_weights, axis=1)
                    <= float(task_residual_bias_limit_nm) + 1.0e-12
                )
            )
            if state_residual
            else None
        ),
        "task_state_residual_weight_peak_l2_nm": (
            state_residual_weight_peak_norm_nm if state_residual else None
        ),
        "task_state_residual_weight_max_component_step_nm": (
            state_residual_weight_max_step_nm if state_residual else None
        ),
        "task_state_residual_weight_total_variation_l1_nm": (
            state_residual_weight_total_variation_nm if state_residual else None
        ),
        "task_state_residual_coefficient_projection_hit_count": (
            state_residual_coefficient_projection_hit_count
            if state_residual
            else None
        ),
        "task_state_residual_observed_output_cap_hit_count": (
            state_residual_observed_output_cap_hit_count
            if state_residual
            else None
        ),
        "task_state_residual_prediction_dynamics_component_evaluation_count": (
            mpc.residual_prediction_dynamics_component_evaluation_count
            if state_residual
            else None
        ),
        "task_state_residual_prediction_dynamics_component_cap_hit_count": (
            mpc.residual_prediction_dynamics_component_cap_hit_count
            if state_residual
            else None
        ),
        "task_state_residual_chosen_rollout_component_evaluation_count": (
            state_residual_chosen_rollout_component_evaluation_count
            if state_residual
            else None
        ),
        "task_state_residual_chosen_rollout_component_cap_hit_count": (
            state_residual_chosen_rollout_component_cap_hit_count
            if state_residual
            else None
        ),
        "task_state_residual_velocity_scale_rad_s": (
            STATE_RESIDUAL_VELOCITY_SCALE_RAD_S if state_residual else None
        ),
        "task_residual_bias_finite": bool(
            all(np.all(np.isfinite(value)) for value in residual_bias_banks.values())
            if phase_banked_residual
            else np.all(np.isfinite(residual_bias))
        ),
        "task_residual_bias_within_limit": bool(
            all(
                np.all(np.abs(value) <= float(task_residual_bias_limit_nm))
                for value in residual_bias_banks.values()
            )
            if phase_banked_residual
            else np.all(np.abs(residual_bias) <= float(task_residual_bias_limit_nm))
        ),
        "truth_firewall": {
            "deployable_truth_consumed": False,
            "hidden_setup_used_only_by_plant_generator_and_evaluation": True,
            "oracle_arm_explicitly_non_deployable": arm == "oracle",
        },
        "setup_evaluation_only": setup.evaluation_record(),
        "task_input": task.record(),
    }
