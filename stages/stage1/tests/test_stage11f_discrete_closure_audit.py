import ast
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]

import run_stage11f_discrete_closure_audit as stage11f


def synthetic_data():
    states = np.column_stack(
        [
            np.arange(71, dtype=float),
            2.0 * np.arange(71, dtype=float),
            0.35 + 0.01 * np.arange(71, dtype=float),
            -0.2 * np.arange(71, dtype=float),
        ]
    )
    actions = np.column_stack(
        [
            np.arange(71, dtype=float) * 0.1,
            -np.arange(71, dtype=float) * 0.05,
        ]
    )
    return {
        "true": states,
        "action": actions,
        "true_params": np.array([1.2, 450.0, 18.0]),
        "nominal_params": np.array([0.95, 360.0, 12.0]),
    }


def true_params():
    return {
        "dt": 0.01,
        "m": 1.2,
        "k": 450.0,
        "b_r": 18.0,
        "F_tan_max": 35.0,
        "F_rad_max": 20.0,
    }


def baseline_row():
    return {
        "truth_radial_weighted_residual_rms": 0.4,
        "truth_angular_weighted_residual_rms": 0.2,
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
        for profile in ("lambda_1d", "lambda_kappa_2d")
    ]


def diagnostic_rows(identities):
    return [
        {
            "condition": condition,
            "seed": seed,
            "window_start": start,
            "window_end": end,
            "transitions": 70,
            "state_source": "true",
            "weighted_ls_lambda_matches_stage11c": True,
        }
        for condition, seed, start, end in identities
    ]


def test_exact_stage11c_stage11d_window_identity_alignment():
    identities = [("clean", 101, 1, 70), ("clean", 101, 11, 80)]
    stage11c_manifest = {
        "actual_windows": 2,
        "conditions": ["clean"],
        "seeds": [101],
    }
    stage11d_manifest = {"actual_windows": 2}
    profiles = stage11f.validate_and_index_stage11c_profiles(
        paired_profile_rows(identities), stage11c_manifest
    )
    diagnostics = stage11f.validate_and_index_stage11d_diagnostics(
        diagnostic_rows(identities), stage11d_manifest
    )
    stage11f.validate_source_alignment(profiles, diagnostics)
    diagnostics.pop(identities[-1])
    with pytest.raises(RuntimeError, match="not exactly aligned"):
        stage11f.validate_source_alignment(profiles, diagnostics)


def test_exact_stage11c_stage11d_stage11e_provenance(
    monkeypatch, tmp_path
):
    paths = {
        name: tmp_path / name
        for name in (
            "replay",
            "config",
            "stage11b",
            "stage11c_manifest",
            "stage11c_profiles",
            "stage11d_runner",
            "stage11d_manifest",
            "stage11d_diagnostics",
        )
    }
    for name, path in paths.items():
        path.write_text(name)
    monkeypatch.setattr(stage11f, "DEFAULT_REPLAY", paths["replay"])
    monkeypatch.setattr(stage11f, "DEFAULT_CONFIG", paths["config"])
    monkeypatch.setattr(stage11f, "STAGE11B_RUNNER", paths["stage11b"])
    monkeypatch.setattr(
        stage11f, "STAGE11C_MANIFEST", paths["stage11c_manifest"]
    )
    monkeypatch.setattr(
        stage11f, "STAGE11C_PROFILES", paths["stage11c_profiles"]
    )
    monkeypatch.setattr(
        stage11f, "STAGE11D_RUNNER", paths["stage11d_runner"]
    )
    monkeypatch.setattr(
        stage11f, "STAGE11D_MANIFEST", paths["stage11d_manifest"]
    )
    monkeypatch.setattr(
        stage11f, "STAGE11D_DIAGNOSTICS", paths["stage11d_diagnostics"]
    )
    replay_hash = stage11f.sha256_file(paths["replay"])
    config_hash = stage11f.sha256_file(paths["config"])
    stage11c = {
        "mechanical_status": "valid_full_run",
        "mechanical_completeness": True,
        "replay_sha256": replay_hash,
        "config_sha256": config_hash,
        "script_sha256": stage11f.sha256_file(paths["stage11b"]),
    }
    stage11d = {
        "mechanical_status": "valid_full_run",
        "mechanical_completeness": True,
        "replay_sha256": replay_hash,
        "config_sha256": config_hash,
        "script_sha256": stage11f.sha256_file(paths["stage11d_runner"]),
        "stage11c_manifest_sha256": stage11f.sha256_file(
            paths["stage11c_manifest"]
        ),
        "stage11c_profile_sha256": stage11f.sha256_file(
            paths["stage11c_profiles"]
        ),
    }
    stage11e = {
        "mechanical_status": "valid_full_run",
        "mechanical_completeness": True,
        "actual_runs": 24,
        "actual_windows": 710,
        "replay_sha256": replay_hash,
        "config_sha256": config_hash,
        "stage11d_manifest_sha256": stage11f.sha256_file(
            paths["stage11d_manifest"]
        ),
        "stage11d_diagnostics_sha256": stage11f.sha256_file(
            paths["stage11d_diagnostics"]
        ),
        "stage11d_runner_sha256": stage11f.sha256_file(
            paths["stage11d_runner"]
        ),
    }
    checks = stage11f.source_provenance_checks(stage11c, stage11d, stage11e)
    assert all(checks.values())
    paths["stage11d_diagnostics"].write_text("changed")
    checks = stage11f.source_provenance_checks(stage11c, stage11d, stage11e)
    assert not checks["stage11d_diagnostics_match_stage11e"]


