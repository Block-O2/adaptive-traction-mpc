import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]

import run_stage11e_block_coverage_calibration as stage11e


def synthetic_problem():
    rng = np.random.default_rng(1105)
    H = rng.normal(size=(2 * stage11e.WINDOW_TRANSITIONS, 3))
    theta = np.array([0.82, 370.0, 14.0])
    transition_noise = rng.normal(scale=0.02, size=(stage11e.WINDOW_TRANSITIONS, 2))
    transition_noise[1:] += 0.45 * transition_noise[:-1]
    y = H @ theta + transition_noise.reshape(-1)
    return H, y, theta


def synthetic_profile(lambda_wls, truth_lambda):
    return {
        "true_lambda_at_minimum": str(lambda_wls),
        "true_truth_lambda": str(truth_lambda),
        "true_truth_in_region_95": "True",
        "true_lambda_region_lower_95": str(lambda_wls - 0.02),
        "true_lambda_region_upper_95": str(lambda_wls + 0.02),
        "true_lambda_region_width_95": "0.04",
        "true_lambda_relative_width": str(0.04 / abs(lambda_wls)),
    }


def paired_profile_rows(identities):
    return [
        {
            "condition": condition,
            "seed": seed,
            "window_start": start,
            "window_end": end,
            "profile": profile,
        }
        for condition, seed, start, end in identities
        for profile in sorted(stage11e.PROFILE_NAMES)
    ]


def diagnostic_rows(identities):
    return [
        {
            "condition": condition,
            "seed": seed,
            "window_start": start,
            "window_end": end,
            "transitions": stage11e.WINDOW_TRANSITIONS,
            "state_source": "true",
            "weighted_ls_lambda_matches_stage11c": True,
        }
        for condition, seed, start, end in identities
    ]


def test_exact_stage11c_stage11d_window_alignment_and_provenance(
    monkeypatch, tmp_path
):
    identities = [("clean", 101, 1, 70), ("clean", 101, 11, 80)]
    stage11c_manifest = {
        "actual_windows": len(identities),
        "conditions": ["clean"],
        "seeds": [101],
        "mechanical_status": "valid_full_run",
        "mechanical_completeness": True,
    }
    stage11d_manifest = {
        "actual_windows": len(identities),
        "mechanical_status": "valid_full_run",
        "mechanical_completeness": True,
        "stage11c_input_hashes_match": True,
    }
    profiles = stage11e.validate_and_index_stage11c_profiles(
        paired_profile_rows(identities), stage11c_manifest
    )
    diagnostics = stage11e.validate_and_index_stage11d_diagnostics(
        diagnostic_rows(identities), stage11d_manifest
    )
    stage11e.validate_source_alignment(profiles, diagnostics)
    diagnostics.pop(identities[-1])
    with pytest.raises(RuntimeError, match="not exactly aligned"):
        stage11e.validate_source_alignment(profiles, diagnostics)

    replay = tmp_path / "replay.csv"
    config = tmp_path / "config.yaml"
    stage11b = tmp_path / "stage11b.py"
    stage11d = tmp_path / "stage11d.py"
    manifest_path = tmp_path / "stage11c_manifest.json"
    profile_path = tmp_path / "stage11c_profiles.csv"
    for path, content in (
        (replay, "replay"),
        (config, "config"),
        (stage11b, "stage11b"),
        (stage11d, "stage11d"),
        (manifest_path, "{}"),
        (profile_path, "profiles"),
    ):
        path.write_text(content)
    stage11c_manifest.update(
        {
            "replay_sha256": stage11e.sha256_file(replay),
            "config_sha256": stage11e.sha256_file(config),
            "script_sha256": stage11e.sha256_file(stage11b),
        }
    )
    stage11d_manifest.update(
        {
            "replay_sha256": stage11e.sha256_file(replay),
            "config_sha256": stage11e.sha256_file(config),
            "script_sha256": stage11e.sha256_file(stage11d),
            "stage11c_manifest_sha256": stage11e.sha256_file(manifest_path),
            "stage11c_profile_sha256": stage11e.sha256_file(profile_path),
        }
    )
    monkeypatch.setattr(stage11e, "DEFAULT_REPLAY", replay)
    monkeypatch.setattr(stage11e, "DEFAULT_CONFIG", config)
    monkeypatch.setattr(stage11e, "STAGE11B_RUNNER", stage11b)
    monkeypatch.setattr(stage11e, "STAGE11D_RUNNER", stage11d)
    monkeypatch.setattr(stage11e, "STAGE11C_MANIFEST", manifest_path)
    monkeypatch.setattr(stage11e, "STAGE11C_PROFILES", profile_path)
    checks = stage11e.source_provenance_checks(
        stage11c_manifest, stage11d_manifest
    )
    assert all(checks.values())
    stage11d.write_text("changed")
    assert not stage11e.source_provenance_checks(
        stage11c_manifest, stage11d_manifest
    )["stage11d_runner_matches_manifest"]


