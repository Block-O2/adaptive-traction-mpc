from __future__ import annotations

from functools import lru_cache
import importlib.util
from pathlib import Path

import pytest

import traction_mpc_stage5.controller_interface as controller_interface


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit_stage5_native_prefix_v1.py"
)
SPEC = importlib.util.spec_from_file_location("stage5_native_prefix_v1", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


@lru_cache(maxsize=1)
def _result():
    return AUDIT.equivalence_audit()


def test_native_prefix_matches_reference_control_decisions() -> None:
    result = _result()
    assert result["passed"]
    for snapshot in result["full_solve_snapshots"]:
        assert snapshot["selected_action_max_abs_difference"] == 0.0
        assert snapshot["selected_sequence_max_abs_difference"] == 0.0
        assert snapshot["maximum_numeric_difference"] <= result["absolute_tolerance"]
        assert all(snapshot["diagnostics_exact"].values())
        assert all(
            row["feasibility_mask_exact"]
            and row["prefix_feasibility_exact"]
            and row["prefix_times_exact"]
            for row in snapshot["populations"]
        )
        assert all(
            row["candidate_actions_exact"] and row["elite_indices_exact"]
            for row in snapshot["cem_iterations"]
        )


def test_native_prefix_matches_every_retained_substep_snapshot() -> None:
    result = _result()
    assert {
        row["label"] for row in result["saved_event_segment_snapshots"]
    } == {
        "known_conservative_false_positive",
        "retained_real_short_transient_violation",
    }
    assert all(
        row["passed"] and not row["truth_used_online"]
        for row in result["saved_event_segment_snapshots"]
    )


def test_native_prefix_contract_and_repeatability_are_frozen() -> None:
    result = _result()
    contract = result["frozen_contract"]
    assert contract["prefix_times_s"] == [0.005, 0.010, 0.015, 0.020]
    assert contract["substep_s"] == 0.00025
    assert contract["substeps_per_prefix"] == 20
    assert contract["candidate_count"] == 32
    assert contract["cem_iterations"] == 2
    assert contract["native_calls_per_population"] == 4
    assert contract["float_precision"] == "float64"
    assert not contract["fast_math"]
    assert contract["fp_contraction"] == "off"
    assert all(result["deterministic_repeatability"].values())


def test_auto_backend_falls_back_and_explicit_native_fails_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = AUDIT.RUNTIME._build_fixed_snapshot()
    monkeypatch.setattr(controller_interface, "_prefix_native", None)
    common = {
        "q_rad": snapshot["observation"].as_array()[:2],
        "human_model": snapshot["human_model"],
        "cuff_allocator": snapshot["mpc"].cuff_allocator,
        "state_rad_rad_s": snapshot["observation"].as_array(),
        "acceleration_limits_rad_s2": snapshot[
            "spec"
        ].task_joint_acceleration_limit_rad_s2,
    }
    fallback = controller_interface.make_interface_aware_first_action_batch_preview(
        snapshot["execution_context"].preview_command_batch,
        snapshot["predictor"],
        snapshot["interface_state"],
        prefix_backend="auto",
        **common,
    )
    assert fallback.prefix_backend_resolved == "numpy"
    with pytest.raises(RuntimeError, match="extension is unavailable"):
        controller_interface.make_interface_aware_first_action_batch_preview(
            snapshot["execution_context"].preview_command_batch,
            snapshot["predictor"],
            snapshot["interface_state"],
            prefix_backend="native",
            **common,
        )


def test_native_source_does_not_cross_truth_or_change_monitor_contract() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "traction_mpc_stage5"
        / "_prefix_native.c"
    ).read_text(encoding="utf-8")
    lowered = source.lower()
    assert "mujoco" not in lowered
    assert "plant_truth" not in lowered
    assert "0.00025" not in source  # dt is passed from the frozen controller config.
    assert "fast-math" not in source
