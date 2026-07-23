import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]

from run_spring2d_adaptive_mpc_conditions import load_experiment_config
from run_spring2d_stage10b_estimator_benchmark import DEFAULT_CONFIG, DEFAULT_REPLAY, arrays, load_replay
import run_stage11b_parameter_subspace_audit as stage11b
from run_stage11b_parameter_subspace_audit import (
    adaptive_profile_lambda,
    adaptive_profile_lambda_kappa,
    aggregate_directions,
    analyze_window,
    build_affine_window,
    pair_profile_rows,
    pair_window_rows,
    paired_full_conclusion,
    profile_lambda_kappa,
    ridge_direction_from_accepted,
    residual_cost,
    svd_metrics,
    verify_truth_metadata,
    write_stage11c_report,
)


def synthetic_problem(noise_scale=0.0):
    rng = np.random.default_rng(7)
    H = rng.normal(size=(80, 3))
    truth = np.array([0.8, 375.0, 15.0])
    return H, H @ truth + rng.normal(scale=noise_scale, size=80), truth


def test_synthetic_1d_profile_recovers_known_parameter():
    H, y, truth = synthetic_problem()
    summary, _ = adaptive_profile_lambda(H, y, truth[0], grid_size=5)
    assert np.isclose(summary["lambda_at_minimum"], truth[0], atol=1.0e-10)


def test_synthetic_2d_profile_recovers_known_parameters():
    H, y, truth = synthetic_problem()
    summary, _ = adaptive_profile_lambda_kappa(H, y, truth[:2], grid_size=5)
    assert np.allclose([summary["lambda_at_minimum"], summary["kappa_at_minimum"]], truth[:2], atol=1.0e-10)


def test_automatic_boundary_expansion_resolves_interval():
    H, _, truth = synthetic_problem()
    H[:, 0] *= 1.0e-3
    rng = np.random.default_rng(19)
    noise = rng.normal(size=len(H))
    noise -= H @ np.linalg.lstsq(H, noise, rcond=None)[0]
    y = H @ truth + 0.4 * noise
    summary, _ = adaptive_profile_lambda(H, y, truth[0], grid_size=5)
    assert summary["expansion_count"] > 0
    assert not summary["boundary_hit"]


def test_adaptive_refinement_converges_from_coarse_grids():
    H, y, truth = synthetic_problem(noise_scale=0.2)
    coarse, _ = adaptive_profile_lambda_kappa(H, y, truth[:2], grid_size=5)
    finer, _ = adaptive_profile_lambda_kappa(H, y, truth[:2], grid_size=9)
    coarse_width = np.array([coarse["lambda_region_width_95"], coarse["kappa_region_width_95"]])
    finer_width = np.array([finer["lambda_region_width_95"], finer["kappa_region_width_95"]])
    assert coarse["refinement_count"] > 0 and finer["refinement_count"] > 0
    assert np.all(np.abs(coarse_width - finer_width) / np.maximum(finer_width, 1.0e-12) < 0.15)


def test_undefined_ridge_when_fewer_than_three_points_are_accepted():
    accepted = [{"lambda": 0.8, "kappa": 375.0}, {"lambda": 0.81, "kappa": 374.0}]
    assert ridge_direction_from_accepted(accepted) is None


def test_2d_profile_cost_equals_direct_weighted_residual_sum():
    H, y, truth = synthetic_problem()
    row = profile_lambda_kappa(H, y, [truth[0]], [truth[1]])[0]
    direct = residual_cost(H, y, np.array([row["lambda"], row["kappa"], row["beta_hat"]]))
    assert np.isclose(row["cost"], direct, rtol=0.0, atol=1.0e-12)