def test_transition_scores_keep_the_two_channels_paired():
    H = np.zeros((2 * stage11e.WINDOW_TRANSITIONS, 3))
    residual = np.zeros(2 * stage11e.WINDOW_TRANSITIONS)
    H[0] = [1.0, 2.0, 3.0]
    H[1] = [10.0, 20.0, 30.0]
    H[2] = [4.0, 5.0, 6.0]
    H[3] = [40.0, 50.0, 60.0]
    residual[:4] = [2.0, 3.0, 5.0, 7.0]
    scores = stage11e.transition_score_contributions(H, residual)
    assert scores.shape == (stage11e.WINDOW_TRANSITIONS, 3)
    assert np.array_equal(scores[0], H[0] * 2.0 + H[1] * 3.0)
    assert np.array_equal(scores[1], H[2] * 5.0 + H[3] * 7.0)
    assert np.count_nonzero(scores[2:]) == 0


def test_bootstrap_is_deterministic_and_has_exactly_70_transitions():
    H, y, _ = synthetic_problem()
    first = stage11e.calibrated_lambda_interval(H, y, 123456)
    second = stage11e.calibrated_lambda_interval(H, y, 123456)
    assert first["half_width"] == second["half_width"]
    assert np.array_equal(
        first["bootstrap_indices"], second["bootstrap_indices"]
    )
    assert first["bootstrap_indices"].shape == (
        stage11e.BOOTSTRAP_REPLICATES,
        stage11e.WINDOW_TRANSITIONS,
    )
    assert np.all(first["bootstrap_indices"] >= 0)
    assert np.all(first["bootstrap_indices"] < stage11e.WINDOW_TRANSITIONS)


def test_wls_point_estimate_remains_unchanged():
    H, y, theta = synthetic_problem()
    Hw, yw = stage11e.weighted_design(H, y, stage11e.ROW_SQRT_WEIGHTS)
    optimum = np.linalg.lstsq(Hw, yw, rcond=None)[0]
    profile = synthetic_profile(optimum[0], theta[0])
    stage11d_row = {"lambda_ls_optimum": str(optimum[0])}
    row = stage11e.compute_window_calibration(
        ("clean", 101, 1, 70),
        H,
        y,
        theta[0],
        profile,
        stage11d_row,
    )
    assert row["lambda_wls_point_estimate"] == optimum[0]
    assert row["stage11c_point_estimate_abs_error"] == 0.0
    assert row["stage11d_point_estimate_abs_error"] == 0.0
    assert row["point_estimate_changed"] is False


def test_truth_lambda_cannot_change_the_calibrated_interval():
    H, y, _ = synthetic_problem()
    first = stage11e.calibrated_lambda_interval(H, y, 9001)
    first_bounds = (first["lower"], first["upper"], first["half_width"])
    assert stage11e.evaluate_lambda_truth(first, first["lambda_wls"])
    assert not stage11e.evaluate_lambda_truth(
        first, first["upper"] + first["half_width"] + 1.0
    )
    second = stage11e.calibrated_lambda_interval(H, y, 9001)
    second_bounds = (second["lower"], second["upper"], second["half_width"])
    assert first_bounds == second_bounds


