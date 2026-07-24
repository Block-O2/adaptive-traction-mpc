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
    DEFAULT_PROFILE_GRID_SIZE,
    OUTPUT_STAGE11C_FORMAL,
    OUTPUT_STAGE11C_SMOKE,
    adaptive_profile_lambda,
    adaptive_profile_lambda_kappa,
    aggregate_directions,
    analyze_window,
    build_run_manifest,
    build_affine_window,
    mechanical_status_for_run,
    pair_profile_rows,
    pair_window_rows,
    parse_cli_args,
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


def paired_report_rows():
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
    source_common = {
        "scope": "overall",
        "summary_kind": "state_source",
        "practical_identifiability": "not established",
        "profile_truth_inclusion_1d_fraction": 0.5,
        "profile_truth_inclusion_2d_fraction": 0.1,
        "cross_condition_stable_1d_subspace": False,
        "cross_condition_stable_2d_subspace": False,
    }
    return [
        {**source_common, "state_source": "estimated"},
        {**source_common, "state_source": "true"},
        paired,
    ]


def test_execution_mode_must_be_selected_explicitly():
    with pytest.raises(SystemExit):
        parse_cli_args([])


@pytest.mark.parametrize(
    "arguments",
    [
        ["--full", "--conditions", "clean"],
        ["--full", "--max-runs", "1"],
        ["--full", "--max-windows", "3"],
        ["--full", "--profile-grid-size", "5"],
    ],
)
def test_full_rejects_partial_options(arguments):
    with pytest.raises(SystemExit):
        parse_cli_args(arguments)


def test_full_requires_paired_state_source():
    with pytest.raises(SystemExit):
        parse_cli_args(["--full", "--state-source", "true"])


def test_default_output_roots_are_separated():
    _, smoke = parse_cli_args(["--smoke"])
    _, full = parse_cli_args(["--full"])
    assert smoke.output_root == OUTPUT_STAGE11C_SMOKE
    assert full.output_root == OUTPUT_STAGE11C_FORMAL


def test_report_only_uses_specified_output_root(tmp_path):
    _, report = parse_cli_args(
        ["--report-only", "--output-root", str(tmp_path)]
    )
    assert report.output_root == tmp_path.resolve()


def test_manifest_contains_required_provenance_fields(tmp_path):
    manifest, mechanical = build_run_manifest(
        "smoke",
        tmp_path,
        "paired",
        ["clean"],
        [101],
        1,
        3,
        5,
        "abc123",
        True,
        "python runner.py --smoke",
    )
    required = {
        "experiment_id", "execution_mode", "git_commit",
        "git_dirty_before_run", "exact_command", "script_path",
        "script_sha256", "replay_path", "replay_sha256", "config_path",
        "config_sha256", "state_source", "conditions", "seeds",
        "expected_runs", "actual_runs", "expected_windows",
        "actual_windows", "window_transitions", "profile_grid_size",
        "output_root", "mechanical_completeness", "mechanical_status",
    }
    assert required <= set(manifest)
    assert manifest["mechanical_status"] == "valid_smoke"
    assert mechanical["mechanical_status"] == "valid_smoke"


def test_incomplete_full_matrix_is_mechanically_invalid():
    status, checks = mechanical_status_for_run(
        "full",
        "paired",
        list(stage11b.CONDITIONS),
        list(stage11b.SEEDS),
        23,
        709,
        24,
        710,
        DEFAULT_PROFILE_GRID_SIZE,
        False,
    )
    assert status == "invalid_incomplete_run"
    assert not checks["runs_complete"]
    assert not checks["windows_complete"]


def test_full_rejects_dirty_worktree_before_loading_replay(monkeypatch):
    monkeypatch.setattr(stage11b, "git_state_before_run", lambda: ("abc123", True))
    with pytest.raises(SystemExit):
        stage11b.main(["--full"])


def test_smoke_and_full_reports_do_not_make_scientific_judgments(tmp_path):
    rows = paired_report_rows()
    smoke_root = tmp_path / "smoke"
    full_root = tmp_path / "full"
    smoke_manifest = {
        "execution_mode": "smoke", "state_source": "paired",
        "actual_runs": 1, "actual_windows": 3,
        "mechanical_status": "valid_smoke",
    }
    full_manifest = {
        "execution_mode": "full", "state_source": "paired",
        "actual_runs": 24, "actual_windows": 710,
        "mechanical_status": "valid_full_run",
    }
    write_stage11c_report(smoke_manifest, rows, [], smoke_root)
    write_stage11c_report(full_manifest, rows, [], full_root)
    smoke = (smoke_root / "stage11c_report.md").read_text()
    full = (full_root / "stage11c_report.md").read_text()
    assert "implementation validation only" in smoke
    assert "Required conclusions" not in smoke
    assert "pending review against the approved Experiment Spec" in full
    assert "Required conclusions" not in full
    assert "dominant limitation" not in full
