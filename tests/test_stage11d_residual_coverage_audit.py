import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]

from run_spring2d_adaptive_mpc_conditions import load_experiment_config
from run_spring2d_stage10b_estimator_benchmark import (
    DEFAULT_CONFIG,
    DEFAULT_REPLAY,
    arrays,
    load_replay,
)
import run_stage11d_residual_coverage_audit as stage11d


def synthetic_problem():
    rng = np.random.default_rng(17)
    H = rng.normal(size=(140, 3))
    truth = np.array([0.8, 375.0, 15.0])
    y = H @ truth + rng.normal(scale=0.1, size=140)
    proxies = {
        "state_magnitude": np.linspace(0.1, 1.0, 70),
        "state_rate_magnitude": np.linspace(0.2, 0.8, 70),
        "action_magnitude": np.linspace(1.0, 2.0, 70),
    }
    profile = {
        "true_lambda_at_minimum": 0.81,
        "true_truth_in_region_95": "True",
        "true_lambda_optimum_relative_error": 0.0125,
        "true_lambda_region_width_95": 0.08,
        "true_lambda_relative_width": 0.1,
    }
    return H, y, truth, proxies, profile


def paired_profile_rows(identities):
    rows = []
    for condition, seed, start, end in identities:
        for profile in sorted(stage11d.PROFILE_NAMES):
            rows.append(
                {
                    "condition": condition,
                    "seed": seed,
                    "window_start": start,
                    "window_end": end,
                    "profile": profile,
                }
            )
    return rows


def test_exact_stage11c_window_identity_alignment():
    identities = [("clean", 101, 1, 70), ("noise", 101, 11, 80)]
    manifest = {
        "actual_windows": 2,
        "conditions": ["clean", "noise"],
        "seeds": [101],
    }
    indexed = stage11d.validate_and_index_stage11c_profiles(
        paired_profile_rows(identities), manifest
    )
    assert set(indexed) == set(identities)
    missing = paired_profile_rows(identities)[:-1]
    with pytest.raises(RuntimeError, match="exactly"):
        stage11d.validate_and_index_stage11c_profiles(missing, manifest)


def test_true_state_window_uses_only_replay_true_states():
    replay = load_replay(DEFAULT_REPLAY)
    data = dict(arrays(replay[("clean", 101)]))
    data["estimated"] = np.full_like(data["estimated"], np.nan)
    config = load_experiment_config(DEFAULT_CONFIG)
    model_params = stage11d.stage9j_overrides(config, "clean")["model_params"]
    H, y, start, proxies = stage11d.build_true_state_window(
        "clean", 101, data, model_params, 70
    )
    assert start == 1
    assert H.shape == (140, 3)
    assert y.shape == (140,)
    assert all(len(values) == 70 for values in proxies.values())
    assert np.all(np.isfinite(H)) and np.all(np.isfinite(y))


def test_ls_optimum_weighted_score_is_near_zero():
    H, y, truth, proxies, profile = synthetic_problem()
    row = stage11d.compute_window_diagnostic(
        ("clean", 101, 1, 70), H, y, truth, proxies, profile
    )
    assert max(
        abs(row[f"ls_score_{name}_raw"]) for name in stage11d.PARAMETER_ORDER
    ) < 1.0e-8


def test_truth_score_uses_unchanged_weighted_design_matrix():
    H, y, truth, proxies, profile = synthetic_problem()
    row = stage11d.compute_window_diagnostic(
        ("clean", 101, 1, 70), H, y, truth, proxies, profile
    )
    Hw, yw = stage11d.weighted_design(H, y, stage11d.ROW_SQRT_WEIGHTS)
    expected = Hw.T @ (Hw @ truth - yw)
    observed = np.array(
        [row[f"truth_score_{name}_raw"] for name in stage11d.PARAMETER_ORDER]
    )
    assert np.allclose(observed, expected, rtol=0.0, atol=1.0e-12)


def test_autocorrelation_residual_channels_are_not_interleaved():
    interleaved = np.array([1.0, 10.0, 2.0, 20.0, 3.0, 30.0, 4.0, 40.0])
    channels = stage11d.split_residual_channels(interleaved)
    assert np.array_equal(channels["radial"], [1.0, 2.0, 3.0, 4.0])
    assert np.array_equal(channels["angular"], [10.0, 20.0, 30.0, 40.0])
    assert np.isclose(
        stage11d.lag_autocorrelation(channels["radial"], 1),
        stage11d.lag_autocorrelation(channels["angular"], 1),
    )
    assert not np.isclose(
        stage11d.lag_autocorrelation(interleaved, 1),
        stage11d.lag_autocorrelation(channels["radial"], 1),
    )


def test_smoke_output_is_local_and_non_authoritative(tmp_path):
    args = stage11d.parse_args(["--smoke"])
    assert args.output_root == stage11d.OUTPUT_SMOKE
    manifest = {
        "execution_mode": "smoke",
        "actual_runs": 1,
        "actual_windows": 3,
    }
    summary = {
        "condition": "clean",
        "n_windows": 3,
        "lambda_truth_inclusion_fraction": 0.5,
        "lambda_optimum_relative_error_median": 0.1,
        "lambda_profile_relative_width_95_median": 0.2,
        "truth_radial_weighted_residual_rms_median": 0.3,
        "truth_angular_weighted_residual_rms_median": 0.4,
        "truth_score_lambda_normalized_median_abs": 0.05,
        "ls_radial_weighted_residual_rms_median": 0.2,
        "ls_angular_weighted_residual_rms_median": 0.3,
        "truth_radial_weighted_autocorr_lag1_median": 0.1,
        "truth_angular_weighted_autocorr_lag1_median": 0.2,
        "truth_radial_weighted_autocorr_lag5_median": 0.05,
        "truth_angular_weighted_autocorr_lag5_median": 0.1,
        "truth_radial_weighted_autocorr_lag10_median": 0.01,
        "truth_angular_weighted_autocorr_lag10_median": 0.02,
        "truth_radial_weighted_squared_corr_state_magnitude_median": 0.11,
        "truth_radial_weighted_squared_corr_state_rate_magnitude_median": 0.12,
        "truth_radial_weighted_squared_corr_action_magnitude_median": 0.13,
        "truth_score_kappa_normalized_median_abs": 0.06,
        "truth_score_beta_normalized_median_abs": 0.07,
    }
    stage11d.write_report(tmp_path, manifest, [summary])
    report = (tmp_path / "stage11d_report.md").read_text()
    assert "local implementation validation only" in report
    assert "automatically selecting H1 or H2" in report
    assert "scientific outcome" in report


def test_smoke_selects_one_run_and_at_most_three_windows():
    identities = [
        ("clean", 101, 1 + 10 * index, 70 + 10 * index)
        for index in range(5)
    ] + [("clean", 102, 1, 70)]
    profiles = {
        identity: {name: {} for name in stage11d.PROFILE_NAMES}
        for identity in identities
    }
    selected = stage11d.choose_identities(profiles, "smoke")
    assert len(selected) == 3
    assert len({identity[:2] for identity in selected}) == 1


def test_manifest_marks_smoke_non_authoritative_contract():
    assert stage11d.resolve_output_root("smoke", None) == stage11d.OUTPUT_SMOKE
    assert stage11d.resolve_output_root("full", None) == stage11d.OUTPUT_FORMAL
    source_manifest = json.loads(stage11d.STAGE11C_MANIFEST.read_text())
    assert source_manifest["mechanical_status"] == "valid_full_run"
