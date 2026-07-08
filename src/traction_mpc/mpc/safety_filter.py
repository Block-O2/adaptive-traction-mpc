"""Runtime one-step action safety filters for Spring2D MPC."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from traction_mpc.models.spring2d_dynamics import step_dynamics
from traction_mpc.mpc.constraints import Spring2DMPCConstraints


@dataclass(frozen=True)
class SafetyFilterResult:
    action_mpc: np.ndarray
    action_safe: np.ndarray
    active: bool
    feasible_candidate_found: bool
    failed: bool
    violation_score: float
    action_delta_norm: float
    one_step_pred_omega_next: float
    one_step_pred_alpha: float
    one_step_pred_delta_r_next: float
    num_candidates: int
    selected_index: int
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def disabled(cls, action: np.ndarray) -> "SafetyFilterResult":
        action_array = np.asarray(action, dtype=float).copy()
        return cls(
            action_mpc=action_array,
            action_safe=action_array.copy(),
            active=False,
            feasible_candidate_found=False,
            failed=False,
            violation_score=0.0,
            action_delta_norm=0.0,
            one_step_pred_omega_next=float("nan"),
            one_step_pred_alpha=float("nan"),
            one_step_pred_delta_r_next=float("nan"),
            num_candidates=0,
            selected_index=-1,
            extra={},
        )

    def as_diagnostics(self) -> dict[str, Any]:
        diagnostics = {
            "F_tan_mpc": float(self.action_mpc[0]),
            "F_rad_mpc": float(self.action_mpc[1]),
            "F_tan_safe": float(self.action_safe[0]),
            "F_rad_safe": float(self.action_safe[1]),
            "action_delta_norm": float(self.action_delta_norm),
            "safety_filter_active": bool(self.active),
            "safety_filter_feasible_candidate_found": bool(self.feasible_candidate_found),
            "safety_filter_failed": bool(self.failed),
            "safety_filter_violation_score": float(self.violation_score),
            "one_step_pred_omega_next": float(self.one_step_pred_omega_next),
            "one_step_pred_alpha": float(self.one_step_pred_alpha),
            "one_step_pred_delta_r_next": float(self.one_step_pred_delta_r_next),
            "safety_filter_num_candidates": int(self.num_candidates),
            "safety_filter_selected_index": int(self.selected_index),
        }
        diagnostics.update(self.extra)
        return diagnostics


@dataclass
class _CandidateEvaluation:
    index: int
    action: np.ndarray
    candidate_type: str
    scale: float
    feasible: bool
    violation_score: float
    raw_violation_score: float
    normalized_violation_score: float
    action_distance: float
    x_next: np.ndarray
    omega_next: float
    alpha: float
    delta_r_next: float
    raw_components: dict[str, float]
    normalized_components: dict[str, float]
    F_tan_sign_flip: bool
    target_error: float


class OneStepSafetyFilter:
    """Derivative-free projection of an MPC action onto one-step constraints."""

    def __init__(
        self,
        config: dict[str, Any],
        constraints: Spring2DMPCConstraints,
        control_dt: float,
    ) -> None:
        self.config = dict(config)
        self.constraints = constraints
        self.control_dt = float(control_dt)
        self.filter_type = str(self.config.get("type", "one_step_projection")).lower()
        self.use_normalized_score = self.filter_type == "one_step_projection_task_aware"
        self.sign_zero_tol = float(self.config.get("sign_zero_tol", 1.0e-6))
        self.action_distance_tie_tol = float(self.config.get("action_distance_tie_tol", 1.0e-6))
        self.scales = [float(value) for value in self.config.get("scales", [1.0, 0.8, 0.6, 0.4, 0.2, 0.0])]
        self.F_tan_offsets = [
            float(value) for value in self.config.get("F_tan_offsets", [-2.0, -1.0, 0.0, 1.0, 2.0])
        ]
        self.F_rad_offsets = [
            float(value) for value in self.config.get("F_rad_offsets", [-0.2, -0.1, 0.0, 0.1, 0.2])
        ]
        weights = self.config.get("violation_weights", {})
        self.violation_weights = {
            "F_tan": float(weights.get("F_tan", 1.0)),
            "F_rad": float(weights.get("F_rad", 1.0)),
            "delta_r": float(weights.get("delta_r", 1.0)),
            "omega": float(weights.get("omega", 1.0)),
            "alpha": float(weights.get("alpha", 1.0)),
        }

    def filter(
        self,
        action_mpc: np.ndarray,
        state_hat: np.ndarray,
        model_params: dict[str, Any],
        target_theta: float | None = None,
    ) -> SafetyFilterResult:
        action_mpc = np.asarray(action_mpc, dtype=float)
        if action_mpc.shape != (2,):
            raise ValueError("Safety filter action must have shape (2,) as [F_tan, F_rad].")
        state_hat = np.asarray(state_hat, dtype=float)
        if state_hat.shape != (4,):
            raise ValueError("Safety filter state must have shape (4,) as [theta, omega, r, r_dot].")

        candidates = self._candidates(action_mpc)
        mpc_evaluation = self._evaluate_candidate(
            -1,
            action_mpc,
            "original",
            float("nan"),
            action_mpc,
            state_hat,
            model_params,
            target_theta,
        )
        evaluations = [
            self._evaluate_candidate(
                index,
                candidate,
                candidate_type,
                scale,
                action_mpc,
                state_hat,
                model_params,
                target_theta,
            )
            for index, (candidate, candidate_type, scale) in enumerate(candidates)
        ]
        finite_evaluations = [item for item in evaluations if np.isfinite(item.violation_score)]
        if not finite_evaluations:
            safe_action = self.constraints.clip_action(action_mpc)
            return SafetyFilterResult(
                action_mpc=action_mpc.copy(),
                action_safe=safe_action,
                active=True,
                feasible_candidate_found=False,
                failed=True,
                violation_score=float("inf"),
                action_delta_norm=float(np.linalg.norm(safe_action - action_mpc)),
                one_step_pred_omega_next=float("nan"),
                one_step_pred_alpha=float("nan"),
                one_step_pred_delta_r_next=float("nan"),
                num_candidates=len(candidates),
                selected_index=-1,
                extra=self._diagnostic_payload(mpc_evaluation, None, state_hat),
            )

        feasible = [item for item in finite_evaluations if item.feasible]
        if self.filter_type == "one_step_projection":
            if feasible:
                selected = min(feasible, key=lambda item: item.action_distance)
                failed = False
            else:
                selected = min(finite_evaluations, key=lambda item: (item.raw_violation_score, item.action_distance))
                failed = True
        elif self.filter_type == "one_step_projection_task_aware":
            if feasible:
                eligible = feasible
                if abs(float(action_mpc[0])) > self.sign_zero_tol:
                    non_flipping = [item for item in feasible if not item.F_tan_sign_flip]
                    if non_flipping:
                        eligible = non_flipping
                min_distance = min(item.action_distance for item in eligible)
                tied = [
                    item
                    for item in eligible
                    if item.action_distance <= min_distance + self.action_distance_tie_tol
                ]
                selected = min(tied, key=lambda item: item.target_error)
                failed = False
            else:
                selected = min(
                    finite_evaluations,
                    key=lambda item: (item.normalized_violation_score, item.action_distance),
                )
                failed = True
        else:
            raise ValueError(f"Unknown safety filter type: {self.filter_type}")

        return SafetyFilterResult(
            action_mpc=action_mpc.copy(),
            action_safe=selected.action.copy(),
            active=True,
            feasible_candidate_found=bool(feasible),
            failed=failed,
            violation_score=float(selected.violation_score),
            action_delta_norm=float(np.sqrt(selected.action_distance)),
            one_step_pred_omega_next=float(selected.omega_next),
            one_step_pred_alpha=float(selected.alpha),
            one_step_pred_delta_r_next=float(selected.delta_r_next),
            num_candidates=len(candidates),
            selected_index=int(selected.index),
            extra=self._diagnostic_payload(mpc_evaluation, selected, state_hat),
        )

    def _candidates(self, action_mpc: np.ndarray) -> list[tuple[np.ndarray, str, float]]:
        raw_candidates: list[tuple[np.ndarray, str, float]] = [
            (action_mpc.copy(), "original", float("nan")),
            (self.constraints.clip_action(action_mpc), "clipped", float("nan")),
        ]
        raw_candidates.extend((action_mpc * scale, f"scale_{scale:.3g}", scale) for scale in self.scales)
        if self.filter_type == "one_step_projection_task_aware":
            raw_candidates.extend(
                (
                    np.array([scale * float(action_mpc[0]), float(action_mpc[1])], dtype=float),
                    f"F_tan_scale_{scale:.3g}",
                    scale,
                )
                for scale in self.scales
            )
        for F_tan_offset in self.F_tan_offsets:
            for F_rad_offset in self.F_rad_offsets:
                raw_candidates.append(
                    (
                        action_mpc + np.array([F_tan_offset, F_rad_offset], dtype=float),
                        "local_grid",
                        float("nan"),
                    )
                )

        candidates: list[tuple[np.ndarray, str, float]] = []
        seen: set[tuple[float, float]] = set()
        for candidate, candidate_type, scale in raw_candidates:
            clipped = self.constraints.clip_action(candidate)
            key = (round(float(clipped[0]), 12), round(float(clipped[1]), 12))
            if key in seen:
                continue
            seen.add(key)
            candidates.append((clipped, candidate_type, scale))
        return candidates

    def _evaluate_candidate(
        self,
        index: int,
        action: np.ndarray,
        candidate_type: str,
        scale: float,
        action_mpc: np.ndarray,
        state_hat: np.ndarray,
        model_params: dict[str, Any],
        target_theta: float | None,
    ) -> _CandidateEvaluation:
        action_distance = float(np.sum((action - action_mpc) ** 2))
        try:
            x_next = step_dynamics(state_hat, action, self.control_dt, model_params)
        except (FloatingPointError, ValueError, np.linalg.LinAlgError, OverflowError):
            return _CandidateEvaluation(
                index=index,
                action=action.copy(),
                candidate_type=candidate_type,
                scale=scale,
                feasible=False,
                violation_score=float("inf"),
                raw_violation_score=float("inf"),
                normalized_violation_score=float("inf"),
                action_distance=action_distance,
                x_next=np.full(4, np.nan, dtype=float),
                omega_next=float("nan"),
                alpha=float("nan"),
                delta_r_next=float("nan"),
                raw_components=self._nan_components(),
                normalized_components=self._nan_components(),
                F_tan_sign_flip=self._F_tan_sign_flip(action_mpc, action),
                target_error=float("inf"),
            )

        if not np.all(np.isfinite(x_next)) or np.max(np.abs(x_next)) > 1.0e6:
            return _CandidateEvaluation(
                index=index,
                action=action.copy(),
                candidate_type=candidate_type,
                scale=scale,
                feasible=False,
                violation_score=float("inf"),
                raw_violation_score=float("inf"),
                normalized_violation_score=float("inf"),
                action_distance=action_distance,
                x_next=np.full(4, np.nan, dtype=float),
                omega_next=float("nan"),
                alpha=float("nan"),
                delta_r_next=float("nan"),
                raw_components=self._nan_components(),
                normalized_components=self._nan_components(),
                F_tan_sign_flip=self._F_tan_sign_flip(action_mpc, action),
                target_error=float("inf"),
            )

        F_tan, F_rad = action
        omega_next = float(x_next[1])
        delta_r_next = float(x_next[2] - float(model_params["L0"]))
        alpha = float((omega_next - float(state_hat[1])) / self.control_dt)
        raw_components = {
            "F_tan": max(0.0, abs(float(F_tan)) - self.constraints.F_tan_max),
            "F_rad": max(0.0, abs(float(F_rad)) - self.constraints.F_rad_max),
            "delta_r": max(0.0, abs(delta_r_next) - self.constraints.delta_r_max),
            "omega": max(0.0, abs(omega_next) - self.constraints.omega_max),
            "alpha": max(0.0, abs(alpha) - self.constraints.alpha_max),
        }
        normalized_components = {
            "F_tan": self._normalize_violation(raw_components["F_tan"], self.constraints.F_tan_max),
            "F_rad": self._normalize_violation(raw_components["F_rad"], self.constraints.F_rad_max),
            "delta_r": self._normalize_violation(raw_components["delta_r"], self.constraints.delta_r_max),
            "omega": self._normalize_violation(raw_components["omega"], self.constraints.omega_max),
            "alpha": self._normalize_violation(raw_components["alpha"], self.constraints.alpha_max),
        }
        raw_violation_score = float(
            sum(self.violation_weights[name] * value**2 for name, value in raw_components.items())
        )
        normalized_violation_score = float(
            sum(self.violation_weights[name] * value**2 for name, value in normalized_components.items())
        )
        violation_score = normalized_violation_score if self.use_normalized_score else raw_violation_score
        feasible = bool(raw_violation_score <= 0.0)
        target_error = abs(float(x_next[0]) - float(target_theta)) if target_theta is not None else float("inf")
        return _CandidateEvaluation(
            index=index,
            action=action.copy(),
            candidate_type=candidate_type,
            scale=scale,
            feasible=feasible,
            violation_score=violation_score,
            raw_violation_score=raw_violation_score,
            normalized_violation_score=normalized_violation_score,
            action_distance=action_distance,
            x_next=x_next.copy(),
            omega_next=omega_next,
            alpha=alpha,
            delta_r_next=delta_r_next,
            raw_components=raw_components,
            normalized_components=normalized_components,
            F_tan_sign_flip=self._F_tan_sign_flip(action_mpc, action),
            target_error=float(target_error),
        )

    def _diagnostic_payload(
        self,
        mpc_evaluation: _CandidateEvaluation,
        selected: _CandidateEvaluation | None,
        state_hat: np.ndarray,
    ) -> dict[str, Any]:
        safe_evaluation = selected
        payload: dict[str, Any] = {
            "safety_filter_type": self.filter_type,
            "safety_filter_state_hat_theta": float(state_hat[0]),
            "safety_filter_state_hat_omega": float(state_hat[1]),
            "safety_filter_state_hat_r": float(state_hat[2]),
            "safety_filter_state_hat_r_dot": float(state_hat[3]),
            "selected_candidate_type": str(selected.candidate_type) if selected is not None else "fallback",
            "selected_candidate_scale": float(selected.scale) if selected is not None else float("nan"),
            "F_tan_sign_flip": bool(selected.F_tan_sign_flip) if selected is not None else False,
        }
        payload.update(self._evaluation_payload("mpc", mpc_evaluation))
        if safe_evaluation is not None:
            payload.update(self._evaluation_payload("safe", safe_evaluation))
        else:
            payload.update(self._empty_evaluation_payload("safe"))
        return payload

    def _evaluation_payload(self, prefix: str, evaluation: _CandidateEvaluation) -> dict[str, Any]:
        return {
            f"pred_{prefix}_theta_next": float(evaluation.x_next[0]),
            f"pred_{prefix}_omega_next": float(evaluation.x_next[1]),
            f"pred_{prefix}_r_next": float(evaluation.x_next[2]),
            f"pred_{prefix}_r_dot_next": float(evaluation.x_next[3]),
            f"pred_{prefix}_alpha": float(evaluation.alpha),
            f"{prefix}_raw_violation_score": float(evaluation.raw_violation_score),
            f"{prefix}_normalized_violation_score": float(evaluation.normalized_violation_score),
            **{
                f"{prefix}_violation_{name}": float(value)
                for name, value in evaluation.raw_components.items()
            },
            **{
                f"{prefix}_normalized_violation_{name}": float(value)
                for name, value in evaluation.normalized_components.items()
            },
        }

    def _empty_evaluation_payload(self, prefix: str) -> dict[str, Any]:
        payload = {
            f"pred_{prefix}_theta_next": float("nan"),
            f"pred_{prefix}_omega_next": float("nan"),
            f"pred_{prefix}_r_next": float("nan"),
            f"pred_{prefix}_r_dot_next": float("nan"),
            f"pred_{prefix}_alpha": float("nan"),
            f"{prefix}_raw_violation_score": float("nan"),
            f"{prefix}_normalized_violation_score": float("nan"),
        }
        for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]:
            payload[f"{prefix}_violation_{name}"] = float("nan")
            payload[f"{prefix}_normalized_violation_{name}"] = float("nan")
        return payload

    def _F_tan_sign_flip(self, action_mpc: np.ndarray, action: np.ndarray) -> bool:
        F_tan_mpc = float(action_mpc[0])
        F_tan_safe = float(action[0])
        if abs(F_tan_mpc) <= self.sign_zero_tol or abs(F_tan_safe) <= self.sign_zero_tol:
            return False
        return bool(np.sign(F_tan_mpc) != np.sign(F_tan_safe))

    @staticmethod
    def _normalize_violation(value: float, limit: float) -> float:
        if limit <= 0.0:
            return float("inf") if value > 0.0 else 0.0
        return float(value / limit)

    @staticmethod
    def _nan_components() -> dict[str, float]:
        return {name: float("nan") for name in ["F_tan", "F_rad", "delta_r", "omega", "alpha"]}


def make_safety_filter(
    config: dict[str, Any],
    constraints: Spring2DMPCConstraints,
    control_dt: float,
) -> OneStepSafetyFilter | None:
    if not bool(config.get("enabled", False)):
        return None
    filter_type = str(config.get("type", "one_step_projection")).lower()
    if filter_type not in {"one_step_projection", "one_step_projection_task_aware"}:
        raise ValueError(f"Unknown safety filter type: {filter_type}")
    return OneStepSafetyFilter(config, constraints, control_dt)