def test_block_length_and_replicate_count_are_fixed():
    assert stage11e.BLOCK_LENGTH == 10
    assert stage11e.BOOTSTRAP_REPLICATES == 2000
    assert stage11e.WINDOW_TRANSITIONS == 70
    with pytest.raises(SystemExit):
        stage11e.parse_args(["--smoke", "--block-length", "5"])
    with pytest.raises(SystemExit):
        stage11e.parse_args(["--smoke", "--replicates", "10"])


def test_smoke_output_is_local_and_non_authoritative(tmp_path):
    args = stage11e.parse_args(["--smoke"])
    assert args.output_root == stage11e.OUTPUT_SMOKE
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
        "baseline_lambda_truth_coverage": 0.5,
        "calibrated_lambda_truth_coverage": 0.75,
        "absolute_coverage_gain": 0.25,
        "baseline_relative_width_median": 0.1,
        "calibrated_relative_width_median": 0.2,
        "width_inflation_factor_median": 2.0,
        "point_estimate_changed_fraction": 0.0,
    }
    stage11e.write_report(tmp_path, manifest, [summary])
    report = (tmp_path / "stage11e_report.md").read_text()
    assert "local smoke artifact" in report
    assert "non-authoritative" in report
    assert "does not select any category" in report
    assert "PASS/FAIL/INCONCLUSIVE" in report


def test_smoke_selects_one_run_and_at_most_three_windows():
    identities = [
        ("clean", 101, 1 + 10 * index, 70 + 10 * index)
        for index in range(5)
    ] + [("clean", 102, 1, 70)]
    selected = stage11e.choose_identities(identities, "smoke")
    assert len(selected) == 3
    assert len({identity[:2] for identity in selected}) == 1


def test_full_rejects_nonempty_output_before_reading_sources(
    monkeypatch, tmp_path
):
    output = tmp_path / "formal"
    output.mkdir()
    (output / "preserve.txt").write_text("keep")
    args = stage11e.parse_args(
        ["--full", "--output-root", str(output)]
    )
    monkeypatch.setattr(
        stage11e,
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
        stage11e, "STAGE11C_MANIFEST", tmp_path / "must_not_be_read.json"
    )
    with pytest.raises(SystemExit, match="non-empty formal output"):
        stage11e.run(args)
    assert (output / "preserve.txt").read_text() == "keep"


def test_mechanical_checks_require_zero_point_estimate_changes():
    identity = ("clean", 101, 1, 70)
    row = {
        "condition": identity[0],
        "seed": identity[1],
        "window_start": identity[2],
        "window_end": identity[3],
        "transitions": 70,
        "state_source": "true",
        "paired_transition_score_rows": 70,
        "paired_transition_score_columns": 3,
        "bootstrap_block_length": 10,
        "bootstrap_replicates": 2000,
        "bootstrap_transitions_per_replicate": 70,
        "point_estimate_changed": False,
    }
    provenance = {"all_source_checks": True}
    checks = stage11e.exact_identity_checks(
        "smoke",
        {("clean", 101)},
        {identity},
        [row],
        provenance,
        source_alignment_complete=True,
        git_clean_for_formal=False,
        required_outputs_complete=True,
    )
    assert all(checks.values())
    changed = dict(row, point_estimate_changed=True)
    checks = stage11e.exact_identity_checks(
        "smoke",
        {("clean", 101)},
        {identity},
        [changed],
        provenance,
        source_alignment_complete=True,
        git_clean_for_formal=False,
        required_outputs_complete=True,
    )
    assert not checks["wls_point_estimate_unchanged"]


def test_window_seed_is_identity_specific_and_repeatable():
    identity = ("clean", 101, 1, 70)
    assert (
        stage11e.deterministic_window_seed(identity)
        == stage11e.deterministic_window_seed(identity)
    )
    assert (
        stage11e.deterministic_window_seed(identity)
        != stage11e.deterministic_window_seed(("clean", 101, 11, 80))
    )
