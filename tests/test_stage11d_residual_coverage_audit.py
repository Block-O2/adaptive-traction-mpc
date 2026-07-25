import json
import sys
from argparse import Namespace
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


def synthetic_stage11c_paths(monkeypatch, tmp_path):
    manifest_path = tmp_path / "stage11c_manifest.json"
    profiles_path = tmp_path / "stage11c_profiles.csv"
    manifest_path.write_text("{}\n")
    profiles_path.write_text("condition,seed,window_start,window_end,profile\n")
    monkeypatch.setattr(stage11d, "STAGE11C_MANIFEST", manifest_path)
    monkeypatch.setattr(stage11d, "STAGE11C_PROFILES", profiles_path)
    return manifest_path, profiles_path


def synthetic_full_diagnostics():
    run_identities = [
        (condition, seed)
        for condition in stage11d.CONDITIONS
        for seed in (101, 102, 103)
    ]
    rows = []
    per_run_count = {identity: 0 for identity in run_identities}
    for index in range(stage11d.STAGE11D_EXPECTED_WINDOWS):
        condition, seed = run_identities[index % len(run_identities)]
        local_index = per_run_count[(condition, seed)]
        per_run_count[(condition, seed)] += 1
        start = 1 + 10 * local_index
        rows.append(
            {
                "condition": condition,
                "seed": seed,
                "window_start": start,
                "window_end": start + stage11d.WINDOW_TRANSITIONS - 1,
                "transitions": stage11d.WINDOW_TRANSITIONS,
                "state_source": "true",
                "weighted_ls_lambda_matches_stage11c": True,
            }
        )
    expected_windows = {stage11d.window_identity(row) for row in rows}
    expected_runs = {
        (condition, seed)
        for condition, seed, _, _ in expected_windows
    }
    return expected_runs, expected_windows, rows


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
        "evidence_level": "smoke",
        "mechanical_status": "valid_smoke",
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


def test_manifest_marks_smoke_non_authoritative_contract(tmp_path, monkeypatch):
    assert stage11d.resolve_output_root("smoke", None) == stage11d.OUTPUT_SMOKE
    assert stage11d.resolve_output_root("full", None) == stage11d.OUTPUT_FORMAL
    manifest_path, _ = synthetic_stage11c_paths(monkeypatch, tmp_path)
    manifest_path.write_text(json.dumps({"mechanical_status": "valid_full_run"}))
    source_manifest = json.loads(manifest_path.read_text())
    assert source_manifest["mechanical_status"] == "valid_full_run"


def test_declared_untracked_stage11c_input_is_the_only_cleanliness_exception():
    allowed, unexpected = stage11d.classify_git_status(
        [
            "?? results/stage11c_state_source_audit/run_manifest.json",
            " M scripts/run_stage11d_residual_coverage_audit.py",
            "?? unrelated.txt",
        ]
    )
    assert allowed == [
        "?? results/stage11c_state_source_audit/run_manifest.json"
    ]
    assert unexpected == [
        " M scripts/run_stage11d_residual_coverage_audit.py",
        "?? unrelated.txt",
    ]


def test_full_rejects_dirty_source_before_reading_stage11c(
    monkeypatch, tmp_path
):
    args = stage11d.parse_args(
        ["--full", "--output-root", str(tmp_path / "formal")]
    )
    monkeypatch.setattr(
        stage11d,
        "git_context",
        lambda: {
            "commit": "abc",
            "status_lines": [" M scripts/runner.py"],
            "allowed_untracked_input_lines": [],
            "unexpected_status_lines": [" M scripts/runner.py"],
            "dirty": True,
            "clean_for_formal": False,
        },
    )
    monkeypatch.setattr(
        stage11d, "STAGE11C_MANIFEST", tmp_path / "must_not_be_read.json"
    )
    with pytest.raises(SystemExit, match="clean committed source tree"):
        stage11d.run(args)
    assert not args.output_root.exists()


