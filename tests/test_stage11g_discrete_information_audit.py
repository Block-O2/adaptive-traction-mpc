import ast
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]

import run_stage11b_parameter_subspace_audit as stage11b
import run_stage11g_discrete_information_audit as stage11g


def true_params():
    return {
        "dt": 0.01,
        "m": 1.2,
        "k": 450.0,
        "b_r": 18.0,
        "g": 9.81,
    }


def synthetic_data():
    steps = np.arange(71, dtype=float)
    return {
        "true": np.column_stack(
            [
                0.1 + 0.001 * steps,
                0.2 + 0.002 * steps,
                0.35 + 0.0005 * steps,
                -0.1 + 0.0015 * steps,
            ]
        ),
        "action": np.column_stack(
            [1.0 + 0.01 * steps, 0.2 - 0.001 * steps]
        ),
    }


def synthetic_transition(state, action, dt, params):
    result = np.asarray(state, dtype=float).copy()
    result[3] += dt * (
        0.2 / params["m"] + 0.01 * params["k"] + 0.03 * params["b_r"]
        + 0.1 * action[1]
    )
    result[1] += dt * (
        0.4 / params["m"] - 0.005 * params["k"] + 0.02 * params["b_r"]
        + 0.1 * action[0]
    )
    return result


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


def closure_rows(identities):
    return [
        {
            "condition": condition,
            "seed": seed,
            "window_start": start,
            "window_end": end,
            "transitions": 70,
            "state_source": "true",
            "discrete_weighted_residual_rms": 0.0,
            "discrete_to_affine_weighted_rms_ratio": 0.0,
        }
        for condition, seed, start, end in identities
    ]


def test_theta_physical_parameter_mapping_round_trip():
    params = true_params()
    theta = stage11g.physical_to_theta(params)
    assert np.allclose(theta, [1 / 1.2, 450 / 1.2, 18 / 1.2])
    reconstructed = stage11g.theta_to_physical_params(theta, params)
    assert reconstructed is not params
    assert reconstructed["m"] == pytest.approx(params["m"])
    assert reconstructed["k"] == pytest.approx(params["k"])
    assert reconstructed["b_r"] == pytest.approx(params["b_r"])
    assert reconstructed["dt"] == params["dt"]


