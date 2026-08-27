"""Sagittal rigid-cuff allocation with exact Human-torque preservation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from traction_mpc_stage3.human import HumanV2Parameters, sleeve_jacobian
from traction_mpc_stage3.reference import _world_from_cuff

from .human_model import allocate_generalized_action
from .surface_loads import CylindricalSurfaceConfig, CylindricalSurfaceLoadModel


@dataclass(frozen=True)
class CuffAwareAllocatorConfig:
    """Dimensionally consistent weights for the equality-constrained allocator."""

    resultant_force_weight: float = 1.0
    cylindrical_surface_effort_weight: float = 1.0
    wrench_continuity_weight: float = 0.0
    cuff_length_m: float = 0.080

    def __post_init__(self) -> None:
        if self.resultant_force_weight < 0.0:
            raise ValueError("resultant force weight must be nonnegative")
        if self.cylindrical_surface_effort_weight < 0.0:
            raise ValueError("surface effort weight must be nonnegative")
        if self.wrench_continuity_weight != 0.0:
            raise ValueError(
                "the registered memoryless allocator keeps continuity weight zero"
            )
        if self.cuff_length_m <= 0.0:
            raise ValueError("cuff length must be positive")

    def as_dict(self) -> dict[str, Any]:
        return {
            "resultant_force_weight": self.resultant_force_weight,
            "cylindrical_surface_effort_weight": (
                self.cylindrical_surface_effort_weight
            ),
            "wrench_continuity_weight": self.wrench_continuity_weight,
            "cuff_length_m": self.cuff_length_m,
            "objective": (
                "lambda_F*||[Fx,Fz]||^2 + "
                "lambda_A*||A_dagger*w_cuff||^2"
            ),
            "constraint": "B(q)*[Fx,Fz,My] = tau_h",
            "surface_proxy_interpretation": (
                "minimum-norm equivalent cylindrical patch-force effort; "
                "not pressure or comfort"
            ),
        }


REGISTERED_CUFF_AWARE_ALLOCATOR_CONFIG = CuffAwareAllocatorConfig()
# Frozen Stage-4 engineering default.  Keep the registered name as a
# backward-compatible alias because existing comparison artifacts reference it.
DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG = REGISTERED_CUFF_AWARE_ALLOCATOR_CONFIG


def _geometry_axes(human: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if hasattr(human, "geometry"):
        geometry = human.geometry
        return (
            np.asarray(geometry.plane_x_world, dtype=float),
            np.asarray(geometry.plane_z_world, dtype=float),
            np.asarray(geometry.joint_axis_world, dtype=float),
        )
    return np.eye(3)[0], np.eye(3)[2], np.eye(3)[1]


def sagittal_allocation_matrix(q_rad: np.ndarray, human: Any) -> np.ndarray:
    """Return B(q) for physical sagittal wrench [Fx, Fz, My]."""

    plane_x, plane_z, _ = _geometry_axes(human)
    force_basis = np.column_stack([plane_x, plane_z])
    if hasattr(human, "geometry"):
        force_map = human.geometry.translational_jacobian_world(q_rad).T
        sagittal_force_map = force_map @ force_basis
    else:
        sagittal_force_map = sleeve_jacobian(q_rad, human)[[0, 2], :].T
    # Physical cuff My is along +joint_axis.  The cuff angular Jacobian is
    # [-axis, +axis], hence generalized moment [-My, +My].
    return np.column_stack([sagittal_force_map, np.array([-1.0, 1.0])])


def sagittal_null_vector(q_rad: np.ndarray, human: Any) -> np.ndarray:
    """Return the one-dimensional null direction with force-unit scale."""

    matrix = sagittal_allocation_matrix(q_rad, human)
    vector = np.cross(matrix[0], matrix[1])
    force_norm = float(np.linalg.norm(vector[:2]))
    if force_norm <= 1e-15:
        raise RuntimeError("sagittal allocation null vector is degenerate")
    return vector / force_norm


def _sagittal_wrench_to_world_matrix(q_rad: np.ndarray, human: Any) -> np.ndarray:
    plane_x, plane_z, joint_axis = _geometry_axes(human)
    matrix = np.zeros((6, 3))
    matrix[:3, 0] = plane_x
    matrix[:3, 1] = plane_z
    matrix[3:, 2] = joint_axis
    return matrix


def _world_from_cuff_rotation(q_rad: np.ndarray, human: Any) -> np.ndarray:
    if hasattr(human, "geometry"):
        return np.asarray(human.geometry.cuff_pose(q_rad).rotation, dtype=float)
    return np.asarray(_world_from_cuff(q_rad).rotation, dtype=float)


def cylindrical_surface_mapping(
    q_rad: np.ndarray,
    human: Any,
    surface_model: CylindricalSurfaceLoadModel,
) -> np.ndarray:
    """Map sagittal [Fx,Fz,My] to the minimum-norm patch-force vector."""

    world_mapping = _sagittal_wrench_to_world_matrix(q_rad, human)
    rotation = _world_from_cuff_rotation(q_rad, human)
    world_to_cuff = np.zeros((6, 6))
    world_to_cuff[:3, :3] = rotation.T
    world_to_cuff[3:, 3:] = rotation.T
    return surface_model.minimum_norm_operator @ world_to_cuff @ world_mapping


def _enrich_allocation(
    result: dict[str, Any],
    generalized_action_nm: np.ndarray,
    q_rad: np.ndarray,
    human: Any,
    *,
    allocation_kind: str,
    surface_model: CylindricalSurfaceLoadModel,
) -> dict[str, Any]:
    plane_x, plane_z, joint_axis = _geometry_axes(human)
    wrench_world = np.asarray(result["wrench_world"], dtype=float)
    sagittal = np.array(
        [
            plane_x @ wrench_world[:3],
            plane_z @ wrench_world[:3],
            joint_axis @ wrench_world[3:],
        ]
    )
    matrix = sagittal_allocation_matrix(q_rad, human)
    residual = matrix @ sagittal - np.asarray(generalized_action_nm, dtype=float)
    rotation = _world_from_cuff_rotation(q_rad, human)
    wrench_cuff = np.concatenate(
        [rotation.T @ wrench_world[:3], rotation.T @ wrench_world[3:]]
    )
    patch_force = surface_model.minimum_norm_operator @ wrench_cuff
    enriched = dict(result)
    enriched.update(
        {
            "allocation_kind": allocation_kind,
            "sagittal_wrench": sagittal,
            "allocation_matrix": matrix,
            "equality_residual_nm": float(np.linalg.norm(residual)),
            "cylindrical_surface_effort_n": float(np.linalg.norm(patch_force)),
            "maximum_local_patch_force_proxy_n": float(
                np.max(np.linalg.norm(patch_force.reshape(-1, 3), axis=1))
            ),
        }
    )
    return enriched


class CurrentForceMinimizingAllocator:
    """Adapter around the unchanged minimum-resultant-force allocation."""

    def __init__(self, cuff_length_m: float = 0.080) -> None:
        self.surface_model = CylindricalSurfaceLoadModel(
            CylindricalSurfaceConfig(cuff_length_m)
        )

    def allocate(
        self, generalized_action_nm: np.ndarray, q_rad: np.ndarray, human: Any
    ) -> dict[str, Any]:
        if hasattr(human, "allocate_generalized_action"):
            result = human.allocate_generalized_action(
                generalized_action_nm, q_rad
            )
        else:
            result = allocate_generalized_action(
                generalized_action_nm, q_rad, human
            )
        return _enrich_allocation(
            result,
            generalized_action_nm,
            q_rad,
            human,
            allocation_kind="current_minimum_resultant_force",
            surface_model=self.surface_model,
        )


class CuffAwareSagittalAllocator:
    """Minimize force plus equivalent surface effort at exactly fixed tau_h."""

    def __init__(
        self,
        config: CuffAwareAllocatorConfig = REGISTERED_CUFF_AWARE_ALLOCATOR_CONFIG,
    ) -> None:
        self.config = config
        self.surface_model = CylindricalSurfaceLoadModel(
            CylindricalSurfaceConfig(config.cuff_length_m)
        )

    def allocate(
        self, generalized_action_nm: np.ndarray, q_rad: np.ndarray, human: Any
    ) -> dict[str, Any]:
        torque = np.asarray(generalized_action_nm, dtype=float)
        matrix = sagittal_allocation_matrix(q_rad, human)
        world_mapping = _sagittal_wrench_to_world_matrix(q_rad, human)
        surface_mapping = cylindrical_surface_mapping(
            q_rad, human, self.surface_model
        )
        force_metric = np.diag([1.0, 1.0, 0.0])
        hessian = (
            self.config.resultant_force_weight * force_metric
            + self.config.cylindrical_surface_effort_weight
            * (surface_mapping.T @ surface_mapping)
        )
        inverse_hessian_bt = np.linalg.solve(hessian, matrix.T)
        dual_matrix = matrix @ inverse_hessian_bt
        sagittal = inverse_hessian_bt @ np.linalg.solve(dual_matrix, torque)
        wrench_world = world_mapping @ sagittal
        force_world = wrench_world[:3]
        physical_my = float(sagittal[2])
        result: dict[str, Any] = {
            "force_world_n": force_world,
            "force_norm_n": float(np.linalg.norm(force_world)),
            # Preserve the legacy key convention: my_nm is opposite physical
            # world/cuff +Y moment, while wrench_world stores physical moment.
            "my_nm": -physical_my,
            "wrench_world": wrench_world,
            "allocation_residual_nm": float(
                np.linalg.norm(matrix @ sagittal - torque)
            ),
            "objective_value_n2": float(sagittal @ hessian @ sagittal),
        }
        return _enrich_allocation(
            result,
            torque,
            q_rad,
            human,
            allocation_kind="cuff_aware_force_plus_surface_effort",
            surface_model=self.surface_model,
        )


def default_engineering_cuff_allocator() -> CuffAwareSagittalAllocator:
    """Return the frozen 1:1 Stage-4 engineering allocator."""

    return CuffAwareSagittalAllocator(DEFAULT_ENGINEERING_CUFF_ALLOCATOR_CONFIG)