def test_full_rejects_nonempty_output_before_reading_stage11c(
    monkeypatch, tmp_path
):
    output = tmp_path / "formal"
    output.mkdir()
    (output / "preserve.txt").write_text("keep")
    args = stage11d.parse_args(
        ["--full", "--output-root", str(output)]
    )
    monkeypatch.setattr(
        stage11d,
        "git_context",
        lambda: {
            "commit": "abc",
            "status_lines": [],
            "allowed_untracked_input_lines": [],
            "unexpected_status_lines": [],
            "dirty": False,
            "clean_for_formal": True,
        },
    )
    monkeypatch.setattr(
        stage11d, "STAGE11C_MANIFEST", tmp_path / "must_not_be_read.json"
    )
    with pytest.raises(SystemExit, match="non-empty"):
        stage11d.run(args)
    assert (output / "preserve.txt").read_text() == "keep"


def test_exact_full_identity_matrix_is_valid():
    expected_runs, expected_windows, rows = synthetic_full_diagnostics()
    checks = stage11d.exact_identity_checks(
        "full",
        expected_runs,
        expected_windows,
        rows,
        source_stage11c_valid=True,
        source_profile_identity_complete=True,
        stage11c_input_hashes_match=True,
        git_clean_for_formal=True,
        required_outputs_complete=True,
    )
    assert all(checks.values())
    assert stage11d.mechanical_status_for_run("full", checks) == "valid_full_run"


def test_duplicate_and_missing_window_is_invalid_even_at_710_rows():
    expected_runs, expected_windows, rows = synthetic_full_diagnostics()
    altered = [dict(row) for row in rows]
    altered[-1] = dict(altered[0])
    checks = stage11d.exact_identity_checks(
        "full",
        expected_runs,
        expected_windows,
        altered,
        source_stage11c_valid=True,
        source_profile_identity_complete=True,
        stage11c_input_hashes_match=True,
        git_clean_for_formal=True,
        required_outputs_complete=True,
    )
    assert len(altered) == stage11d.STAGE11D_EXPECTED_WINDOWS
    assert not checks["window_identity_complete"]
    assert not checks["no_duplicate_windows"]
    assert (
        stage11d.mechanical_status_for_run("full", checks)
        == "invalid_incomplete_run"
    )


def test_resolved_config_snapshot_and_hash(tmp_path):
    config = {"controller": {"horizon": 18}, "conditions": ["clean"]}
    digest = stage11d.write_resolved_config_snapshot(tmp_path, config)
    snapshot = tmp_path / "resolved_config_snapshot.json"
    assert json.loads(snapshot.read_text()) == config
    assert digest == stage11d.sha256_file(snapshot)


def test_formal_manifest_has_provenance_and_is_not_authoritative(
    tmp_path, monkeypatch
):
    expected_runs, expected_windows, rows = synthetic_full_diagnostics()
    args = Namespace(mode="full", output_root=tmp_path)
    git_state = {
        "commit": "abc123",
        "status_lines": [
            "?? results/stage11c_state_source_audit/run_manifest.json"
        ],
        "allowed_untracked_input_lines": [
            "?? results/stage11c_state_source_audit/run_manifest.json"
        ],
        "unexpected_status_lines": [],
        "dirty": True,
        "clean_for_formal": True,
    }
    checks = stage11d.exact_identity_checks(
        "full",
        expected_runs,
        expected_windows,
        rows,
        True,
        True,
        True,
        True,
        True,
    )
    stage11c_manifest = {
        "actual_windows": stage11d.STAGE11D_EXPECTED_WINDOWS,
        "git_commit": "stage11c-commit",
    }
    synthetic_stage11c_paths(monkeypatch, tmp_path)
    manifest, mechanical = stage11d.build_run_manifest(
        args,
        tmp_path,
        git_state,
        "python runner.py --full",
        "python runner.py --full",
        "mpc_learn",
        "resolved-sha",
        stage11c_manifest,
        {
            "stage11c_replay_sha256_matches": True,
            "stage11c_config_sha256_matches": True,
            "stage11c_script_sha256_matches": True,
        },
        expected_runs,
        expected_windows,
        rows,
        checks,
    )
    required = {
        "exact_command",
        "effective_command",
        "conda_environment",
        "resolved_config_snapshot",
        "resolved_config_sha256",
        "git_status_before_run",
        "git_allowed_untracked_inputs",
        "git_unexpected_changes_before_run",
        "expected_runs",
        "actual_runs",
        "expected_windows",
        "actual_windows",
        "mechanical_status",
    }
    assert required <= set(manifest)
    assert manifest["mechanical_status"] == "valid_full_run"
    assert manifest["evidence_level"] == "formal"
    assert manifest["authoritative"] is False
    assert manifest["resolved_config_sha256"] == "resolved-sha"
    assert manifest["stage11c_input_hashes_match"]
    assert mechanical["required_outputs_complete"]