def test_affine_discrete_window_and_provenance_alignment(
    monkeypatch, tmp_path
):
    identities = [("clean", 101, 1, 70), ("clean", 101, 11, 80)]
    stage11c_manifest = {
        "actual_windows": 2,
        "conditions": ["clean"],
        "seeds": [101],
    }
    stage11d_manifest = {"actual_windows": 2}
    stage11f_manifest = {"actual_windows": 2}
    profiles = stage11g.validate_and_index_stage11c_profiles(
        paired_profile_rows(identities), stage11c_manifest
    )
    diagnostics = stage11g.validate_and_index_stage11d_diagnostics(
        diagnostic_rows(identities), stage11d_manifest
    )
    closure = stage11g.validate_and_index_stage11f_metrics(
        closure_rows(identities), stage11f_manifest
    )
    stage11g.validate_source_alignment(profiles, diagnostics, closure)
    closure.pop(identities[-1])
    with pytest.raises(RuntimeError, match="not exactly aligned"):
        stage11g.validate_source_alignment(profiles, diagnostics, closure)

    names = (
        "replay",
        "config",
        "stage11b",
        "stage11c_manifest",
        "stage11c_profiles",
        "stage11d_manifest",
        "stage11d_diagnostics",
        "stage11f_runner",
        "env_source",
        "dynamics_source",
    )
    paths = {name: tmp_path / name for name in names}
    for name, path in paths.items():
        path.write_text(name)
    for attribute, key in (
        ("DEFAULT_REPLAY", "replay"),
        ("DEFAULT_CONFIG", "config"),
        ("STAGE11B_RUNNER", "stage11b"),
        ("STAGE11C_MANIFEST", "stage11c_manifest"),
        ("STAGE11C_PROFILES", "stage11c_profiles"),
        ("STAGE11D_MANIFEST", "stage11d_manifest"),
        ("STAGE11D_DIAGNOSTICS", "stage11d_diagnostics"),
        ("STAGE11F_RUNNER", "stage11f_runner"),
        ("SPRING2D_ENV_SOURCE", "env_source"),
        ("SPRING2D_DYNAMICS_SOURCE", "dynamics_source"),
    ):
        monkeypatch.setattr(stage11g, attribute, paths[key])
    replay_hash = stage11g.sha256_file(paths["replay"])
    config_hash = stage11g.sha256_file(paths["config"])
    stage11c = {
        "mechanical_status": "valid_full_run",
        "mechanical_completeness": True,
        "replay_sha256": replay_hash,
        "config_sha256": config_hash,
        "script_sha256": stage11g.sha256_file(paths["stage11b"]),
    }
    stage11d = {
        "mechanical_status": "valid_full_run",
        "mechanical_completeness": True,
        "replay_sha256": replay_hash,
        "config_sha256": config_hash,
        "stage11c_manifest_sha256": stage11g.sha256_file(
            paths["stage11c_manifest"]
        ),
        "stage11c_profile_sha256": stage11g.sha256_file(
            paths["stage11c_profiles"]
        ),
    }
    stage11f = {
        "mechanical_status": "valid_full_run",
        "mechanical_completeness": True,
        "actual_runs": 24,
        "actual_windows": 710,
        "replay_sha256": replay_hash,
        "config_sha256": config_hash,
        "script_sha256": stage11g.sha256_file(paths["stage11f_runner"]),
        "stage11c_manifest_sha256": stage11g.sha256_file(
            paths["stage11c_manifest"]
        ),
        "stage11c_profiles_sha256": stage11g.sha256_file(
            paths["stage11c_profiles"]
        ),
        "stage11d_manifest_sha256": stage11g.sha256_file(
            paths["stage11d_manifest"]
        ),
        "stage11d_diagnostics_sha256": stage11g.sha256_file(
            paths["stage11d_diagnostics"]
        ),
        "spring2d_env_source_sha256": stage11g.sha256_file(
            paths["env_source"]
        ),
        "spring2d_dynamics_source_sha256": stage11g.sha256_file(
            paths["dynamics_source"]
        ),
    }
    checks = stage11g.source_provenance_checks(
        stage11c, stage11d, stage11f
    )
    assert all(checks.values())
    paths["stage11f_runner"].write_text("changed")
    assert not stage11g.source_provenance_checks(
        stage11c, stage11d, stage11f
    )["stage11f_runner_matches_manifest"]


def test_exact_step_dynamics_reuse(monkeypatch):
    calls = []

    def sentinel(state, action, dt, params):
        calls.append((state, action, dt, params))
        return synthetic_transition(state, action, dt, params)

    monkeypatch.setattr(stage11g, "replay_generation_transition", sentinel)
    params = true_params()
    theta = stage11g.physical_to_theta(params)
    state = synthetic_data()["true"][0]
    action = synthetic_data()["action"][1]
    output = stage11g.exact_discrete_output(state, action, theta, params)
    assert len(calls) == 1
    assert calls[0][0] is state
    assert calls[0][1] is action
    assert output.shape == (2,)


def test_70_transitions_and_140_by_3_jacobian_shape():
    primary, half, steps = stage11g.build_discrete_window_jacobians(
        synthetic_data(),
        1,
        70,
        true_params(),
        transition_fn=synthetic_transition,
    )
    assert primary.shape == (140, 3)
    assert half.shape == (140, 3)
    assert steps.shape == (3,)


def test_radial_angular_order_and_weights_are_unchanged():
    params = true_params()
    theta = stage11g.physical_to_theta(params)
    state = synthetic_data()["true"][0]
    action = synthetic_data()["action"][1]
    output = stage11g.exact_discrete_output(
        state, action, theta, params, transition_fn=synthetic_transition
    )
    predicted = synthetic_transition(state, action, params["dt"], params)
    assert output[0] == pytest.approx(
        (predicted[3] - state[3]) / params["dt"]
    )
    assert output[1] == pytest.approx(
        (predicted[1] - state[1]) / params["dt"]
    )
    assert tuple(stage11g.CHANNEL_NAMES) == ("radial", "angular")
    assert np.array_equal(stage11g.ROW_SQRT_WEIGHTS, [0.6, 0.25])
    assert np.array_equal(stage11g.PHYSICAL_SCALE, [1.0, 450.0, 20.0])


