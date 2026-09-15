"""Focused checks for the diagnostic-only final-campaign root-cause audit."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit_stage5_interface_robustness_remaining_issues.py"
)
SPEC = importlib.util.spec_from_file_location("stage5_remaining_issues_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_frozen_failure_prediction_and_command_reconstruction() -> None:
    trace = AUDIT._trace("low_low_high", 20260824)
    prediction = AUDIT._first_prediction(trace)
    assert prediction["acceleration_deg_s2"][1] == pytest.approx(
        547.0878549816765
    )
    assert prediction["q2_margin_deg_s2"] == pytest.approx(52.912145018323486)
    for index in range(len(trace["time_s"])):
        components = AUDIT._low_level_components(trace, index)
        assert components["saved_command_residual_norm"] < 1.0e-4


def test_benchmark_summary_keeps_wall_and_process_semantics_separate() -> None:
    summary = AUDIT.summarize_benchmark_samples(
        [10.0, 12.0, 14.0], [9.0, 11.0, 13.0], 2
    )
    assert summary["repetitions"] == 3
    assert summary["wall_mean_ms"] == pytest.approx(12.0)
    assert summary["process_mean_ms"] == pytest.approx(11.0)
    assert summary["wall_minus_process_mean_ms"] == pytest.approx(1.0)
    assert summary["gc_events"] == 2
    with pytest.raises(ValueError):
        AUDIT.summarize_benchmark_samples([1.0], [1.0, 2.0], 0)
