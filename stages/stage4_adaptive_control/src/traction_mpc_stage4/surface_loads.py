"""Finite-surface load decompositions for the validated rigid cuff plant.

This module is evaluation-only.  It never modifies MuJoCo dynamics and its
patch loads are not controller or estimator inputs.  The cylindrical 4x4
surface model is the active engineering formulation.  The earlier collinear
four-point model remains below only as reproducible engineering provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET

import numpy as np

from traction_mpc_stage3.coupled import (
    SHANK_RADIUS_M,
    SLEEVE_OUTER_RADIUS_M,
    build_coupled_model_xml,
)
from traction_mpc_stage3.human import HUMAN, HumanV2Parameters


ACHIEVABLE_WRENCH_ROWS = np.array([0, 1, 2, 4, 5], dtype=int)
UNACHIEVABLE_WRENCH_ROWS = np.array([3], dtype=int)


def _cross_product_matrix(vector: np.ndarray) -> np.ndarray:
    x, y, z = np.asarray(vector, dtype=float)
    return np.array(
        [
            [0.0, -z, y],
            [z, 0.0, -x],
            [-y, x, 0.0],
        ]
    )


@dataclass(frozen=True)
class FiniteSurfaceConfig:
    cuff_length_m: float
    patch_count: int = 4
    patch_weights: tuple[float, ...] = (1.0, 1.0, 1.0, 1.0)

    def __post_init__(self) -> None:
        if self.patch_count != 4:
            raise ValueError("the registered finite-surface audit uses four patches")
        if self.cuff_length_m <= 0.0:
            raise ValueError("cuff_length_m must be positive")
        weights = np.asarray(self.patch_weights, dtype=float)
        if weights.shape != (self.patch_count,) or np.any(weights <= 0.0):
            raise ValueError("patch_weights must contain four positive values")

    @property
    def patch_offsets_m(self) -> np.ndarray:
        indices = np.arange(self.patch_count, dtype=float)
        return ((indices + 0.5) / self.patch_count - 0.5) * self.cuff_length_m

    @property
    def patch_positions_cuff_m(self) -> np.ndarray:
        positions = np.zeros((self.patch_count, 3))
        positions[:, 0] = self.patch_offsets_m
        return positions

    def as_dict(self) -> dict[str, object]:
        return {
            "cuff_length_m": self.cuff_length_m,
            "patch_count": self.patch_count,
            "patch_weights": list(self.patch_weights),
            "patch_offsets_m": self.patch_offsets_m.tolist(),
            "patch_positions_cuff_m": self.patch_positions_cuff_m.tolist(),
            "load_sharing_rule": (
                "minimum weighted sum of squared patch-force norms subject to exact achievable resultant wrench"
            ),
            "patch_direct_moments": False,
            "evaluation_only": True,
        }


@dataclass(frozen=True)
class SurfaceLoadResult:
    patch_forces_cuff_n: np.ndarray
    requested_wrench_cuff: np.ndarray
    reproduced_wrench_cuff: np.ndarray
    residual_wrench_cuff: np.ndarray


class FiniteSurfaceLoadModel:
    """Legacy rank-5 collinear model retained as engineering provenance."""

    def __init__(self, config: FiniteSurfaceConfig) -> None:
        self.config = config
        self.wrench_map = self._build_wrench_map()
        self.achievable_map = self.wrench_map[ACHIEVABLE_WRENCH_ROWS]
        weights = np.repeat(np.asarray(config.patch_weights, dtype=float), 3)
        self.objective_weight = np.diag(weights)
        inverse_weight = np.diag(1.0 / weights)
        gram = self.achievable_map @ inverse_weight @ self.achievable_map.T
        self.minimum_norm_operator = (
            inverse_weight
            @ self.achievable_map.T
            @ np.linalg.inv(gram)
        )
        singular_values = np.linalg.svd(self.wrench_map, compute_uv=False)
        tolerance = max(self.wrench_map.shape) * np.finfo(float).eps * singular_values[0]
        self.rank = int(np.sum(singular_values > tolerance))
        self.nullity = int(self.wrench_map.shape[1] - self.rank)
        self.singular_values = singular_values

    def _build_wrench_map(self) -> np.ndarray:
        matrix = np.zeros((6, 3 * self.config.patch_count))
        for index, position in enumerate(self.config.patch_positions_cuff_m):
            columns = slice(3 * index, 3 * index + 3)
            matrix[:3, columns] = np.eye(3)
            matrix[3:, columns] = _cross_product_matrix(position)
        return matrix

    def decompose(self, wrench_cuff: np.ndarray) -> SurfaceLoadResult:
        requested = np.asarray(wrench_cuff, dtype=float)
        if requested.shape[-1] != 6 or not np.all(np.isfinite(requested)):
            raise ValueError("wrench_cuff must be finite with final dimension six")
        flat = requested.reshape(-1, 6)
        achievable_targets = flat[:, ACHIEVABLE_WRENCH_ROWS]
        flat_forces = achievable_targets @ self.minimum_norm_operator.T
        flat_reproduced = flat_forces @ self.wrench_map.T
        return SurfaceLoadResult(
            patch_forces_cuff_n=flat_forces.reshape(
                requested.shape[:-1] + (self.config.patch_count, 3)
            ),
            requested_wrench_cuff=requested.copy(),
            reproduced_wrench_cuff=flat_reproduced.reshape(requested.shape),
            residual_wrench_cuff=(flat - flat_reproduced).reshape(requested.shape),
        )

    def diagnostics(self) -> dict[str, object]:
        return {
            "wrench_order": ["Fx", "Fy", "Fz", "Mx", "My", "Mz"],
            "wrench_map_rank": self.rank,
            "wrench_map_nullity": self.nullity,
            "singular_values": self.singular_values.tolist(),
            "achievable_components": ["Fx", "Fy", "Fz", "My", "Mz"],
            "unachievable_components": ["Mx"],
            "reason": (
                "collinear axial translational patches have zero lever arm for moment about the cuff axis"
            ),
            "minimum_norm_operator": self.minimum_norm_operator.tolist(),
        }


def surface_load_metrics(
    result: SurfaceLoadResult,
) -> dict[str, object]:
    forces = np.asarray(result.patch_forces_cuff_n)
    if forces.ndim != 3:
        raise ValueError("surface_load_metrics expects a time-by-patch-by-axis result")
    norms = np.linalg.norm(forces, axis=2)
    mean_norm = np.mean(norms, axis=1)
    concentration = np.divide(
        np.max(norms, axis=1),
        mean_norm,
        out=np.ones_like(mean_norm),
        where=mean_norm > 1e-12,
    )
    peak_share = np.divide(
        np.max(norms, axis=1),
        np.sum(norms, axis=1),
        out=np.full_like(mean_norm, 1.0 / forces.shape[1]),
        where=np.sum(norms, axis=1) > 1e-12,
    )
    residual = np.asarray(result.residual_wrench_cuff)
    achievable_residual = residual[:, ACHIEVABLE_WRENCH_ROWS]
    return {
        "peak_force_norm_n_per_patch": np.max(norms, axis=0).tolist(),
        "rms_force_norm_n_per_patch": np.sqrt(np.mean(norms**2, axis=0)).tolist(),
        "peak_abs_force_component_n_per_patch": np.max(
            np.abs(forces), axis=0
        ).tolist(),
        "rms_force_component_n_per_patch": np.sqrt(
            np.mean(forces**2, axis=0)
        ).tolist(),
        "maximum_local_force_n": float(np.max(norms)),
        "proximal_peak_force_n": float(np.max(norms[:, 0])),
        "distal_peak_force_n": float(np.max(norms[:, -1])),
        "proximal_rms_force_n": float(np.sqrt(np.mean(norms[:, 0] ** 2))),
        "distal_rms_force_n": float(np.sqrt(np.mean(norms[:, -1] ** 2))),
        "peak_load_concentration_max_over_mean": float(np.max(concentration)),
        "rms_load_concentration_max_over_mean": float(
            np.sqrt(np.mean(concentration**2))
        ),
        "peak_patch_share_of_sum_local_norm": float(np.max(peak_share)),
        "peak_achievable_wrench_reproduction_residual": float(
            np.max(np.abs(achievable_residual))
        ),
        "peak_unachievable_axial_moment_residual_nm": float(
            np.max(np.abs(residual[:, 3]))
        ),
        "rms_unachievable_axial_moment_residual_nm": float(
            np.sqrt(np.mean(residual[:, 3] ** 2))
        ),
    }


def build_rigid_finite_surface_model_xml(
    human: HumanV2Parameters = HUMAN,
    config: FiniteSurfaceConfig = FiniteSurfaceConfig(0.080),
) -> str:
    """Change only the collision-disabled sleeve visual; keep the rigid weld."""

    root = ET.fromstring(build_coupled_model_xml(human))
    root.set("model", "ur10e_human_v2_rigid_finite_surface_cuff")
    visual = root.find(".//geom[@name='sleeve_geom']")
    if visual is None:
        raise RuntimeError("rigid cuff visual geometry is missing")
    half_length = 0.5 * config.cuff_length_m
    visual.set(
        "fromto",
        (
            f"{human.sleeve_center_m - half_length:.12g} 0 0 "
            f"{human.sleeve_center_m + half_length:.12g} 0 0"
        ),
    )
    visual.set("contype", "0")
    visual.set("conaffinity", "0")
    return ET.tostring(root, encoding="unicode")


@dataclass(frozen=True)
class CylindricalSurfaceConfig:
    """Equal-area axial-by-circumferential cylindrical patch grid."""

    cuff_length_m: float
    radius_m: float = SHANK_RADIUS_M
    axial_patch_count: int = 4
    circumferential_patch_count: int = 4
    patch_weights: tuple[float, ...] = (1.0,) * 16

    def __post_init__(self) -> None:
        if self.cuff_length_m <= 0.0:
            raise ValueError("cuff_length_m must be positive")
        if self.radius_m <= 0.0:
            raise ValueError("radius_m must be positive")
        if self.axial_patch_count != 4 or self.circumferential_patch_count != 4:
            raise ValueError("the registered cylindrical audit uses a 4x4 patch grid")
        weights = np.asarray(self.patch_weights, dtype=float)
        if weights.shape != (self.patch_count,) or np.any(weights <= 0.0):
            raise ValueError("patch_weights must contain sixteen positive values")

    @property
    def patch_count(self) -> int:
        return self.axial_patch_count * self.circumferential_patch_count

    @property
    def axial_offsets_m(self) -> np.ndarray:
        indices = np.arange(self.axial_patch_count, dtype=float)
        return (
            (indices + 0.5) / self.axial_patch_count - 0.5
        ) * self.cuff_length_m

    @property
    def circumferential_angles_rad(self) -> np.ndarray:
        return (
            2.0
            * np.pi
            * np.arange(self.circumferential_patch_count, dtype=float)
            / self.circumferential_patch_count
        )

    @property
    def patch_positions_grid_cuff_m(self) -> np.ndarray:
        positions = np.zeros(
            (self.axial_patch_count, self.circumferential_patch_count, 3)
        )
        positions[:, :, 0] = self.axial_offsets_m[:, None]
        positions[:, :, 1] = self.radius_m * np.cos(
            self.circumferential_angles_rad
        )[None, :]
        positions[:, :, 2] = self.radius_m * np.sin(
            self.circumferential_angles_rad
        )[None, :]
        return positions

    @property
    def patch_positions_cuff_m(self) -> np.ndarray:
        return self.patch_positions_grid_cuff_m.reshape(self.patch_count, 3)

    @property
    def equal_patch_area_m2(self) -> float:
        return (
            2.0
            * np.pi
            * self.radius_m
            * self.cuff_length_m
            / self.patch_count
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "cuff_length_m": self.cuff_length_m,
            "contact_surface_radius_m": self.radius_m,
            "contact_surface_radius_source": "existing Human V2 SHANK_RADIUS_M",
            "visual_outer_radius_m": SLEEVE_OUTER_RADIUS_M,
            "axial_patch_count": self.axial_patch_count,
            "circumferential_patch_count": self.circumferential_patch_count,
            "patch_count": self.patch_count,
            "patch_weights": list(self.patch_weights),
            "equal_patch_area_m2": self.equal_patch_area_m2,
            "axial_offsets_m": self.axial_offsets_m.tolist(),
            "circumferential_angles_deg": np.degrees(
                self.circumferential_angles_rad
            ).tolist(),
            "patch_positions_cuff_m": self.patch_positions_cuff_m.tolist(),
            "load_sharing_rule": (
                "minimum weighted sum of squared 3D patch-force norms subject to exact full resultant wrench"
            ),
            "patch_direct_moments": False,
            "evaluation_only": True,
        }


class CylindricalSurfaceLoadModel:
    """Full-rank minimum-weighted-norm cylindrical patch-force decomposition."""

    def __init__(self, config: CylindricalSurfaceConfig) -> None:
        self.config = config
        self.wrench_map = self._build_wrench_map()
        weights = np.repeat(np.asarray(config.patch_weights, dtype=float), 3)
        self.objective_weight = np.diag(weights)
        inverse_weight = np.diag(1.0 / weights)
        gram = self.wrench_map @ inverse_weight @ self.wrench_map.T
        self.minimum_norm_operator = (
            inverse_weight @ self.wrench_map.T @ np.linalg.inv(gram)
        )
        singular_values = np.linalg.svd(self.wrench_map, compute_uv=False)
        tolerance = (
            max(self.wrench_map.shape)
            * np.finfo(float).eps
            * singular_values[0]
        )
        self.rank = int(np.sum(singular_values > tolerance))
        self.nullity = int(self.wrench_map.shape[1] - self.rank)
        self.singular_values = singular_values
        self.rank_tolerance = float(tolerance)
        if self.rank != 6:
            raise ValueError(
                "cylindrical patch geometry is degenerate and cannot reproduce a full wrench"
            )

    def _build_wrench_map(self) -> np.ndarray:
        matrix = np.zeros((6, 3 * self.config.patch_count))
        for index, position in enumerate(self.config.patch_positions_cuff_m):
            columns = slice(3 * index, 3 * index + 3)
            matrix[:3, columns] = np.eye(3)
            matrix[3:, columns] = _cross_product_matrix(position)
        return matrix

    def decompose(self, wrench_cuff: np.ndarray) -> SurfaceLoadResult:
        requested = np.asarray(wrench_cuff, dtype=float)
        if requested.shape[-1] != 6 or not np.all(np.isfinite(requested)):
            raise ValueError("wrench_cuff must be finite with final dimension six")
        flat = requested.reshape(-1, 6)
        flat_forces = flat @ self.minimum_norm_operator.T
        flat_reproduced = flat_forces @ self.wrench_map.T
        return SurfaceLoadResult(
            patch_forces_cuff_n=flat_forces.reshape(
                requested.shape[:-1] + (self.config.patch_count, 3)
            ),
            requested_wrench_cuff=requested.copy(),
            reproduced_wrench_cuff=flat_reproduced.reshape(requested.shape),
            residual_wrench_cuff=(flat - flat_reproduced).reshape(requested.shape),
        )

    def diagnostics(self) -> dict[str, object]:
        positions = self.config.patch_positions_cuff_m
        moment_information = np.zeros((3, 3))
        for position in positions:
            moment_information += (
                float(position @ position) * np.eye(3)
                - np.outer(position, position)
            )
        return {
            "wrench_order": ["Fx", "Fy", "Fz", "Mx", "My", "Mz"],
            "wrench_map_shape": list(self.wrench_map.shape),
            "wrench_map_rank": self.rank,
            "wrench_map_nullity": self.nullity,
            "rank_tolerance": self.rank_tolerance,
            "singular_values_mixed_force_moment_units": self.singular_values.tolist(),
            "full_6d_wrench_achievable": self.rank == 6,
            "moment_information_matrix_m2": moment_information.tolist(),
            "minimum_norm_operator_shape": list(self.minimum_norm_operator.shape),
            "reason": (
                "nonzero circumferential radius makes the patch positions non-collinear and provides a lever arm for cuff-axis moment"
            ),
        }


def cylindrical_surface_load_metrics(
    result: SurfaceLoadResult,
    config: CylindricalSurfaceConfig,
) -> dict[str, object]:
    forces = np.asarray(result.patch_forces_cuff_n)
    if forces.ndim != 3 or forces.shape[1:] != (config.patch_count, 3):
        raise ValueError(
            "cylindrical_surface_load_metrics expects time-by-16-by-axis forces"
        )
    grid = forces.reshape(
        -1, config.axial_patch_count, config.circumferential_patch_count, 3
    )
    norms = np.linalg.norm(grid, axis=3)
    flat_norms = norms.reshape(len(norms), config.patch_count)
    summed_local_norm = np.sum(flat_norms, axis=1)
    mean_local_norm = np.mean(flat_norms, axis=1)
    maximum_local_by_time = np.max(flat_norms, axis=1)
    concentration = np.divide(
        maximum_local_by_time,
        mean_local_norm,
        out=np.ones_like(mean_local_norm),
        where=mean_local_norm > 1e-12,
    )
    patch_share = np.divide(
        maximum_local_by_time,
        summed_local_norm,
        out=np.full_like(summed_local_norm, 1.0 / config.patch_count),
        where=summed_local_norm > 1e-12,
    )
    peak_time_index = int(np.argmax(maximum_local_by_time))
    axial_sum_norm = np.sum(norms, axis=2)
    circumferential_sum_norm = np.sum(norms, axis=1)
    axial_resultant_norm = np.linalg.norm(np.sum(grid, axis=2), axis=2)
    circumferential_resultant_norm = np.linalg.norm(np.sum(grid, axis=1), axis=2)
    residual = np.asarray(result.residual_wrench_cuff)
    return {
        "peak_force_norm_n_per_patch_axial_by_circumferential": np.max(
            norms, axis=0
        ).tolist(),
        "rms_force_norm_n_per_patch_axial_by_circumferential": np.sqrt(
            np.mean(norms**2, axis=0)
        ).tolist(),
        "maximum_local_force_n": float(np.max(flat_norms)),
        "peak_axial_row_sum_local_norm_n": np.max(
            axial_sum_norm, axis=0
        ).tolist(),
        "rms_axial_row_sum_local_norm_n": np.sqrt(
            np.mean(axial_sum_norm**2, axis=0)
        ).tolist(),
        "peak_axial_row_resultant_force_norm_n": np.max(
            axial_resultant_norm, axis=0
        ).tolist(),
        "peak_proximal_row_sum_local_norm_n": float(
            np.max(axial_sum_norm[:, 0])
        ),
        "peak_distal_row_sum_local_norm_n": float(
            np.max(axial_sum_norm[:, -1])
        ),
        "peak_circumferential_sector_sum_local_norm_n": np.max(
            circumferential_sum_norm, axis=0
        ).tolist(),
        "rms_circumferential_sector_sum_local_norm_n": np.sqrt(
            np.mean(circumferential_sum_norm**2, axis=0)
        ).tolist(),
        "peak_circumferential_sector_resultant_force_norm_n": np.max(
            circumferential_resultant_norm, axis=0
        ).tolist(),
        "circumferential_sector_angles_deg": np.degrees(
            config.circumferential_angles_rad
        ).tolist(),
        "peak_load_concentration_max_over_mean": float(np.max(concentration)),
        "load_concentration_at_maximum_local_force": float(
            concentration[peak_time_index]
        ),
        "peak_patch_share_of_sum_local_norm": float(np.max(patch_share)),
        "patch_share_at_maximum_local_force": float(patch_share[peak_time_index]),
        "peak_full_wrench_reproduction_residual": float(
            np.max(np.abs(residual))
        ),
        "rms_full_wrench_reproduction_residual": float(
            np.sqrt(np.mean(residual**2))
        ),
    }


def build_rigid_cylindrical_surface_model_xml(
    human: HumanV2Parameters = HUMAN,
    config: CylindricalSurfaceConfig = CylindricalSurfaceConfig(0.080),
) -> str:
    """Parameterize only the massless/collision-disabled visual cuff length."""

    root = ET.fromstring(build_coupled_model_xml(human))
    root.set("model", "ur10e_human_v2_rigid_cylindrical_surface_cuff")
    visual = root.find(".//geom[@name='sleeve_geom']")
    if visual is None:
        raise RuntimeError("rigid cuff visual geometry is missing")
    half_length = 0.5 * config.cuff_length_m
    visual.set(
        "fromto",
        (
            f"{human.sleeve_center_m - half_length:.12g} 0 0 "
            f"{human.sleeve_center_m + half_length:.12g} 0 0"
        ),
    )
    visual.set("size", f"{SLEEVE_OUTER_RADIUS_M:.12g}")
    visual.set("contype", "0")
    visual.set("conaffinity", "0")
    return ET.tostring(root, encoding="unicode")