def test_central_differences_are_deterministic():
    params = true_params()
    theta = stage11g.physical_to_theta(params)
    state = synthetic_data()["true"][0]
    action = synthetic_data()["action"][1]
    first, steps_first = stage11g.central_difference_transition_jacobian(
        state,
        action,
        theta,
        params,
        transition_fn=synthetic_transition,
    )
    second, steps_second = stage11g.central_difference_transition_jacobian(
        state,
        action,
        theta,
        params,
        transition_fn=synthetic_transition,
    )
    assert np.array_equal(first, second)
    assert np.array_equal(steps_first, steps_second)
    assert np.array_equal(
        steps_first,
        stage11g.PRIMARY_RELATIVE_STEP * np.maximum(np.abs(theta), 1.0),
    )


def test_half_step_stability_detection():
    primary = np.ones((140, 3))
    stable = stage11g.half_step_stability(primary, primary.copy())
    assert stable["stable"]
    assert stable["maximum_column_relative_discrepancy"] == 0.0
    unstable_half = primary.copy()
    unstable_half[:, 2] *= 0.5
    unstable = stage11g.half_step_stability(primary, unstable_half)
    assert not unstable["stable"]
    assert (
        unstable["maximum_column_relative_discrepancy"]
        > stage11g.HALF_STEP_MAX_COLUMN_RELATIVE_DISCREPANCY
    )


def test_changing_replay_next_state_does_not_change_jacobian():
    data = synthetic_data()
    modified = {key: value.copy() for key, value in data.items()}
    modified["true"][70] += np.array([99.0, 88.0, 77.0, 66.0])
    first, first_half, _ = stage11g.build_discrete_window_jacobians(
        data,
        1,
        70,
        true_params(),
        transition_fn=synthetic_transition,
    )
    second, second_half, _ = stage11g.build_discrete_window_jacobians(
        modified,
        1,
        70,
        true_params(),
        transition_fn=synthetic_transition,
    )
    assert np.array_equal(first, second)
    assert np.array_equal(first_half, second_half)


def test_stage11b_svd_metric_function_is_reused():
    assert stage11g.svd_metrics is stage11b.svd_metrics
    matrix = np.arange(420, dtype=float).reshape(140, 3) + np.eye(140, 3)
    assert stage11g.svd_metrics(matrix, y=None)["rank"] == stage11b.svd_metrics(
        matrix, y=None
    )["rank"]


def test_no_fit_optimizer_estimator_identifier_or_controller_call():
    source = "\n".join(
        [
            inspect.getsource(stage11g.compute_window_information),
            inspect.getsource(stage11g.build_discrete_window_jacobians),
            inspect.getsource(
                stage11g.central_difference_transition_jacobian
            ),
        ]
    )
    tree = ast.parse(source)
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
        "act",
    }
    assert called_names.isdisjoint(forbidden)


def test_smoke_output_is_local_neutral_and_non_authoritative(tmp_path):
    args = stage11g.parse_args(["--smoke"])
    assert args.output_root == stage11g.OUTPUT_SMOKE
    manifest = {
        "execution_mode": "smoke",
        "evidence_level": "smoke",
        "mechanical_status": "valid_smoke",
        "actual_runs": 1,
        "actual_windows": 3,
        "transition_function": stage11g.REPLAY_TRANSITION_QUALNAME,
    }
    summary = {
        "condition": "clean",
        "n_windows": 3,
        "exact_rank3_fraction": 1.0,
        "affine_rank3_fraction": 1.0,
        "exact_conditional_lambda_information_abs_median": 1.0,
        "affine_conditional_lambda_information_abs_median": 2.0,
        "exact_to_affine_conditional_lambda_information_ratio_median": 0.5,
        "exact_affine_physical_weak_direction_angle_deg_median": 2.0,
        "half_step_max_column_relative_discrepancy_p95": 1e-8,
    }
    stage11g.write_report(tmp_path, manifest, [summary])
    report = (tmp_path / "stage11g_report.md").read_text()
    assert "local smoke artifact" in report
    assert "non-authoritative" in report
    assert "does not select a category" in report
    assert "PASS/FAIL/INCONCLUSIVE" in report
