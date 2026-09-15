"""Engineering-only Stage-5 Goal-MPC smoke runtime on Plant v1."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage3.spring_damper_interface import InterfaceParameters
from traction_mpc_stage4.cuff_allocator import default_engineering_cuff_allocator
from traction_mpc_stage4.measurement import CausalMeasurementLayer, MeasurementCase
from traction_mpc_stage4.mpc import SAFE_ACTION, HumanMPCConfig
from traction_mpc_stage4.track_brake import BRAKE

from .acceleration import (
    CausalModelAccelerationMonitor,
    MODEL_WRENCH_REALIZED_ACCELERATION,
)
from .baseline_replay import FixedStage5Estimator, Stage5SensorBoundaryPlant
from .controller_interface import (
    CONTROLLER_NOMINAL_INTERFACE,
    INTERFACE_AWARE_ESTIMATOR_Q_DQ,
    InterfaceAwareHumanStateObserver,
    NominalInterfaceHoldPredictor,
    make_interface_aware_first_action_batch_preview,
)
from .goal_mpc import (
    GoalDirectedHumanSpaceMPC,
    local_command_reference,
    support_action,
)
from .hold_stabilizer import (
    BumplessExecutableReferenceHandoff,
    BumplessLoadedHoldHandoff,
    LoadedEquilibriumHoldStabilizer,
    LoadedHoldHandoffConfig,
    filter_stage5_executable_action_with_pose,
    initialize_plant_at_loaded_equilibrium,
    solve_loaded_hold_equilibrium,
)
from .human import STAGE5_HUMAN
from .interface_uncertainty import (
    InterfaceUncertaintyMonitor,
    InterfaceUncertaintySpec,
    start_episode_uncertainty_aware,
    transition_phase_uncertainty_aware,
)
from .loaded_execution import (
    build_stage5_loaded_execution_context,
    loaded_execution_target_from_equilibrium,
    with_explicit_robot_target,
)
from .loaded_supervisor import Stage5LoadedTrackBrakeSupervisor
from .mechanics import NOMINAL_PHYSICS_DT_S, STAGE5_RIGID_INTERFACE
from .task import (
    PROVISIONAL_CONTROLLER_COMPLETION_MARGIN,
    PROVISIONAL_LOW_MODERATE_GOAL_TASK,
    ControllerCompletionMargin,
    GoalTaskSpec,
    TaskPhase,
    abort_episode,
    diagnostic_normalized_progress,
    start_episode,
    transition_phase,
    true_episode_complete,
)


CONTROL_DT_S = 0.005
MPC_DT_S = 0.020
FIXED_HUMAN_MODEL_VERSION = "stage5_fixed_registered_human_v1"


class InitialConditionValidationError(ValueError):
    """Structured t=0 rejection for engineering sweep aggregation."""

    def __init__(self, message: str, diagnostics: dict[str, Any]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


def _estimator_observe(estimator: FixedStage5Estimator, measurement: Any) -> None:
    estimator.observe(
        time_s=measurement.sample_time_s,
        position_world_m=measurement.attachment_position_m,
        rotation_world_from_cuff=measurement.attachment_rotation_matrix,
        linear_velocity_world_m_s=measurement.attachment_velocity_m_s,
        angular_velocity_world_rad_s=measurement.attachment_angular_velocity_rad_s,
        force_world_n=measurement.cuff_force_vector_n,
        moment_world_nm=measurement.cuff_moment_vector_nm,
        bed_contaminated=False,
    )


def _task_spec_record(spec: GoalTaskSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "schema": spec.schema,
        "provisional": spec.provisional_not_hardware_or_clinically_calibrated,
        "start_return_target_deg": np.degrees(spec.start_return_target_rad).tolist(),
        "outbound_goal_target_deg": np.degrees(spec.outbound_goal_target_rad).tolist(),
        "q_bounds_deg": np.degrees(np.asarray(spec.q_bounds_rad)).tolist(),
        "joint_angle_completion_tolerance_deg": np.degrees(
            spec.joint_angle_completion_tolerance_rad
        ).tolist(),
        "joint_velocity_completion_tolerance_deg_s": np.degrees(
            spec.joint_velocity_completion_tolerance_rad_s
        ).tolist(),
        "hold_duration_s": spec.hold_duration_s,
        "phase_timeout_s": spec.phase_timeout_s,
        "task_joint_velocity_limit_rad_s": spec.task_joint_velocity_limit_rad_s,
        "task_joint_velocity_limit_deg_s": (
            None
            if spec.task_joint_velocity_limit_rad_s is None
            else np.degrees(spec.task_joint_velocity_limit_rad_s).tolist()
        ),
        "task_joint_acceleration_limit_rad_s2": (
            spec.task_joint_acceleration_limit_rad_s2
        ),
        "task_joint_acceleration_limit_deg_s2": (
            None
            if spec.task_joint_acceleration_limit_rad_s2 is None
            else np.degrees(spec.task_joint_acceleration_limit_rad_s2).tolist()
        ),
    }


def _completion_margin_record(
    spec: GoalTaskSpec, margin: ControllerCompletionMargin
) -> dict[str, Any]:
    angle, velocity = margin.tightened_tolerances(spec)
    return {
        "original_task_angle_tolerance_deg": np.degrees(
            spec.joint_angle_completion_tolerance_rad
        ).tolist(),
        "original_task_velocity_tolerance_deg_s": np.degrees(
            spec.joint_velocity_completion_tolerance_rad_s
        ).tolist(),
        "controller_angle_margin_deg": np.degrees(
            margin.joint_angle_margin_rad
        ).tolist(),
        "controller_velocity_margin_deg_s": np.degrees(
            margin.joint_velocity_margin_rad_s
        ).tolist(),
        "controller_effective_angle_tolerance_deg": np.degrees(angle).tolist(),
        "controller_effective_velocity_tolerance_deg_s": np.degrees(
            velocity
        ).tolist(),
        "source_evidence": margin.source_evidence,
        "truth_used_online": False,
    }


def _executable_command_record(
    *, time_s: float, phase: TaskPhase, action_nm: np.ndarray, command: Any
) -> dict[str, Any]:
    """Serializable transition evidence for one exact executable command."""

    return {
        "time_s": float(time_s),
        "phase": phase.value,
        "action_nm": np.asarray(action_nm, dtype=float).tolist(),
        "wrench_total_world": np.asarray(
            command.wrench_total_world, dtype=float
        ).tolist(),
        "force_position_n": np.asarray(command.force_position_n).tolist(),
        "force_velocity_n": np.asarray(command.force_velocity_n).tolist(),
        "force_allocator_n": np.asarray(command.force_allocator_n).tolist(),
        "moment_orientation_nm": np.asarray(command.moment_orientation_nm).tolist(),
        "moment_angular_velocity_nm": np.asarray(
            command.moment_angular_velocity_nm
        ).tolist(),
        "moment_allocator_nm": np.asarray(command.moment_allocator_nm).tolist(),
        "robot_joint_torque_command_nm": np.asarray(
            command.joint_torque_command_nm
        ).tolist(),
        "robot_joint_torque_unclipped_nm": np.asarray(
            command.unclipped_joint_torque_nm
        ).tolist(),
    }


def _write_plots(output_dir: Path, trace: dict[str, np.ndarray]) -> None:
    time = trace["time_s"]
    estimated = np.degrees(trace["estimated_state_rad_rad_s"][:, :2])
    truth = np.degrees(trace["evaluation_human_q_rad"])
    start = np.degrees(PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad)
    goal = np.degrees(PROVISIONAL_LOW_MODERATE_GOAL_TASK.outbound_goal_target_rad)

    fig, axes = plt.subplots(2, 1, figsize=(9.0, 6.8), sharex=True)
    for joint, axis in enumerate(axes):
        axis.plot(time, estimated[:, joint], label=f"estimated q{joint + 1}", linewidth=1.7)
        axis.plot(
            time,
            truth[:, joint],
            "--",
            label=f"evaluation-only MuJoCo q{joint + 1}",
            linewidth=1.0,
        )
        axis.axhline(start[joint], color="0.45", linestyle=":", label="start/return")
        axis.axhline(goal[joint], color="tab:green", linestyle=":", label="outbound goal")
        axis.set_ylabel("angle [deg]")
        axis.grid(alpha=0.25)
    axes[0].legend(ncol=2, fontsize=8)
    axes[-1].set_xlabel("time [s]")
    fig.suptitle("Stage-5 Goal-MPC smoke: free q1/q2 state trajectory")
    fig.tight_layout()
    fig.savefig(output_dir / "q_trajectory.png", dpi=170)
    plt.close(fig)

    force = np.linalg.norm(trace["physical_cuff_force_world_n"], axis=1)
    fig, axis = plt.subplots(figsize=(9.0, 3.8))
    axis.plot(time, force, color="tab:red", linewidth=1.4)
    axis.axhline(
        CUFF_TRANSLATIONAL_FORCE_GATE_N,
        color="black",
        linestyle="--",
        label="Stage-4 simulation engineering gate",
    )
    axis.set_xlabel("time [s]")
    axis.set_ylabel("physical cuff force [N]")
    axis.set_title("Stage-5 Goal-MPC smoke: physical cuff-force norm")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "cuff_force.png", dpi=170)
    plt.close(fig)


def run_goal_mpc_smoke(
    output_dir: Path,
    *,
    spec: GoalTaskSpec = PROVISIONAL_LOW_MODERATE_GOAL_TASK,
    completion_margin: ControllerCompletionMargin = (
        PROVISIONAL_CONTROLLER_COMPLETION_MARGIN
    ),
    maximum_duration_s: float = 30.5,
    plant_interface_parameters: InterfaceParameters = STAGE5_RIGID_INTERFACE,
    plant_case_name: str = "matched_plant_v1",
    record_selected_horizon_diagnostics: bool = False,
    use_loaded_local_hold: bool = False,
    stop_on_return_entry: bool = False,
    use_bumpless_return_handoff: bool = False,
    diagnose_feasibility_loss: bool = False,
    feasibility_checkpoint_time_s: float | None = None,
    initialize_loaded_equilibrium_with_plant_truth: bool = False,
    interface_uncertainty_spec: InterfaceUncertaintySpec | None = None,
    planning_physical_force_ceiling_n: float = CUFF_TRANSLATIONAL_FORCE_GATE_N,
    planning_joint_velocity_ceiling_rad_s: tuple[float, float] | None = None,
    mpc_config: HumanMPCConfig | None = None,
    plant_factory: Callable[[InterfaceParameters], Stage5SensorBoundaryPlant]
    | None = None,
    session_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one explicitly engineering-only low/moderate Goal-MPC v1.1 episode."""

    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing smoke output: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    if maximum_duration_s <= 0.0 or not np.isfinite(maximum_duration_s):
        raise ValueError("maximum_duration_s must be finite and positive")

    reusing_session = session_context is not None and bool(session_context)
    if reusing_session:
        if interface_uncertainty_spec is not None:
            raise ValueError("repeatability session forbids uncertainty-bank authority")
        if plant_factory is not None:
            raise ValueError("plant_factory is valid only when starting a session")
        plant = session_context["plant"]
        truth = plant.observe()
        estimator_layer = session_context["estimator_layer"]
        mpc_layer = session_context["mpc_layer"]
        low_level_layer = session_context["low_level_layer"]
        estimator = session_context["estimator"]
        current_model = estimator.model
        cuff_allocator = session_context["cuff_allocator"]
        interface_observer = session_context["interface_observer"]
        acceleration_monitor = session_context["acceleration_monitor"]
        interface_uncertainty_monitor = None
        screening_interface_predictor = session_context[
            "screening_interface_predictor"
        ]
        diagnostic_interface_predictor = session_context[
            "diagnostic_interface_predictor"
        ]
        mpc = session_context["mpc"]
        supervisor = session_context["supervisor"]
        start_loaded_equilibrium = session_context["start_loaded_equilibrium"]
        if not np.isclose(
            mpc.planning_physical_force_ceiling_n,
            planning_physical_force_ceiling_n,
        ):
            raise ValueError("session planning-force ceiling changed")
        if mpc.planning_joint_velocity_ceiling_rad_s != (
            None
            if planning_joint_velocity_ceiling_rad_s is None
            else tuple(float(value) for value in planning_joint_velocity_ceiling_rad_s)
        ):
            raise ValueError("session planning-velocity ceiling changed")
    else:
        plant = (
            Stage5SensorBoundaryPlant(
                STAGE5_HUMAN, interface_parameters=plant_interface_parameters
            )
            if plant_factory is None
            else plant_factory(plant_interface_parameters)
        )
        truth = plant.reset(np.asarray(spec.start_return_target_rad, dtype=float))
        ideal = MeasurementCase(
            name="stage5_goal_mpc_ideal_200hz",
            update_rate_hz=200.0,
            latency_s=0.0,
        )
        estimator_layer = CausalMeasurementLayer(ideal, truth)
        mpc_layer = CausalMeasurementLayer(ideal, truth)
        low_level_layer = CausalMeasurementLayer(ideal, truth)
        estimator_measurement = estimator_layer.current
        estimator = FixedStage5Estimator(
            estimator_measurement.attachment_position_m,
            estimator_measurement.attachment_rotation_matrix,
            np.asarray(spec.start_return_target_rad, dtype=float),
        )
        _estimator_observe(estimator, estimator_measurement)
        current_model = estimator.model
        cuff_allocator = default_engineering_cuff_allocator()
    initialization_interface = CONTROLLER_NOMINAL_INTERFACE
    if not reusing_session and initialize_loaded_equilibrium_with_plant_truth:
        # Evaluation-fixture setup only: hold Human q/dq and the required static
        # support wrench fixed while allowing the plant's robot-side cuff pose
        # to reflect its actual K/D.  This record is never passed to the
        # observer, MPC, screening, supervisor, or HOLD controller.
        initialization_interface = replace(
            CONTROLLER_NOMINAL_INTERFACE,
            model_version=f"evaluation_fixture__{plant_case_name}",
            translation_stiffness_n_m=tuple(
                float(value)
                for value in plant_interface_parameters.translation_stiffness_n_m
            ),
            translation_damping_ns_m=tuple(
                float(value)
                for value in plant_interface_parameters.translation_damping_ns_m
            ),
            rotation_stiffness_nm_rad=float(
                plant_interface_parameters.rotation_stiffness_nm_rad
            ),
            rotation_damping_nms_rad=float(
                plant_interface_parameters.rotation_damping_nms_rad
            ),
        )
        evaluation_initializer = getattr(
            plant, "evaluation_loaded_initialization_interface", None
        )
        if evaluation_initializer is not None:
            initialization_interface = evaluation_initializer(
                initialization_interface,
                spec,
                current_model,
                cuff_allocator,
            )
    if not reusing_session:
        start_loaded_equilibrium = solve_loaded_hold_equilibrium(
            spec,
            current_model,
            cuff_allocator,
            interface=initialization_interface,
            target_q_rad=np.asarray(spec.start_return_target_rad, dtype=float),
        )
        truth = initialize_plant_at_loaded_equilibrium(
            plant, current_model, start_loaded_equilibrium
        )
        # Rebase only the causal sensor buffers after changing the time-zero
        # engineering initial condition.  The fixed Human model was calibrated
        # from the undeformed reset measurement and remains controller-side.
        estimator_layer = CausalMeasurementLayer(ideal, truth)
        mpc_layer = CausalMeasurementLayer(ideal, truth)
        low_level_layer = CausalMeasurementLayer(ideal, truth)
        estimator_measurement = estimator_layer.current
        _estimator_observe(estimator, estimator_measurement)
        current_model = estimator.model
        interface_observer = (
            InterfaceAwareHumanStateObserver()
            if interface_uncertainty_spec is None
            else None
        )
        acceleration_monitor = (
            CausalModelAccelerationMonitor(interval_s=MPC_DT_S)
            if interface_uncertainty_spec is None
            else None
        )
        interface_uncertainty_monitor = (
            None
            if interface_uncertainty_spec is None
            else InterfaceUncertaintyMonitor(interface_uncertainty_spec)
        )
        # The selected Human-space action is held for the 20 ms MPC interval even
        # though its executable robot command is refreshed every 5 ms.  Screen the
        # full action hold; keep a separate 5 ms predictor for time-aligned error.
        screening_interface_predictor = NominalInterfaceHoldPredictor(
            control_dt_s=MPC_DT_S,
            planning_force_ceiling_n=planning_physical_force_ceiling_n,
        )
        diagnostic_interface_predictor = NominalInterfaceHoldPredictor(
            control_dt_s=CONTROL_DT_S
        )
        plant.neutral_robot_q = low_level_layer.current.robot_q_rad.copy()
        mpc = GoalDirectedHumanSpaceMPC(
            HumanMPCConfig() if mpc_config is None else mpc_config,
            cuff_allocator=cuff_allocator,
            planning_physical_force_ceiling_n=planning_physical_force_ceiling_n,
            planning_joint_velocity_ceiling_rad_s=(
                planning_joint_velocity_ceiling_rad_s
            ),
        )
        supervisor = Stage5LoadedTrackBrakeSupervisor()
    loaded_equilibrium = None
    hold_stabilizer = None
    hold_handoff = None
    return_handoff = None
    if use_loaded_local_hold:
        loaded_equilibrium = solve_loaded_hold_equilibrium(
            spec, current_model, cuff_allocator
        )
        hold_stabilizer = LoadedEquilibriumHoldStabilizer(
            loaded_equilibrium, current_model
        )
        hold_handoff = BumplessLoadedHoldHandoff(
            hold_stabilizer, config=LoadedHoldHandoffConfig()
        )
    if use_bumpless_return_handoff:
        if not use_loaded_local_hold:
            raise ValueError("return handoff requires the loaded local HOLD chain")
        return_handoff = BumplessExecutableReferenceHandoff(
            config=LoadedHoldHandoffConfig()
        )
    initial_uncertainty_estimate = None
    if interface_uncertainty_monitor is None:
        initial_task_observation, initial_interface_state = interface_observer.update(
            mpc_layer.current,
            current_model,
            human_model_version=FIXED_HUMAN_MODEL_VERSION,
        )
        initial_realized_acceleration = (
            session_context["last_realized_acceleration"]
            if reusing_session
            else acceleration_monitor.update(
                initial_task_observation, initial_interface_state, current_model
            )
        )
    else:
        initial_uncertainty_estimate = interface_uncertainty_monitor.update(
            mpc_layer.current,
            current_model,
            human_model_version=FIXED_HUMAN_MODEL_VERSION,
        )
        initial_nominal = initial_uncertainty_estimate.nominal
        initial_task_observation = initial_nominal.observation
        initial_interface_state = initial_nominal.interface_state
        initial_realized_acceleration = initial_nominal.model_acceleration
    latest_realized_acceleration = initial_realized_acceleration
    try:
        if initial_uncertainty_estimate is None:
            task_state = start_episode(
                spec,
                initial_task_observation.as_array()[:2],
                initial_task_observation.as_array()[2:],
                initial_realized_acceleration.acceleration_rad_s2,
            )
        else:
            task_state = start_episode_uncertainty_aware(
                spec, initial_uncertainty_estimate
            )
    except ValueError as error:
        initial_state = initial_task_observation.as_array()
        truth_interface = plant._evaluate_current_interface()
        message = str(error)
        if "INTERFACE_UNCERTAINTY" in message:
            abort_reason = message.rsplit(": ", 1)[-1]
        elif "TASK_ACCELERATION_LIMIT" in message:
            abort_reason = "TASK_ACCELERATION_LIMIT"
        elif "settled start/return target" in message:
            abort_reason = "INITIAL_CONDITION_OUTSIDE_SETTLED_START_SET"
        else:
            abort_reason = "INITIAL_CONDITION_VALIDATION_ERROR"
        raise InitialConditionValidationError(
            message,
            {
                "task_status": "ABORTED",
                "abort_reason": abort_reason,
                "validation_error": message,
                "time_s": float(truth.time_s),
                "estimated_q_rad": initial_state[:2].tolist(),
                "estimated_dq_rad_s": initial_state[2:].tolist(),
                "truth_q_rad": np.asarray(truth.human_q_rad, dtype=float).tolist(),
                "truth_dq_rad_s": np.asarray(
                    truth.human_dq_rad_s, dtype=float
                ).tolist(),
                "deployable_acceleration_rad_s2": (
                    initial_realized_acceleration.acceleration_rad_s2.tolist()
                ),
                "truth_acceleration_rad_s2": np.asarray(
                    plant.data.qacc[plant.human_dof_indices], dtype=float
                ).tolist(),
                "physical_force_world_n": np.asarray(
                    truth.cuff_force_vector_n, dtype=float
                ).tolist(),
                "physical_moment_world_nm": np.asarray(
                    truth.cuff_moment_vector_nm, dtype=float
                ).tolist(),
                "truth_interface_translation_human_m": (
                    truth_interface.displacement_human_m.tolist()
                ),
                "truth_interface_rotation_human_rad": (
                    truth_interface.rotation_error_human_rad.tolist()
                ),
                "estimated_interface_translation_human_m": (
                    initial_interface_state.displacement_human_m.tolist()
                ),
                "estimated_interface_rotation_human_rad": (
                    initial_interface_state.rotation_error_human_rad.tolist()
                ),
                "task_velocity_limit_rad_s": (
                    None
                    if spec.task_joint_velocity_limit_rad_s is None
                    else list(spec.task_joint_velocity_limit_rad_s)
                ),
                "task_acceleration_limit_rad_s2": (
                    None
                    if spec.task_joint_acceleration_limit_rad_s2 is None
                    else list(spec.task_joint_acceleration_limit_rad_s2)
                ),
                "mujoco_warning_counts": plant.warning_counts(),
                "controller_truth_parameter_separation_preserved": True,
                "interface_uncertainty_state_range_rad_rad_s": (
                    None
                    if initial_uncertainty_estimate is None
                    else {
                        "minimum": np.min(
                            initial_uncertainty_estimate.state_matrix, axis=0
                        ).tolist(),
                        "maximum": np.max(
                            initial_uncertainty_estimate.state_matrix, axis=0
                        ).tolist(),
                    }
                ),
            },
        ) from error

    initial_support_action = support_action(
        initial_task_observation.as_array(), current_model
    )
    initial_support_operating_point = solve_loaded_hold_equilibrium(
        spec,
        current_model,
        cuff_allocator,
        target_q_rad=initial_task_observation.as_array()[:2],
        target_dq_rad_s=initial_task_observation.as_array()[2:],
    )
    initial_support_filter = filter_stage5_executable_action_with_pose(
        plant=plant,
        measurement=low_level_layer.current,
        observation=initial_task_observation,
        interface_state=initial_interface_state,
        human_model=current_model,
        cuff_allocator=cuff_allocator,
        action_nm=initial_support_action,
        reference=initial_support_operating_point.low_level_reference,
        execution_target=loaded_execution_target_from_equilibrium(
            initial_support_operating_point, current_model
        ),
    )
    if not initial_support_filter.feasible:
        raise RuntimeError("time-zero loaded support command is not executable-safe")
    if reusing_session:
        current_action = np.asarray(session_context["current_action_nm"], dtype=float).copy()
        initial_support_command = session_context["last_executable_command"]
    else:
        current_action = initial_support_filter.action_nm.copy()
        initial_support_command = initial_support_filter.filtered_preview.command
        plant.apply_executable_command(initial_support_command)
        screening_interface_predictor.synchronize(
            initial_interface_state,
            initial_support_command.wrench_total_world,
        )
        diagnostic_interface_predictor.synchronize(
            initial_interface_state,
            initial_support_command.wrench_total_world,
        )
    last_executable_command = initial_support_command
    episode_origin_time_s = float(truth.time_s)

    physics_substeps = int(round(CONTROL_DT_S / NOMINAL_PHYSICS_DT_S))
    if physics_substeps * NOMINAL_PHYSICS_DT_S != CONTROL_DT_S:
        raise RuntimeError("Plant-v1 timestep must divide the 5 ms control period")
    high_level_steps = int(round(MPC_DT_S / CONTROL_DT_S))
    if high_level_steps * CONTROL_DT_S != MPC_DT_S:
        raise RuntimeError("MPC period must divide the control period")

    previous_phase = task_state.phase
    previous_task_time_s = float(truth.time_s)
    pending_abort_reason: str | None = None
    task_events = [
        {"time_s": float(truth.time_s), "phase": task_state.phase.value, "reason": None}
    ]
    solver_runtimes_ms: list[float] = []
    solver_statuses: list[str] = []
    solver_timing_breakdowns: list[dict[str, float]] = []
    solver_feasible_candidate_evaluations: list[int] = []
    solver_first_action_feasible_candidate_evaluations: list[int] = []
    safety_filter_statuses: list[str] = []
    safety_filter_interventions: list[float] = []
    mpc_failure_count = 0
    last_mpc_failure_diagnostics: dict[str, Any] | None = None
    feasibility_loss_audit: dict[str, Any] | None = None
    feasibility_sequence_artifact: dict[str, np.ndarray] = {}
    selected_prediction_time: list[float] = []
    selected_prediction_first_state: list[np.ndarray] = []
    selected_prediction_terminal_state: list[np.ndarray] = []
    selected_prediction_first_wrench: list[np.ndarray] = []
    selected_prediction_first_hold_peak_force: list[float] = []
    selected_prediction_first_hold_peak_moment: list[float] = []
    selected_prediction_first_interface_translation: list[np.ndarray] = []
    selected_prediction_first_interface_velocity: list[np.ndarray] = []
    selected_prediction_first_interface_rotation: list[np.ndarray] = []
    selected_prediction_first_interface_angular_velocity: list[np.ndarray] = []
    selected_prediction_initial_drive: list[np.ndarray] = []
    selected_prediction_initial_angular_drive: list[np.ndarray] = []
    selected_prediction_first_base_drive_world: list[np.ndarray] = []
    selected_prediction_first_base_angular_drive_world: list[np.ndarray] = []
    selected_prediction_first_executable_wrench_world: list[np.ndarray] = []
    selected_prefix_prediction_time: list[float] = []
    selected_prefix_prediction_acceleration: list[np.ndarray] = []
    selected_prefix_prediction_state: list[np.ndarray] = []
    selected_prefix_prediction_margin: list[np.ndarray] = []
    selected_prefix_prediction_feasible: list[bool] = []
    selected_prefix_executable_wrench_increment: list[np.ndarray] = []
    brake_event_count = 0
    force_gate_event_count = 0
    structural_event_count = 0
    hold_control_runtimes_ms: list[float] = []
    handoff_entry_time_s: float | None = None
    handoff_initial_force_jump_n: float | None = None
    handoff_initial_moment_jump_nm: float | None = None
    hold_command_force_slew_n: list[float] = []
    hold_command_moment_slew_nm: list[float] = []
    previous_command_wrench = np.asarray(
        initial_support_command.wrench_total_world, dtype=float
    ).copy()
    last_outbound_mpc_command: dict[str, Any] | None = None
    first_hold_command: dict[str, Any] | None = None
    last_hold_command: dict[str, Any] | None = None
    first_return_mpc_command: dict[str, Any] | None = None
    hold_to_return_force_jump_n: float | None = None
    hold_to_return_moment_jump_nm: float | None = None
    hold_to_return_action_jump_nm: float | None = None
    hold_to_return_robot_torque_jump_nm: float | None = None
    outbound_to_hold_force_jump_n: float | None = None
    outbound_to_hold_moment_jump_nm: float | None = None
    outbound_to_hold_action_jump_nm: float | None = None
    outbound_to_hold_robot_torque_jump_nm: float | None = None
    return_handoff_entry_time_s: float | None = None
    return_handoff_completed_time_s: float | None = None
    return_handoff_runtimes_ms: list[float] = []
    return_handoff_force_steps_n: list[float] = []
    return_handoff_moment_steps_nm: list[float] = []
    return_mpc_resumed_after_handoff = False

    trace_time: list[float] = []
    trace_estimated_state: list[np.ndarray] = []
    trace_true_q: list[np.ndarray] = []
    trace_true_dq: list[np.ndarray] = []
    trace_realized_acceleration: list[np.ndarray] = []
    trace_instantaneous_model_acceleration: list[np.ndarray] = []
    trace_realized_acceleration_interval_start: list[float] = []
    trace_realized_generalized_input: list[np.ndarray] = []
    trace_evaluation_acceleration: list[np.ndarray] = []
    trace_force: list[np.ndarray] = []
    trace_moment: list[np.ndarray] = []
    trace_phase: list[str] = []
    trace_progress: list[float] = []
    trace_action: list[np.ndarray] = []
    trace_support_action: list[np.ndarray] = []
    trace_motion_increment: list[np.ndarray] = []
    trace_executable_wrench: list[np.ndarray] = []
    trace_local_reference_q: list[np.ndarray] = []
    trace_observation_age: list[float] = []
    trace_predicted_force: list[np.ndarray] = []
    trace_predicted_peak_force: list[float] = []
    trace_interface_translation: list[np.ndarray] = []
    trace_interface_rotation: list[np.ndarray] = []
    trace_estimated_interface_translation: list[np.ndarray] = []
    trace_estimated_interface_velocity: list[np.ndarray] = []
    trace_estimated_interface_rotation: list[np.ndarray] = []
    trace_estimated_interface_angular_velocity: list[np.ndarray] = []
    trace_prediction_base_drive_world: list[np.ndarray] = []
    trace_prediction_base_angular_drive_world: list[np.ndarray] = []
    trace_prediction_previous_executable_wrench: list[np.ndarray] = []
    trace_robot_cuff_position_world: list[np.ndarray] = []
    trace_robot_cuff_rotation_world: list[np.ndarray] = []
    trace_robot_cuff_linear_velocity_world: list[np.ndarray] = []
    trace_robot_cuff_angular_velocity_world: list[np.ndarray] = []
    trace_measured_cuff_force_world: list[np.ndarray] = []
    trace_measured_cuff_moment_world: list[np.ndarray] = []
    trace_uncertainty_state_min: list[np.ndarray] = []
    trace_uncertainty_state_max: list[np.ndarray] = []
    trace_uncertainty_acceleration_min: list[np.ndarray] = []
    trace_uncertainty_acceleration_max: list[np.ndarray] = []
    trace_uncertainty_causal_acceleration_available: list[bool] = []
    pending_predicted_force = np.full(3, np.nan)
    pending_predicted_peak_force = float("nan")

    maximum_steps = int(np.ceil(maximum_duration_s / CONTROL_DT_S)) + 1
    for control_index in range(maximum_steps):
        truth = plant.observe()
        estimator_measurement = estimator_layer.update(truth)
        mpc_measurement = mpc_layer.update(truth)
        low_level_measurement = low_level_layer.update(truth)
        phase_changed = False

        high_level_cycle = control_index % high_level_steps == 0
        if high_level_cycle:
            _estimator_observe(estimator, estimator_measurement)
            current_model = estimator.model
        uncertainty_estimate = None
        if interface_uncertainty_monitor is None:
            task_observation, interface_state = interface_observer.update(
                mpc_measurement,
                current_model,
                human_model_version=FIXED_HUMAN_MODEL_VERSION,
            )
        else:
            uncertainty_estimate = interface_uncertainty_monitor.update(
                mpc_measurement,
                current_model,
                human_model_version=FIXED_HUMAN_MODEL_VERSION,
            )
            nominal_uncertainty_estimate = uncertainty_estimate.nominal
            task_observation = nominal_uncertainty_estimate.observation
            interface_state = nominal_uncertainty_estimate.interface_state
        screening_interface_predictor.update_from_measurement(interface_state)
        diagnostic_interface_predictor.update_from_measurement(interface_state)
        estimated_state = task_observation.as_array()
        if uncertainty_estimate is not None:
            realized_acceleration = uncertainty_estimate.nominal.model_acceleration
        elif (
            task_observation.sample_timestamp_s
            <= latest_realized_acceleration.sample_timestamp_s + 1.0e-12
        ):
            # A 200 Hz causal measurement can be read more than once at a
            # floating-point scheduler boundary.  Duplicate reads reuse the
            # already-published causal record; they are not new samples.
            realized_acceleration = latest_realized_acceleration
        else:
            realized_acceleration = acceleration_monitor.update(
                task_observation, interface_state, current_model
            )
            latest_realized_acceleration = realized_acceleration
        evaluation_acceleration = np.asarray(
            plant.data.qacc[plant.human_dof_indices], dtype=float
        ).copy()
        support_operating_point = solve_loaded_hold_equilibrium(
            spec,
            current_model,
            cuff_allocator,
            target_q_rad=estimated_state[:2],
            target_dq_rad_s=estimated_state[2:],
        )
        support_reference = support_operating_point.low_level_reference
        support_execution_target = loaded_execution_target_from_equilibrium(
            support_operating_point, current_model
        )

        current_time_s = float(truth.time_s)
        dt_task = current_time_s - previous_task_time_s
        if dt_task > 1.0e-12:
            if pending_abort_reason is not None:
                task_state = abort_episode(task_state, pending_abort_reason)
            else:
                if uncertainty_estimate is None:
                    task_state = transition_phase(
                        spec,
                        task_state,
                        estimated_state[:2],
                        estimated_state[2:],
                        dt_task,
                        ddq_rad_s2=realized_acceleration.acceleration_rad_s2,
                        completion_margin=completion_margin,
                    )
                else:
                    task_state = transition_phase_uncertainty_aware(
                        spec,
                        task_state,
                        uncertainty_estimate,
                        dt_task,
                        completion_margin=completion_margin,
                    )
            previous_task_time_s = current_time_s
            if task_state.phase is not previous_phase:
                phase_changed = True
                task_events.append(
                    {
                        "time_s": current_time_s,
                        "phase": task_state.phase.value,
                        "reason": task_state.abort_reason,
                    }
                )
                previous_phase = task_state.phase

        progress = diagnostic_normalized_progress(spec, task_state.phase, estimated_state[:2])
        trace_time.append(current_time_s)
        trace_estimated_state.append(estimated_state.copy())
        trace_true_q.append(np.asarray(truth.human_q_rad, dtype=float).copy())
        trace_true_dq.append(np.asarray(truth.human_dq_rad_s, dtype=float).copy())
        trace_realized_acceleration.append(
            realized_acceleration.acceleration_rad_s2.copy()
        )
        trace_instantaneous_model_acceleration.append(
            realized_acceleration.instantaneous_acceleration_rad_s2.copy()
        )
        trace_realized_acceleration_interval_start.append(
            realized_acceleration.interval_start_timestamp_s
        )
        trace_realized_generalized_input.append(
            realized_acceleration.generalized_human_input_nm.copy()
        )
        trace_evaluation_acceleration.append(evaluation_acceleration)
        trace_force.append(np.asarray(truth.cuff_force_vector_n, dtype=float).copy())
        trace_moment.append(np.asarray(truth.cuff_moment_vector_nm, dtype=float).copy())
        trace_phase.append(task_state.phase.value)
        trace_progress.append(float("nan") if progress is None else progress)
        trace_action.append(current_action.copy())
        current_support = support_action(estimated_state, current_model)
        trace_support_action.append(current_support.copy())
        trace_motion_increment.append(current_action - current_support)
        trace_executable_wrench.append(previous_command_wrench.copy())
        trace_observation_age.append(task_observation.age_s)
        trace_predicted_force.append(pending_predicted_force.copy())
        trace_predicted_peak_force.append(pending_predicted_peak_force)
        interface_truth, _, _ = plant.interface_diagnostics()
        trace_interface_translation.append(
            interface_truth.displacement_human_m.copy()
        )
        trace_interface_rotation.append(
            interface_truth.rotation_error_human_rad.copy()
        )
        trace_estimated_interface_translation.append(
            interface_state.displacement_human_m.copy()
        )
        trace_estimated_interface_velocity.append(
            interface_state.velocity_human_m_s.copy()
        )
        trace_estimated_interface_rotation.append(
            interface_state.rotation_error_human_rad.copy()
        )
        trace_estimated_interface_angular_velocity.append(
            interface_state.angular_velocity_human_rad_s.copy()
        )
        explicit_prediction_state = screening_interface_predictor.explicit_state
        if explicit_prediction_state is None:
            raise RuntimeError("interface prediction state was not initialized")
        trace_prediction_base_drive_world.append(
            explicit_prediction_state.base_drive_world_n.copy()
        )
        trace_prediction_base_angular_drive_world.append(
            explicit_prediction_state.base_angular_drive_world_nm.copy()
        )
        trace_prediction_previous_executable_wrench.append(
            explicit_prediction_state.previous_executable_wrench_world.copy()
        )
        # Deployable identification boundary for future shadow-online work.
        # These are diagnostic copies only and do not enter Goal-MPC or task
        # decisions.
        trace_robot_cuff_position_world.append(
            np.asarray(mpc_measurement.attachment_position_m, dtype=float).copy()
        )
        trace_robot_cuff_rotation_world.append(
            np.asarray(mpc_measurement.attachment_rotation_matrix, dtype=float).copy()
        )
        trace_robot_cuff_linear_velocity_world.append(
            np.asarray(mpc_measurement.attachment_velocity_m_s, dtype=float).copy()
        )
        trace_robot_cuff_angular_velocity_world.append(
            np.asarray(
                mpc_measurement.attachment_angular_velocity_rad_s, dtype=float
            ).copy()
        )
        trace_measured_cuff_force_world.append(
            np.asarray(mpc_measurement.cuff_force_vector_n, dtype=float).copy()
        )
        trace_measured_cuff_moment_world.append(
            np.asarray(mpc_measurement.cuff_moment_vector_nm, dtype=float).copy()
        )
        if uncertainty_estimate is not None:
            uncertainty_states = uncertainty_estimate.state_matrix
            uncertainty_accelerations = (
                uncertainty_estimate.decision_acceleration_matrix
            )
            trace_uncertainty_state_min.append(np.min(uncertainty_states, axis=0))
            trace_uncertainty_state_max.append(np.max(uncertainty_states, axis=0))
            trace_uncertainty_acceleration_min.append(
                np.min(uncertainty_accelerations, axis=0)
            )
            trace_uncertainty_acceleration_max.append(
                np.max(uncertainty_accelerations, axis=0)
            )
            trace_uncertainty_causal_acceleration_available.append(
                bool(len(uncertainty_estimate.available_causal_acceleration_matrix))
            )

        if task_state.phase in (TaskPhase.COMPLETE, TaskPhase.ABORTED):
            trace_local_reference_q.append(estimated_state[:2].copy())
            break
        if stop_on_return_entry and task_state.phase is TaskPhase.RETURN:
            trace_local_reference_q.append(estimated_state[:2].copy())
            break
        if (
            current_time_s - episode_origin_time_s
            >= maximum_duration_s - 1.0e-12
        ):
            task_state = abort_episode(task_state, "SMOKE_MAXIMUM_DURATION")
            task_events.append(
                {
                    "time_s": current_time_s,
                    "phase": task_state.phase.value,
                    "reason": task_state.abort_reason,
                }
            )
            trace_local_reference_q.append(estimated_state[:2].copy())
            break

        local_hold_cycle = use_loaded_local_hold and task_state.phase is TaskPhase.HOLD
        return_handoff_in_progress = bool(
            use_bumpless_return_handoff
            and task_state.phase is TaskPhase.RETURN
            and return_handoff is not None
            and return_handoff.active
            and not return_handoff.complete
        )
        return_resume_cycle = bool(
            use_bumpless_return_handoff
            and task_state.phase is TaskPhase.RETURN
            and return_handoff is not None
            and return_handoff.complete
            and not return_mpc_resumed_after_handoff
        )
        solve_this_cycle = (
            ((high_level_cycle or phase_changed) and not return_handoff_in_progress)
            or return_resume_cycle
        ) and not local_hold_cycle
        mpc_diagnostics: dict[str, Any] | None = None
        proposed_action: np.ndarray | None = None
        proposed_filter_result = None
        local_reference = None
        return_handoff_cycle = False
        if local_hold_cycle:
            assert hold_handoff is not None
            if not hold_handoff.active:
                hold_handoff.activate(
                    measurement=low_level_measurement,
                    observation=task_observation,
                    interface_state=interface_state,
                    cuff_allocator=cuff_allocator,
                    previous_executable_wrench_world=previous_command_wrench,
                )
                handoff_entry_time_s = current_time_s
            started = perf_counter()
            (
                proposed_action,
                local_reference,
                proposed_filter_result,
                _,
            ) = hold_handoff.command(
                plant=plant,
                measurement=low_level_measurement,
                observation=task_observation,
                interface_state=interface_state,
                cuff_allocator=cuff_allocator,
                dt_s=CONTROL_DT_S,
            )
            hold_control_runtimes_ms.append(1000.0 * (perf_counter() - started))
            current_action = proposed_action.copy()
        if solve_this_cycle:
            if (
                use_loaded_local_hold
                and task_state.phase is TaskPhase.RETURN
                and first_return_mpc_command is None
            ):
                # The Goal-MPC slew term must start from the command that was
                # actually executed during local HOLD, not stale OUTBOUND state.
                mpc.synchronize_executed_total_action(
                    current_action, task_observation, current_model
                )
            supervisor.note_track_mpc_solve()
            screening_execution_context = build_stage5_loaded_execution_context(
                plant=plant,
                measurement=low_level_measurement,
                observation=task_observation,
                interface_state=interface_state,
                human_model=current_model,
                cuff_allocator=cuff_allocator,
                target=support_execution_target,
            )
            executable_batch_preview = (
                screening_execution_context.preview_command_batch
            )
            candidate_batch_preview = make_interface_aware_first_action_batch_preview(
                executable_batch_preview,
                screening_interface_predictor,
                interface_state,
                q_rad=estimated_state[:2],
                human_model=current_model,
                cuff_allocator=cuff_allocator,
                state_rad_rad_s=estimated_state,
                acceleration_limits_rad_s2=(
                    None
                    if spec.task_joint_acceleration_limit_rad_s2 is None
                    else np.asarray(
                        spec.task_joint_acceleration_limit_rad_s2, dtype=float
                    )
                ),
            )
            solve_initial_drive, solve_initial_angular_drive = (
                screening_interface_predictor.inferred_base_drive_human(
                    interface_state
                )
            )

            previous_selected_sequence = (
                None if mpc.last_sequence is None else mpc.last_sequence.copy()
            )
            previous_safest_sequence = (
                None
                if mpc.last_safest_feasible_sequence is None
                else mpc.last_safest_feasible_sequence.copy()
            )
            previous_safest_margin = float(mpc.last_safest_feasible_margin)
            if (
                diagnose_feasibility_loss
                and feasibility_loss_audit is None
                and feasibility_checkpoint_time_s is not None
                and current_time_s >= feasibility_checkpoint_time_s - 1.0e-12
            ):
                continuations = mpc.build_deterministic_continuations(
                    task_observation,
                    task_state,
                    spec,
                    current_model,
                    previous_selected_sequence_nm=previous_selected_sequence,
                    previous_safest_sequence_nm=previous_safest_sequence,
                )
                continuation_audit = mpc.audit_candidate_sequences_with_preview(
                    task_observation,
                    task_state,
                    spec,
                    current_model,
                    continuations,
                    first_action_batch_preview=candidate_batch_preview,
                )
                feasibility_sequence_artifact = {
                    name: value.copy() for name, value in continuations.items()
                }
                explicit_state = screening_interface_predictor.explicit_state
                assert explicit_state is not None
                feasibility_loss_audit = {
                    "checkpoint_time_s": current_time_s,
                    "checkpoint_state_rad_rad_s": estimated_state.tolist(),
                    "previous_accepted_solve_time_s": (
                        None
                        if not selected_prediction_time
                        else selected_prediction_time[-1]
                    ),
                    "measured_minus_previous_prediction_rad_rad_s": (
                        None
                        if not selected_prediction_first_state
                        else (
                            estimated_state - selected_prediction_first_state[-1]
                        ).tolist()
                    ),
                    "explicit_prediction_state": {
                        "model_version": explicit_state.model_version,
                        "transition_assumption": (
                            explicit_state.transition_assumption
                        ),
                        "base_drive_world_n": (
                            explicit_state.base_drive_world_n.tolist()
                        ),
                        "base_angular_drive_world_nm": (
                            explicit_state.base_angular_drive_world_nm.tolist()
                        ),
                        "previous_executable_wrench_world": (
                            explicit_state.previous_executable_wrench_world.tolist()
                        ),
                    },
                    "measured_minus_previous_predicted_interface_state": (
                        None
                        if not selected_prediction_first_interface_translation
                        else {
                            "translation_human_m": (
                                interface_state.displacement_human_m
                                - selected_prediction_first_interface_translation[-1]
                            ).tolist(),
                            "velocity_human_m_s": (
                                interface_state.velocity_human_m_s
                                - selected_prediction_first_interface_velocity[-1]
                            ).tolist(),
                            "rotation_human_rad": (
                                interface_state.rotation_error_human_rad
                                - selected_prediction_first_interface_rotation[-1]
                            ).tolist(),
                            "angular_velocity_human_rad_s": (
                                interface_state.angular_velocity_human_rad_s
                                - selected_prediction_first_interface_angular_velocity[-1]
                            ).tolist(),
                            "base_drive_world_n": (
                                explicit_state.base_drive_world_n
                                - selected_prediction_first_base_drive_world[-1]
                            ).tolist(),
                            "base_angular_drive_world_nm": (
                                explicit_state.base_angular_drive_world_nm
                                - selected_prediction_first_base_angular_drive_world[-1]
                            ).tolist(),
                            "previous_executable_wrench_world": (
                                explicit_state.previous_executable_wrench_world
                                - selected_prediction_first_executable_wrench_world[-1]
                            ).tolist(),
                        }
                    ),
                    "previous_selected_sequence_available": (
                        previous_selected_sequence is not None
                    ),
                    "previous_safest_population_sequence_available": (
                        previous_safest_sequence is not None
                    ),
                    "previous_safest_population_margin": previous_safest_margin,
                    "deterministic_continuations": continuation_audit,
                    "sequence_artifact": "feasibility_loss_sequences.npz",
                }

            started = perf_counter()
            proposed_action, mpc_diagnostics = mpc.solve_goal(
                task_observation,
                task_state,
                spec,
                current_model,
                first_action_batch_preview=candidate_batch_preview,
            )
            solver_runtimes_ms.append(1000.0 * (perf_counter() - started))
            solver_statuses.append(str(mpc_diagnostics["status"]))
            solver_feasible_candidate_evaluations.append(
                int(mpc_diagnostics["feasible_candidate_evaluations"])
            )
            solver_first_action_feasible_candidate_evaluations.append(
                int(mpc_diagnostics["first_action_feasible_candidate_evaluations"])
            )
            selected_prefix_prediction = candidate_batch_preview.last_prediction
            if (
                proposed_action is not None
                and selected_prefix_prediction is not None
                and selected_prefix_prediction.predicted_prefix_acceleration_rad_s2
                is not None
            ):
                if selected_prefix_prediction.prefix_times_s is None or not np.allclose(
                    selected_prefix_prediction.prefix_times_s,
                    np.asarray([0.005, 0.010, 0.015, 0.020]),
                    atol=1.0e-12,
                    rtol=0.0,
                ):
                    raise RuntimeError("selected V2 prefix timestamps are invalid")
                prefix_executable = np.concatenate(
                    [
                        selected_prefix_prediction.executable_batch.force_total_n[0],
                        selected_prefix_prediction.executable_batch.moment_total_nm[0],
                    ]
                )
                selected_prefix_prediction_time.append(current_time_s)
                selected_prefix_prediction_acceleration.append(
                    selected_prefix_prediction.predicted_prefix_acceleration_rad_s2[
                        0
                    ].copy()
                )
                assert (
                    selected_prefix_prediction.predicted_prefix_states_rad_rad_s
                    is not None
                    and selected_prefix_prediction.prefix_acceleration_margin_rad_s2
                    is not None
                    and selected_prefix_prediction.prefix_acceleration_feasible
                    is not None
                )
                selected_prefix_prediction_state.append(
                    selected_prefix_prediction.predicted_prefix_states_rad_rad_s[
                        0
                    ].copy()
                )
                selected_prefix_prediction_margin.append(
                    selected_prefix_prediction.prefix_acceleration_margin_rad_s2[
                        0
                    ].copy()
                )
                selected_prefix_prediction_feasible.append(
                    bool(selected_prefix_prediction.prefix_acceleration_feasible[0])
                )
                selected_prefix_executable_wrench_increment.append(
                    prefix_executable
                    - screening_interface_predictor.previous_executable_wrench_world
                )
            if (
                feasibility_loss_audit is not None
                and feasibility_loss_audit.get("checkpoint_time_s")
                == current_time_s
            ):
                feasibility_loss_audit["checkpoint_production_solve"] = {
                    "status": mpc_diagnostics["status"],
                    "feasible_candidate_evaluations": mpc_diagnostics[
                        "feasible_candidate_evaluations"
                    ],
                    "minimum_constraint_margin": mpc_diagnostics[
                        "minimum_constraint_margin"
                    ],
                }
            timing_breakdown = mpc_diagnostics.get("implementation_timing_ms")
            if isinstance(timing_breakdown, dict):
                solver_timing_breakdowns.append(
                    {
                        str(name): float(value)
                        for name, value in timing_breakdown.items()
                        if np.isfinite(value)
                    }
                )
            if return_resume_cycle:
                return_mpc_resumed_after_handoff = True
            if proposed_action is None:
                mpc_failure_count += 1
                last_mpc_failure_diagnostics = dict(mpc_diagnostics)
                if diagnose_feasibility_loss and feasibility_loss_audit is None:
                    continuations = mpc.build_deterministic_continuations(
                        task_observation,
                        task_state,
                        spec,
                        current_model,
                        previous_selected_sequence_nm=previous_selected_sequence,
                        previous_safest_sequence_nm=previous_safest_sequence,
                    )
                    continuation_audit = mpc.audit_candidate_sequences_with_preview(
                        task_observation,
                        task_state,
                        spec,
                        current_model,
                        continuations,
                        first_action_batch_preview=candidate_batch_preview,
                    )
                    diagnostic_config = replace(
                        mpc.config,
                        candidate_count=512,
                        elite_count=32,
                        cem_iterations=6,
                    )
                    diagnostic_mpc = GoalDirectedHumanSpaceMPC(
                        diagnostic_config,
                        objective=mpc.goal_objective,
                        seed_pacing=mpc.seed_pacing,
                        motion_config=mpc.motion_config,
                        cuff_allocator=cuff_allocator,
                        implementation=mpc.implementation,
                        record_timing_breakdown=True,
                    )
                    diagnostic_mpc.last_action = mpc.last_action.copy()
                    if previous_selected_sequence is not None:
                        diagnostic_mpc.last_sequence = (
                            previous_selected_sequence.copy()
                        )
                    offline_started = perf_counter()
                    offline_action, offline_diagnostics = diagnostic_mpc.solve_goal(
                        task_observation,
                        task_state,
                        spec,
                        current_model,
                        first_action_batch_preview=candidate_batch_preview,
                    )
                    offline_runtime_ms = 1000.0 * (perf_counter() - offline_started)
                    if (
                        offline_action is not None
                        and diagnostic_mpc.last_sequence is not None
                    ):
                        continuations["larger_offline_cem_selected"] = (
                            diagnostic_mpc.last_sequence.copy()
                        )
                        continuation_audit.update(
                            mpc.audit_candidate_sequences_with_preview(
                                task_observation,
                                task_state,
                                spec,
                                current_model,
                                {
                                    "larger_offline_cem_selected": (
                                        diagnostic_mpc.last_sequence
                                    )
                                },
                                first_action_batch_preview=candidate_batch_preview,
                            )
                        )
                    feasibility_sequence_artifact = {
                        name: value.copy() for name, value in continuations.items()
                    }
                    one_step_prediction = (
                        None
                        if not selected_prediction_first_state
                        else selected_prediction_first_state[-1].tolist()
                    )
                    one_step_error = (
                        None
                        if not selected_prediction_first_state
                        else (
                            estimated_state - selected_prediction_first_state[-1]
                        ).tolist()
                    )
                    feasibility_loss_audit = {
                        "failure_time_s": current_time_s,
                        "failure_state_rad_rad_s": estimated_state.tolist(),
                        "previous_accepted_solve_time_s": (
                            None
                            if not selected_prediction_time
                            else selected_prediction_time[-1]
                        ),
                        "previous_one_step_prediction_rad_rad_s": one_step_prediction,
                        "measured_minus_previous_prediction_rad_rad_s": one_step_error,
                        "interface_estimate_at_failure": {
                            "translation_human_m": (
                                interface_state.displacement_human_m.tolist()
                            ),
                            "velocity_human_m_s": (
                                interface_state.velocity_human_m_s.tolist()
                            ),
                            "rotation_human_rad": (
                                interface_state.rotation_error_human_rad.tolist()
                            ),
                            "angular_velocity_human_rad_s": (
                                interface_state.angular_velocity_human_rad_s.tolist()
                            ),
                        },
                        "previous_one_step_interface_prediction": (
                            None
                            if not selected_prediction_first_interface_translation
                            else {
                                "translation_human_m": (
                                    selected_prediction_first_interface_translation[-1].tolist()
                                ),
                                "velocity_human_m_s": (
                                    selected_prediction_first_interface_velocity[-1].tolist()
                                ),
                                "rotation_human_rad": (
                                    selected_prediction_first_interface_rotation[-1].tolist()
                                ),
                                "angular_velocity_human_rad_s": (
                                    selected_prediction_first_interface_angular_velocity[-1].tolist()
                                ),
                            }
                        ),
                        "previous_selected_sequence_available": (
                            previous_selected_sequence is not None
                        ),
                        "previous_safest_population_sequence_available": (
                            previous_safest_sequence is not None
                        ),
                        "previous_safest_population_margin": previous_safest_margin,
                        "inferred_base_drive_human_at_failure": (
                            solve_initial_drive.tolist()
                        ),
                        "inferred_base_angular_drive_human_at_failure": (
                            solve_initial_angular_drive.tolist()
                        ),
                        "previous_solve_inferred_base_drive_human": (
                            None
                            if not selected_prediction_initial_drive
                            else selected_prediction_initial_drive[-1].tolist()
                        ),
                        "previous_solve_inferred_base_angular_drive_human": (
                            None
                            if not selected_prediction_initial_angular_drive
                            else selected_prediction_initial_angular_drive[-1].tolist()
                        ),
                        "production_failure": dict(mpc_diagnostics),
                        "deterministic_continuations": continuation_audit,
                        "larger_offline_search": {
                            "candidate_count": 512,
                            "elite_count": 32,
                            "cem_iterations": 6,
                            "runtime_ms": offline_runtime_ms,
                            "status": offline_diagnostics["status"],
                            "feasible_candidate_evaluations": (
                                offline_diagnostics[
                                    "feasible_candidate_evaluations"
                                ]
                            ),
                            "minimum_constraint_margin": offline_diagnostics[
                                "minimum_constraint_margin"
                            ],
                            "production_settings_changed": False,
                        },
                        "sequence_artifact": "feasibility_loss_sequences.npz",
                    }
            else:
                current_action = proposed_action.copy()
                if record_selected_horizon_diagnostics:
                    if mpc.last_sequence is None:
                        raise RuntimeError("accepted MPC solve did not retain a sequence")
                    mpc._active_human_model = current_model
                    try:
                        selected = candidate_batch_preview.rollout_horizon(
                            estimated_state,
                            mpc.last_sequence[np.newaxis, ...],
                            mpc._batched_base_step,
                            action_resolver=mpc._support_action_batch,
                        )
                    finally:
                        mpc._active_human_model = None
                    selected_prediction_time.append(current_time_s)
                    selected_prediction_first_state.append(
                        selected.predicted_human_states[0, 0].copy()
                    )
                    selected_prediction_terminal_state.append(
                        selected.predicted_human_states[0, -1].copy()
                    )
                    selected_prediction_first_wrench.append(
                        selected.transmitted_mean_wrench_world[0, 0].copy()
                    )
                    selected_prediction_first_hold_peak_force.append(
                        float(selected.predicted_peak_force_n[0, 0])
                    )
                    selected_prediction_first_hold_peak_moment.append(
                        float(selected.predicted_peak_moment_nm[0, 0])
                    )
                    selected_prediction_first_interface_translation.append(
                        selected.interface_displacement_human_m[0, 0].copy()
                    )
                    selected_prediction_first_interface_velocity.append(
                        selected.interface_velocity_human_m_s[0, 0].copy()
                    )
                    selected_prediction_first_interface_rotation.append(
                        selected.interface_rotation_error_human_rad[0, 0].copy()
                    )
                    selected_prediction_first_interface_angular_velocity.append(
                        selected.interface_angular_velocity_human_rad_s[0, 0].copy()
                    )
                    selected_prediction_initial_drive.append(
                        solve_initial_drive.copy()
                    )
                    selected_prediction_initial_angular_drive.append(
                        solve_initial_angular_drive.copy()
                    )
                    selected_prediction_first_base_drive_world.append(
                        selected.base_drive_world_n[0, 0].copy()
                    )
                    selected_prediction_first_base_angular_drive_world.append(
                        selected.base_angular_drive_world_nm[0, 0].copy()
                    )
                    selected_prediction_first_executable_wrench_world.append(
                        selected.executable_wrench_world[0, 0].copy()
                    )

        if local_reference is None:
            local_reference = support_reference
        if (
            use_bumpless_return_handoff
            and task_state.phase is TaskPhase.RETURN
            and return_handoff is not None
            and not return_handoff.complete
        ):
            if not return_handoff.active:
                return_handoff.activate(previous_command_wrench)
                return_handoff_entry_time_s = current_time_s
            started = perf_counter()
            local_reference, _ = return_handoff.reference(
                plant=plant,
                measurement=low_level_measurement,
                observation=task_observation,
                interface_state=interface_state,
                action_nm=current_action,
                human_model=current_model,
                cuff_allocator=cuff_allocator,
                desired_reference=local_reference,
            )
            proposed_filter_result = filter_stage5_executable_action_with_pose(
                plant=plant,
                measurement=low_level_measurement,
                observation=task_observation,
                interface_state=interface_state,
                human_model=current_model,
                cuff_allocator=cuff_allocator,
                action_nm=current_action,
                reference=local_reference,
                execution_target=support_execution_target,
            )
            return_handoff_runtimes_ms.append(
                1000.0 * (perf_counter() - started)
            )
            return_handoff_cycle = True
        if proposed_filter_result is None:
            execution_context = build_stage5_loaded_execution_context(
                plant=plant,
                measurement=low_level_measurement,
                observation=task_observation,
                interface_state=interface_state,
                human_model=current_model,
                cuff_allocator=cuff_allocator,
                target=support_execution_target,
            )
            execution_filter = execution_context.make_force_filter()
            execution_filter(current_action[np.newaxis, :])
            proposed_filter_result = execution_filter.selected_result(current_action)
        trace_local_reference_q.append(local_reference.q_rad.copy())
        supervisor_target = support_execution_target
        if local_hold_cycle:
            assert hold_stabilizer is not None
            supervisor_target = with_explicit_robot_target(
                loaded_execution_target_from_equilibrium(
                    hold_stabilizer.equilibrium, current_model
                ),
                local_reference,
            )
        elif return_handoff_cycle:
            supervisor_target = with_explicit_robot_target(
                support_execution_target, local_reference
            )
        supervisor.bind_loaded_execution(
            task_observation, interface_state, supervisor_target
        )
        decision = supervisor.command(
            plant=plant,
            measurement=low_level_measurement,
            estimated_state=estimated_state,
            human_model=current_model,
            cuff_allocator=cuff_allocator,
            track_reference=local_reference,
            proposed_action_nm=(
                proposed_action
                if mpc_diagnostics is not None or local_hold_cycle
                else current_action
            ),
            mpc_status=(
                SAFE_ACTION
                if local_hold_cycle
                else (None if mpc_diagnostics is None else mpc_diagnostics["status"])
            ),
            proposed_filter_result=proposed_filter_result,
        )
        if decision.safety_filter is not None:
            safety_filter_statuses.append(str(decision.safety_filter["status"]))
            safety_filter_interventions.append(
                float(decision.safety_filter["intervention_coordinate_norm"])
            )
        if decision.mode == BRAKE:
            brake_event_count += int(brake_event_count == 0)
            pending_abort_reason = str(decision.trigger or "BRAKE")
        if decision.terminate:
            task_state = abort_episode(
                task_state, str(decision.terminate_reason or "BRAKE_INFEASIBLE")
            )
            task_events.append(
                {
                    "time_s": current_time_s,
                    "phase": task_state.phase.value,
                    "reason": task_state.abort_reason,
                }
            )
            break
        if decision.action_nm is None or decision.executable_preview is None:
            raise RuntimeError("execution supervisor returned an incomplete command")
        current_action = decision.action_nm.copy()
        # Predict the exact post-filter action actually sent to the plant.  This
        # diagnostic uses the same pure nominal propagation as MPC screening.
        command_wrench = np.asarray(
            decision.executable_preview.command.wrench_total_world, dtype=float
        )
        command_record = _executable_command_record(
            time_s=current_time_s,
            phase=task_state.phase,
            action_nm=current_action,
            command=decision.executable_preview.command,
        )
        if local_hold_cycle:
            pending_predicted_force = np.full(3, np.nan)
            pending_predicted_peak_force = float("nan")
            hold_command_force_slew_n.append(
                float(np.linalg.norm(command_wrench[:3] - previous_command_wrench[:3]))
            )
            hold_command_moment_slew_nm.append(
                float(np.linalg.norm(command_wrench[3:] - previous_command_wrench[3:]))
            )
            if handoff_initial_force_jump_n is None:
                handoff_initial_force_jump_n = hold_command_force_slew_n[-1]
                handoff_initial_moment_jump_nm = hold_command_moment_slew_nm[-1]
                first_hold_command = command_record
                if last_outbound_mpc_command is not None:
                    outbound_action = np.asarray(
                        last_outbound_mpc_command["action_nm"], dtype=float
                    )
                    outbound_torque = np.asarray(
                        last_outbound_mpc_command["robot_joint_torque_command_nm"],
                        dtype=float,
                    )
                    outbound_to_hold_force_jump_n = handoff_initial_force_jump_n
                    outbound_to_hold_moment_jump_nm = handoff_initial_moment_jump_nm
                    outbound_to_hold_action_jump_nm = float(
                        np.linalg.norm(current_action - outbound_action)
                    )
                    outbound_to_hold_robot_torque_jump_nm = float(
                        np.linalg.norm(
                            np.asarray(
                                command_record["robot_joint_torque_command_nm"],
                                dtype=float,
                            )
                            - outbound_torque
                        )
                    )
            last_hold_command = command_record
            previous_command_wrench = command_wrench.copy()
        else:
            if task_state.phase is TaskPhase.OUTBOUND:
                last_outbound_mpc_command = command_record
            elif (
                task_state.phase is TaskPhase.RETURN
                and first_return_mpc_command is None
            ):
                first_return_mpc_command = command_record
                if last_hold_command is not None:
                    last_wrench = np.asarray(
                        last_hold_command["wrench_total_world"], dtype=float
                    )
                    last_action = np.asarray(
                        last_hold_command["action_nm"], dtype=float
                    )
                    hold_to_return_force_jump_n = float(
                        np.linalg.norm(command_wrench[:3] - last_wrench[:3])
                    )
                    hold_to_return_moment_jump_nm = float(
                        np.linalg.norm(command_wrench[3:] - last_wrench[3:])
                    )
                    hold_to_return_action_jump_nm = float(
                        np.linalg.norm(current_action - last_action)
                    )
                    hold_to_return_robot_torque_jump_nm = float(
                        np.linalg.norm(
                            np.asarray(
                                command_record["robot_joint_torque_command_nm"],
                                dtype=float,
                            )
                            - np.asarray(
                                last_hold_command["robot_joint_torque_command_nm"],
                                dtype=float,
                            )
                        )
                    )
            if return_handoff_cycle:
                pending_predicted_force = np.full(3, np.nan)
                pending_predicted_peak_force = float("nan")
                return_handoff_force_steps_n.append(
                    float(
                        np.linalg.norm(
                            command_wrench[:3] - previous_command_wrench[:3]
                        )
                    )
                )
                return_handoff_moment_steps_nm.append(
                    float(
                        np.linalg.norm(
                            command_wrench[3:] - previous_command_wrench[3:]
                        )
                    )
                )
                return_handoff.advance(CONTROL_DT_S)
                if return_handoff.complete:
                    return_handoff_completed_time_s = current_time_s + CONTROL_DT_S
            else:
                diagnostic_target = support_execution_target
                if local_hold_cycle:
                    assert hold_stabilizer is not None
                    diagnostic_target = with_explicit_robot_target(
                        loaded_execution_target_from_equilibrium(
                            hold_stabilizer.equilibrium, current_model
                        ),
                        local_reference,
                    )
                executed_context = build_stage5_loaded_execution_context(
                    plant=plant,
                    measurement=low_level_measurement,
                    observation=task_observation,
                    interface_state=interface_state,
                    human_model=current_model,
                    cuff_allocator=cuff_allocator,
                    target=diagnostic_target,
                )
                executed_batch = executed_context.preview_command_batch(
                    current_action[np.newaxis, :]
                )
                executed_prediction = diagnostic_interface_predictor.predict_batch(
                    interface_state, executed_batch
                )
                pending_predicted_force = (
                    executed_prediction.predicted_endpoint_force_world_n[0].copy()
                )
                pending_predicted_peak_force = float(
                    executed_prediction.predicted_peak_force_n[0]
                )
            previous_command_wrench = command_wrench.copy()
        plant.apply_executable_command(decision.executable_preview.command)
        last_executable_command = decision.executable_preview.command
        screening_interface_predictor.synchronize(
            interface_state,
            decision.executable_preview.command.wrench_total_world,
        )
        diagnostic_interface_predictor.synchronize(
            interface_state,
            decision.executable_preview.command.wrench_total_world,
        )

        for _ in range(physics_substeps):
            truth = plant.step()
        force_norm = float(np.linalg.norm(truth.cuff_force_vector_n))
        if force_norm > CUFF_TRANSLATIONAL_FORCE_GATE_N + 1.0e-9:
            force_gate_event_count += 1
            pending_abort_reason = "PHYSICAL_CUFF_FORCE_GATE"
        true_q = np.asarray(truth.human_q_rad, dtype=float)
        if (
            np.any(true_q < np.asarray(STAGE5_HUMAN.q_min_rad) - 1.0e-9)
            or np.any(true_q > np.asarray(STAGE5_HUMAN.q_max_rad) + 1.0e-9)
            or bool(truth.unintended_contact_pairs)
            or not np.all(np.isfinite(true_q))
        ):
            structural_event_count += 1
            pending_abort_reason = "SIMULATION_STRUCTURAL_EVENT"

    trace = {
        "time_s": np.asarray(trace_time, dtype=float),
        "estimated_state_rad_rad_s": np.asarray(trace_estimated_state, dtype=float),
        "evaluation_human_q_rad": np.asarray(trace_true_q, dtype=float),
        "evaluation_human_dq_rad_s": np.asarray(trace_true_dq, dtype=float),
        "deployable_realized_acceleration_rad_s2": np.asarray(
            trace_realized_acceleration, dtype=float
        ),
        "deployable_instantaneous_model_acceleration_rad_s2": np.asarray(
            trace_instantaneous_model_acceleration, dtype=float
        ),
        "deployable_acceleration_interval_start_s": np.asarray(
            trace_realized_acceleration_interval_start, dtype=float
        ),
        "deployable_measured_generalized_input_nm": np.asarray(
            trace_realized_generalized_input, dtype=float
        ),
        "evaluation_only_instantaneous_acceleration_rad_s2": np.asarray(
            trace_evaluation_acceleration, dtype=float
        ),
        "physical_cuff_force_world_n": np.asarray(trace_force, dtype=float),
        "physical_cuff_moment_world_nm": np.asarray(trace_moment, dtype=float),
        "task_phase": np.asarray(trace_phase, dtype=str),
        "diagnostic_progress": np.asarray(trace_progress, dtype=float),
        "executed_generalized_action_nm": np.asarray(trace_action, dtype=float),
        "support_generalized_action_nm": np.asarray(
            trace_support_action, dtype=float
        ),
        "motion_increment_generalized_action_nm": np.asarray(
            trace_motion_increment, dtype=float
        ),
        "executed_command_wrench_world": np.asarray(
            trace_executable_wrench, dtype=float
        ),
        "local_reference_q_rad": np.asarray(trace_local_reference_q, dtype=float),
        "task_observation_age_s": np.asarray(trace_observation_age, dtype=float),
        "predicted_next_physical_cuff_force_world_n": np.asarray(
            trace_predicted_force, dtype=float
        ),
        "predicted_hold_peak_physical_cuff_force_n": np.asarray(
            trace_predicted_peak_force, dtype=float
        ),
        "interface_translation_human_m": np.asarray(
            trace_interface_translation, dtype=float
        ),
        "interface_rotation_human_rad": np.asarray(
            trace_interface_rotation, dtype=float
        ),
        "estimated_interface_translation_human_m": np.asarray(
            trace_estimated_interface_translation, dtype=float
        ),
        "estimated_interface_velocity_human_m_s": np.asarray(
            trace_estimated_interface_velocity, dtype=float
        ),
        "estimated_interface_rotation_human_rad": np.asarray(
            trace_estimated_interface_rotation, dtype=float
        ),
        "estimated_interface_angular_velocity_human_rad_s": np.asarray(
            trace_estimated_interface_angular_velocity, dtype=float
        ),
        "prediction_base_drive_world_n": np.asarray(
            trace_prediction_base_drive_world, dtype=float
        ),
        "prediction_base_angular_drive_world_nm": np.asarray(
            trace_prediction_base_angular_drive_world, dtype=float
        ),
        "prediction_previous_executable_wrench_world": np.asarray(
            trace_prediction_previous_executable_wrench, dtype=float
        ),
        "deployable_robot_cuff_position_world_m": np.asarray(
            trace_robot_cuff_position_world, dtype=float
        ),
        "deployable_robot_cuff_rotation_world": np.asarray(
            trace_robot_cuff_rotation_world, dtype=float
        ),
        "deployable_robot_cuff_linear_velocity_world_m_s": np.asarray(
            trace_robot_cuff_linear_velocity_world, dtype=float
        ),
        "deployable_robot_cuff_angular_velocity_world_rad_s": np.asarray(
            trace_robot_cuff_angular_velocity_world, dtype=float
        ),
        "deployable_measured_cuff_force_world_n": np.asarray(
            trace_measured_cuff_force_world, dtype=float
        ),
        "deployable_measured_cuff_moment_world_nm": np.asarray(
            trace_measured_cuff_moment_world, dtype=float
        ),
        "interface_uncertainty_state_min_rad_rad_s": np.asarray(
            trace_uncertainty_state_min, dtype=float
        ).reshape(-1, 4),
        "interface_uncertainty_state_max_rad_rad_s": np.asarray(
            trace_uncertainty_state_max, dtype=float
        ).reshape(-1, 4),
        "interface_uncertainty_acceleration_min_rad_s2": np.asarray(
            trace_uncertainty_acceleration_min, dtype=float
        ).reshape(-1, 2),
        "interface_uncertainty_acceleration_max_rad_s2": np.asarray(
            trace_uncertainty_acceleration_max, dtype=float
        ).reshape(-1, 2),
        "interface_uncertainty_causal_acceleration_available": np.asarray(
            trace_uncertainty_causal_acceleration_available, dtype=bool
        ),
        "selected_prediction_time_s": np.asarray(
            selected_prediction_time, dtype=float
        ),
        "selected_prediction_first_state_rad_rad_s": np.asarray(
            selected_prediction_first_state, dtype=float
        ).reshape(-1, 4),
        "selected_prediction_terminal_state_rad_rad_s": np.asarray(
            selected_prediction_terminal_state, dtype=float
        ).reshape(-1, 4),
        "selected_prediction_first_transmitted_wrench_world": np.asarray(
            selected_prediction_first_wrench, dtype=float
        ).reshape(-1, 6),
        "selected_prediction_first_hold_peak_force_n": np.asarray(
            selected_prediction_first_hold_peak_force, dtype=float
        ),
        "selected_prediction_first_hold_peak_moment_nm": np.asarray(
            selected_prediction_first_hold_peak_moment, dtype=float
        ),
        "selected_prediction_first_interface_translation_human_m": np.asarray(
            selected_prediction_first_interface_translation, dtype=float
        ).reshape(-1, 3),
        "selected_prediction_first_interface_velocity_human_m_s": np.asarray(
            selected_prediction_first_interface_velocity, dtype=float
        ).reshape(-1, 3),
        "selected_prediction_first_interface_rotation_human_rad": np.asarray(
            selected_prediction_first_interface_rotation, dtype=float
        ).reshape(-1, 3),
        "selected_prediction_first_interface_angular_velocity_human_rad_s": np.asarray(
            selected_prediction_first_interface_angular_velocity, dtype=float
        ).reshape(-1, 3),
        "selected_prediction_initial_drive_human": np.asarray(
            selected_prediction_initial_drive, dtype=float
        ).reshape(-1, 3),
        "selected_prediction_initial_angular_drive_human": np.asarray(
            selected_prediction_initial_angular_drive, dtype=float
        ).reshape(-1, 3),
        "selected_prediction_first_base_drive_world_n": np.asarray(
            selected_prediction_first_base_drive_world, dtype=float
        ).reshape(-1, 3),
        "selected_prediction_first_base_angular_drive_world_nm": np.asarray(
            selected_prediction_first_base_angular_drive_world, dtype=float
        ).reshape(-1, 3),
        "selected_prediction_first_executable_wrench_world": np.asarray(
            selected_prediction_first_executable_wrench_world, dtype=float
        ).reshape(-1, 6),
        "selected_v2_prefix_prediction_time_s": np.asarray(
            selected_prefix_prediction_time, dtype=float
        ),
        "selected_v2_prefix_acceleration_rad_s2": np.asarray(
            selected_prefix_prediction_acceleration, dtype=float
        ).reshape(-1, 4, 2),
        "selected_v2_prefix_state_rad_rad_s": np.asarray(
            selected_prefix_prediction_state, dtype=float
        ).reshape(-1, 4, 4),
        "selected_v2_prefix_acceleration_margin_rad_s2": np.asarray(
            selected_prefix_prediction_margin, dtype=float
        ).reshape(-1, 4, 2),
        "selected_v2_prefix_acceleration_feasible": np.asarray(
            selected_prefix_prediction_feasible, dtype=bool
        ),
        "selected_v2_prefix_executable_wrench_increment_world": np.asarray(
            selected_prefix_executable_wrench_increment, dtype=float
        ).reshape(-1, 6),
        "mpc_feasible_candidate_evaluations": np.asarray(
            solver_feasible_candidate_evaluations, dtype=int
        ),
        "mpc_first_action_feasible_candidate_evaluations": np.asarray(
            solver_first_action_feasible_candidate_evaluations, dtype=int
        ),
    }
    # A repeatability session keeps plant/controller clocks and causal history
    # continuous, while each saved episode uses a local zero-based time axis.
    # This is a reporting transform only; all online transitions above used the
    # unchanged absolute causal timestamps.
    for key in (
        "time_s",
        "deployable_acceleration_interval_start_s",
        "selected_prediction_time_s",
        "selected_v2_prefix_prediction_time_s",
    ):
        values = trace[key]
        finite = np.isfinite(values)
        values[finite] -= episode_origin_time_s
    for event in task_events:
        event["time_s"] = float(event["time_s"] - episode_origin_time_s)
    if handoff_entry_time_s is not None:
        handoff_entry_time_s -= episode_origin_time_s
    if return_handoff_entry_time_s is not None:
        return_handoff_entry_time_s -= episode_origin_time_s
    if return_handoff_completed_time_s is not None:
        return_handoff_completed_time_s -= episode_origin_time_s
    time = trace["time_s"]
    force_norm = np.linalg.norm(trace["physical_cuff_force_world_n"], axis=1)
    moment_norm = np.linalg.norm(trace["physical_cuff_moment_world_nm"], axis=1)
    estimated_q = trace["estimated_state_rad_rad_s"][:, :2]
    evaluation_q = trace["evaluation_human_q_rad"]
    evaluation_dq = trace["evaluation_human_dq_rad_s"]
    estimated_dq = trace["estimated_state_rad_rad_s"][:, 2:]
    deployable_realized_ddq = trace["deployable_realized_acceleration_rad_s2"]
    deployable_instantaneous_ddq = trace[
        "deployable_instantaneous_model_acceleration_rad_s2"
    ]
    evaluation_instantaneous_ddq = trace[
        "evaluation_only_instantaneous_acceleration_rad_s2"
    ]
    legacy_estimated_ddq = np.zeros_like(estimated_dq)
    evaluation_interval_ddq = np.zeros_like(evaluation_dq)
    if len(time) > 1:
        sample_dt = np.diff(time)[:, None]
        legacy_estimated_ddq[1:] = np.diff(estimated_dq, axis=0) / sample_dt
    for index, timestamp in enumerate(time):
        interval_start = max(float(time[0]), float(timestamp - MPC_DT_S))
        duration = float(timestamp - interval_start)
        if duration <= 1.0e-15:
            evaluation_interval_ddq[index] = evaluation_instantaneous_ddq[index]
            continue
        start_dq = np.array(
            [
                np.interp(
                    interval_start,
                    time[: index + 1],
                    evaluation_dq[: index + 1, joint],
                )
                for joint in range(2)
            ]
        )
        evaluation_interval_ddq[index] = (
            evaluation_dq[index] - start_dq
        ) / duration
    selected_prediction_acceleration = np.empty((0, 2), dtype=float)
    aligned_acceleration_intervals: list[dict[str, Any]] = []
    if len(trace["selected_prediction_time_s"]):
        predicted_items: list[np.ndarray] = []
        for start_time, predicted_state in zip(
            trace["selected_prediction_time_s"],
            trace["selected_prediction_first_state_rad_rad_s"],
            strict=True,
        ):
            start_matches = np.flatnonzero(np.isclose(time, start_time, atol=1.0e-10))
            if not len(start_matches):
                continue
            start_index = int(start_matches[0])
            predicted_acceleration = (
                predicted_state[2:] - estimated_dq[start_index]
            ) / MPC_DT_S
            predicted_items.append(predicted_acceleration)
            end_time = float(start_time + MPC_DT_S)
            end_matches = np.flatnonzero(np.isclose(time, end_time, atol=1.0e-10))
            if not len(end_matches):
                continue
            end_index = int(end_matches[0])
            interval_time = time[start_index : end_index + 1]
            causal_model_mean = np.trapezoid(
                deployable_instantaneous_ddq[start_index : end_index + 1],
                interval_time,
                axis=0,
            ) / MPC_DT_S
            aligned_acceleration_intervals.append(
                {
                    "start_time_s": float(start_time),
                    "end_time_s": end_time,
                    "mpc_predicted_interval_acceleration_deg_s2": np.degrees(
                        predicted_acceleration
                    ).tolist(),
                    "deployable_model_causal_interval_mean_deg_s2": np.degrees(
                        causal_model_mean
                    ).tolist(),
                    "estimated_realized_interval_acceleration_deg_s2": np.degrees(
                        (estimated_dq[end_index] - estimated_dq[start_index])
                        / MPC_DT_S
                    ).tolist(),
                    "evaluation_only_truth_interval_acceleration_deg_s2": np.degrees(
                        (evaluation_dq[end_index] - evaluation_dq[start_index])
                        / MPC_DT_S
                    ).tolist(),
                }
            )
        if predicted_items:
            selected_prediction_acceleration = np.asarray(
                predicted_items, dtype=float
            )
    trace["selected_prediction_first_acceleration_rad_s2"] = (
        selected_prediction_acceleration
    )
    q_error = estimated_q - evaluation_q
    dq_error = estimated_dq - evaluation_dq
    predicted_force = trace["predicted_next_physical_cuff_force_world_n"]
    valid_force_prediction = np.all(np.isfinite(predicted_force), axis=1)
    force_vector_error = np.linalg.norm(
        predicted_force[valid_force_prediction]
        - trace["physical_cuff_force_world_n"][valid_force_prediction],
        axis=1,
    )
    force_norm_error = np.abs(
        np.linalg.norm(predicted_force[valid_force_prediction], axis=1)
        - force_norm[valid_force_prediction]
    )
    goal = np.asarray(spec.outbound_goal_target_rad)
    start = np.asarray(spec.start_return_target_rad)
    outbound_samples = np.isin(trace["task_phase"], [TaskPhase.OUTBOUND.value, TaskPhase.HOLD.value])
    outbound_error = np.linalg.norm(estimated_q[outbound_samples] - goal, axis=1)
    normalized_q1 = (estimated_q[:, 0] - start[0]) / (goal[0] - start[0])
    normalized_q2 = (estimated_q[:, 1] - start[1]) / (goal[1] - start[1])
    path_coordination_difference = np.abs(normalized_q1 - normalized_q2)
    solver = np.asarray(solver_runtimes_ms, dtype=float)
    hold_runtime = np.asarray(hold_control_runtimes_ms, dtype=float)
    hold_samples = trace["task_phase"] == TaskPhase.HOLD.value
    return_indices = np.flatnonzero(trace["task_phase"] == TaskPhase.RETURN.value)
    if len(return_indices):
        # The transition sample closes the final 5 ms interval that the task
        # state counted toward HOLD before changing the phase label.
        hold_samples[return_indices[0]] = True
    goal_set_condition = np.all(
        np.abs(estimated_q - goal)
        <= np.asarray(spec.joint_angle_completion_tolerance_rad),
        axis=1,
    ) & np.all(
        np.abs(estimated_dq)
        <= np.asarray(spec.joint_velocity_completion_tolerance_rad_s),
        axis=1,
    )
    hold_inside_set = hold_samples & goal_set_condition
    longest_hold_inside_s = 0.0
    current_hold_inside_s = 0.0
    for inside in hold_inside_set:
        current_hold_inside_s = (
            current_hold_inside_s + CONTROL_DT_S if inside else 0.0
        )
        longest_hold_inside_s = max(longest_hold_inside_s, current_hold_inside_s)
    hold_indices = np.flatnonzero(hold_samples)
    initial_indices = np.flatnonzero(time <= min(float(time[-1]), 0.10) + 1.0e-12)
    last_hold_index = int(hold_indices[-1]) if len(hold_indices) else None
    hold_invalid_indices = hold_indices[~goal_set_condition[hold_indices]]
    settled_hold_recovery_s = None
    if handoff_entry_time_s is not None:
        if not len(hold_invalid_indices):
            settled_hold_recovery_s = 0.0
        elif hold_invalid_indices[-1] + 1 < len(time):
            settled_hold_recovery_s = float(
                time[hold_invalid_indices[-1] + 1] - handoff_entry_time_s
            )
    phase_metrics: dict[str, Any] = {}
    phase_landmarks: dict[str, list[dict[str, Any]]] = {}
    for phase in (TaskPhase.OUTBOUND, TaskPhase.HOLD, TaskPhase.RETURN):
        indices = np.flatnonzero(trace["task_phase"] == phase.value)
        if not len(indices):
            continue
        phase_time = time[indices]
        phase_force = force_norm[indices]
        phase_metrics[phase.value] = {
            "start_time_s": float(phase_time[0]),
            "end_time_s": float(phase_time[-1]),
            "q_min_deg": np.degrees(np.min(estimated_q[indices], axis=0)).tolist(),
            "q_max_deg": np.degrees(np.max(estimated_q[indices], axis=0)).tolist(),
            "terminal_q_deg": np.degrees(estimated_q[indices[-1]]).tolist(),
            "terminal_dq_deg_s": np.degrees(estimated_dq[indices[-1]]).tolist(),
            "peak_force_n": float(np.max(phase_force)),
            "cumulative_force_n_s": (
                float(np.trapezoid(phase_force, phase_time))
                if len(indices) > 1
                else 0.0
            ),
            "peak_moment_nm": float(np.max(moment_norm[indices])),
        }
        landmark_indices = np.unique(
            np.rint(np.linspace(indices[0], indices[-1], 5)).astype(int)
        )
        phase_landmarks[phase.value] = [
            {
                "time_s": float(time[index]),
                "q_deg": np.degrees(estimated_q[index]).tolist(),
                "dq_deg_s": np.degrees(estimated_dq[index]).tolist(),
            }
            for index in landmark_indices
        ]
    active_phase_at_termination = next(
        phase
        for phase in reversed(trace["task_phase"])
        if phase not in (TaskPhase.COMPLETE.value, TaskPhase.ABORTED.value)
    )
    terminal_target = (
        goal
        if active_phase_at_termination in (
            TaskPhase.OUTBOUND.value,
            TaskPhase.HOLD.value,
        )
        else start
    )
    transition_completion_audit: list[dict[str, Any]] = []
    original_angle_tolerance = np.asarray(
        spec.joint_angle_completion_tolerance_rad
    )
    original_velocity_tolerance = np.asarray(
        spec.joint_velocity_completion_tolerance_rad_s
    )
    tightened_angle_tolerance, tightened_velocity_tolerance = (
        completion_margin.tightened_tolerances(spec)
    )
    for event in task_events[1:]:
        phase_name = str(event["phase"])
        if phase_name not in {
            TaskPhase.HOLD.value,
            TaskPhase.RETURN.value,
            TaskPhase.COMPLETE.value,
        }:
            continue
        event_index = int(np.argmin(np.abs(time - float(event["time_s"]))))
        target = goal if phase_name in {TaskPhase.HOLD.value, TaskPhase.RETURN.value} else start
        estimate_position_error = np.abs(estimated_q[event_index] - target)
        truth_position_error = np.abs(evaluation_q[event_index] - target)
        estimate_velocity = np.abs(estimated_dq[event_index])
        truth_velocity = np.abs(evaluation_dq[event_index])
        transition_completion_audit.append(
            {
                "entered_phase": phase_name,
                "time_s": float(time[event_index]),
                "estimated_position_error_deg": np.degrees(
                    estimate_position_error
                ).tolist(),
                "evaluation_only_truth_position_error_deg": np.degrees(
                    truth_position_error
                ).tolist(),
                "estimated_abs_velocity_deg_s": np.degrees(
                    estimate_velocity
                ).tolist(),
                "evaluation_only_truth_abs_velocity_deg_s": np.degrees(
                    truth_velocity
                ).tolist(),
                "estimator_minus_truth_q_deg": np.degrees(
                    estimated_q[event_index] - evaluation_q[event_index]
                ).tolist(),
                "estimator_minus_truth_dq_deg_s": np.degrees(
                    estimated_dq[event_index] - evaluation_dq[event_index]
                ).tolist(),
                "controller_tightened_set_clearance": {
                    "position_deg": np.degrees(
                        np.asarray(tightened_angle_tolerance)
                        - estimate_position_error
                    ).tolist(),
                    "velocity_deg_s": np.degrees(
                        np.asarray(tightened_velocity_tolerance) - estimate_velocity
                    ).tolist(),
                },
                "evaluation_truth_original_set_clearance": {
                    "position_deg": np.degrees(
                        original_angle_tolerance - truth_position_error
                    ).tolist(),
                    "velocity_deg_s": np.degrees(
                        original_velocity_tolerance - truth_velocity
                    ).tolist(),
                },
                "evaluation_truth_satisfies_original_task_set": bool(
                    np.all(truth_position_error <= original_angle_tolerance + 1.0e-12)
                    and np.all(truth_velocity <= original_velocity_tolerance + 1.0e-12)
                ),
            }
        )
    timing_names = sorted(
        {name for item in solver_timing_breakdowns for name in item}
    )
    timing_breakdown_summary = {
        name: {
            "mean": float(np.mean([item[name] for item in solver_timing_breakdowns if name in item])),
            "p95": float(np.percentile([item[name] for item in solver_timing_breakdowns if name in item], 95)),
            "max": float(np.max([item[name] for item in solver_timing_breakdowns if name in item])),
        }
        for name in timing_names
    }
    summary = {
        "evidence_category": "engineering_smoke_only",
        "selected_horizon_diagnostics_recorded": bool(
            record_selected_horizon_diagnostics
        ),
        "plant": "Stage-5 Plant v1",
        "controller": (
            "stage5_support_centered_goal_mpc_loaded_hold_bumpless_return_v1"
            if use_bumpless_return_handoff
            else (
                "stage5_goal_mpc_outbound_plus_loaded_local_hold_v1"
                if use_loaded_local_hold
                else "stage5_goal_directed_human_space_cem_mpc_v1.3"
            )
        ),
        "plant_case_name": plant_case_name,
        "repeatability_session": {
            "session_reused": bool(reusing_session),
            "episode_index": (
                1
                if session_context is None
                else int(session_context.get("episode_count", 0)) + 1
            ),
            "continuous_plant_clock_and_rng": session_context is not None,
            "plant_estimator_interface_history_reconstructed": False,
            "episode_local_task_state_created": True,
        },
        "loaded_initialization": {
            "human_q_dq_and_required_support_wrench_shared_with_checkpoint": True,
            "robot_side_pose_uses_plant_truth_interface": bool(
                initialize_loaded_equilibrium_with_plant_truth
            ),
            "plant_truth_use_is_evaluation_fixture_only": bool(
                initialize_loaded_equilibrium_with_plant_truth
            ),
            "plant_truth_passed_to_online_controller": False,
        },
        "fixed_human_control_model": True,
        "human_model_version": FIXED_HUMAN_MODEL_VERSION,
        "online_identification_or_learning": False,
        "learned_terminal_value": 0.0,
        "prescribed_full_q_reference_used": False,
        "fixed_q1_q2_coordination_ratio": False,
        "path_corridor_active": False,
        "support_centered_goal_mpc": {
            "decomposition": "u_total = u_support + delta_u_motion",
            "support_definition": (
                "inverse_dynamics(q_hat,dq_hat,qdd=0,fixed_human_model)"
            ),
            "cem_optimized_variable": "delta_u_motion",
            "initialization_anchors": [
                "support_only_zero_motion",
                "smooth_current_executed_command_continuation",
                "independently_paced_small_motion_seed",
            ],
            "motion_sampling_initial_std_nm": list(
                mpc.motion_config.exploration_std_nm
            ),
            "motion_sampling_floor_std_nm": list(
                mpc.motion_config.exploration_std_floor_nm
            ),
            "time_zero_loaded_initial_condition": True,
            "time_zero_support_action_nm": initial_support_action.tolist(),
            "time_zero_physical_human_wrench_world": (
                start_loaded_equilibrium.physical_human_wrench_world.tolist()
            ),
            "time_zero_interface_translation_mm": (
                1000.0
                * start_loaded_equilibrium.interface_displacement_human_m
            ).tolist(),
            "time_zero_interface_rotation_deg": np.degrees(
                start_loaded_equilibrium.interface_rotation_error_human_rad
            ).tolist(),
            "initial_0p1s": {
                "peak_abs_estimated_velocity_deg_s": np.degrees(
                    np.max(np.abs(estimated_dq[initial_indices]), axis=0)
                ).tolist(),
                "peak_abs_evaluation_velocity_deg_s": np.degrees(
                    np.max(np.abs(evaluation_dq[initial_indices]), axis=0)
                ).tolist(),
                "peak_abs_deployable_realized_acceleration_deg_s2": np.degrees(
                    np.max(
                        np.abs(deployable_realized_ddq[initial_indices]), axis=0
                    )
                ).tolist(),
                "peak_abs_evaluation_interval_acceleration_deg_s2": np.degrees(
                    np.max(
                        np.abs(evaluation_interval_ddq[initial_indices]), axis=0
                    )
                ).tolist(),
                "peak_physical_force_n": float(
                    np.max(force_norm[initial_indices])
                ),
                "peak_physical_moment_nm": float(
                    np.max(moment_norm[initial_indices])
                ),
            },
        },
        "physics_dt_s": NOMINAL_PHYSICS_DT_S,
        "control_dt_s": CONTROL_DT_S,
        "mpc_dt_s": MPC_DT_S,
        "task_spec": _task_spec_record(spec),
        "controller_completion_margin": _completion_margin_record(
            spec, completion_margin
        ),
        "transition_completion_audit": transition_completion_audit,
        "interface_model_separation": {
            "plant_truth_runtime_owner": "Stage5SensorBoundaryPlant",
            "plant_truth_parameters": {
                "translation_stiffness_n_m": list(
                    plant_interface_parameters.translation_stiffness_n_m
                ),
                "translation_damping_ns_m": list(
                    plant_interface_parameters.translation_damping_ns_m
                ),
                "rotation_stiffness_nm_rad": (
                    plant_interface_parameters.rotation_stiffness_nm_rad
                ),
                "rotation_damping_nms_rad": (
                    plant_interface_parameters.rotation_damping_nms_rad
                ),
            },
            "controller_nominal_model_version": (
                CONTROLLER_NOMINAL_INTERFACE.model_version
            ),
            "controller_nominal_parameters": {
                "translation_stiffness_n_m": list(
                    CONTROLLER_NOMINAL_INTERFACE.translation_stiffness_n_m
                ),
                "translation_damping_ns_m": list(
                    CONTROLLER_NOMINAL_INTERFACE.translation_damping_ns_m
                ),
                "rotation_stiffness_nm_rad": (
                    CONTROLLER_NOMINAL_INTERFACE.rotation_stiffness_nm_rad
                ),
                "rotation_damping_nms_rad": (
                    CONTROLLER_NOMINAL_INTERFACE.rotation_damping_nms_rad
                ),
            },
            "controller_reads_plant_truth_interface_state_or_parameters": False,
            "explicit_prediction_state": {
                "type": "ExplicitInterfacePredictionState",
                "coordinates": [
                    "interface_translation_human",
                    "interface_velocity_human",
                    "interface_rotation_error_human",
                    "interface_angular_velocity_human",
                    "human_rotation_world",
                    "base_drive_world",
                    "base_angular_drive_world",
                    "previous_executable_wrench_world",
                    "timestamp",
                    "model_version",
                ],
                "measurement_update": (
                    "replace deployable interface coordinates; carry drive state"
                ),
                "drive_transition": (
                    "zero-order hold plus known executable-wrench increment"
                ),
                "hidden_short_derivative_reinitialization": False,
            },
        },
        "task_observation_source": INTERFACE_AWARE_ESTIMATOR_Q_DQ,
        "interface_uncertainty_monitor": {
            "enabled": interface_uncertainty_spec is not None,
            "method": (
                None
                if interface_uncertainty_spec is None
                else interface_uncertainty_spec.method
            ),
            "hypothesis_count": (
                0
                if initial_uncertainty_estimate is None
                else len(initial_uncertainty_estimate.hypotheses)
            ),
            "translation_stiffness_scale_range": (
                None
                if interface_uncertainty_spec is None
                else list(
                    interface_uncertainty_spec.translation_stiffness_scale_range
                )
            ),
            "rotation_stiffness_scale_range": (
                None
                if interface_uncertainty_spec is None
                else list(
                    interface_uncertainty_spec.rotation_stiffness_scale_range
                )
            ),
            "joint_damping_scale_range": (
                None
                if interface_uncertainty_spec is None
                else list(interface_uncertainty_spec.joint_damping_scale_range)
            ),
            "completion_requires_all_hypotheses": interface_uncertainty_spec
            is not None,
            "motion_envelope_requires_all_hypotheses": interface_uncertainty_spec
            is not None,
            "causal_dq_derivative_requires_full_window": True,
            "truth_used_online": False,
            "empirical_range_not_guaranteed_bound": True,
            "maximum_state_range_width_deg_deg_s": (
                None
                if not trace_uncertainty_state_min
                else np.degrees(
                    np.max(
                        np.asarray(trace_uncertainty_state_max)
                        - np.asarray(trace_uncertainty_state_min),
                        axis=0,
                    )
                ).tolist()
            ),
            "maximum_abs_acceleration_range_deg_s2": (
                None
                if not trace_uncertainty_acceleration_min
                else np.degrees(
                    np.max(
                        np.maximum(
                            np.abs(np.asarray(trace_uncertainty_acceleration_min)),
                            np.abs(np.asarray(trace_uncertainty_acceleration_max)),
                        ),
                        axis=0,
                    )
                ).tolist()
            ),
        },
        "interface_robustness_planning": {
            "physical_force_ceiling_n": float(
                planning_physical_force_ceiling_n
            ),
            "physical_force_reserve_to_200n_gate_n": float(
                CUFF_TRANSLATIONAL_FORCE_GATE_N
                - planning_physical_force_ceiling_n
            ),
            "joint_velocity_ceiling_deg_s": (
                None
                if planning_joint_velocity_ceiling_rad_s is None
                else np.degrees(
                    planning_joint_velocity_ceiling_rad_s
                ).tolist()
            ),
            "registered_velocity_and_force_limits_unchanged": True,
            "truth_used_online": False,
        },
        "human_state_estimation_error": {
            "q_rmse_deg": np.degrees(
                np.sqrt(np.mean(q_error * q_error, axis=0))
            ).tolist(),
            "q_peak_abs_deg": np.degrees(
                np.max(np.abs(q_error), axis=0)
            ).tolist(),
            "dq_rmse_deg_s": np.degrees(
                np.sqrt(np.mean(dq_error * dq_error, axis=0))
            ).tolist(),
            "dq_peak_abs_deg_s": np.degrees(
                np.max(np.abs(dq_error), axis=0)
            ).tolist(),
            "truth_role": "evaluation_only",
        },
        "physical_force_prediction_error": {
            "aligned_prediction_count": int(np.count_nonzero(valid_force_prediction)),
            "vector_error_rmse_n": float(
                np.sqrt(np.mean(force_vector_error**2))
            ),
            "vector_error_p95_n": float(np.percentile(force_vector_error, 95)),
            "vector_error_max_n": float(np.max(force_vector_error)),
            "norm_error_rmse_n": float(np.sqrt(np.mean(force_norm_error**2))),
            "norm_error_p95_n": float(np.percentile(force_norm_error, 95)),
            "norm_error_max_n": float(np.max(force_norm_error)),
        },
        "task_status": task_state.phase.value,
        "true_episode_complete": true_episode_complete(task_state),
        "abort_reason": task_state.abort_reason,
        "task_duration_s": float(time[-1]),
        "active_phase_at_termination": active_phase_at_termination,
        "phase_transitions": task_events,
        "estimated_terminal_error_deg": np.degrees(
            estimated_q[-1] - terminal_target
        ).tolist(),
        "evaluation_only_terminal_error_deg": np.degrees(
            evaluation_q[-1] - terminal_target
        ).tolist(),
        "estimated_terminal_dq_deg_s": np.degrees(estimated_dq[-1]).tolist(),
        "evaluation_only_terminal_dq_deg_s": np.degrees(
            evaluation_dq[-1]
        ).tolist(),
        "phase_metrics": phase_metrics,
        "actual_q1_q2_path": {
            "phase_landmarks": phase_landmarks,
            "full_trace_artifact": "trace.npz",
            "plot_artifact": "q_trajectory.png",
            "prescribed_reference": None,
        },
        "outbound_target_error_rmse_deg": float(
            np.degrees(np.sqrt(np.mean(outbound_error**2)))
        ),
        "minimum_outbound_target_error_deg": float(
            np.degrees(np.min(outbound_error))
        ),
        "estimated_q_range_deg": {
            "minimum": np.degrees(np.min(estimated_q, axis=0)).tolist(),
            "maximum": np.degrees(np.max(estimated_q, axis=0)).tolist(),
        },
        "evaluation_only_q_range_deg": {
            "minimum": np.degrees(np.min(evaluation_q, axis=0)).tolist(),
            "maximum": np.degrees(np.max(evaluation_q, axis=0)).tolist(),
        },
        "peak_abs_estimated_joint_velocity_deg_s": np.degrees(
            np.max(np.abs(trace["estimated_state_rad_rad_s"][:, 2:]), axis=0)
        ).tolist(),
        "peak_abs_evaluation_only_joint_velocity_deg_s": np.degrees(
            np.max(np.abs(trace["evaluation_human_dq_rad_s"]), axis=0)
        ).tolist(),
        "peak_abs_estimated_joint_acceleration_deg_s2": np.degrees(
            np.max(np.abs(deployable_realized_ddq), axis=0)
        ).tolist(),
        "peak_abs_evaluation_only_joint_acceleration_deg_s2": np.degrees(
            np.max(np.abs(evaluation_interval_ddq), axis=0)
        ).tolist(),
        "acceleration_semantics": {
            "registered_limit_deg_s2": (
                None
                if spec.task_joint_acceleration_limit_rad_s2 is None
                else np.degrees(
                    spec.task_joint_acceleration_limit_rad_s2
                ).tolist()
            ),
            "mpc_predicted_acceleration": {
                "definition": "delta predicted dq over the 20 ms MPC interval",
                "peak_abs_deg_s2": (
                    np.degrees(
                        np.max(np.abs(selected_prediction_acceleration), axis=0)
                    ).tolist()
                    if len(selected_prediction_acceleration)
                    else None
                ),
                "constraint_authority": True,
            },
            "deployable_realized_acceleration": {
                "definition": (
                    "causal time mean over at most 20 ms of fixed-Human-model "
                    "qdd from q_hat,dq_hat and same-timestamp measured "
                    "Human-site cuff wrench"
                ),
                "source": MODEL_WRENCH_REALIZED_ACCELERATION,
                "peak_abs_deg_s2": np.degrees(
                    np.max(np.abs(deployable_realized_ddq), axis=0)
                ).tolist(),
                "online_monitor_authority": True,
                "causal": True,
                "truth_used_online": False,
            },
            "evaluation_only_truth_acceleration": {
                "definition": (
                    "evaluation dq change over the identical causal interval "
                    "used by the deployable monitor"
                ),
                "peak_abs_deg_s2": np.degrees(
                    np.max(np.abs(evaluation_interval_ddq), axis=0)
                ).tolist(),
                "online_authority": False,
            },
            "instantaneous_diagnostics_not_constraint_authority": {
                "deployable_model_peak_abs_deg_s2": np.degrees(
                    np.max(np.abs(deployable_instantaneous_ddq), axis=0)
                ).tolist(),
                "evaluation_only_mujoco_qacc_peak_abs_deg_s2": np.degrees(
                    np.max(np.abs(evaluation_instantaneous_ddq), axis=0)
                ).tolist(),
            },
            "legacy_estimated_velocity_difference": {
                "definition": "backward 5 ms difference of deployable estimated dq",
                "peak_abs_deg_s2": np.degrees(
                    np.max(np.abs(legacy_estimated_ddq), axis=0)
                ).tolist(),
                "online_monitor_authority": False,
            },
            "aligned_20ms_intervals": aligned_acceleration_intervals,
            "startup_exemption": False,
        },
        "motion_envelope": {
            "velocity_limit_deg_s": (
                None
                if spec.task_joint_velocity_limit_rad_s is None
                else np.degrees(spec.task_joint_velocity_limit_rad_s).tolist()
            ),
            "acceleration_limit_deg_s2": (
                None
                if spec.task_joint_acceleration_limit_rad_s2 is None
                else np.degrees(
                    spec.task_joint_acceleration_limit_rad_s2
                ).tolist()
            ),
            "estimated_velocity_satisfied": bool(
                spec.task_joint_velocity_limit_rad_s is None
                or np.all(
                    np.max(np.abs(estimated_dq), axis=0)
                    <= np.asarray(spec.task_joint_velocity_limit_rad_s) + 1.0e-9
                )
            ),
            "deployable_realized_acceleration_satisfied": bool(
                spec.task_joint_acceleration_limit_rad_s2 is None
                or np.all(
                    np.max(np.abs(deployable_realized_ddq), axis=0)
                    <= np.asarray(spec.task_joint_acceleration_limit_rad_s2)
                    + 1.0e-9
                )
            ),
            "evaluation_only_velocity_satisfied": bool(
                spec.task_joint_velocity_limit_rad_s is None
                or np.all(
                    np.max(np.abs(evaluation_dq), axis=0)
                    <= np.asarray(spec.task_joint_velocity_limit_rad_s) + 1.0e-9
                )
            ),
            "evaluation_only_acceleration_satisfied": bool(
                spec.task_joint_acceleration_limit_rad_s2 is None
                or np.all(
                    np.max(np.abs(evaluation_interval_ddq), axis=0)
                    <= np.asarray(spec.task_joint_acceleration_limit_rad_s2)
                    + 1.0e-9
                )
            ),
            "mpc_predicted_acceleration_satisfied": bool(
                spec.task_joint_acceleration_limit_rad_s2 is None
                or not len(selected_prediction_acceleration)
                or np.all(
                    np.max(np.abs(selected_prediction_acceleration), axis=0)
                    <= np.asarray(spec.task_joint_acceleration_limit_rad_s2)
                    + 1.0e-9
                )
            ),
        },
        "peak_physical_cuff_force_n": float(np.max(force_norm)),
        "cumulative_physical_cuff_force_n_s": float(np.trapezoid(force_norm, time)),
        "peak_physical_cuff_moment_nm": float(np.max(moment_norm)),
        "peak_interface_translation_mm": float(
            1000.0
            * np.max(
                np.linalg.norm(trace["interface_translation_human_m"], axis=1)
            )
        ),
        "peak_interface_rotation_deg": float(
            np.degrees(
                np.max(
                    np.linalg.norm(trace["interface_rotation_human_rad"], axis=1)
                )
            )
        ),
        "safety_filter_status_counts": dict(Counter(safety_filter_statuses)),
        "maximum_safety_filter_intervention_coordinate_norm": float(
            max(safety_filter_interventions, default=0.0)
        ),
        "brake_event_count": brake_event_count,
        "force_gate_event_count": force_gate_event_count,
        "structural_event_count": structural_event_count,
        "mujoco_warning_counts": plant.warning_counts(),
        "mpc_solve_count": int(len(solver)),
        "mpc_failure_count": mpc_failure_count,
        "last_mpc_failure_diagnostics": last_mpc_failure_diagnostics,
        "feasibility_loss_audit": feasibility_loss_audit,
        "mpc_status_counts": dict(Counter(solver_statuses)),
        "mpc_runtime_ms": {
            "mean": float(np.mean(solver)) if len(solver) else None,
            "p95": float(np.percentile(solver, 95)) if len(solver) else None,
            "max": float(np.max(solver)) if len(solver) else None,
            "replanning_period_ms": 1000.0 * MPC_DT_S,
            "deadline_miss_count": int(np.count_nonzero(solver > 1000.0 * MPC_DT_S)),
            "deadline_miss_fraction": (
                float(np.mean(solver > 1000.0 * MPC_DT_S))
                if len(solver)
                else None
            ),
        },
        "mpc_runtime_breakdown_ms": timing_breakdown_summary,
        "loaded_local_hold": {
            "enabled": bool(use_loaded_local_hold),
            "handoff_duration_s": (
                hold_handoff.config.duration_s if hold_handoff is not None else None
            ),
            "handoff_entry_time_s": handoff_entry_time_s,
            "initial_executable_force_command_jump_n": handoff_initial_force_jump_n,
            "initial_executable_moment_command_jump_nm": handoff_initial_moment_jump_nm,
            "maximum_hold_force_command_step_n": float(
                max(hold_command_force_slew_n, default=0.0)
            ),
            "maximum_hold_moment_command_step_nm": float(
                max(hold_command_moment_slew_nm, default=0.0)
            ),
            "longest_continuous_goal_set_interval_s": longest_hold_inside_s,
            "settled_recovery_after_handoff_s": settled_hold_recovery_s,
            "return_entry_observed": bool(len(return_indices)),
            "terminal_q_error_deg": (
                np.degrees(estimated_q[last_hold_index] - goal).tolist()
                if last_hold_index is not None
                else None
            ),
            "terminal_dq_deg_s": (
                np.degrees(estimated_dq[last_hold_index]).tolist()
                if last_hold_index is not None
                else None
            ),
            "peak_physical_force_n": (
                float(np.max(force_norm[hold_indices]))
                if len(hold_indices)
                else None
            ),
            "cumulative_physical_force_n_s": (
                float(np.trapezoid(force_norm[hold_indices], time[hold_indices]))
                if len(hold_indices) > 1
                else None
            ),
            "peak_physical_moment_nm": (
                float(np.max(moment_norm[hold_indices]))
                if len(hold_indices)
                else None
            ),
            "peak_interface_translation_mm": (
                float(
                    1000.0
                    * np.max(
                        np.linalg.norm(
                            trace["interface_translation_human_m"][hold_indices],
                            axis=1,
                        )
                    )
                )
                if len(hold_indices)
                else None
            ),
            "peak_interface_rotation_deg": (
                float(
                    np.degrees(
                        np.max(
                            np.linalg.norm(
                                trace["interface_rotation_human_rad"][hold_indices],
                                axis=1,
                            )
                        )
                    )
                )
                if len(hold_indices)
                else None
            ),
            "state_estimation_rmse": (
                {
                    "q_deg": np.degrees(
                        np.sqrt(np.mean(q_error[hold_indices] ** 2, axis=0))
                    ).tolist(),
                    "dq_deg_s": np.degrees(
                        np.sqrt(np.mean(dq_error[hold_indices] ** 2, axis=0))
                    ).tolist(),
                }
                if len(hold_indices)
                else None
            ),
            "stabilizer_plus_safety_runtime_ms": {
                "mean": float(np.mean(hold_runtime)) if len(hold_runtime) else None,
                "p95": (
                    float(np.percentile(hold_runtime, 95))
                    if len(hold_runtime)
                    else None
                ),
                "max": float(np.max(hold_runtime)) if len(hold_runtime) else None,
            },
            "equilibrium": (
                {
                    "q_goal_deg": np.degrees(
                        loaded_equilibrium.q_goal_rad
                    ).tolist(),
                    "required_human_generalized_input_nm": (
                        loaded_equilibrium.required_human_generalized_input_nm.tolist()
                    ),
                    "physical_human_wrench_world": (
                        loaded_equilibrium.physical_human_wrench_world.tolist()
                    ),
                    "interface_translation_human_mm": (
                        1000.0
                        * loaded_equilibrium.interface_displacement_human_m
                    ).tolist(),
                    "interface_rotation_error_human_deg": np.degrees(
                        loaded_equilibrium.interface_rotation_error_human_rad
                    ).tolist(),
                }
                if loaded_equilibrium is not None
                else None
            ),
        },
        "command_handoffs": {
            "outbound_last_goal_mpc": last_outbound_mpc_command,
            "hold_first_local": first_hold_command,
            "hold_last_local": last_hold_command,
            "return_first_goal_mpc": first_return_mpc_command,
            "hold_to_return_jump": {
                "force_n": hold_to_return_force_jump_n,
                "moment_nm": hold_to_return_moment_jump_nm,
                "generalized_action_nm": hold_to_return_action_jump_nm,
                "robot_joint_torque_command_nm": (
                    hold_to_return_robot_torque_jump_nm
                ),
            },
            "outbound_to_hold_jump": {
                "force_n": outbound_to_hold_force_jump_n,
                "moment_nm": outbound_to_hold_moment_jump_nm,
                "generalized_action_nm": outbound_to_hold_action_jump_nm,
                "robot_joint_torque_command_nm": (
                    outbound_to_hold_robot_torque_jump_nm
                ),
            },
            "goal_mpc_last_action_synchronized_to_executed_hold_action": bool(
                use_loaded_local_hold
            ),
            "return_reference_handoff": {
                "enabled": bool(use_bumpless_return_handoff),
                "entry_time_s": return_handoff_entry_time_s,
                "completed_time_s": return_handoff_completed_time_s,
                "duration_s": (
                    return_handoff.config.duration_s
                    if return_handoff is not None
                    else None
                ),
                "maximum_force_command_step_n": float(
                    max(return_handoff_force_steps_n, default=0.0)
                ),
                "maximum_moment_command_step_nm": float(
                    max(return_handoff_moment_steps_nm, default=0.0)
                ),
                "adapter_runtime_ms": {
                    "mean": (
                        float(np.mean(return_handoff_runtimes_ms))
                        if return_handoff_runtimes_ms
                        else None
                    ),
                    "p95": (
                        float(np.percentile(return_handoff_runtimes_ms, 95))
                        if return_handoff_runtimes_ms
                        else None
                    ),
                    "max": (
                        float(np.max(return_handoff_runtimes_ms))
                        if return_handoff_runtimes_ms
                        else None
                    ),
                },
            },
            "return_terminal_stabilizer_used": False,
        },
        "maximum_task_observation_age_ms": float(
            1000.0 * np.max(trace["task_observation_age_s"])
        ),
        "maximum_normalized_q1_q2_progress_difference": float(
            np.max(path_coordination_difference)
        ),
        "path_freedom_interpretation": (
            "diagnostic only; formulation contains no ratio/corridor and unit tests "
            "accept q1-first and q2-first candidates"
        ),
        "goal_mpc_formulation": {
            "stage_target_distance_weight": mpc.goal_objective.stage_target_distance_weight,
            "terminal_target_error_weight": mpc.goal_objective.terminal_target_error_weight,
            "terminal_velocity_error_weight": mpc.goal_objective.terminal_velocity_error_weight,
            "hold_set_violation_weight": (
                mpc.goal_objective.hold_set_violation_weight
            ),
            "hold_inside_regulation_weight": (
                mpc.goal_objective.hold_inside_regulation_weight
            ),
            "hold_physical_force_weight": (
                mpc.goal_objective.hold_physical_force_weight
            ),
            "action_weight_inherited": mpc.config.action_weight,
            "action_rate_weight_inherited": mpc.config.action_rate_weight,
            "resultant_force_weight_inherited": mpc.config.resultant_force_weight,
            "cylindrical_surface_effort_weight_inherited": (
                mpc.config.cylindrical_surface_effort_weight
            ),
            "wrench_slew_weight_inherited": mpc.config.wrench_slew_weight,
            "learned_terminal_value": 0.0,
            "prescribed_reference": None,
        },
        "v1_1_execution_contract": {
            "robot_side_measurement_interpreted_as_human_state": False,
            "interface_state_propagated_over_first_action_hold": True,
            "first_action_hold_s": MPC_DT_S,
            "first_human_prediction_input": (
                "nominal_mean_transmitted_generalized_input_over_hold"
            ),
            "first_action_screening": "batched_executable_plus_nominal_interface",
            "selected_sequence_duplicate_diagnostic_rollout_removed": True,
        },
        "v1_3_completion_aligned_hold": {
            "outbound": "unchanged_goal_directed_objective",
            "hold_set_violation_weight": (
                mpc.goal_objective.hold_set_violation_weight
            ),
            "hold_inside_regulation_weight": (
                mpc.goal_objective.hold_inside_regulation_weight
            ),
            "hold_physical_force_weight": (
                mpc.goal_objective.hold_physical_force_weight
            ),
            "hold_admissible_set_source": "GoalTaskSpec completion tolerances",
            "hold_set_execution_semantics": (
                "enforce when a plant/task-safe sampled sequence remains inside; "
                "otherwise retain safety-hard minimum-violation recovery"
            ),
            "full_horizon_interface_prediction": True,
            "return": "unchanged_goal_directed_objective_with_return_target",
            "normalization": {
                "q_scale_deg": np.degrees(mpc.q_scale).tolist(),
                "dq_scale_deg_s": np.degrees(mpc.dq_scale).tolist(),
            },
        },
        "controller_parameter_change": (
            "Interface Robustness v1 adds only a controller-side predicted-force "
            "ceiling and independent-joint planning-velocity ceiling; the 200 N "
            "physical gate and registered motion envelope remain unchanged. "
            "Architecture, action space, objective weights, horizon, candidate "
            "count, iterations, Safety Filter, BRAKE, Plant v1, support+motion "
            "coordinates, and HOLD gains are unchanged"
            if planning_physical_force_ceiling_n
            < CUFF_TRANSLATIONAL_FORCE_GATE_N - 1.0e-12
            or planning_joint_velocity_ceiling_rad_s is not None
            else (
                "The nominal interface predictor carries an explicit versioned "
                "base-drive/history state across solves using zero-order hold plus "
                "known executable-wrench increments. CEM/action space, objective "
                "weights, horizon, candidate count, iterations, constraints, Safety "
                "Filter, BRAKE, Plant v1, support+motion coordinates, and HOLD gains "
                "are unchanged"
            )
        ),
    }
    np.savez_compressed(output_dir / "trace.npz", **trace)
    if feasibility_sequence_artifact:
        np.savez_compressed(
            output_dir / "feasibility_loss_sequences.npz",
            **feasibility_sequence_artifact,
        )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_plots(output_dir, trace)
    if session_context is not None:
        session_context.update(
            {
                "plant": plant,
                "estimator_layer": estimator_layer,
                "mpc_layer": mpc_layer,
                "low_level_layer": low_level_layer,
                "estimator": estimator,
                "cuff_allocator": cuff_allocator,
                "interface_observer": interface_observer,
                "acceleration_monitor": acceleration_monitor,
                "screening_interface_predictor": screening_interface_predictor,
                "diagnostic_interface_predictor": diagnostic_interface_predictor,
                "mpc": mpc,
                "supervisor": supervisor,
                "start_loaded_equilibrium": start_loaded_equilibrium,
                "current_action_nm": current_action.copy(),
                "last_executable_command": last_executable_command,
                "last_realized_acceleration": realized_acceleration,
                "episode_count": int(session_context.get("episode_count", 0)) + 1,
            }
        )
    return summary


__all__ = ["FIXED_HUMAN_MODEL_VERSION", "run_goal_mpc_smoke"]
