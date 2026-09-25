"""Final Stage-5 matched posture-region experiment primitives.

The temporary region changes only the Goal-MPC waypoint. It never emits a
robot command and never reads MuJoCo Human truth or measured cuff force.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

import numpy as np

from .matched_branch import Stage5RuntimeSnapshot
from .task import GoalTaskSpec, TaskPhase


class PostureRegion(str, Enum):
    HIP_BIASED = "hip_biased"
    BALANCED = "balanced"
    KNEE_BIASED = "knee_biased"


@dataclass(frozen=True)
class PostureRegionSpec:
    start_name: str
    start_phase: TaskPhase
    start_minimum_progress: float
    region: PostureRegion
    center_progress: tuple[float, float]
    half_width_progress: tuple[float, float]
    maximum_waypoint_duration_s: float

    def __post_init__(self) -> None:
        if not self.start_name:
            raise ValueError("posture-region start name must be non-empty")
        if self.start_phase not in (TaskPhase.OUTBOUND, TaskPhase.RETURN):
            raise ValueError("posture-region starts require a moving task phase")
        if not 0.0 < self.start_minimum_progress < 1.0:
            raise ValueError("start progress must lie strictly inside the phase")
        if len(self.center_progress) != 2 or not all(
            np.isfinite(value) and 0.0 < value < 1.0
            for value in self.center_progress
        ):
            raise ValueError("region center must contain two finite interior progresses")
        if len(self.half_width_progress) != 2 or not all(
            np.isfinite(value) and 0.0 < value < 0.5
            for value in self.half_width_progress
        ):
            raise ValueError("region half-width must contain two finite positive values")
        if any(
            center - width <= 0.0 or center + width >= 1.0
            for center, width in zip(
                self.center_progress, self.half_width_progress, strict=True
            )
        ):
            raise ValueError("posture region must remain inside normalized task envelope")
        if not np.isfinite(self.maximum_waypoint_duration_s) or (
            self.maximum_waypoint_duration_s <= 0.0
        ):
            raise ValueError("maximum waypoint duration must be finite and positive")


def outbound_normalized_progress(
    q_rad: Sequence[float], task: GoalTaskSpec
) -> np.ndarray:
    q = np.asarray(q_rad, dtype=float)
    start = np.asarray(task.start_return_target_rad, dtype=float)
    goal = np.asarray(task.outbound_goal_target_rad, dtype=float)
    if q.shape != (2,) or not np.all(np.isfinite(q)):
        raise ValueError("q_rad must be a finite q1/q2 pair")
    return (q - start) / (goal - start)


def progress_to_q_rad(
    progress: Sequence[float], task: GoalTaskSpec
) -> np.ndarray:
    normalized = np.asarray(progress, dtype=float)
    if normalized.shape != (2,) or not np.all(np.isfinite(normalized)):
        raise ValueError("normalized progress must be a finite q1/q2 pair")
    start = np.asarray(task.start_return_target_rad, dtype=float)
    goal = np.asarray(task.outbound_goal_target_rad, dtype=float)
    return start + normalized * (goal - start)


def audit_posture_regions(
    *,
    task: GoalTaskSpec,
    starts: Sequence[Mapping[str, Any]],
    regions: Sequence[Mapping[str, Any]],
    maximum_waypoint_duration_s: float,
    effective_velocity_deg_s: Sequence[float],
    minimum_adjacent_center_distance: float,
    minimum_extreme_center_distance: float,
) -> dict[str, Any]:
    """Audit geometry and conservative velocity reachability without force data."""

    centers = {
        str(region["name"]): np.asarray(region["center_progress"], dtype=float)
        for region in regions
    }
    widths = {
        str(region["name"]): np.asarray(region["half_width_progress"], dtype=float)
        for region in regions
    }
    expected = {
        PostureRegion.HIP_BIASED.value,
        PostureRegion.BALANCED.value,
        PostureRegion.KNEE_BIASED.value,
    }
    if set(centers) != expected:
        raise ValueError("feasibility audit requires the three named posture regions")
    for name in expected:
        PostureRegionSpec(
            start_name="audit",
            start_phase=TaskPhase.OUTBOUND,
            start_minimum_progress=0.25,
            region=PostureRegion(name),
            center_progress=tuple(centers[name]),
            half_width_progress=tuple(widths[name]),
            maximum_waypoint_duration_s=maximum_waypoint_duration_s,
        )

    order = [
        PostureRegion.HIP_BIASED.value,
        PostureRegion.BALANCED.value,
        PostureRegion.KNEE_BIASED.value,
    ]
    adjacent = [
        float(np.linalg.norm(centers[left] - centers[right]))
        for left, right in zip(order[:-1], order[1:], strict=True)
    ]
    extreme = float(np.linalg.norm(centers[order[0]] - centers[order[-1]]))
    boxes_disjoint = all(
        bool(
            np.any(
                np.abs(centers[left] - centers[right])
                > widths[left] + widths[right]
            )
        )
        for left, right in zip(order[:-1], order[1:], strict=True)
    )

    velocity_deg_s = np.asarray(effective_velocity_deg_s, dtype=float)
    excursion_deg = np.degrees(
        np.asarray(task.outbound_goal_target_rad)
        - np.asarray(task.start_return_target_rad)
    )
    reachability: list[dict[str, Any]] = []
    for start in starts:
        phase_progress = float(start["minimum_progress"])
        start_outbound_progress = (
            np.full(2, phase_progress)
            if str(start["phase"]) == TaskPhase.OUTBOUND.value
            else np.full(2, 1.0 - phase_progress)
        )
        for name in order:
            distance_deg = np.abs(
                (centers[name] - start_outbound_progress) * excursion_deg
            )
            conservative_time_s = float(np.max(distance_deg / velocity_deg_s))
            reachability.append(
                {
                    "start_name": str(start["name"]),
                    "region": name,
                    "nominal_start_outbound_progress": start_outbound_progress.tolist(),
                    "center_progress": centers[name].tolist(),
                    "required_joint_excursion_deg": distance_deg.tolist(),
                    "velocity_only_lower_bound_s": conservative_time_s,
                    "within_fixed_waypoint_budget": bool(
                        conservative_time_s < maximum_waypoint_duration_s
                    ),
                }
            )

    q_bounds = np.asarray(task.q_bounds_rad, dtype=float)
    centers_q = {
        name: progress_to_q_rad(center, task) for name, center in centers.items()
    }
    inside_task_bounds = all(
        bool(np.all(q_bounds[:, 0] < q) and np.all(q < q_bounds[:, 1]))
        for q in centers_q.values()
    )
    mean_progress_equal = bool(
        np.ptp([np.mean(center) for center in centers.values()]) <= 1.0e-12
    )
    passed = bool(
        min(adjacent) >= minimum_adjacent_center_distance
        and extreme >= minimum_extreme_center_distance
        and boxes_disjoint
        and inside_task_bounds
        and mean_progress_equal
        and all(row["within_fixed_waypoint_budget"] for row in reachability)
    )
    return {
        "force_or_moment_used_to_select_regions": False,
        "adjacent_center_distances": adjacent,
        "extreme_center_distance": extreme,
        "region_boxes_disjoint": boxes_disjoint,
        "equal_mean_normalized_progress": mean_progress_equal,
        "centers_q_deg": {
            name: np.degrees(q).tolist() for name, q in centers_q.items()
        },
        "inside_existing_task_bounds": inside_task_bounds,
        "reachability": reachability,
        "passed": passed,
    }


class PostureRegionIntervention:
    """Temporary waypoint region for the unchanged Goal-MPC controller."""

    intervention_kind = "temporary_intermediate_posture_region"

    def __init__(self, spec: PostureRegionSpec) -> None:
        self.spec = spec
        self.snapshot: Stage5RuntimeSnapshot | None = None
        self.activation_time_s: float | None = None
        self.region_entry_time_s: float | None = None
        self.region_entry_progress: np.ndarray | None = None
        self._goal_transition_pending = False
        self.solve_times_s: list[float] = []
        self.prefix_feasible: list[bool] = []

    def should_capture(
        self,
        *,
        phase: TaskPhase,
        progress: float | None,
        high_level_cycle: bool,
    ) -> bool:
        return bool(
            self.snapshot is None
            and high_level_cycle
            and phase is self.spec.start_phase
            and progress is not None
            and progress >= self.spec.start_minimum_progress
        )

    def register_snapshot(
        self, snapshot: Stage5RuntimeSnapshot, episode_time_s: float
    ) -> None:
        if self.snapshot is not None:
            raise RuntimeError("posture-region snapshot already captured")
        self.snapshot = snapshot
        self.activation_time_s = float(episode_time_s)

    def active(self, episode_time_s: float, phase: TaskPhase) -> bool:
        if self.activation_time_s is None or phase is not self.spec.start_phase:
            return False
        if self.region_entry_time_s is not None:
            return False
        elapsed = float(episode_time_s) - self.activation_time_s
        return -1.0e-12 <= elapsed < self.spec.maximum_waypoint_duration_s - 1.0e-12

    def planning_spec(
        self,
        task: GoalTaskSpec,
        *,
        episode_time_s: float,
        phase: TaskPhase,
        q_rad: np.ndarray | None = None,
    ) -> GoalTaskSpec:
        if self.activation_time_s is not None and self.region_entry_time_s is None:
            if q_rad is None:
                raise ValueError("posture-region planning requires deployable q")
            progress = outbound_normalized_progress(q_rad, task)
            center = np.asarray(self.spec.center_progress, dtype=float)
            width = np.asarray(self.spec.half_width_progress, dtype=float)
            if phase is self.spec.start_phase and np.all(
                np.abs(progress - center) <= width + 1.0e-12
            ):
                self.region_entry_time_s = float(episode_time_s)
                self.region_entry_progress = progress.copy()
                self._goal_transition_pending = True
        if not self.active(episode_time_s, phase):
            return task
        target = tuple(float(value) for value in progress_to_q_rad(self.spec.center_progress, task))
        if phase is TaskPhase.OUTBOUND:
            return replace(task, outbound_goal_target_rad=target)
        return replace(task, start_return_target_rad=target)

    def consume_goal_transition(self) -> bool:
        pending = self._goal_transition_pending
        self._goal_transition_pending = False
        return pending

    def candidate_action(
        self,
        action_nm: np.ndarray,
        *,
        episode_time_s: float,
        phase: TaskPhase,
    ) -> np.ndarray:
        return np.asarray(action_nm, dtype=float).copy()

    def apply(
        self,
        action_nm: np.ndarray,
        *,
        episode_time_s: float,
        phase: TaskPhase,
        prefix_feasible: bool,
    ) -> np.ndarray:
        action = np.asarray(action_nm, dtype=float).copy()
        if self.active(episode_time_s, phase):
            self.solve_times_s.append(float(episode_time_s))
            self.prefix_feasible.append(bool(prefix_feasible))
            if not prefix_feasible:
                raise RuntimeError("posture-region Goal-MPC action is prefix-infeasible")
        return action

    def report(self) -> dict[str, Any]:
        return {
            "intervention_kind": self.intervention_kind,
            "start_name": self.spec.start_name,
            "phase": self.spec.start_phase.value,
            "minimum_progress": self.spec.start_minimum_progress,
            "region": self.spec.region.value,
            "center_progress": list(self.spec.center_progress),
            "half_width_progress": list(self.spec.half_width_progress),
            "maximum_waypoint_duration_s": self.spec.maximum_waypoint_duration_s,
            "snapshot_captured": self.snapshot is not None,
            "activation_time_s": self.activation_time_s,
            "region_entry_time_s": self.region_entry_time_s,
            "region_entry_progress": (
                None
                if self.region_entry_progress is None
                else self.region_entry_progress.tolist()
            ),
            "release_time_s": self.region_entry_time_s,
            "maximum_release_deadline_s": (
                None
                if self.activation_time_s is None
                else self.activation_time_s + self.spec.maximum_waypoint_duration_s
            ),
            "release_rule": "first deployable entry into target region",
            "decision_state_sha256": (
                None if self.snapshot is None else self.snapshot.decision_state_sha256
            ),
            "deployable_start": (
                None if self.snapshot is None else self.snapshot.deployable_start
            ),
            "waypoint_solve_count": len(self.solve_times_s),
            "waypoint_solve_times_s": self.solve_times_s,
            "all_waypoint_prefixes_feasible": bool(
                self.prefix_feasible and all(self.prefix_feasible)
            ),
            "direct_robot_command_output": False,
            "force_or_truth_used_for_branch_decision": False,
            "control_authority_after_release": "same_frozen_baseline_goal_mpc",
            "full_prescribed_trajectory": False,
        }


__all__ = [
    "PostureRegion",
    "PostureRegionIntervention",
    "PostureRegionSpec",
    "audit_posture_regions",
    "outbound_normalized_progress",
    "progress_to_q_rad",
]