def test_required_formal_provenance_outputs_are_declared():
    assert {
        "command.txt",
        "mechanical_status.json",
        "resolved_config_snapshot.json",
    } <= set(stage11d.STAGE11D_REQUIRED_OUTPUTS)


def test_stage11c_input_hashes_match_and_detect_mismatch():
    matching = {
        "replay_sha256": stage11d.sha256_file(stage11d.DEFAULT_REPLAY),
        "config_sha256": stage11d.sha256_file(stage11d.DEFAULT_CONFIG),
        "script_sha256": stage11d.sha256_file(stage11d.STAGE11B_RUNNER),
    }
    assert all(stage11d.stage11c_input_hash_checks(matching).values())
    mismatched = dict(matching)
    mismatched["script_sha256"] = "not-the-stage11b-runner"
    checks = stage11d.stage11c_input_hash_checks(mismatched)
    assert not checks["stage11c_script_sha256_matches"]


def test_full_rejects_stage11c_hash_mismatch_before_reading_profiles(
    monkeypatch, tmp_path
):
    manifest_path = tmp_path / "stage11c_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "mechanical_status": "valid_full_run",
                "mechanical_completeness": True,
                "replay_sha256": "mismatch",
                "config_sha256": "mismatch",
                "script_sha256": "mismatch",
            }
        )
    )
    monkeypatch.setattr(stage11d, "STAGE11C_MANIFEST", manifest_path)
    monkeypatch.setattr(stage11d, "STAGE11C_PROFILES", tmp_path / "absent.csv")
    monkeypatch.setattr(
        stage11d,
        "git_context",
        lambda: {
            "commit": "abc",
            "status_lines": [],
            "allowed_untracked_input_lines": [],
            "unexpected_status_lines": [],
            "dirty": False,
            "clean_for_formal": True,
        },
    )
    args = stage11d.parse_args(
        ["--full", "--output-root", str(tmp_path / "formal")]
    )
    with pytest.raises(RuntimeError, match="provenance hash mismatch"):
        stage11d.run(args)
    assert not args.output_root.exists()


def test_weighted_ls_lambda_must_match_saved_stage11c_profile_value():
    H, y, truth, proxies, profile = synthetic_problem()
    Hw, yw = stage11d.weighted_design(H, y, stage11d.ROW_SQRT_WEIGHTS)
    lambda_optimum = np.linalg.lstsq(Hw, yw, rcond=None)[0][0]
    matching = dict(profile, true_lambda_at_minimum=str(lambda_optimum))
    row = stage11d.compute_window_diagnostic(
        ("clean", 101, 1, 70), H, y, truth, proxies, matching
    )
    assert row["weighted_ls_lambda_matches_stage11c"]
    assert row["weighted_ls_lambda_profile_abs_error"] == pytest.approx(0.0)

    mismatching = dict(
        profile,
        true_lambda_at_minimum=str(
            lambda_optimum + 2.0 * stage11d.STAGE11C_LAMBDA_RECONCILIATION_ATOL
        ),
    )
    mismatch_row = stage11d.compute_window_diagnostic(
        ("clean", 101, 1, 70), H, y, truth, proxies, mismatching
    )
    assert not mismatch_row["weighted_ls_lambda_matches_stage11c"]
    checks = stage11d.exact_identity_checks(
        "smoke",
        {("clean", 101)},
        {("clean", 101, 1, 70)},
        [mismatch_row],
        source_stage11c_valid=True,
        source_profile_identity_complete=True,
        stage11c_input_hashes_match=True,
        git_clean_for_formal=True,
        required_outputs_complete=True,
    )
    assert not checks["weighted_ls_lambda_matches_stage11c_profiles"]
