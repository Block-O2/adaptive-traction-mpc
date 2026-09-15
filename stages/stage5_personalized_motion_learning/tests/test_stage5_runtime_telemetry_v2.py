from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit_stage5_runtime_telemetry_v2.py"
)
SPEC = importlib.util.spec_from_file_location("stage5_runtime_telemetry_v2", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def _rows(wall: list[float], process: list[float]):
    return [
        {
            "wall_ms": w,
            "process_ms": p,
            "section__human": 0.5 * p,
            "section__interface": 0.25 * p,
        }
        for w, p in zip(wall, process, strict=True)
    ]


def test_runtime_window_keeps_wall_process_and_sections_separate() -> None:
    summary = AUDIT.summarize_window(_rows([10.0, 12.0], [9.0, 11.0]))
    assert summary["wall_mean_ms"] == pytest.approx(11.0)
    assert summary["process_mean_ms"] == pytest.approx(10.0)
    assert summary["wall_minus_process_mean_ms"] == pytest.approx(1.0)
    assert summary["section_mean_ms"]["human"] == pytest.approx(5.0)


def test_runtime_case_classification_does_not_overclaim_b4() -> None:
    first = AUDIT.summarize_window(_rows([10.0, 10.0], [9.0, 9.0]))
    wall_only = AUDIT.summarize_window(_rows([12.0, 12.0], [9.1, 9.1]))
    both = AUDIT.summarize_window(_rows([12.0, 12.0], [11.0, 11.0]))
    neither = AUDIT.summarize_window(_rows([10.5, 10.5], [9.3, 9.3]))
    assert AUDIT.classify_runtime_growth(first, wall_only)["comparison_case"] == "A"
    assert AUDIT.classify_runtime_growth(first, both)["comparison_case"] == "B"
    assert AUDIT.classify_runtime_growth(first, neither)["comparison_case"] == "C"
    assert AUDIT.classify_runtime_growth(first, wall_only)[
        "b1_to_b6_classification"
    ] == "B6"
