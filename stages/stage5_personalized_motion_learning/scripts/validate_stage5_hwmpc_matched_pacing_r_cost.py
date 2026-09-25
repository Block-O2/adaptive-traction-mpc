#!/usr/bin/env python3
"""Matched-pacing cuff-interaction study across the frozen HWMPC r range."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    nominal_base_parameters,
)
from traction_mpc_stage4.minimal_adaptation import effective_base_parameters
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_waypoint_mpc import HumanWaypointMPCPrototypeV1
from traction_mpc_stage5.human_waypoint_scheduler import (
    QuinticHumanWaypointSchedulerV1,
)
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK, TaskPhase

from validate_stage5_human_waypoint_mpc import _MPCPhaseController
from validate_stage5_human_waypoint_shadow import (
    CONTROL_DT_S,
    _jsonable,
    _prepare_runtime,
    _run_case,
)
from validate_stage5_human_waypoint_trajectory_diversity import (
    _path_distance,
    _sequence_metrics,
)
from validate_stage5_hwmpc_human_personalization import _geometry


SCHEMA = "stage5_hwmpc_matched_pacing_r_cost_validation_v1"
DEFAULT_CONFIG = Path(
    "stages/stage5_personalized_motion_learning/configs/"
    "stage5_hwmpc_matched_pacing_r_cost_v1.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fixed_models(config: dict[str, Any]) -> tuple[Any, Any, str]:
    fixed = config["fixed_human"]
    source = Path(fixed["source_artifact"])
    observed_hash = _sha256(source)
    if observed_hash != fixed["source_artifact_sha256"]:
        raise ValueError("fixed personalized-model source artifact hash changed")
    source_payload = json.loads(source.read_text(encoding="utf-8"))
    condition = next(
        row
        for row in source_payload["conditions"]
        if row["condition"] == fixed["mismatch_condition"]
    )
    lineage = condition["arms"]["progressive"]["authority"]["lineage"]
    source_model = lineage[fixed["control_model_id"]]
    if (
        source_model["post_update_support"] != "positive"
        or source_model["post_update_evidence_id"] != fixed["support_evidence_id"]
        or not np.allclose(
            source_model["theta"], fixed["control_theta"], atol=0.0, rtol=0.0
        )
    ):
        raise ValueError("fixed personalized Human model lacks matching support")
    theta = np.asarray(fixed["control_theta"], dtype=float)
    control_model = BaseParameterHumanModel(
        _geometry(),
        effective_base_parameters(theta, nominal_base_parameters(STAGE5_HUMAN)),
        STAGE5_HUMAN,
    )
    truth_scale = float(fixed["truth_scales_evaluation_only"][2])
    truth_human = replace(
        STAGE5_HUMAN,
        passive_damping_nms_rad=tuple(
            truth_scale
            * np.asarray(STAGE5_HUMAN.passive_damping_nms_rad, dtype=float)
        ),
    )
    return truth_human, control_model, str(fixed["control_model_id"])


class _MatchedPacingHWMPCController:
    """Study-only fixed-time phase driver around the unchanged HWMPC phase."""

    def __init__(
        self,
        mpc: HumanWaypointMPCPrototypeV1,
        scheduler: QuinticHumanWaypointSchedulerV1,
        *,
        coordination_r: float,
        outbound_duration_s: float,
        hold_duration_s: float,
        return_duration_s: float,
    ) -> None:
        self.mpc = mpc
        self.scheduler = scheduler
        self.coordination_r = float(coordination_r)
        self.phase_durations_s = {
            TaskPhase.OUTBOUND: float(outbound_duration_s),
            TaskPhase.HOLD: float(hold_duration_s),
            TaskPhase.RETURN: float(return_duration_s),
        }
        self.phase_starts_s = {
            TaskPhase.OUTBOUND: 0.0,
            TaskPhase.HOLD: float(outbound_duration_s),
            TaskPhase.RETURN: float(outbound_duration_s + hold_duration_s),
        }
        self.total_duration_s = float(
            outbound_duration_s + hold_duration_s + return_duration_s
        )
        self.phase = TaskPhase.OUTBOUND
        self.phase_controller = self._new_phase(TaskPhase.OUTBOUND)
        self.phase_records = [self.phase_controller]
        self.boundary_checks: list[dict[str, Any]] = []
        self.completed_time_s: float | None = None
        self.execution_context: dict[str, Any] | None = None
        self._terminal_checked = False

    def _new_phase(self, phase: TaskPhase) -> _MPCPhaseController:
        return _MPCPhaseController(
            mpc=self.mpc,
            scheduler=self.scheduler,
            phase=phase,
            phase_start_s=self.phase_starts_s[phase],
            coordination_preference_r=self.coordination_r,
        )

    def bind_execution_context(self, **context: Any) -> None:
        self.execution_context = dict(context)
        self.phase_controller.bind_execution_context(**context)

    def _goal(self, phase: TaskPhase) -> np.ndarray:
        return np.asarray(
            self.scheduler.spec.start_return_target_rad
            if phase is TaskPhase.RETURN
            else self.scheduler.spec.outbound_goal_target_rad,
            dtype=float,
        )

    def _record_boundary(
        self, phase: TaskPhase, time_s: float, state: np.ndarray
    ) -> bool:
        target = self._goal(phase)
        inside = self.phase_controller._inside(state, target)
        self.boundary_checks.append(
            {
                "phase": phase.value,
                "boundary_time_s": float(time_s),
                "inside_existing_completion_criteria": inside,
                "q_error_deg": np.degrees(state[:2] - target),
                "dq_deg_s": np.degrees(state[2:]),
                "natural_completion_time_s": self.phase_controller.completed_time_s,
            }
        )
        return inside

    def __call__(self, time_s: float, state: np.ndarray):
        hold_start = self.phase_starts_s[TaskPhase.HOLD]
        return_start = self.phase_starts_s[TaskPhase.RETURN]
        if self.phase is TaskPhase.OUTBOUND and time_s + 1.0e-12 >= hold_start:
            self._record_boundary(TaskPhase.OUTBOUND, hold_start, state)
            self.phase = TaskPhase.HOLD
            self.phase_controller = self._new_phase(TaskPhase.HOLD)
            self.phase_records.append(self.phase_controller)
            if self.execution_context is not None:
                self.phase_controller.bind_execution_context(**self.execution_context)
        if self.phase is TaskPhase.HOLD and time_s + 1.0e-12 >= return_start:
            self._record_boundary(TaskPhase.HOLD, return_start, state)
            self.phase = TaskPhase.RETURN
            self.phase_controller = self._new_phase(TaskPhase.RETURN)
            self.phase_records.append(self.phase_controller)
            if self.execution_context is not None:
                self.phase_controller.bind_execution_context(**self.execution_context)
        if (
            self.phase is TaskPhase.RETURN
            and time_s + 1.0e-12 >= self.total_duration_s
            and not self._terminal_checked
        ):
            self._terminal_checked = True
            if self._record_boundary(TaskPhase.RETURN, self.total_duration_s, state):
                self.completed_time_s = self.total_duration_s
        return self.phase_controller(time_s, state)

    def record(self) -> dict[str, Any]:
        return {
            "coordination_r": self.coordination_r,
            "phase_durations_s": {
                phase.value: duration
                for phase, duration in self.phase_durations_s.items()
            },
            "phase_starts_s": {
                phase.value: start for phase, start in self.phase_starts_s.items()
            },
            "total_duration_s": self.total_duration_s,
            "completed_time_s": self.completed_time_s,
            "boundary_checks": _jsonable(self.boundary_checks),
            "all_boundaries_inside_existing_completion_criteria": bool(
                len(self.boundary_checks) == 3
                and all(
                    row["inside_existing_completion_criteria"]
                    for row in self.boundary_checks
                )
            ),
            "phases": [item.record() for item in self.phase_records],
            "mpc": self.mpc.record(),
        }


def _observed_phase_durations(trace: list[dict[str, Any]]) -> dict[str, float]:
    phase_order = ("OUTBOUND", "HOLD", "RETURN")
    first_time = {
        phase: min(float(row["elapsed_s"]) for row in trace if row["phase"] == phase)
        for phase in phase_order
    }
    return {
        "OUTBOUND": first_time["HOLD"] - first_time["OUTBOUND"],
        "HOLD": first_time["RETURN"] - first_time["HOLD"],
        "RETURN": max(float(row["elapsed_s"]) for row in trace)
        - first_time["RETURN"],
    }


def _run_profile(
    *,
    profile: dict[str, Any],
    order_seed: int,
    pacing: dict[str, Any],
    truth_human: Any,
    control_human_model: Any,
    control_model_version: str,
) -> dict[str, Any]:
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    start = np.asarray(spec.start_return_target_rad, dtype=float)
    scheduler = QuinticHumanWaypointSchedulerV1(
        spec, control_human_model, reference_period_s=CONTROL_DT_S
    )
    mpc = HumanWaypointMPCPrototypeV1(spec, scheduler)
    controller = _MatchedPacingHWMPCController(
        mpc,
        scheduler,
        coordination_r=float(profile["r"]),
        outbound_duration_s=float(pacing["outbound_duration_s"]),
        hold_duration_s=float(pacing["hold_duration_s"]),
        return_duration_s=float(pacing["return_duration_s"]),
    )

    def runtime_factory(name: str, start_q_rad: np.ndarray) -> dict[str, Any]:
        return _prepare_runtime(
            name,
            start_q_rad,
            truth_human=truth_human,
            control_human_model=control_human_model,
            control_human_model_version=control_model_version,
        )

    metrics = _run_case(
        name=f"matched_r_cost_seed{order_seed}_{profile['name']}",
        kind="hwmpc_matched_pacing_r_cost",
        start_q_rad=start,
        duration_s=controller.total_duration_s,
        stateful_schedule=controller,
        completion_check=lambda: controller.completed_time_s is not None,
        schedule_context_hook=controller.bind_execution_context,
        runtime_factory=runtime_factory,
    )
    controller_record = controller.record()
    observed_durations = _observed_phase_durations(metrics["trace"])
    nominal_durations = controller_record["phase_durations_s"]
    maximum_duration_error = max(
        abs(observed_durations[phase] - nominal_durations[phase])
        for phase in nominal_durations
    )
    safety = metrics["execution_safety"]
    complete = bool(
        controller.completed_time_s is not None
        and metrics["termination_reason"] is None
        and metrics["final_within_existing_task_tolerance"]
    )
    safe = bool(
        metrics["human_motion_authority"]["violation_count"] == 0
        and safety["shank_bed_contact_sample_count"] == 0
        and safety["brake_cycle_count"] == 0
        and safety["force_gate_event_count"] == 0
        and safety["torque_clip_event_count"] == 0
    )
    interaction = metrics["interaction"]
    case = {
        "profile_name": str(profile["name"]),
        "coordination_r": float(profile["r"]),
        "order_seed": int(order_seed),
        "completed": complete,
        "safety_contract_passed": safe,
        "matched_pacing_contract_passed": bool(
            controller_record[
                "all_boundaries_inside_existing_completion_criteria"
            ]
            and maximum_duration_error <= CONTROL_DT_S + 1.0e-12
        ),
        "completion_time_s": controller.completed_time_s,
        "actual_phase_durations_s": observed_durations,
        "maximum_phase_duration_error_s": maximum_duration_error,
        "cumulative_measured_cuff_force_n_s": interaction[
            "integral_cuff_force_n_s"
        ],
        "mean_measured_cuff_force_n": float(
            interaction["integral_cuff_force_n_s"] / controller.total_duration_s
        ),
        "peak_measured_cuff_force_n": interaction["peak_cuff_force_n"],
        "peak_measured_cuff_moment_nm": interaction["peak_cuff_moment_nm"],
        "scheduled_peak_abs_20ms_acceleration_deg_s2": metrics[
            "waypoint_contract_acceleration"
        ]["peak_abs_scheduled_20ms_acceleration_deg_s2"],
        "realized_peak_abs_20ms_acceleration_deg_s2": metrics[
            "human_motion_authority"
        ]["peak_abs_20ms_acceleration_deg_s2"],
        "q_tracking_rmse_deg": metrics["estimated_q_tracking_rmse_deg"],
        "dq_tracking_rmse_deg_s": metrics["estimated_dq_tracking_rmse_deg_s"],
        "maximum_robot_torque_fraction": safety["maximum_robot_torque_fraction"],
        "minimum_truth_shank_clearance_mm": safety[
            "minimum_truth_shank_clearance_mm"
        ],
        "shank_bed_contact_sample_count": safety[
            "shank_bed_contact_sample_count"
        ],
        "safety_filter_intervention_count": safety[
            "safety_filter_intervention_count"
        ],
        "brake_cycle_count": safety["brake_cycle_count"],
        "force_gate_event_count": safety["force_gate_event_count"],
        "torque_clip_event_count": safety["torque_clip_event_count"],
        "human_motion_violation_count": metrics["human_motion_authority"][
            "violation_count"
        ],
        "controller": controller_record,
        "metrics": metrics,
    }
    case["trajectory_metrics"] = _sequence_metrics(case, float(profile["r"]))
    return case


def _summarize_profiles(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for r_value in sorted({float(case["coordination_r"]) for case in cases}):
        selected = [case for case in cases if case["coordination_r"] == r_value]
        forces = np.asarray(
            [case["cumulative_measured_cuff_force_n_s"] for case in selected]
        )
        summaries.append(
            {
                "coordination_r": r_value,
                "profile_name": selected[0]["profile_name"],
                "replicate_count": len(selected),
                "force_integral_mean_n_s": float(np.mean(forces)),
                "force_integral_std_n_s": float(np.std(forces, ddof=0)),
                "force_integral_min_n_s": float(np.min(forces)),
                "force_integral_max_n_s": float(np.max(forces)),
                "force_integral_range_n_s": float(np.ptp(forces)),
                "mean_force_mean_n": float(
                    np.mean([case["mean_measured_cuff_force_n"] for case in selected])
                ),
                "peak_force_max_n": float(
                    np.max([case["peak_measured_cuff_force_n"] for case in selected])
                ),
                "peak_moment_max_nm": float(
                    np.max([case["peak_measured_cuff_moment_nm"] for case in selected])
                ),
                "representative_trajectory": selected[0]["trajectory_metrics"],
            }
        )
    return summaries


def _effect_analysis(
    summaries: list[dict[str, Any]], cases: list[dict[str, Any]]
) -> dict[str, Any]:
    r_values = np.asarray([row["coordination_r"] for row in summaries], dtype=float)
    force = np.asarray(
        [row["force_integral_mean_n_s"] for row in summaries], dtype=float
    )
    force_range = float(np.ptp(force))
    balanced_index = int(np.argmin(np.abs(r_values)))
    relative_range = float(force_range / force[balanced_index])
    maximum_within_range = float(
        max(row["force_integral_range_n_s"] for row in summaries)
    )
    repeatability_ratio = (
        0.0 if force_range <= 1.0e-15 else maximum_within_range / force_range
    )
    design = np.column_stack((np.ones(len(r_values)), r_values))
    intercept, slope = np.linalg.lstsq(design, force, rcond=None)[0]
    fitted = intercept + slope * r_values
    total = float(np.sum((force - np.mean(force)) ** 2))
    residual = float(np.sum((force - fitted) ** 2))
    r_squared = 1.0 if total <= 1.0e-15 else 1.0 - residual / total
    spearman = spearmanr(r_values, force)
    minimum_index = int(np.argmin(force))
    maximum_index = int(np.argmax(force))
    minimum_case = summaries[minimum_index]
    maximum_case = summaries[maximum_index]
    shared_phases = sorted(
        set(minimum_case["representative_trajectory"]["realized_paths"])
        & set(maximum_case["representative_trajectory"]["realized_paths"])
    )
    path_distances = {
        phase: _path_distance(
            minimum_case["representative_trajectory"]["realized_paths"][phase],
            maximum_case["representative_trajectory"]["realized_paths"][phase],
        )
        for phase in shared_phases
    }
    mean_path_distance = float(
        np.mean([row["rms_distance_deg"] for row in path_distances.values()])
    )
    completion_times = np.asarray(
        [
            float(case["completion_time_s"])
            for case in cases
            if case["completion_time_s"] is not None
        ],
        dtype=float,
    )
    return {
        "between_r_force_integral_range_n_s": force_range,
        "relative_range_vs_balanced": relative_range,
        "maximum_within_r_seed_range_n_s": maximum_within_range,
        "within_to_between_range_ratio": repeatability_ratio,
        "linear_slope_n_s_per_r": float(slope),
        "linear_r_squared": r_squared,
        "spearman_rho": float(spearman.statistic),
        "spearman_pvalue_descriptive": float(spearman.pvalue),
        "minimum_force_r": float(r_values[minimum_index]),
        "maximum_force_r": float(r_values[maximum_index]),
        "minimum_force_integral_n_s": float(force[minimum_index]),
        "maximum_force_integral_n_s": float(force[maximum_index]),
        "minimum_vs_maximum_force_path_distance": path_distances,
        "mean_phase_rms_path_distance_deg": mean_path_distance,
        "completed_case_count": int(len(completion_times)),
        "incomplete_case_count": int(len(cases) - len(completion_times)),
        "completion_time_range_s": (
            None if not len(completion_times) else float(np.ptp(completion_times))
        ),
        "interpretation": (
            "seed labels randomize isolated-run order only; zero within-r spread "
            "demonstrates deterministic repeat-run invariance, not stochastic robustness"
        ),
    }


def _plot(
    summaries: list[dict[str, Any]], cases: list[dict[str, Any]], path: Path
) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    colors = plt.cm.coolwarm(np.linspace(0.05, 0.95, len(summaries)))
    for color, summary in zip(colors, summaries, strict=True):
        trajectory = summary["representative_trajectory"]["realized_paths"]
        outbound = np.degrees(np.asarray(trajectory["OUTBOUND"]["q_rad"]))
        ret = np.degrees(np.asarray(trajectory["RETURN"]["q_rad"]))
        label = f"r={summary['coordination_r']:+.3f}"
        axes[0].plot(outbound[:, 0], outbound[:, 1], color=color, label=label)
        axes[0].plot(ret[:, 0], ret[:, 1], color=color, linestyle="--")
    axes[0].set(
        title="Matched-pacing realized q1-q2 paths",
        xlabel="q1 [deg]",
        ylabel="q2 [deg]",
    )
    axes[0].legend(fontsize=8)
    axes[0].grid(True, alpha=0.3)

    for case in cases:
        axes[1].scatter(
            case["coordination_r"],
            case["cumulative_measured_cuff_force_n_s"],
            color="0.65",
            s=18,
        )
    axes[1].plot(
        [row["coordination_r"] for row in summaries],
        [row["force_integral_mean_n_s"] for row in summaries],
        color="black",
        marker="o",
    )
    axes[1].set(
        title="Primary outcome: cuff-force integral",
        xlabel="coordination r",
        ylabel="N s over fixed 4.9 s",
    )
    axes[1].grid(True, alpha=0.3)

    phase_colors = {"OUTBOUND": "tab:blue", "HOLD": "tab:orange", "RETURN": "tab:green"}
    for phase, color in phase_colors.items():
        axes[2].scatter(
            [case["coordination_r"] for case in cases],
            [case["actual_phase_durations_s"][phase] for case in cases],
            color=color,
            s=18,
            label=phase,
        )
    axes[2].set(
        title="Observed matched phase durations",
        xlabel="coordination r",
        ylabel="duration [s]",
    )
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_validation(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "stage5_hwmpc_matched_pacing_r_cost_v1":
        raise ValueError("unexpected matched-pacing r-cost schema")
    if config.get("status") != "PREREGISTERED_BEFORE_MATCHED_PACING_COST_OUTCOMES":
        raise ValueError("matched-pacing study config must remain preregistered")
    support = config["coordination"]["frozen_support_interval"]
    profiles = list(config["coordination"]["representative_profiles"])
    if profiles[0]["r"] != support[0] or profiles[-1]["r"] != support[1]:
        raise ValueError("representative profiles must include both support boundaries")
    if any(not support[0] <= float(row["r"]) <= support[1] for row in profiles):
        raise ValueError("representative r lies outside frozen support")
    pacing = config["matched_pacing"]
    spec = PROVISIONAL_LOW_MODERATE_GOAL_TASK
    if (
        not np.isclose(pacing["hold_duration_s"], spec.hold_duration_s)
        or not np.isclose(pacing["registered_phase_timeout_s_unchanged"], spec.phase_timeout_s)
        or not np.isclose(pacing["control_period_s"], CONTROL_DT_S)
    ):
        raise ValueError("matched pacing changed the registered task/control timing")
    truth_human, control_model, model_version = _fixed_models(config)
    cases = []
    for order_seed in config["repeatability"]["order_randomization_seeds"]:
        rng = np.random.default_rng(int(order_seed))
        for profile_index in rng.permutation(len(profiles)):
            cases.append(
                _run_profile(
                    profile=profiles[int(profile_index)],
                    order_seed=int(order_seed),
                    pacing=pacing,
                    truth_human=truth_human,
                    control_human_model=control_model,
                    control_model_version=model_version,
                )
            )
    summaries = _summarize_profiles(cases)
    effect = _effect_analysis(summaries, cases)
    analysis = config["analysis_contract"]
    contract_valid = all(
        case["completed"]
        and case["safety_contract_passed"]
        and case["matched_pacing_contract_passed"]
        for case in cases
    )
    range_pass = bool(
        effect["relative_range_vs_balanced"]
        >= analysis["minimum_relative_force_integral_range_for_RC_A"]
    )
    repeatability_pass = bool(
        effect["within_to_between_range_ratio"]
        <= analysis["maximum_within_r_range_fraction_of_between_r_range_for_RC_A"]
    )
    path_pass = bool(
        effect["mean_phase_rms_path_distance_deg"]
        >= analysis["minimum_path_rms_distance_deg_for_RC_A"]
    )
    numerical_separation = bool(
        effect["between_r_force_integral_range_n_s"]
        > max(1.0e-9, 3.0 * effect["maximum_within_r_seed_range_n_s"])
    )
    if not contract_valid:
        decision = "RC-C — TIMING/EXECUTION CONTRACT NOT VALID"
    elif range_pass and repeatability_pass and path_pass:
        decision = "RC-A — MATCHED-PACING PATH/COST SEPARATION CONFIRMED"
    elif not numerical_separation or not path_pass:
        decision = "RC-D — CURRENT r FAMILY DOES NOT PROVIDE USEFUL COST SEPARATION"
    else:
        decision = "RC-B — SMALL OR INCONSISTENT PATH EFFECT"

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "matched_pacing_r_cost.png"
    _plot(summaries, cases, plot_path)
    payload = _jsonable(
        {
            "schema": SCHEMA,
            "evidence_category": config["evidence_category"],
            "decision": decision,
            "config": config,
            "fixed_model_version": model_version,
            "cases": cases,
            "profile_summary": summaries,
            "primary_analysis": effect,
            "criteria_observed": {
                "all_timing_execution_contracts_valid": contract_valid,
                "relative_force_integral_range_passed": range_pass,
                "repeatability_ratio_passed": repeatability_pass,
                "path_distance_passed": path_pass,
                "force_separation_above_repeatability_scale": numerical_separation,
            },
            "scope_invariants": {
                "force_used_for_selection_or_control": False,
                "human_model_updated": False,
                "trust_driven_pacing_active": False,
                "value_imitation_or_rl_active": False,
                "controller_scheduler_or_interface_changed": False,
                "task_safety_contact_or_r_bounds_changed": False,
                "stage3_or_stage4_changed": False,
                "historical_results_changed": False,
            },
            "plot": str(plot_path),
        }
    )
    result_path = output_dir / "matched_pacing_r_cost.json"
    result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "decision": decision,
                "criteria_observed": payload["criteria_observed"],
                "primary_analysis": effect,
                "profiles": [
                    {
                        "r": row["coordination_r"],
                        "force_integral_mean_n_s": row["force_integral_mean_n_s"],
                        "force_integral_range_n_s": row["force_integral_range_n_s"],
                    }
                    for row in summaries
                ],
                "output_dir": str(output_dir),
            },
            indent=2,
        )
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    run_validation(arguments.config, arguments.output_dir)


if __name__ == "__main__":
    main()
