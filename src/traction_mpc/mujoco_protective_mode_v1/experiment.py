"""Registered M1 engineering-smoke execution and metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import numpy as np

from .config import HumanV2Parameters, ProtectiveModeConfig
from .controller import ActuatorCommand, ProtectiveModeController
from .environment import Observation, ProtectiveModeEnvironment


@dataclass
class CaseResult:
    case_name: str
    config: ProtectiveModeConfig
    parameters: HumanV2Parameters
    arrays: dict[str, np.ndarray]
    metrics: dict[str, Any]


def run_case(
    config: ProtectiveModeConfig | None = None,
    case_name: str = "baseline_30deg",
    manual_veto_time_s: float | None = None,
) -> CaseResult:
    """Run one deterministic MuJoCo engineering-smoke case."""

    config = config or ProtectiveModeConfig()
    parameters = HumanV2Parameters()
    environment = ProtectiveModeEnvironment(parameters, config)
    observation = environment.reset()
    controller = ProtectiveModeController(
        parameters,
        config,
        observation.robot_position_m,
        manual_veto_time_s=manual_veto_time_s,
    )
    records: list[dict[str, Any]] = []
    post_veto_duration_s = 1.0
    while observation.time_s <= controller.end_time_s + config.control_dt_s:
        command = controller.command(
            observation.time_s,
            observation.q_rad,
            observation.dq_rad_s,
            observation.robot_position_m,
            observation.interaction_force_n,
        )
        next_observation = environment.step(command)
        records.append(_record(observation, next_observation, command))
        observation = next_observation
        if controller.veto_start_s is not None and (
            observation.time_s >= controller.veto_start_s + post_veto_duration_s
        ):
            break
    arrays = _arrays(records)
    metrics = _metrics(arrays, controller, config)
    metrics["case_name"] = case_name
    metrics["q_switch_deg"] = config.q_switch_deg
    metrics["manual_veto_time_s"] = manual_veto_time_s
    return CaseResult(case_name, config, parameters, arrays, metrics)


def _record(
    observation: Observation,
    next_observation: Observation,
    command: ActuatorCommand,
) -> dict[str, Any]:
    return {
        "time_s": observation.time_s,
        "q_rad": observation.q_rad,
        "dq_rad_s": observation.dq_rad_s,
        "q_reference_rad": command.q_reference,
        "dq_reference_rad_s": command.dq_reference,
        "robot_position_m": observation.robot_position_m,
        "robot_velocity_m_s": observation.robot_velocity_m_s,
        "robot_command_position_m": command.position_m,
        "robot_command_velocity_m_s": command.velocity_m_s,
        "actuator_force_n": next_observation.actuator_force_n,
        "interaction_force_n": observation.interaction_force_n,
        "peak_interaction_force_n": next_observation.substep_peak_interaction_force_n,
        "bed_force_n": observation.bed_force_n,
        "peak_bed_force_n": next_observation.substep_peak_bed_force_n,
        "bed_penetration_m": observation.max_bed_penetration_m,
        "peak_bed_penetration_m": next_observation.substep_peak_penetration_m,
        "bed_contact_count": observation.bed_contact_count,
        "cuff_length_m": observation.cuff_length_m,
        "cuff_extension_m": observation.cuff_extension_m,
        "cuff_active": observation.cuff_active,
        "mode": command.mode,
        "automatic_force_veto": command.automatic_force_veto,
        "manual_veto_probe": command.manual_veto_probe,
    }


def _arrays(records: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    keys = records[0].keys()
    arrays: dict[str, np.ndarray] = {}
    for key in keys:
        values = [record[key] for record in records]
        if key == "mode":
            arrays[key] = np.asarray(values, dtype="U32")
        else:
            arrays[key] = np.asarray(values)
    return arrays


def _metrics(
    arrays: dict[str, np.ndarray],
    controller: ProtectiveModeController,
    config: ProtectiveModeConfig,
) -> dict[str, Any]:
    time = arrays["time_s"]
    q_deg = np.degrees(arrays["q_rad"])
    dq_deg_s = np.degrees(arrays["dq_rad_s"])
    modes = arrays["mode"]
    sequence = _stable_sequence(modes)
    expected = [
        "BED_START",
        "KINEMATIC_TAKEOFF",
        "NORMAL_REHAB",
        "KINEMATIC_LANDING",
        "TERMINAL",
    ]
    terminal_mask = time >= max(time[-1] - 0.5, controller.terminal_start_s)
    if not np.any(terminal_mask):
        terminal_mask = np.arange(len(time)) >= max(0, len(time) - 1)
    terminal_q2 = float(np.mean(q_deg[terminal_mask, 1]))
    terminal_speed = float(np.max(np.abs(dq_deg_s[terminal_mask, 1])))
    terminal_bed_force = float(np.mean(arrays["bed_force_n"][terminal_mask]))
    automatic_veto = bool(np.any(arrays["automatic_force_veto"]))
    manual_veto = bool(np.any(arrays["manual_veto_probe"]))
    completed_timeline = time[-1] >= controller.end_time_s - config.control_dt_s
    sequence_complete = sequence == expected
    terminal_stable = (
        abs(terminal_q2 - config.q_terminal_deg) <= config.terminal_position_tolerance_deg
        and terminal_speed <= config.terminal_velocity_tolerance_deg_s
        and terminal_bed_force >= config.stable_bed_force_n
    )
    mechanical_complete = completed_timeline and sequence_complete and terminal_stable and not automatic_veto
    if automatic_veto:
        classification = "AUTOMATIC_FORCE_VETO"
    elif manual_veto:
        classification = "MANUAL_VETO_PROBE"
    elif mechanical_complete:
        classification = "COMPLETE"
    else:
        classification = "TERMINAL_UNSTABLE_OR_INCOMPLETE"

    bed_active = arrays["bed_force_n"] >= config.stable_bed_force_n
    cuff_expected = np.isin(modes, ["KINEMATIC_TAKEOFF", "NORMAL_REHAB", "KINEMATIC_LANDING"])
    cuff_loss = cuff_expected & ~arrays["cuff_active"]
    bed_transitions = _transition_count(bed_active)
    cuff_transitions = _transition_count(arrays["cuff_active"])
    dt = config.control_dt_s
    interaction_rate = np.diff(arrays["interaction_force_n"], prepend=arrays["interaction_force_n"][0]) / dt
    bed_rate = np.diff(arrays["bed_force_n"], prepend=arrays["bed_force_n"][0]) / dt
    switch_metrics = {}
    for name, switch_time in (
        ("takeoff_to_normal", controller.normal_start_s),
        ("normal_to_landing", controller.landing_start_s),
    ):
        window = np.abs(time - switch_time) <= 0.10
        if not np.any(window) or time[-1] < switch_time:
            switch_metrics[f"{name}_peak_force_n"] = None
            switch_metrics[f"{name}_force_step_n"] = None
            switch_metrics[f"{name}_command_position_step_m"] = None
            switch_metrics[f"{name}_command_velocity_step_m_s"] = None
            continue
        before = np.searchsorted(time, switch_time, side="left")
        before = min(max(before, 1), len(time) - 1)
        switch_metrics[f"{name}_peak_force_n"] = float(np.max(arrays["peak_interaction_force_n"][window]))
        switch_metrics[f"{name}_force_step_n"] = float(
            abs(arrays["interaction_force_n"][before] - arrays["interaction_force_n"][before - 1])
        )
        switch_metrics[f"{name}_command_position_step_m"] = float(
            np.linalg.norm(
                arrays["robot_command_position_m"][before] - arrays["robot_command_position_m"][before - 1]
            )
        )
        switch_metrics[f"{name}_command_velocity_step_m_s"] = float(
            np.linalg.norm(
                arrays["robot_command_velocity_m_s"][before] - arrays["robot_command_velocity_m_s"][before - 1]
            )
        )

    veto_metrics = _veto_metrics(arrays, controller, config)
    takeoff_index = _index_at_or_before(time, controller.normal_start_s)
    landing_index = _index_at_or_before(time, controller.terminal_start_s)
    takeoff_q2 = float(q_deg[takeoff_index, 1])
    landing_q2 = float(q_deg[landing_index, 1])
    q2_min = float(np.min(q_deg[:, 1]))
    q2_max = float(np.max(q_deg[:, 1]))
    return {
        "classification": classification,
        "mechanical_complete": bool(mechanical_complete),
        "mode_sequence": ">".join(sequence),
        "duration_s": float(time[-1]),
        "terminal_q2_mean_deg": terminal_q2,
        "terminal_q2_peak_speed_deg_s": terminal_speed,
        "terminal_bed_force_mean_n": terminal_bed_force,
        "takeoff_end_q2_deg": takeoff_q2,
        "takeoff_end_error_deg": abs(takeoff_q2 - config.q_switch_deg),
        "landing_end_q2_deg": landing_q2,
        "landing_end_error_deg": abs(landing_q2 - config.q_terminal_deg),
        "minimum_q2_deg": q2_min,
        "maximum_q2_deg": q2_max,
        "q2_rom_violation_observed": bool(q2_min < -1e-6 or q2_max > 100.0 + 1e-6),
        "max_interaction_force_n": float(np.max(arrays["peak_interaction_force_n"])),
        "max_interaction_force_rate_n_s": float(np.max(np.abs(interaction_rate))),
        "max_bed_force_n": float(np.max(arrays["peak_bed_force_n"])),
        "max_bed_force_rate_n_s": float(np.max(np.abs(bed_rate))),
        "max_bed_penetration_mm": float(1000 * np.max(arrays["peak_bed_penetration_m"])),
        "max_cuff_extension_mm": float(1000 * np.max(arrays["cuff_extension_m"])),
        "cuff_loss_sample_count": int(np.count_nonzero(cuff_loss)),
        "bed_contact_transition_count": bed_transitions,
        "cuff_active_transition_count": cuff_transitions,
        "bed_chatter_observed": bool(bed_transitions > config.chatter_transition_limit),
        "cuff_chatter_observed": bool(cuff_transitions > config.chatter_transition_limit),
        "automatic_force_veto": automatic_veto,
        "manual_veto_probe": manual_veto,
        **switch_metrics,
        **veto_metrics,
    }


def _veto_metrics(
    arrays: dict[str, np.ndarray],
    controller: ProtectiveModeController,
    config: ProtectiveModeConfig,
) -> dict[str, float | None]:
    if controller.veto_start_s is None:
        return {
            "veto_time_s": None,
            "veto_q2_braking_distance_deg": None,
            "veto_robot_braking_distance_mm": None,
            "veto_peak_interaction_force_n": None,
            "veto_settling_time_s": None,
        }
    time = arrays["time_s"]
    start = int(np.searchsorted(time, controller.veto_start_s, side="left"))
    start = min(start, len(time) - 1)
    q2 = np.degrees(arrays["q_rad"][:, 1])
    q2_distance = float(np.max(np.abs(q2[start:] - q2[start])))
    robot = arrays["robot_position_m"]
    robot_distance = float(1000 * np.max(np.linalg.norm(robot[start:] - robot[start], axis=1)))
    peak_force = float(np.max(arrays["peak_interaction_force_n"][start:]))
    speed = np.abs(np.degrees(arrays["dq_rad_s"][:, 1]))
    settling_time = None
    required = max(1, int(round(0.1 / config.control_dt_s)))
    for index in range(start, max(start, len(time) - required)):
        if np.all(speed[index : index + required] <= config.terminal_velocity_tolerance_deg_s):
            settling_time = float(time[index] - time[start])
            break
    return {
        "veto_time_s": float(time[start]),
        "veto_q2_braking_distance_deg": q2_distance,
        "veto_robot_braking_distance_mm": robot_distance,
        "veto_peak_interaction_force_n": peak_force,
        "veto_settling_time_s": settling_time,
    }


def _stable_sequence(values: np.ndarray) -> list[str]:
    sequence: list[str] = []
    for value in values.tolist():
        if not sequence or sequence[-1] != value:
            sequence.append(value)
    return sequence


def _transition_count(values: np.ndarray) -> int:
    if len(values) < 2:
        return 0
    return int(np.count_nonzero(values[1:] != values[:-1]))


def _index_at_or_before(time: np.ndarray, target: float) -> int:
    return min(max(int(np.searchsorted(time, target, side="right")) - 1, 0), len(time) - 1)


def result_metadata(result: CaseResult) -> dict[str, Any]:
    return {
        "case_name": result.case_name,
        "config": asdict(result.config),
        "parameters": asdict(result.parameters),
        "metrics": result.metrics,
    }
