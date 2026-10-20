"""Shadow-only deployable prediction support-domain evaluator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


SUPPORT_DOMAIN_VERSION = "stage5_joint_deployable_knn_support_v1"
CALIBRATION_DISTANCE_QUANTILE = 0.95


FEATURE_BLOCK_PREFIXES = {
    "robot_state": ("robot_q_", "robot_dq_"),
    "human_state": ("human_",),
    "cuff_kinematics": (
        "cuff_position_",
        "cuff_rotvec_",
        "cuff_linear_velocity_",
        "cuff_angular_velocity_",
    ),
    "interface_load": (
        "interface_displacement_",
        "interface_velocity_",
        "interface_rotation_",
        "interface_angular_velocity_",
        "measured_force_",
        "measured_moment_",
    ),
    "command_history": (
        "previous_action_",
        "previous_action_delta_",
        "candidate_action_",
        "candidate_minus_previous_",
    ),
    "known_geometry": ("shank_clearance_",),
}


def _finite_matrix(name: str, value: Any, columns: int | None = None) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.ndim != 2:
        raise ValueError(f"{name} must be a matrix")
    if columns is not None and result.shape[1] != columns:
        raise ValueError(f"{name} must have {columns} columns")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be finite")
    return result.copy()


def feature_block_indices(feature_names: tuple[str, ...]) -> dict[str, np.ndarray]:
    """Map the frozen deployable feature contract to equal-weight blocks."""

    names = tuple(feature_names)
    blocks: dict[str, np.ndarray] = {}
    consumed: set[int] = set()
    for block, prefixes in FEATURE_BLOCK_PREFIXES.items():
        indices = np.asarray(
            [
                index
                for index, name in enumerate(names)
                if any(name.startswith(prefix) for prefix in prefixes)
            ],
            dtype=int,
        )
        if not len(indices):
            raise ValueError(f"feature block {block!r} is empty")
        blocks[block] = indices
        consumed.update(indices.tolist())
    identity = [
        index for index, name in enumerate(names) if name == "robot_identity_cr12_0"
    ]
    if len(identity) != 1:
        raise ValueError("feature contract needs exactly one robot identity field")
    consumed.add(identity[0])
    if consumed != set(range(len(names))):
        missing = [names[index] for index in sorted(set(range(len(names))) - consumed)]
        raise ValueError(f"unassigned deployable features: {missing}")
    return blocks


@dataclass(frozen=True)
class SupportDecision:
    supported: bool
    reasons: tuple[str, ...]
    joint_distance: float | None
    joint_distance_limit: float
    nearest_reference_index: int | None
    block_distances: dict[str, float]

    @property
    def label(self) -> str:
        return "SUPPORTED" if self.supported else "UNSUPPORTED"

    def record(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "supported": self.supported,
            "reasons": list(self.reasons),
            "joint_distance": self.joint_distance,
            "joint_distance_limit": self.joint_distance_limit,
            "nearest_reference_index": self.nearest_reference_index,
            "block_distances": dict(self.block_distances),
        }


@dataclass(frozen=True)
class PredictionSupportDomainV1:
    """One equal-block, same-robot nearest-neighbour support domain."""

    feature_names: tuple[str, ...]
    feature_center: np.ndarray
    feature_scale: np.ndarray
    development_features: np.ndarray
    development_robot_identity: np.ndarray
    block_indices: dict[str, np.ndarray]
    joint_distance_limit: float
    block_distance_limits: dict[str, float]
    calibration_distance_quantile: float
    development_group_ids: tuple[str, ...]
    calibration_group_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        count = len(self.feature_names)
        center = np.asarray(self.feature_center, dtype=float)
        scale = np.asarray(self.feature_scale, dtype=float)
        development = _finite_matrix(
            "development_features", self.development_features, count
        )
        identities = np.asarray(self.development_robot_identity, dtype=int)
        if center.shape != (count,) or not np.all(np.isfinite(center)):
            raise ValueError("feature_center must be finite")
        if scale.shape != (count,) or not np.all(np.isfinite(scale)):
            raise ValueError("feature_scale must be finite")
        if np.any(scale <= 0.0):
            raise ValueError("feature_scale must be positive")
        if identities.shape != (len(development),):
            raise ValueError("development robot identities are inconsistent")
        if not np.isfinite(self.joint_distance_limit) or self.joint_distance_limit < 0.0:
            raise ValueError("joint distance limit must be finite and nonnegative")
        if not 0.0 < self.calibration_distance_quantile <= 1.0:
            raise ValueError("calibration distance quantile must lie in (0,1]")
        expected_blocks = feature_block_indices(self.feature_names)
        for block, indices in expected_blocks.items():
            if block not in self.block_indices or not np.array_equal(
                indices, np.asarray(self.block_indices[block], dtype=int)
            ):
                raise ValueError("feature block mapping changed")
            limit = self.block_distance_limits.get(block)
            if limit is None or not np.isfinite(limit) or limit < 0.0:
                raise ValueError(f"invalid distance limit for block {block}")
        object.__setattr__(self, "feature_center", center.copy())
        object.__setattr__(self, "feature_scale", scale.copy())
        object.__setattr__(self, "development_features", development.copy())
        object.__setattr__(self, "development_robot_identity", identities.copy())
        object.__setattr__(
            self,
            "block_indices",
            {key: np.asarray(value, dtype=int).copy() for key, value in expected_blocks.items()},
        )

    @property
    def identity_index(self) -> int:
        return self.feature_names.index("robot_identity_cr12_0")

    @property
    def clearance_index(self) -> int:
        return self.feature_names.index("shank_clearance_0")

    def _distances(
        self, feature: np.ndarray, reference_indices: np.ndarray
    ) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        query = (feature - self.feature_center) / self.feature_scale
        reference = (
            self.development_features[reference_indices] - self.feature_center
        ) / self.feature_scale
        block_distance = {
            block: np.sqrt(
                np.mean(
                    np.square(reference[:, indices] - query[None, indices]), axis=1
                )
            )
            for block, indices in self.block_indices.items()
        }
        joint = np.sqrt(
            np.mean(
                np.column_stack(
                    [np.square(block_distance[block]) for block in self.block_indices]
                ),
                axis=1,
            )
        )
        return joint, block_distance

    def evaluate(
        self,
        feature: np.ndarray,
        *,
        causal_history_valid: bool,
    ) -> SupportDecision:
        value = np.asarray(feature, dtype=float)
        reasons: list[str] = []
        if value.shape != (len(self.feature_names),) or not np.all(np.isfinite(value)):
            return SupportDecision(
                supported=False,
                reasons=("NONFINITE_OR_MALFORMED_DEPLOYABLE_FEATURES",),
                joint_distance=None,
                joint_distance_limit=self.joint_distance_limit,
                nearest_reference_index=None,
                block_distances={},
            )
        if not causal_history_valid:
            reasons.append("CAUSAL_HISTORY_INVALID")
        if value[self.clearance_index] <= 0.0:
            reasons.append("GEOMETRIC_CONTACT_OR_PENETRATION")
        identity = int(round(value[self.identity_index]))
        reference_indices = np.flatnonzero(
            self.development_robot_identity == identity
        )
        if not len(reference_indices):
            return SupportDecision(
                supported=False,
                reasons=tuple(reasons + ["ROBOT_IDENTITY_UNCALIBRATED"]),
                joint_distance=None,
                joint_distance_limit=self.joint_distance_limit,
                nearest_reference_index=None,
                block_distances={},
            )
        joint, blocks = self._distances(value, reference_indices)
        local_index = int(np.argmin(joint))
        nearest_index = int(reference_indices[local_index])
        joint_distance = float(joint[local_index])
        nearest_blocks = {
            block: float(distance[local_index]) for block, distance in blocks.items()
        }
        if joint_distance > self.joint_distance_limit + 1.0e-12:
            reasons.append("OUTSIDE_JOINT_DEPLOYABLE_SUPPORT")
            for block, distance in nearest_blocks.items():
                if distance > self.block_distance_limits[block] + 1.0e-12:
                    reasons.append(f"OUTSIDE_{block.upper()}_SUPPORT")
        return SupportDecision(
            supported=not reasons,
            reasons=tuple(reasons),
            joint_distance=joint_distance,
            joint_distance_limit=self.joint_distance_limit,
            nearest_reference_index=nearest_index,
            block_distances=nearest_blocks,
        )

    def record(self) -> dict[str, Any]:
        return {
            "version": SUPPORT_DOMAIN_VERSION,
            "definition": (
                "same-robot nearest development neighbour in an equal-weight "
                "six-block standardized deployable feature space"
            ),
            "feature_names": list(self.feature_names),
            "feature_center": self.feature_center,
            "feature_scale": self.feature_scale,
            "feature_blocks": {
                block: [self.feature_names[index] for index in indices]
                for block, indices in self.block_indices.items()
            },
            "development_reference_count": len(self.development_features),
            "joint_distance_limit": self.joint_distance_limit,
            "block_distance_limits": dict(self.block_distance_limits),
            "calibration_distance_quantile": self.calibration_distance_quantile,
            "development_group_ids": list(self.development_group_ids),
            "calibration_group_ids": list(self.calibration_group_ids),
            "explicit_contact_rule": "shank clearance <= 0 is unsupported",
            "observed_4p97mm_used_as_threshold": False,
            "mujoco_truth_online_input": False,
        }


def fit_prediction_support_domain_v1(
    *,
    feature_names: tuple[str, ...],
    development_features: np.ndarray,
    calibration_features: np.ndarray,
    development_group_ids: tuple[str, ...],
    calibration_group_ids: tuple[str, ...],
    calibration_distance_quantile: float = CALIBRATION_DISTANCE_QUANTILE,
) -> PredictionSupportDomainV1:
    """Fit one support domain without using error or MuJoCo-truth labels."""

    names = tuple(feature_names)
    development = _finite_matrix(
        "development_features", development_features, len(names)
    )
    calibration = _finite_matrix(
        "calibration_features", calibration_features, len(names)
    )
    if not len(development) or not len(calibration):
        raise ValueError("development and calibration features must be nonempty")
    identity_index = names.index("robot_identity_cr12_0")
    identities = np.rint(development[:, identity_index]).astype(int)
    calibration_identities = np.rint(calibration[:, identity_index]).astype(int)
    if not set(calibration_identities).issubset(set(identities)):
        raise ValueError("calibration includes an undeveloped robot identity")
    center = np.mean(development, axis=0)
    scale = np.std(development, axis=0)
    scale = np.where(scale > 1.0e-9, scale, 1.0)
    blocks = feature_block_indices(names)
    provisional = PredictionSupportDomainV1(
        feature_names=names,
        feature_center=center,
        feature_scale=scale,
        development_features=development,
        development_robot_identity=identities,
        block_indices=blocks,
        joint_distance_limit=0.0,
        block_distance_limits={block: 0.0 for block in blocks},
        calibration_distance_quantile=calibration_distance_quantile,
        development_group_ids=tuple(development_group_ids),
        calibration_group_ids=tuple(calibration_group_ids),
    )
    calibration_joint: list[float] = []
    calibration_blocks = {block: [] for block in blocks}
    for feature, identity in zip(calibration, calibration_identities):
        reference_indices = np.flatnonzero(identities == identity)
        joint, block_distance = provisional._distances(feature, reference_indices)
        nearest = int(np.argmin(joint))
        calibration_joint.append(float(joint[nearest]))
        for block in blocks:
            calibration_blocks[block].append(float(block_distance[block][nearest]))
    return PredictionSupportDomainV1(
        feature_names=names,
        feature_center=center,
        feature_scale=scale,
        development_features=development,
        development_robot_identity=identities,
        block_indices=blocks,
        joint_distance_limit=float(
            np.quantile(calibration_joint, calibration_distance_quantile)
        ),
        block_distance_limits={
            block: float(np.quantile(values, calibration_distance_quantile))
            for block, values in calibration_blocks.items()
        },
        calibration_distance_quantile=calibration_distance_quantile,
        development_group_ids=tuple(development_group_ids),
        calibration_group_ids=tuple(calibration_group_ids),
    )
