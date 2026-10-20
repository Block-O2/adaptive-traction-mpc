#!/usr/bin/env python3
"""Validate one causal completed-segment terminal handoff rule for dynamic HWMPC."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from export_stage5_hwmpc_state_feedback_dataset_v1 import export_dataset
from traction_mpc_stage5.task import TaskPhase
from validate_stage5_human_waypoint_shadow import _candidate, _jsonable
from validate_stage5_hwmpc_matched_pacing_r_cost import _fixed_models
from validate_stage5_hwmpc_state_feedback_v1 import (
    StateFeedbackMatchedPacingControllerV1,
    _feedback_comparisons,
    _plot,
    _run_episode,
    _short_branch_checks,
)
from validate_stage5_hwmpc_terminal_closeout_v1 import (
    _failure_reason,
    _group_summary,
    _runtime_summary,
)


SCHEMA = "stage5_hwmpc_state_triggered_terminal_validation_v1"
DEFAULT_CONFIG = Path(
    "stages/stage5_personalized_motion_learning/configs/"
    "stage5_hwmpc_state_triggered_terminal_v1.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class StateTriggeredTerminalControllerV1(StateFeedbackMatchedPacingControllerV1):
    """Choose exactly one early-at-1.4 or fallback-at-1.5 handoff per phase."""

    def __init__(self, *args: Any, trigger: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.early_eligibility_start_s = float(trigger["early_eligibility_start_s"])
        self.fallback_handoff_s = float(trigger["fallback_handoff_s"])
        self.reference_rest_tolerance_rad_s = 1.0e-12
        if not self.early_eligibility_start_s < self.fallback_handoff_s:
            raise ValueError("early terminal eligibility must precede fallback")
        if not np.isclose(
            self.terminal_start_s,
            self.fallback_handoff_s,
            atol=1.0e-12,
            rtol=0.0,
        ):
            raise ValueError("base planner reserve must remain the original fallback")
        self.handoff_decisions: dict[TaskPhase, dict[str, Any]] = {}

    def _enter_phase(self, phase: TaskPhase, time_s: float, state: np.ndarray) -> None:
        super()._enter_phase(phase, time_s, state)

    def _segment_complete_at_rest(self) -> tuple[bool, bool, bool]:
        segment_complete = bool(
            self.active_session is not None
            and self.active_schedule is not None
            and self.active_session.progress_s + 1.0e-12
            >= self.active_schedule.duration_s
        )
        reference_at_rest = bool(
            self.last_reference_state is not None
            and np.all(
                np.abs(self.last_reference_state[2:])
                <= self.reference_rest_tolerance_rad_s
            )
        )
        return segment_complete and reference_at_rest, segment_complete, reference_at_rest

    def _latch_handoff_decision(self, phase_elapsed_s: float, state: np.ndarray) -> None:
        if self.phase in self.handoff_decisions:
            return
        eligible, segment_complete, reference_at_rest = self._segment_complete_at_rest()
        self.handoff_decisions[self.phase] = {
            "phase": self.phase.value,
            "decision_phase_elapsed_s": float(phase_elapsed_s),
            "active_segment_complete": segment_complete,
            "emitted_reference_at_rest": reference_at_rest,
            "emitted_q_ref_rad": (
                None if self.last_reference_state is None else self.last_reference_state[:2].copy()
            ),
            "emitted_dq_ref_rad_s": (
                None if self.last_reference_state is None else self.last_reference_state[2:].copy()
            ),
            "deployable_state_rad_rad_s": state.copy(),
            "selected_handoff_s": (
                self.early_eligibility_start_s if eligible else self.fallback_handoff_s
            ),
            "selection_reason": (
                "active_segment_complete_and_emitted_reference_at_rest"
                if eligible
                else "fallback_active_segment_incomplete_or_reference_not_at_rest"
            ),
        }

    def _continue_current_segment(
        self, time_s: float, state: np.ndarray
    ):
        if self.active_session is None or self.active_schedule is None:
            raise ValueError("terminal reserve window has no active coordination segment")
        phase_elapsed_s = float(time_s - self.phase_starts[self.phase])
        sample = self.active_session.advance(
            current_q_hat_rad=state[:2],
            current_dq_hat_rad_s=state[2:],
            phase_elapsed_s=phase_elapsed_s,
        )
        self.last_reference_state = np.concatenate([sample.q_rad, sample.dq_rad_s])
        return _candidate(
            f"trigger_wait_{self.phase.value.lower()}_{phase_elapsed_s:.3f}",
            self.phase,
            sample.q_rad,
            sample.dq_rad_s,
        )

    def _triggered_terminal_candidate(
        self, phase_elapsed_s: float, state: np.ndarray
    ):
        decision = self.handoff_decisions[self.phase]
        handoff_s = float(decision["selected_handoff_s"])
        if self.terminal_schedule is None:
            self._start_terminal(phase_elapsed_s, state)
            decision["actual_handoff_phase_elapsed_s"] = float(phase_elapsed_s)
            decision["terminal_start_q_ref_rad"] = self.last_reference_state[:2].copy()
            decision["terminal_start_dq_ref_rad_s"] = self.last_reference_state[2:].copy()
        assert self.terminal_schedule is not None
        sample = self.terminal_schedule.sample(max(0.0, phase_elapsed_s - handoff_s))
        self.last_reference_state = np.concatenate([sample.q_rad, sample.dq_rad_s])
        return _candidate(
            f"trigger_terminal_{self.phase.value.lower()}_{phase_elapsed_s:.3f}",
            self.phase,
            sample.q_rad,
            sample.dq_rad_s,
        )

    def __call__(self, time_s: float, state: np.ndarray):
        hold_start = self.phase_starts[TaskPhase.HOLD]
        return_start = self.phase_starts[TaskPhase.RETURN]
        if self.phase is TaskPhase.OUTBOUND and time_s + 1.0e-12 >= hold_start:
            self._record_boundary(TaskPhase.OUTBOUND, hold_start, state)
            self._enter_phase(TaskPhase.HOLD, time_s, state)
        if self.phase is TaskPhase.HOLD and time_s + 1.0e-12 >= return_start:
            self._record_boundary(TaskPhase.HOLD, return_start, state)
            self._enter_phase(TaskPhase.RETURN, time_s, state)
        if (
            self.phase is TaskPhase.RETURN
            and time_s + 1.0e-12 >= self.total_duration_s
            and not self._terminal_boundary_checked
        ):
            self._terminal_boundary_checked = True
            self._finalize_pending(time_s, state, "task_boundary")
            if self._record_boundary(TaskPhase.RETURN, self.total_duration_s, state):
                self.completed_time_s = self.total_duration_s

        phase_elapsed_s = float(time_s - self.phase_starts[self.phase])
        if self.phase is TaskPhase.HOLD:
            goal = self._goal(TaskPhase.HOLD)
            self.last_reference_state = np.concatenate([goal, np.zeros(2)])
            return _candidate(
                f"trigger_hold_{phase_elapsed_s:.3f}", self.phase, goal, np.zeros(2)
            )
        if phase_elapsed_s + 1.0e-12 >= self.early_eligibility_start_s:
            self._latch_handoff_decision(phase_elapsed_s, state)
            handoff_s = float(self.handoff_decisions[self.phase]["selected_handoff_s"])
            if phase_elapsed_s + 1.0e-12 >= handoff_s:
                return self._triggered_terminal_candidate(phase_elapsed_s, state)
            return self._continue_current_segment(time_s, state)
        return self._sample_dynamic(time_s, state)

    def record(self) -> dict[str, Any]:
        record = super().record()
        record["terminal_handoff_rule"] = {
            "version": "completed_segment_at_rest_terminal_handoff_v1",
            "early_eligibility_start_s": self.early_eligibility_start_s,
            "fallback_handoff_s": self.fallback_handoff_s,
            "reference_rest_tolerance_rad_s": self.reference_rest_tolerance_rad_s,
            "decisions": [
                self.handoff_decisions[phase]
                for phase in (TaskPhase.OUTBOUND, TaskPhase.RETURN)
                if phase in self.handoff_decisions
            ],
        }
        return record


def _diagnostic_rows(source: dict[str, Any]) -> list[dict[str, Any]]:
    old_path = Path(
        "stages/stage5_personalized_motion_learning/results/engineering_validation/"
        "hwmpc_state_feedback_v1_attempt_02/state_feedback_hwmpc_validation.json"
    )
    old = json.loads(old_path.read_text(encoding="utf-8"))
    old_by_name = {case["episode"]["name"]: case for case in old["episodes"]}
    rows: list[dict[str, Any]] = []
    for case in source["episodes"]:
        name = case["episode"]["name"]
        for phase, global_time in (("OUTBOUND", 1.4), ("RETURN", 4.1)):
            trace_rows = [row for row in case["metrics"]["trace"] if row["phase"] == phase]
            trace = min(trace_rows, key=lambda row: abs(row["elapsed_s"] - global_time))
            decisions = [
                row
                for row in case["controller"]["planner"]["decisions"]
                if row["phase"] == phase and row["phase_elapsed_s"] <= 1.4 + 1.0e-12
            ]
            last = max(decisions, key=lambda row: row["phase_elapsed_s"])
            evaluation = next(
                row for row in last["evaluations"] if row["label"] == last["executed_label"]
            )
            q_ref = np.asarray(trace["requested_q_rad"], dtype=float)
            dq_ref = np.asarray(trace["requested_dq_rad_s"], dtype=float)
            target = np.asarray(evaluation["target_q_rad"], dtype=float)
            state = np.asarray(trace["estimated_state_rad_rad_s"], dtype=float)
            goal = np.radians([20.0, 35.0] if phase == "OUTBOUND" else [5.0, 10.0])
            rows.append(
                {
                    "episode": name,
                    "phase": phase,
                    "active_reference_segment_complete": bool(
                        np.allclose(q_ref, target, atol=1.0e-10, rtol=0.0)
                        and np.allclose(dq_ref, 0.0, atol=1.0e-10, rtol=0.0)
                    ),
                    "emitted_q_ref_deg": np.degrees(q_ref),
                    "emitted_dq_ref_deg_s": np.degrees(dq_ref),
                    "deployable_q_deg": np.degrees(state[:2]),
                    "deployable_dq_deg_s": np.degrees(state[2:]),
                    "remaining_terminal_error_deg": np.degrees(goal - q_ref),
                    "previously_needed_early_reserve": (
                        True
                        if name == "explore_seed_101"
                        else False if name in old_by_name else None
                    ),
                    "fixed_1p4_handoff_contact": bool(
                        case["execution_safety"]["shank_bed_contact_sample_count"] > 0
                    ),
                    "fixed_1p4_minimum_clearance_mm": case["execution_safety"][
                        "minimum_truth_shank_clearance_mm"
                    ],
                }
            )
    return rows


def _classify(cases: list[dict[str, Any]]) -> str:
    seed101 = next(case for case in cases if case["episode"]["name"] == "explore_seed_101")
    contacts = sum(
        case["execution_safety"]["shank_bed_contact_sample_count"] for case in cases
    )
    if not seed101["completed"]:
        return "ST-B — trigger restores terminal failure"
    if contacts:
        return "ST-C — trigger still causes contact"
    if all(
        case["completed"] and case["motion_and_execution_contract_passed"]
        for case in cases
    ):
        return "ST-A — reference-state trigger cleanly separates the cases"
    return "ST-D — cases are not separable by this simple causal trigger"


def run_validation(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema") != "stage5_hwmpc_state_triggered_terminal_v1":
        raise ValueError("unexpected state-triggered terminal config schema")
    if config.get("status") != "FROZEN_AFTER_CAUSAL_SEPARABILITY_AUDIT_BEFORE_EXECUTION":
        raise ValueError("trigger logic and test budget were not frozen before execution")
    source = config["source"]
    fixed_config_path = Path(source["fixed_reserve_config"])
    retained_result_path = Path(source["retained_11_result"])
    if _sha256(fixed_config_path) != source["fixed_reserve_config_sha256"]:
        raise ValueError("fixed-reserve config hash changed")
    if _sha256(retained_result_path) != source["retained_11_result_sha256"]:
        raise ValueError("retained 11 result hash changed")
    retained_source = json.loads(retained_result_path.read_text(encoding="utf-8"))
    prechange_diagnostic = _diagnostic_rows(retained_source)
    truth_human, control_model, model_version = _fixed_models(config)
    branch_checks = _short_branch_checks(config, control_model)

    def controller_factory(**kwargs: Any) -> StateTriggeredTerminalControllerV1:
        return StateTriggeredTerminalControllerV1(
            **kwargs, trigger=config["single_rule"]
        )

    retained = [
        _run_episode(
            config,
            episode,
            truth_human,
            control_model,
            model_version,
            controller_factory=controller_factory,
        )
        for episode in config["bounded_test_budget"]["retained_episodes"]
    ]
    trigger_classification = _classify(retained)
    fresh: list[dict[str, Any]] = []
    if trigger_classification.startswith("ST-A"):
        fresh = [
            _run_episode(
                config,
                episode,
                truth_human,
                control_model,
                model_version,
                controller_factory=controller_factory,
            )
            for episode in config["bounded_test_budget"][
                "conditional_fresh_validation_episodes"
            ]
        ]
    cases = retained + fresh
    retained_summary = _group_summary(retained)
    fresh_summary = None if not fresh else _group_summary(fresh)
    all_complete = all(case["completed"] for case in cases)
    all_safe = all(case["motion_and_execution_contract_passed"] for case in cases)
    distinct_actions = len(
        {
            tuple(np.round(decision["executed_action_delta_q_rad"], 10))
            for case in cases
            for decision in case["controller"]["planner"]["decisions"]
        }
    )
    if (
        trigger_classification.startswith("ST-A")
        and fresh
        and all_complete
        and all_safe
        and distinct_actions >= 3
    ):
        conclusion = "TB2-A — DYNAMIC WAYPOINT BASELINE CLOSED OUT FOR LEARNING-DATA GENERATION"
    elif trigger_classification.startswith("ST-B") or trigger_classification.startswith("ST-D"):
        conclusion = "TB2-C — SIMPLE TERMINAL HANDOFF LOGIC IS INSUFFICIENT"
    else:
        conclusion = "TB2-B — STATE-TRIGGER IMPROVES CLOSEOUT BUT BASELINE REMAINS UNRELIABLE"

    handoff_usage = {
        case["episode"]["name"]: {
            row["phase"]: row
            for row in case["controller"]["terminal_handoff_rule"]["decisions"]
        }
        for case in cases
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_path = output_dir / "state_triggered_terminal_paths.png"
    _plot(cases, plot_path)
    result = _jsonable({
        "schema": SCHEMA,
        "evidence_category": config["evidence_category"],
        "trigger_classification": trigger_classification,
        "conclusion": conclusion,
        "config": config,
        "prechange_t1p4_diagnostic": prechange_diagnostic,
        "short_branch_checks": branch_checks,
        "retained_summary": retained_summary,
        "conditional_fresh_summary": fresh_summary,
        "conditional_fresh_executed": bool(fresh),
        "runtime": _runtime_summary(cases),
        "timing_semantics": config["timing_contract"],
        "terminal_handoff_usage": handoff_usage,
        "distinct_direct_delta_q_action_count": distinct_actions,
        "feedback_dependence_comparisons": _feedback_comparisons(cases),
        "episodes": cases,
        "all_complete": all_complete,
        "all_motion_and_execution_contracts_passed": all_safe,
        "plot": str(plot_path),
        "scope_invariants": config["scope"],
        "limitations": [
            "bounded deterministic MuJoCo engineering evidence only",
            "synchronous simulation pauses physical time during high-level planning",
            "high-level wall-clock latency is not represented as plant delay",
            "no hardware realtime or formal safety claim",
        ],
    })
    result_path = output_dir / "state_triggered_terminal_validation.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    dataset_summary = export_dataset(
        result_path, output_dir / "learning_transitions_v1.jsonl"
    )
    print(
        json.dumps(
            {
                "trigger_classification": trigger_classification,
                "conclusion": conclusion,
                "retained_summary": retained_summary,
                "conditional_fresh_executed": bool(fresh),
                "conditional_fresh_summary": fresh_summary,
                "distinct_actions": distinct_actions,
                "handoff_usage": {
                    name: {
                        phase: row["selected_handoff_s"]
                        for phase, row in phases.items()
                    }
                    for name, phases in handoff_usage.items()
                },
                "dataset_summary": dataset_summary,
                "output_dir": str(output_dir),
            },
            indent=2,
        )
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    run_validation(arguments.config, arguments.output_dir)


if __name__ == "__main__":
    main()
