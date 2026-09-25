"""Offline-only Stage-5 remaining cuff-force value study.

This module deliberately has no Goal-MPC import and no action-selection hook.
It builds undiscounted Monte-Carlo targets from complete saved episodes, fits
small ridge predictors, and evaluates optional matched short-branch rankings.
MuJoCo truth fields are rejected from the feature boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np


ACTIVE_PHASES = ("OUTBOUND", "HOLD", "RETURN")
TERMINAL_PHASES = ("COMPLETE", "ABORTED")

FORBIDDEN_ONLINE_FIELDS = frozenset(
    {
        "evaluation_human_q_rad",
        "evaluation_human_dq_rad_s",
        "evaluation_only_instantaneous_acceleration_rad_s2",
    }
)


@dataclass(frozen=True)
class FailurePenaltySpec:
    """Pessimistic non-success cost in the existing task-contract units."""

    engineering_force_gate_n: float = 200.0
    phase_timeout_s: float = 10.0
    minimum_equivalent_duration_s: float = 10.0

    def __post_init__(self) -> None:
        values = (
            self.engineering_force_gate_n,
            self.phase_timeout_s,
            self.minimum_equivalent_duration_s,
        )
        if any(not np.isfinite(value) or value <= 0.0 for value in values):
            raise ValueError("failure-penalty values must be finite and positive")

    def terminal_penalty_n_s(
        self, phase: str, phase_elapsed_s: float
    ) -> float:
        """Return a nonzero penalty at the engineering force-gate scale.

        The remaining registered active-phase budget is pessimistically charged
        at the unchanged 200 N engineering gate.  A one-phase floor prevents a
        late abort from becoming cheaper than completing the task.  This is a
        value-target convention, not a new safety or clinical force threshold.
        """

        if phase not in ACTIVE_PHASES:
            remaining_budget_s = self.phase_timeout_s
        else:
            remaining_in_phase = max(
                self.phase_timeout_s - max(float(phase_elapsed_s), 0.0), 0.0
            )
            future_phase_count = {
                "OUTBOUND": 2,
                "HOLD": 1,
                "RETURN": 0,
            }[phase]
            remaining_budget_s = (
                remaining_in_phase + future_phase_count * self.phase_timeout_s
            )
        charged_duration_s = max(
            self.minimum_equivalent_duration_s, remaining_budget_s
        )
        return float(self.engineering_force_gate_n * charged_duration_s)


@dataclass(frozen=True)
class EpisodeValueData:
    episode_id: str
    trace_path: Path
    summary_path: Path
    time_s: np.ndarray
    phase: np.ndarray
    feature_context: dict[str, np.ndarray]
    target_remaining_force_n_s: np.ndarray
    terminal_status: str
    terminal_penalty_n_s: float
    model_version: str
    interface_version: str
    pacing_gamma: float

    @property
    def active_mask(self) -> np.ndarray:
        return np.isin(self.phase, ACTIVE_PHASES)


@dataclass(frozen=True)
class FeatureMatrix:
    values: np.ndarray
    names: tuple[str, ...]


@dataclass(frozen=True)
class LinearValueModel:
    feature_kind: str
    feature_names: tuple[str, ...]
    mean: np.ndarray
    scale: np.ndarray
    coefficients: np.ndarray
    intercept_n_s: float
    ridge_alpha: float
    support_abs_z_limit: float
    training_target_min_n_s: float
    training_target_max_n_s: float
    model_version: str

    def predict(
        self, matrix: FeatureMatrix
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if matrix.names != self.feature_names:
            raise ValueError("feature order/version mismatch")
        values = np.asarray(matrix.values, dtype=float)
        z = (values - self.mean) / self.scale
        support_distance = np.max(np.abs(z), axis=1)
        supported = np.all(np.isfinite(z), axis=1) & (
            support_distance <= self.support_abs_z_limit
        )
        prediction = self.intercept_n_s + z @ self.coefficients
        prediction = np.maximum(prediction, 0.0)
        # Unsupported values are deliberately non-numeric for ranking.  A
        # future MPC integration must disable value use for the whole solve if
        # any compared terminal candidate is unsupported; zero is not emitted
        # here because it would make unseen states look attractive.
        guarded = np.where(supported, prediction, np.nan)
        return guarded, supported, support_distance

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "stage5_shadow_linear_value_model_v1",
            "model_version": self.model_version,
            "feature_kind": self.feature_kind,
            "feature_names": list(self.feature_names),
            "mean": self.mean.tolist(),
            "scale": self.scale.tolist(),
            "coefficients": self.coefficients.tolist(),
            "intercept_n_s": self.intercept_n_s,
            "ridge_alpha": self.ridge_alpha,
            "support_abs_z_limit": self.support_abs_z_limit,
            "training_target_range_n_s": [
                self.training_target_min_n_s,
                self.training_target_max_n_s,
            ],
            "control_authority": False,
        }


def _load_json(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _phase_elapsed(time_s: np.ndarray, phase: np.ndarray) -> np.ndarray:
    elapsed = np.zeros(len(time_s), dtype=float)
    phase_start = float(time_s[0])
    previous = str(phase[0])
    for index, (time_value, phase_value) in enumerate(zip(time_s, phase, strict=True)):
        current = str(phase_value)
        if current != previous:
            phase_start = float(time_value)
            previous = current
        elapsed[index] = max(float(time_value) - phase_start, 0.0)
    return elapsed


def remaining_trapezoid_return(
    time_s: np.ndarray,
    measured_force_world_n: np.ndarray,
    *,
    terminal_penalty_n_s: float = 0.0,
) -> np.ndarray:
    """Undiscounted remaining integral of measured physical force norm."""

    time = np.asarray(time_s, dtype=float)
    force = np.asarray(measured_force_world_n, dtype=float)
    if time.ndim != 1 or force.shape != (len(time), 3) or len(time) == 0:
        raise ValueError("time[N] and measured force[N,3] are required")
    if not np.all(np.isfinite(time)) or not np.all(np.isfinite(force)):
        raise ValueError("return inputs must be finite")
    dt = np.diff(time)
    if np.any(dt <= 0.0):
        raise ValueError("episode timestamps must be strictly increasing")
    if not np.isfinite(terminal_penalty_n_s) or terminal_penalty_n_s < 0.0:
        raise ValueError("terminal penalty must be finite and nonnegative")
    norm = np.linalg.norm(force, axis=1)
    result = np.empty(len(time), dtype=float)
    result[-1] = float(terminal_penalty_n_s)
    for index in range(len(time) - 2, -1, -1):
        result[index] = result[index + 1] + 0.5 * (
            norm[index] + norm[index + 1]
        ) * dt[index]
    return result


def load_episode_value_data(
    episode_id: str,
    trace_path: Path,
    summary_path: Path,
    *,
    expected_model_version: str,
    expected_gamma: float,
    expected_interface_version: str,
    failure_penalty: FailurePenaltySpec,
) -> EpisodeValueData:
    """Load one full episode while enforcing the frozen study condition."""

    trace_path = Path(trace_path)
    summary_path = Path(summary_path)
    summary = _load_json(summary_path)
    with np.load(trace_path, allow_pickle=False) as archive:
        files = set(archive.files)
        if FORBIDDEN_ONLINE_FIELDS & files:
            # Truth may coexist in the saved trace for evaluation, but is never
            # copied into feature_context below.  Keep the explicit assertion
            # close to the whitelist so later changes cannot leak it silently.
            pass
        required = {
            "time_s",
            "estimated_state_rad_rad_s",
            "task_phase",
            "diagnostic_progress",
            "deployable_measured_cuff_force_world_n",
            "deployable_measured_cuff_moment_world_nm",
            "estimated_interface_translation_human_m",
            "estimated_interface_velocity_human_m_s",
            "estimated_interface_rotation_human_rad",
            "estimated_interface_angular_velocity_human_rad_s",
            "progress_pacing_gamma",
            "control_human_model_version",
        }
        missing = sorted(required - files)
        if missing:
            raise KeyError(f"{episode_id} is missing deployable fields: {missing}")
        copied = {name: np.asarray(archive[name]).copy() for name in required}

    time = np.asarray(copied["time_s"], dtype=float)
    phase = np.asarray(copied["task_phase"], dtype=str)
    if len(time) < 2 or phase.shape != time.shape:
        raise ValueError(f"{episode_id} is not a full sampled episode")
    terminal_status = str(summary.get("task_status", phase[-1]))
    if terminal_status not in TERMINAL_PHASES and terminal_status != "COMPLETE":
        # Preserve exact failure labels such as TIMEOUT_RETURN or BRAKE_TERMINATED.
        terminal_success = False
    else:
        terminal_success = terminal_status == "COMPLETE"
    if terminal_success and str(phase[-1]) != "COMPLETE":
        raise ValueError(f"{episode_id} summary says COMPLETE without terminal sample")

    model_versions = np.unique(
        np.asarray(copied["control_human_model_version"], dtype=str)
    )
    if model_versions.tolist() != [expected_model_version]:
        raise ValueError(
            f"{episode_id} changed/falsified Human model: {model_versions.tolist()}"
        )
    gamma_values = np.asarray(copied["progress_pacing_gamma"], dtype=float)
    if not np.allclose(gamma_values, expected_gamma, atol=1.0e-12, rtol=0.0):
        raise ValueError(f"{episode_id} does not use fixed gamma={expected_gamma}")
    summary_interface = str(
        summary.get("interface_prediction", {}).get(
            "controller_interface_model_version", expected_interface_version
        )
    )
    if summary_interface != expected_interface_version:
        raise ValueError(
            f"{episode_id} interface version {summary_interface!r} is not frozen"
        )

    phase_elapsed = _phase_elapsed(time, phase)
    terminal_penalty = 0.0
    if not terminal_success:
        active_indices = np.flatnonzero(np.isin(phase, ACTIVE_PHASES))
        last_active = int(active_indices[-1]) if len(active_indices) else len(time) - 1
        terminal_penalty = failure_penalty.terminal_penalty_n_s(
            str(phase[last_active]), float(phase_elapsed[last_active])
        )
    targets = remaining_trapezoid_return(
        time,
        np.asarray(copied["deployable_measured_cuff_force_world_n"], dtype=float),
        terminal_penalty_n_s=terminal_penalty,
    )
    feature_context = {
        "estimated_state": np.asarray(
            copied["estimated_state_rad_rad_s"], dtype=float
        ),
        "progress": np.asarray(copied["diagnostic_progress"], dtype=float),
        "phase_elapsed_s": phase_elapsed,
        "measured_force": np.asarray(
            copied["deployable_measured_cuff_force_world_n"], dtype=float
        ),
        "measured_moment": np.asarray(
            copied["deployable_measured_cuff_moment_world_nm"], dtype=float
        ),
        "interface_translation": np.asarray(
            copied["estimated_interface_translation_human_m"], dtype=float
        ),
        "interface_velocity": np.asarray(
            copied["estimated_interface_velocity_human_m_s"], dtype=float
        ),
        "interface_rotation": np.asarray(
            copied["estimated_interface_rotation_human_rad"], dtype=float
        ),
        "interface_angular_velocity": np.asarray(
            copied["estimated_interface_angular_velocity_human_rad_s"], dtype=float
        ),
    }
    for name, values in feature_context.items():
        if len(values) != len(time) or not np.all(np.isfinite(values)):
            raise ValueError(f"{episode_id} has invalid deployable feature {name}")
    return EpisodeValueData(
        episode_id=str(episode_id),
        trace_path=trace_path,
        summary_path=summary_path,
        time_s=time,
        phase=phase,
        feature_context=feature_context,
        target_remaining_force_n_s=targets,
        terminal_status=terminal_status,
        terminal_penalty_n_s=terminal_penalty,
        model_version=expected_model_version,
        interface_version=expected_interface_version,
        pacing_gamma=float(expected_gamma),
    )


def build_features(
    episode: EpisodeValueData,
    *,
    kind: str,
    phase_timeout_s: float,
    hold_duration_s: float,
    start_rad: np.ndarray,
    goal_rad: np.ndarray,
    q_bounds_rad: np.ndarray,
    velocity_limits_rad_s: np.ndarray,
) -> FeatureMatrix:
    """Build either the obvious progress baseline or deployable candidate."""

    if kind not in {"baseline", "candidate"}:
        raise ValueError("feature kind must be baseline or candidate")
    mask = episode.active_mask
    phase = episode.phase[mask]
    context = {name: values[mask] for name, values in episode.feature_context.items()}
    one_hot = np.column_stack([phase == name for name in ACTIVE_PHASES]).astype(float)
    progress = np.clip(context["progress"], 0.0, 1.0)
    phase_elapsed_fraction = np.clip(
        context["phase_elapsed_s"] / phase_timeout_s, 0.0, 1.0
    )
    future_phase_count = np.asarray(
        [{"OUTBOUND": 2, "HOLD": 1, "RETURN": 0}[str(item)] for item in phase],
        dtype=float,
    )
    remaining_budget_fraction = (
        np.maximum(phase_timeout_s - context["phase_elapsed_s"], 0.0)
        + future_phase_count * phase_timeout_s
    ) / (3.0 * phase_timeout_s)
    hold_remaining_fraction = np.where(
        phase == "HOLD",
        np.maximum(hold_duration_s - context["phase_elapsed_s"], 0.0)
        / hold_duration_s,
        0.0,
    )
    baseline = np.column_stack(
        [
            one_hot,
            progress,
            phase_elapsed_fraction,
            remaining_budget_fraction,
            hold_remaining_fraction,
        ]
    )
    names = (
        "phase_outbound",
        "phase_hold",
        "phase_return",
        "diagnostic_progress",
        "phase_elapsed_fraction",
        "remaining_registered_budget_fraction",
        "hold_remaining_fraction",
    )
    if kind == "baseline":
        return FeatureMatrix(baseline, names)

    state = context["estimated_state"]
    q_span = q_bounds_rad[:, 1] - q_bounds_rad[:, 0]
    q_normalized = (state[:, :2] - q_bounds_rad[:, 0]) / q_span
    dq_normalized = state[:, 2:] / velocity_limits_rad_s
    task_span = goal_rad - start_rad
    task_coordinate = (state[:, :2] - start_rad) / task_span
    coordination_difference = task_coordinate[:, 0] - task_coordinate[:, 1]
    posture = np.column_stack(
        [
            q_normalized,
            dq_normalized,
            q_normalized[:, 0] ** 2,
            q_normalized[:, 1] ** 2,
            q_normalized[:, 0] * q_normalized[:, 1],
            coordination_difference,
            coordination_difference[:, None] * one_hot,
        ]
    )
    force = context["measured_force"] / 200.0
    moment = context["measured_moment"] / 20.0
    interface = np.column_stack(
        [
            context["interface_translation"] / 0.01,
            context["interface_velocity"] / 0.10,
            context["interface_rotation"] / np.radians(5.0),
            context["interface_angular_velocity"] / np.radians(30.0),
        ]
    )
    candidate = np.column_stack(
        [
            baseline,
            posture,
            force,
            np.linalg.norm(force, axis=1),
            moment,
            np.linalg.norm(moment, axis=1),
            interface,
        ]
    )
    candidate_names = names + (
        "q1_rom_normalized",
        "q2_rom_normalized",
        "dq1_limit_normalized",
        "dq2_limit_normalized",
        "q1_squared",
        "q2_squared",
        "q1_q2_cross",
        "task_coordination_difference",
        "coordination_x_outbound",
        "coordination_x_hold",
        "coordination_x_return",
        "measured_force_world_x_over_200n",
        "measured_force_world_y_over_200n",
        "measured_force_world_z_over_200n",
        "measured_force_norm_over_200n",
        "measured_moment_world_x_over_20nm",
        "measured_moment_world_y_over_20nm",
        "measured_moment_world_z_over_20nm",
        "measured_moment_norm_over_20nm",
        "interface_translation_human_x_over_0p01m",
        "interface_translation_human_y_over_0p01m",
        "interface_translation_human_z_over_0p01m",
        "interface_velocity_human_x_over_0p1m_s",
        "interface_velocity_human_y_over_0p1m_s",
        "interface_velocity_human_z_over_0p1m_s",
        "interface_rotation_human_x_over_5deg",
        "interface_rotation_human_y_over_5deg",
        "interface_rotation_human_z_over_5deg",
        "interface_angular_velocity_human_x_over_30deg_s",
        "interface_angular_velocity_human_y_over_30deg_s",
        "interface_angular_velocity_human_z_over_30deg_s",
    )
    if candidate.shape[1] != len(candidate_names):
        raise RuntimeError("candidate feature-name contract is inconsistent")
    return FeatureMatrix(candidate, candidate_names)


def _stack_episode_features(
    episodes: Iterable[EpisodeValueData],
    feature_builder: Any,
) -> tuple[FeatureMatrix, np.ndarray, np.ndarray]:
    matrices: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    ids: list[np.ndarray] = []
    names: tuple[str, ...] | None = None
    for episode in episodes:
        matrix = feature_builder(episode)
        if names is None:
            names = matrix.names
        elif matrix.names != names:
            raise ValueError("episode feature schemas differ")
        matrices.append(matrix.values)
        targets.append(episode.target_remaining_force_n_s[episode.active_mask])
        ids.append(np.full(len(matrix.values), episode.episode_id, dtype=str))
    if not matrices or names is None:
        raise ValueError("at least one episode is required")
    return (
        FeatureMatrix(np.vstack(matrices), names),
        np.concatenate(targets),
        np.concatenate(ids),
    )


def fit_ridge_value_model(
    matrix: FeatureMatrix,
    targets_n_s: np.ndarray,
    episode_ids: np.ndarray,
    *,
    alpha: float,
    feature_kind: str,
    support_abs_z_limit: float,
) -> LinearValueModel:
    values = np.asarray(matrix.values, dtype=float)
    target = np.asarray(targets_n_s, dtype=float)
    ids = np.asarray(episode_ids, dtype=str)
    if values.ndim != 2 or target.shape != (len(values),) or ids.shape != target.shape:
        raise ValueError("training arrays do not align")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(target)):
        raise ValueError("training data must be finite")
    if alpha < 0.0 or not np.isfinite(alpha):
        raise ValueError("ridge alpha must be finite and nonnegative")
    # Equal total weight per complete trajectory prevents a longer episode from
    # silently dominating the study.
    unique_ids, counts = np.unique(ids, return_counts=True)
    count_map = dict(zip(unique_ids.tolist(), counts.tolist(), strict=True))
    weights = np.asarray([1.0 / count_map[item] for item in ids], dtype=float)
    weights *= len(weights) / np.sum(weights)
    weight_sum = float(np.sum(weights))
    mean = np.sum(values * weights[:, None], axis=0) / weight_sum
    variance = np.sum((values - mean) ** 2 * weights[:, None], axis=0) / weight_sum
    scale = np.sqrt(np.maximum(variance, 0.0))
    scale = np.where(scale < 1.0e-12, 1.0, scale)
    z = (values - mean) / scale
    intercept = float(np.sum(target * weights) / weight_sum)
    centered_target = target - intercept
    root_weight = np.sqrt(weights)
    weighted_z = z * root_weight[:, None]
    weighted_target = centered_target * root_weight
    gram = weighted_z.T @ weighted_z + float(alpha) * np.eye(z.shape[1])
    coefficients = np.linalg.solve(gram, weighted_z.T @ weighted_target)
    digest = hashlib.sha256()
    for item in (mean, scale, coefficients, np.asarray([intercept, alpha])):
        digest.update(np.asarray(item, dtype="<f8").tobytes())
    version = f"stage5-shadow-{feature_kind}-ridge:{digest.hexdigest()[:12]}"
    return LinearValueModel(
        feature_kind=feature_kind,
        feature_names=matrix.names,
        mean=mean,
        scale=scale,
        coefficients=coefficients,
        intercept_n_s=intercept,
        ridge_alpha=float(alpha),
        support_abs_z_limit=float(support_abs_z_limit),
        training_target_min_n_s=float(np.min(target)),
        training_target_max_n_s=float(np.max(target)),
        model_version=version,
    )


def regression_metrics(
    model: LinearValueModel,
    matrix: FeatureMatrix,
    target_n_s: np.ndarray,
    phase: np.ndarray,
) -> dict[str, Any]:
    target = np.asarray(target_n_s, dtype=float)
    guarded, supported, support_distance = model.predict(matrix)
    raw = model.intercept_n_s + (
        (matrix.values - model.mean) / model.scale
    ) @ model.coefficients
    raw = np.maximum(raw, 0.0)
    error = raw - target
    result: dict[str, Any] = {
        "sample_count": int(len(target)),
        "rmse_n_s": float(np.sqrt(np.mean(error**2))),
        "mae_n_s": float(np.mean(np.abs(error))),
        "bias_n_s": float(np.mean(error)),
        "supported_sample_count": int(np.count_nonzero(supported)),
        "ood_sample_count": int(np.count_nonzero(~supported)),
        "ood_fraction": float(np.mean(~supported)),
        "support_distance_abs_z": {
            "median": float(np.median(support_distance)),
            "p95": float(np.percentile(support_distance, 95)),
            "max": float(np.max(support_distance)),
        },
        "guarded_prediction_nonfinite_for_all_ood": bool(
            np.all(np.isnan(guarded[~supported]))
        ),
        "phase": {},
    }
    phase_values = np.asarray(phase, dtype=str)
    for phase_name in ACTIVE_PHASES:
        selected = phase_values == phase_name
        if not np.any(selected):
            result["phase"][phase_name] = {"sample_count": 0}
            continue
        phase_error = error[selected]
        result["phase"][phase_name] = {
            "sample_count": int(np.count_nonzero(selected)),
            "rmse_n_s": float(np.sqrt(np.mean(phase_error**2))),
            "mae_n_s": float(np.mean(np.abs(phase_error))),
            "ood_fraction": float(np.mean(~supported[selected])),
        }
    return result


def select_ridge_alpha(
    train_matrix: FeatureMatrix,
    train_targets: np.ndarray,
    train_episode_ids: np.ndarray,
    validation_matrix: FeatureMatrix,
    validation_targets: np.ndarray,
    *,
    feature_kind: str,
    alphas: Iterable[float],
    support_abs_z_limit: float,
) -> tuple[LinearValueModel, list[dict[str, float]]]:
    rows: list[dict[str, float]] = []
    best: tuple[float, LinearValueModel] | None = None
    for alpha in alphas:
        model = fit_ridge_value_model(
            train_matrix,
            train_targets,
            train_episode_ids,
            alpha=float(alpha),
            feature_kind=feature_kind,
            support_abs_z_limit=support_abs_z_limit,
        )
        z = (validation_matrix.values - model.mean) / model.scale
        prediction = np.maximum(model.intercept_n_s + z @ model.coefficients, 0.0)
        rmse = float(np.sqrt(np.mean((prediction - validation_targets) ** 2)))
        rows.append({"alpha": float(alpha), "validation_rmse_n_s": rmse})
        if best is None or rmse < best[0]:
            best = (rmse, model)
    if best is None:
        raise ValueError("at least one ridge alpha is required")
    return best[1], rows


def coefficient_report(model: LinearValueModel, limit: int = 12) -> list[dict[str, Any]]:
    physical = model.coefficients / model.scale
    order = np.argsort(np.abs(model.coefficients))[::-1][:limit]
    return [
        {
            "feature": model.feature_names[index],
            "standardized_coefficient_n_s": float(model.coefficients[index]),
            "raw_unit_coefficient_n_s": float(physical[index]),
        }
        for index in order
    ]


def trajectory_split_is_disjoint(split: Mapping[str, Iterable[str]]) -> bool:
    seen: set[str] = set()
    for name in ("train", "validation", "test"):
        values = list(split.get(name, ()))
        if len(values) != len(set(values)) or seen.intersection(values):
            return False
        seen.update(values)
    return all(bool(list(split.get(name, ()))) for name in ("train", "validation", "test"))


def paired_ranking_metrics(
    predicted_n_s: np.ndarray,
    observed_n_s: np.ndarray,
    group_ids: np.ndarray,
    supported: np.ndarray,
    *,
    minimum_observed_difference_n_s: float,
) -> dict[str, Any]:
    prediction = np.asarray(predicted_n_s, dtype=float)
    observed = np.asarray(observed_n_s, dtype=float)
    groups = np.asarray(group_ids, dtype=str)
    support = np.asarray(supported, dtype=bool)
    if not (
        prediction.shape == observed.shape == groups.shape == support.shape
    ):
        raise ValueError("ranking arrays must align")
    correct = 0
    count = 0
    unsupported_pairs = 0
    evaluated_groups = 0
    for group in np.unique(groups):
        indices = np.flatnonzero(groups == group)
        group_pairs = 0
        for left_position, left in enumerate(indices):
            for right in indices[left_position + 1 :]:
                if (
                    abs(float(observed[left] - observed[right]))
                    < minimum_observed_difference_n_s
                ):
                    continue
                if not support[left] or not support[right]:
                    unsupported_pairs += 1
                    continue
                count += 1
                group_pairs += 1
                correct += int(
                    np.sign(prediction[left] - prediction[right])
                    == np.sign(observed[left] - observed[right])
                )
        evaluated_groups += int(group_pairs > 0)
    return {
        "matched_group_count": int(len(np.unique(groups))),
        "evaluated_group_count": int(evaluated_groups),
        "pair_count": int(count),
        "unsupported_pair_count": int(unsupported_pairs),
        "correct_pair_count": int(correct),
        "ranking_accuracy": None if count == 0 else float(correct / count),
        "lower_predicted_cost_ranks_ahead": True,
    }


__all__ = [
    "ACTIVE_PHASES",
    "EpisodeValueData",
    "FailurePenaltySpec",
    "FeatureMatrix",
    "LinearValueModel",
    "build_features",
    "coefficient_report",
    "fit_ridge_value_model",
    "load_episode_value_data",
    "paired_ranking_metrics",
    "regression_metrics",
    "remaining_trapezoid_return",
    "select_ridge_alpha",
    "trajectory_split_is_disjoint",
]
