from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


RUNNER_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "architecture_recovery_v2"
    / "run_functional_campaign.py"
)
SPEC = importlib.util.spec_from_file_location("v2_campaign_runner", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


ARMS = (
    "oracle",
    "adaptive",
    "fixed_nominal",
    "wrong_geometry_adaptive_dynamics",
    "no_dynamics_adaptation",
)


def _row(arm: str, setup_seed: int, task_seed: int) -> dict[str, object]:
    rmse = {
        "oracle": 0.5,
        "adaptive": 1.0,
        "fixed_nominal": 5.0,
        "wrong_geometry_adaptive_dynamics": 4.0,
        "commissioning_only_dynamics": 1.5,
        "no_dynamics_adaptation": 2.0,
    }[arm]
    return {
        "arm": arm,
        "seed": setup_seed,
        "task_seed": task_seed,
        "completed": arm in {"oracle", "adaptive"},
        "full_horizon_executed": True,
        "clearance_evaluation_enabled": True,
        "q_tracking_rmse_deg": rmse,
        "q_tracking_max_abs_deg": 2.0 * rmse,
        "force_peak_n": 100.0,
        "moment_peak_nm": 20.0,
        "probe_force_peak_n": 150.0,
        "probe_moment_peak_nm": 25.0,
        "probe_rom_violation": False,
        "probe_consistency_abort_count": 0,
        "post_probe_constructed_reference_min_clearance_m_evaluation_only": 0.02,
        "post_probe_constructed_reference_clearance_violation_evaluation_only": False,
        "rom_violation_samples": 0,
        "solver_failure_count": 0,
        "safety_abort_count": 0,
        "estimated_rom_supervisor_abort_count": 0,
        "termination_reason": "completed",
        "setup_evaluation_only": {
            "generation_attempt": 0,
            "generation_rejection_counts": {},
        },
    }


def _gates() -> dict[str, object]:
    return {
        "expected_case_count_per_arm": 2,
        "expected_arms": list(ARMS),
        "adaptive_completion_rate_minimum": 0.9,
        "adaptive_tracking_rmse_deg_median_maximum": 3.0,
        "adaptive_tracking_rmse_deg_p95_maximum": 5.0,
        "force_peak_n_maximum": 200.0,
        "moment_peak_nm_maximum": 60.0,
        "adaptive_vs_fixed_median_improvement_fraction_minimum": 0.2,
        "adaptive_vs_fixed_completion_rate_margin_minimum": 0.5,
        "adaptive_vs_no_dynamics_median_improvement_fraction_minimum": 0.2,
        "adaptive_vs_no_dynamics_completion_rate_margin_minimum": 0.5,
        "adaptive_vs_wrong_geometry_median_improvement_fraction_minimum": 0.2,
        "adaptive_vs_wrong_geometry_completion_rate_margin_minimum": 0.5,
        "adaptive_minus_oracle_median_gap_deg_maximum": 2.5,
    }


def test_formal_gate_requires_paired_unique_matrix_and_probe_safety() -> None:
    rows = [
        _row(arm, setup_seed, task_seed)
        for setup_seed, task_seed in ((1, 101), (2, 102))
        for arm in ARMS
    ]
    result = RUNNER.evaluate_gates(RUNNER.summarize(rows), _gates())
    assert result is not None and result["passed"]

    duplicate = [dict(row) for row in rows]
    duplicate[-1]["seed"] = 1
    duplicate[-1]["task_seed"] = 101
    result = RUNNER.evaluate_gates(RUNNER.summarize(duplicate), _gates())
    assert result is not None
    assert not result["checks"]["complete_paired_matrix"]

    probe_failure = [dict(row) for row in rows]
    adaptive = next(row for row in probe_failure if row["arm"] == "adaptive")
    adaptive["probe_rom_violation"] = True
    result = RUNNER.evaluate_gates(RUNNER.summarize(probe_failure), _gates())
    assert result is not None
    assert not result["checks"]["adaptive_probe_rom"]

    clearance_not_evaluated = [dict(row) for row in rows]
    adaptive = next(
        row for row in clearance_not_evaluated if row["arm"] == "adaptive"
    )
    adaptive["clearance_evaluation_enabled"] = False
    result = RUNNER.evaluate_gates(
        RUNNER.summarize(clearance_not_evaluated), _gates()
    )
    assert result is not None
    assert not result["checks"]["adaptive_clearance_evaluated"]

    post_probe_reference_failure = [dict(row) for row in rows]
    adaptive = next(
        row for row in post_probe_reference_failure if row["arm"] == "adaptive"
    )
    adaptive[
        "post_probe_constructed_reference_clearance_violation_evaluation_only"
    ] = True
    result = RUNNER.evaluate_gates(
        RUNNER.summarize(post_probe_reference_failure), _gates()
    )
    assert result is not None
    assert not result["checks"][
        "adaptive_post_probe_constructed_reference_clearance"
    ]

    post_probe_reference_missing = [dict(row) for row in rows]
    adaptive = next(
        row for row in post_probe_reference_missing if row["arm"] == "adaptive"
    )
    adaptive.pop(
        "post_probe_constructed_reference_min_clearance_m_evaluation_only"
    )
    result = RUNNER.evaluate_gates(
        RUNNER.summarize(post_probe_reference_missing), _gates()
    )
    assert result is not None
    assert not result["checks"][
        "adaptive_post_probe_constructed_reference_clearance"
    ]


def test_exception_rows_remain_in_denominator_without_empty_max_crash() -> None:
    rows = [_row(arm, 1, 101) for arm in ARMS]
    failed = {
        "arm": "adaptive",
        "seed": 2,
        "task_seed": 102,
        "completed": False,
        "full_horizon_executed": False,
        "termination_reason": "runner_exception:RuntimeError",
    }
    rows.append(failed)
    summary = RUNNER.summarize(rows)
    adaptive = summary["by_arm"]["adaptive"]
    assert adaptive["case_count"] == 2
    assert adaptive["completion_rate"] == 0.5
    assert adaptive["tracking_metric_count"] == 1


def test_generation_summary_deduplicates_arms_and_reports_rejections() -> None:
    rows = [_row(arm, 1, 101) for arm in ARMS]
    for row in rows:
        row["setup_evaluation_only"] = {
            "generation_attempt": 2,
            "generation_rejection_counts": {
                "clearance": 2,
                "combined_rejected_proposal": 2,
            },
        }
    generation = RUNNER.summarize(rows)["case_generation"]
    assert generation["generated_case_count"] == 1
    assert generation["proposal_draw_count_for_generated_cases"] == 3
    assert generation["realized_acceptance_fraction_for_generated_cases"] == pytest.approx(1 / 3)
    assert generation["rejection_causes_before_acceptance"]["clearance"] == 2


def test_lying_bed_config_fails_closed_without_clearance_fields() -> None:
    with pytest.raises(ValueError, match="fail-closed mechanics fields"):
        RUNNER.validate_config(
            {
                "environment_contract": {
                    "scenario": "lying_bed_contact_free_clearance"
                },
                "hidden_generation": {"bed_height_m": 0.012},
            }
        )


def test_ablation_gate_requires_paired_safe_continual_benefit() -> None:
    arms = (
        "adaptive",
        "commissioning_only_dynamics",
        "no_dynamics_adaptation",
    )
    rows = [
        _row(arm, setup_seed, task_seed)
        for setup_seed, task_seed in ((1, 101), (2, 102))
        for arm in arms
    ]
    for row in rows:
        if row["arm"] == "commissioning_only_dynamics":
            row["completed"] = False
        elif row["arm"] == "no_dynamics_adaptation":
            row["completed"] = False
    gates = {
        "expected_case_count_per_arm": 2,
        "expected_arms": list(arms),
        "force_peak_n_maximum": 200.0,
        "moment_peak_nm_maximum": 60.0,
        "continual_vs_commissioning_median_improvement_fraction_minimum": 0.20,
        "continual_vs_commissioning_completion_rate_margin_minimum": 0.25,
        "continual_vs_no_dynamics_median_improvement_fraction_minimum": 0.20,
        "continual_vs_no_dynamics_completion_rate_margin_minimum": 0.50,
    }
    result = RUNNER.evaluate_ablation_gates(RUNNER.summarize(rows), gates)
    assert result is not None and result["passed"]

    unsafe = [dict(row) for row in rows]
    adaptive = next(row for row in unsafe if row["arm"] == "adaptive")
    adaptive["probe_settle_timeout_count"] = 1
    result = RUNNER.evaluate_ablation_gates(RUNNER.summarize(unsafe), gates)
    assert result is not None
    assert not result["checks"]["continual_probe_settle_timeout"]


def test_formal_gate_can_require_commissioning_only_separation() -> None:
    arms = (*ARMS, "commissioning_only_dynamics")
    rows = [
        _row(arm, setup_seed, task_seed)
        for setup_seed, task_seed in ((1, 101), (2, 102))
        for arm in arms
    ]
    for row in rows:
        if row["arm"] == "commissioning_only_dynamics":
            row["completed"] = False
    gates = _gates()
    gates["expected_arms"] = list(arms)
    gates[
        "adaptive_vs_commissioning_median_improvement_fraction_minimum"
    ] = 0.20
    gates[
        "adaptive_vs_commissioning_completion_rate_margin_minimum"
    ] = 0.25
    result = RUNNER.evaluate_gates(RUNNER.summarize(rows), gates)
    assert result is not None and result["passed"]

    insufficient = [dict(row) for row in rows]
    for row in insufficient:
        if row["arm"] == "commissioning_only_dynamics":
            row["completed"] = True
            row["q_tracking_rmse_deg"] = 1.05
            row["q_tracking_max_abs_deg"] = 2.1
    result = RUNNER.evaluate_gates(RUNNER.summarize(insufficient), gates)
    assert result is not None
    assert not result["checks"]["adaptive_beats_commissioning_only"]