def test_reuses_environment_replay_transition_routine(monkeypatch):
    captured = {}

    def sentinel(state, action, dt, params):
        captured["args"] = (state, action, dt, params)
        return np.asarray(state) + 1.0

    monkeypatch.setattr(stage11f.spring2d_env, "step_dynamics", sentinel)
    state = np.arange(4, dtype=float)
    action = np.array([1.0, 2.0])
    params = true_params()
    result = stage11f.replay_generation_transition(
        state, action, params["dt"], params
    )
    assert np.array_equal(result, state + 1.0)
    assert captured["args"][0] is state
    assert captured["args"][1] is action
    assert captured["args"][2] == params["dt"]
    assert captured["args"][3] is params


def test_correct_xt_ut_to_next_alignment_and_true_parameters():
    data = synthetic_data()
    params = true_params()
    calls = []

    def aligned_transition(state, action, dt, supplied_params):
        index = len(calls) + 1
        assert np.array_equal(state, data["true"][index - 1])
        assert np.array_equal(action, data["action"][index])
        assert dt == params["dt"]
        assert supplied_params is params
        calls.append(index)
        return data["true"][index]

    row = stage11f.compute_window_closure(
        ("clean", 101, 1, 70),
        data,
        params,
        baseline_row(),
        transition_fn=aligned_transition,
    )
    assert calls == list(range(1, 71))
    assert row["transitions"] == 70
    assert row["transition_alignment"] == "true[step-1],action[step]->true[step]"
    assert row["true_parameter_source"] == "stage9j_condition_true_params"
    assert row["true_m"] == params["m"]
    assert row["true_k"] == params["k"]
    assert row["true_b_r"] == params["b_r"]
    assert row["discrete_weighted_residual_rms"] == 0.0
    assert row["discrete_to_affine_weighted_rms_ratio"] == 0.0


def test_radial_angular_order_and_weights_match_stage11d():
    residuals = np.zeros((70, 4))
    residuals[:, 1] = 4.0
    residuals[:, 3] = 2.0
    channels = stage11f.acceleration_equivalent_channels(residuals, 0.5)
    assert np.array_equal(channels[:, 0], np.full(70, 4.0))
    assert np.array_equal(channels[:, 1], np.full(70, 8.0))
    weighted = stage11f.weighted_closure_channels(channels)
    assert np.array_equal(
        weighted[:, 0], channels[:, 0] * stage11f.ROW_SQRT_WEIGHTS[0]
    )
    assert np.array_equal(
        weighted[:, 1], channels[:, 1] * stage11f.ROW_SQRT_WEIGHTS[1]
    )
    assert tuple(stage11f.CHANNEL_NAMES) == ("radial", "angular")
    assert np.array_equal(stage11f.ROW_SQRT_WEIGHTS, [0.6, 0.25])


def test_compute_path_has_no_fit_optimizer_estimator_or_identifier_call():
    tree = ast.parse(inspect.getsource(stage11f.compute_window_closure))
    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_names.add(node.func.attr)
    forbidden = {
        "fit",
        "minimize",
        "least_squares",
        "lstsq",
        "optimize",
        "update",
        "predict",
        "add_transition",
        "add_measurement",
    }
    assert called_names.isdisjoint(forbidden)


def test_results_are_deterministic():
    data = synthetic_data()
    params = true_params()

    def exact_transition(state, action, dt, supplied_params):
        del action, dt, supplied_params
        index = int(round(state[0])) + 1
        return data["true"][index]

    first = stage11f.compute_window_closure(
        ("clean", 101, 1, 70),
        data,
        params,
        baseline_row(),
        transition_fn=exact_transition,
    )
    second = stage11f.compute_window_closure(
        ("clean", 101, 1, 70),
        data,
        params,
        baseline_row(),
        transition_fn=exact_transition,
    )
    assert first == second
    for name in stage11f.STATE_NAMES:
        assert len(json.loads(first[f"{name}_residual_trajectory_json"])) == 70


def test_smoke_output_is_local_non_authoritative_and_neutral(tmp_path):
    args = stage11f.parse_args(["--smoke"])
    assert args.output_root == stage11f.OUTPUT_SMOKE
    manifest = {
        "execution_mode": "smoke",
        "evidence_level": "smoke",
        "mechanical_status": "valid_smoke",
        "actual_runs": 1,
        "actual_windows": 3,
        "transition_function": stage11f.REPLAY_TRANSITION_QUALNAME,
    }
    summary = {
        "condition": "clean",
        "n_windows": 3,
        "discrete_weighted_residual_rms_median": 0.0,
        "affine_weighted_residual_rms_median": 0.1,
        "discrete_to_affine_weighted_rms_ratio_median": 0.0,
        "discrete_to_affine_weighted_rms_ratio_p95": 0.0,
        "all_recorded_actions_within_limits": True,
    }
    stage11f.write_report(tmp_path, manifest, [summary])
    report = (tmp_path / "stage11f_report.md").read_text()
    assert "local smoke artifact" in report
    assert "non-authoritative" in report
    assert "does not select a category" in report
    assert "PASS/FAIL/INCONCLUSIVE" in report


def test_smoke_selects_one_run_and_at_most_three_windows():
    identities = [
        ("clean", 101, 1 + 10 * index, 70 + 10 * index)
        for index in range(5)
    ] + [("clean", 102, 1, 70)]
    selected = stage11f.choose_identities(identities, "smoke")
    assert len(selected) == 3
    assert len({identity[:2] for identity in selected}) == 1


def test_exact_transition_object_is_currently_shared():
    checks = stage11f.transition_reuse_checks()
    assert all(checks.values())
