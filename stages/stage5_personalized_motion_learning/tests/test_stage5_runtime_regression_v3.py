from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit_stage5_runtime_regression_v3.py"
)
SPEC = importlib.util.spec_from_file_location("stage5_runtime_regression_v3", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_runtime_summary_reports_all_registered_quantiles() -> None:
    result = AUDIT.summarize([1.0, 2.0, 3.0, 4.0, 5.0])
    assert set(result) == {"mean", "median", "p95", "p99", "max"}
    assert result["mean"] == 3.0
    assert result["median"] == 3.0
    assert result["max"] == 5.0


def test_benchmark_modes_do_not_change_production_configuration() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "candidate_count=" not in source
    assert "cem_iterations=" not in source
    assert "horizon_steps=" not in source
    assert "_reuse_cached_subsets = False" in source
    assert "v2_prefix_uncached" in source


def test_fixed_snapshot_subset_cache_is_behaviorally_equivalent() -> None:
    result = AUDIT.equivalence_gate()
    assert result["passed"]
    assert result["selected_first_action_max_abs_difference"] == 0.0
    assert result["selected_sequence_max_abs_difference"] == 0.0
    assert all(
        row["candidate_feasibility_mask_exact"]
        for row in result["cem_populations"]
    )