def test_scaled_svd_direction_maps_back_by_division():
    H, _, _ = synthetic_problem()
    result = svd_metrics(H)
    repeated = np.tile(np.array([0.6, 0.25]), len(H) // 2)
    Hw = H * repeated[:, None]
    scale = np.linalg.norm(Hw, axis=0)
    expected = result["normalized_weak_direction"] / scale
    expected /= np.linalg.norm(expected)
    assert np.allclose(np.abs(result["physical_weak_direction"] @ expected), 1.0, atol=1.0e-12)


def test_sign_ambiguous_vectors_aggregate_identically():
    vectors = np.array([[1.0, 2.0, -0.5], [-1.0, -2.0, 0.5]])
    positive = aggregate_directions(vectors)
    negative = aggregate_directions(-vectors)
    assert np.allclose(positive["projector_eigenvalues"], negative["projector_eigenvalues"])
    assert np.isclose(abs(positive["direction"] @ negative["direction"]), 1.0)


def test_noiseless_affine_truth_is_in_profile_minimum_region():
    H, y, truth = synthetic_problem()
    one, _ = adaptive_profile_lambda(H, y, truth[0], grid_size=5)
    two, _ = adaptive_profile_lambda_kappa(H, y, truth[:2], grid_size=5)
    assert one["truth_in_region_95"]
    assert two["truth_in_region_95"]


def test_mismatch_truth_metadata_matches_actual_plant_and_not_nominal():
    replay = load_replay(DEFAULT_REPLAY)
    config = load_experiment_config(DEFAULT_CONFIG)
    for condition in ("mass_mismatch", "parameter_mismatch_low_k", "parameter_mismatch_high_k"):
        data = arrays(replay[(condition, 101)])
        verify_truth_metadata(condition, data, config)
    ambiguous = dict(arrays(replay[("mass_mismatch", 101)]))
    ambiguous["true_params"] = ambiguous["nominal_params"].copy()
    with pytest.raises(RuntimeError, match="do not match|nominal or ambiguous"):
        verify_truth_metadata("mass_mismatch", ambiguous, config)


def test_true_and_estimated_modes_share_windows_and_controls():
    replay = load_replay(DEFAULT_REPLAY)
    data = arrays(replay[("clean", 101)])
    config = load_experiment_config(DEFAULT_CONFIG)
    model_params = stage11b.stage9j_overrides(config, "clean")["model_params"]
    end = 300
    _, _, estimated_start = build_affine_window("clean", 101, data, model_params, end, "estimated")
    _, _, true_start = build_affine_window("clean", 101, data, model_params, end, "true")
    assert estimated_start == true_start == end - stage11b.WINDOW_TRANSITIONS + 1
    assert np.array_equal(data["action"][estimated_start : end + 1], data["action"][true_start : end + 1])


def test_true_mode_uses_only_replay_true_states():
    replay = load_replay(DEFAULT_REPLAY)
    data = dict(arrays(replay[("clean", 101)]))
    data["estimated"] = np.full_like(data["estimated"], np.nan)
    config = load_experiment_config(DEFAULT_CONFIG)
    model_params = stage11b.stage9j_overrides(config, "clean")["model_params"]
    H, y, _ = build_affine_window("clean", 101, data, model_params, 300, "true")
    assert np.all(np.isfinite(H)) and np.all(np.isfinite(y))
    with pytest.raises(AssertionError):
        build_affine_window("clean", 101, data, model_params, 300, "estimated")


def test_paired_rows_are_aligned_by_window_and_profile():
    replay = load_replay(DEFAULT_REPLAY)
    data = arrays(replay[("clean", 101)])
    config = load_experiment_config(DEFAULT_CONFIG)
    model_params = stage11b.stage9j_overrides(config, "clean")["model_params"]
    estimated_window, estimated_profiles, _ = analyze_window("clean", 101, data, model_params, 300, 5, "estimated")
    true_window, true_profiles, _ = analyze_window("clean", 101, data, model_params, 300, 5, "true")
    paired_window = pair_window_rows(estimated_window, true_window)
    paired_profiles = pair_profile_rows(estimated_profiles, true_profiles)
    assert paired_window["window_start"] == estimated_window["window_start"] == true_window["window_start"]
    assert len(paired_profiles) == 2
    assert {row["profile"] for row in paired_profiles} == {"lambda_1d", "lambda_kappa_2d"}


def test_synthetic_noiseless_true_state_includes_truth(monkeypatch):
    H, y, truth = synthetic_problem()
    data = {"true_params": np.array([1.0 / truth[0], truth[1] / truth[0], truth[2] / truth[0]])}
    monkeypatch.setattr(stage11b, "build_affine_window", lambda *args: (H, y, 1))
    _, profiles, _ = analyze_window("synthetic", 0, data, {}, 70, 5, "true")
    assert all(profile["state_source"] == "true" and profile["truth_in_region_95"] for profile in profiles)


def test_stage11c_report_conclusions_require_full_paired_results(monkeypatch, tmp_path):
    paired = {
        "state_source": "paired", "scope": "overall",
        "true_minus_estimated_truth_inclusion_1d": 0.5,
        "true_minus_estimated_truth_inclusion_2d": 0.5,
        "true_minus_estimated_residual_rms_median": -0.1,
        "true_minus_estimated_physical_condition_median": 0.0,
        "true_minus_estimated_conditional_lambda_information_ratio_median": 0.2,
        "true_minus_estimated_v1_angle_median_deg": 2.0,
        "true_minus_estimated_v12_principal_angle_median_deg": 3.0,
        "true_minus_estimated_v1_stability_concentration": 0.1,
        "true_minus_estimated_v12_stability_concentration": 0.1,
    }
    smoke_manifest = {"mode": "smoke", "state_source": "paired", "runs": 1, "windows": 3}
    full_manifest = {"mode": "full", "state_source": "paired", "runs": 24, "windows": 710}
    assert paired_full_conclusion(smoke_manifest, [paired]) is None
    assert paired_full_conclusion(full_manifest, [paired]) is not None
    monkeypatch.setattr(stage11b, "OUTPUT_STAGE11C", tmp_path)
    write_stage11c_report(smoke_manifest, [paired], [])
    assert "Required conclusions" not in (tmp_path / "stage11c_report.md").read_text()
