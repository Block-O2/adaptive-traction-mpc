"""Torque-preserving executable-force projection for Stage 4."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import numpy as np

from traction_mpc_stage3.executable_command import (
    ExecutableCommandBatchPreview,
    ExecutableCommandPreview,
    PreparedExecutableCommandContext,
    preview_executable_commands_batch,
)
from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage3.reference import CuffPoseReference

from .cuff_allocator import (
    sagittal_allocation_matrix,
    sagittal_null_vector,
    sagittal_wrench_to_world_matrix,
)
from .executable_command import (
    Stage4ExecutableCommandPreview,
    prepare_stage4_executable_command_context,
)


SAFE_UNCHANGED = "SAFE_UNCHANGED"
SAFE_FILTERED = "SAFE_FILTERED"
FILTER_INFEASIBLE = "FILTER_INFEASIBLE"


@dataclass(frozen=True)
class ExecutableForceFilterContext:
    """Candidate-invariant geometry and executable-command state."""

    estimated_state: np.ndarray
    human_model: Any
    cuff_allocator: Any
    command_context: PreparedExecutableCommandContext
    allocation_matrix: np.ndarray
    sagittal_null_vector: np.ndarray
    world_mapping: np.ndarray
    world_null_wrench: np.ndarray


@dataclass(frozen=True)
class ExecutableForceFilterResult:
    status: str
    action_nm: np.ndarray
    nominal_preview: Stage4ExecutableCommandPreview
    filtered_preview: Stage4ExecutableCommandPreview
    nominal_sagittal_wrench: np.ndarray
    filtered_sagittal_wrench: np.ndarray
    null_sagittal_wrench: np.ndarray
    lambda_value: float
    intervention_coordinate_norm: float
    force_intervention_norm_n: float
    moment_intervention_norm_nm: float
    torque_residual_nm: float
    torque_exactly_preserved: bool
    computation_ms: float

    @property
    def feasible(self) -> bool:
        return self.status in {SAFE_UNCHANGED, SAFE_FILTERED}

    def metadata(self) -> dict[str, Any]:
        nominal = self.nominal_preview
        filtered = self.filtered_preview
        return {
            "status": self.status,
            "nominal_wrench_world": np.asarray(
                nominal.allocation["wrench_world"]
            ).tolist(),
            "filtered_wrench_world": np.asarray(
                filtered.allocation["wrench_world"]
            ).tolist(),
            "nominal_force_total_n": nominal.command.force_total_n.tolist(),
            "filtered_force_total_n": filtered.command.force_total_n.tolist(),
            "nominal_executable_force_norm_n": (
                nominal.command.translational_force_norm_n
            ),
            "filtered_executable_force_norm_n": (
                filtered.command.translational_force_norm_n
            ),
            "lambda": self.lambda_value,
            "intervention_coordinate_norm": self.intervention_coordinate_norm,
            "force_intervention_norm_n": self.force_intervention_norm_n,
            "moment_intervention_norm_nm": self.moment_intervention_norm_nm,
            "executable_force_margin_n": (
                filtered.command.margin_to_force_gate_n
            ),
            "torque_residual_nm": self.torque_residual_nm,
            "torque_exactly_preserved": self.torque_exactly_preserved,
            "computation_ms": self.computation_ms,
        }


@dataclass(frozen=True)
class ExecutableForceFilterBatchResult:
    actions_nm: np.ndarray
    statuses: np.ndarray
    nominal_wrenches_world: np.ndarray
    filtered_wrenches_world: np.ndarray
    nominal_sagittal_wrenches: np.ndarray
    filtered_sagittal_wrenches: np.ndarray
    null_sagittal_wrench: np.ndarray
    lambdas: np.ndarray
    intervention_coordinate_norms: np.ndarray
    force_intervention_norms_n: np.ndarray
    moment_intervention_norms_nm: np.ndarray
    torque_residuals_nm: np.ndarray
    torque_exactly_preserved: np.ndarray
    nominal_commands: ExecutableCommandBatchPreview
    filtered_commands: ExecutableCommandBatchPreview
    computation_ms: float

    def __len__(self) -> int:
        return int(len(self.actions_nm))

    @property
    def feasible(self) -> np.ndarray:
        command_feasible = np.where(
            self.statuses == SAFE_UNCHANGED,
            self.nominal_commands.feasible,
            self.filtered_commands.feasible,
        )
        return np.asarray(
            (self.statuses != FILTER_INFEASIBLE)
            & command_feasible
            & self.torque_exactly_preserved,
            dtype=bool,
        )

    @property
    def filter_status(self) -> np.ndarray:
        return self.statuses.copy()

    @staticmethod
    def _allocation(
        wrench_world: np.ndarray,
        sagittal_wrench: np.ndarray,
        matrix: np.ndarray,
        action_nm: np.ndarray,
        kind: str,
    ) -> dict[str, Any]:
        force = np.asarray(wrench_world[:3], dtype=float)
        return {
            "allocation_kind": kind,
            "wrench_world": np.asarray(wrench_world, dtype=float).copy(),
            "force_world_n": force.copy(),
            "force_norm_n": float(np.linalg.norm(force)),
            "sagittal_wrench": np.asarray(sagittal_wrench, dtype=float).copy(),
            "allocation_matrix": matrix.copy(),
            "equality_residual_nm": float(
                np.linalg.norm(matrix @ sagittal_wrench - action_nm)
            ),
        }

    def command(self, index: int) -> ExecutableCommandPreview:
        if self.statuses[index] == SAFE_UNCHANGED:
            return self.nominal_commands.command(index)
        return self.filtered_commands.command(index)

    def result(
        self,
        index: int,
        allocation_matrix: np.ndarray,
    ) -> ExecutableForceFilterResult:
        nominal_allocation = self._allocation(
            self.nominal_wrenches_world[index],
            self.nominal_sagittal_wrenches[index],
            allocation_matrix,
            self.actions_nm[index],
            "nominal_cuff_allocator",
        )
        filtered_allocation = self._allocation(
            self.filtered_wrenches_world[index],
            self.filtered_sagittal_wrenches[index],
            allocation_matrix,
            self.actions_nm[index],
            (
                "executable_force_safe_unchanged"
                if self.statuses[index] == SAFE_UNCHANGED
                else (
                    "executable_force_nullspace_filtered"
                    if self.statuses[index] == SAFE_FILTERED
                    else "executable_force_filter_infeasible"
                )
            ),
        )
        nominal = Stage4ExecutableCommandPreview(
            allocation=nominal_allocation,
            command=self.nominal_commands.command(index),
        )
        filtered = Stage4ExecutableCommandPreview(
            allocation=filtered_allocation,
            command=self.command(index),
        )
        return ExecutableForceFilterResult(
            status=str(self.statuses[index]),
            action_nm=self.actions_nm[index].copy(),
            nominal_preview=nominal,
            filtered_preview=filtered,
            nominal_sagittal_wrench=(
                self.nominal_sagittal_wrenches[index].copy()
            ),
            filtered_sagittal_wrench=(
                self.filtered_sagittal_wrenches[index].copy()
            ),
            null_sagittal_wrench=self.null_sagittal_wrench.copy(),
            lambda_value=float(self.lambdas[index]),
            intervention_coordinate_norm=float(
                self.intervention_coordinate_norms[index]
            ),
            force_intervention_norm_n=float(
                self.force_intervention_norms_n[index]
            ),
            moment_intervention_norm_nm=float(
                self.moment_intervention_norms_nm[index]
            ),
            torque_residual_nm=float(self.torque_residuals_nm[index]),
            torque_exactly_preserved=bool(
                self.torque_exactly_preserved[index]
            ),
            computation_ms=self.computation_ms,
        )

    def filter_metadata(self, index: int) -> dict[str, Any]:
        return {
            "status": str(self.statuses[index]),
            "nominal_wrench_world": self.nominal_wrenches_world[index].tolist(),
            "filtered_wrench_world": self.filtered_wrenches_world[index].tolist(),
            "lambda": float(self.lambdas[index]),
            "intervention_coordinate_norm": float(
                self.intervention_coordinate_norms[index]
            ),
            "force_intervention_norm_n": float(
                self.force_intervention_norms_n[index]
            ),
            "moment_intervention_norm_nm": float(
                self.moment_intervention_norms_nm[index]
            ),
            "nominal_executable_force_norm_n": float(
                self.nominal_commands.translational_force_norm_n[index]
            ),
            "filtered_executable_force_norm_n": float(
                self.command(index).translational_force_norm_n
            ),
            "executable_force_margin_n": float(
                self.command(index).margin_to_force_gate_n
            ),
            "torque_residual_nm": float(self.torque_residuals_nm[index]),
            "torque_exactly_preserved": bool(
                self.torque_exactly_preserved[index]
            ),
        }


def prepare_executable_force_filter_context(
    *,
    plant: Any,
    measurement: Any,
    estimated_state: np.ndarray,
    human_model: Any,
    cuff_allocator: Any,
    reference: CuffPoseReference,
) -> ExecutableForceFilterContext:
    """Prepare all state/geometry terms shared by a candidate batch."""

    state, command_context = prepare_stage4_executable_command_context(
        plant=plant,
        measurement=measurement,
        estimated_state=estimated_state,
        human_model=human_model,
        reference=reference,
    )
    q = state[:2]
    matrix = sagittal_allocation_matrix(q, human_model)
    null = sagittal_null_vector(q, human_model)
    world_mapping = sagittal_wrench_to_world_matrix(q, human_model)
    world_null = world_mapping @ null
    if np.linalg.matrix_rank(matrix) != 2:
        raise RuntimeError("sagittal cuff allocation matrix is not rank two")
    if np.linalg.norm(matrix @ null) > 1.0e-10:
        raise RuntimeError("computed cuff wrench direction is not in null(B)")
    return ExecutableForceFilterContext(
        estimated_state=state.copy(),
        human_model=human_model,
        cuff_allocator=cuff_allocator,
        command_context=command_context,
        allocation_matrix=matrix,
        sagittal_null_vector=null,
        world_mapping=world_mapping,
        world_null_wrench=world_null,
    )


def _nominal_wrenches(
    context: ExecutableForceFilterContext,
    actions_nm: np.ndarray,
) -> np.ndarray:
    allocate_batch = getattr(
        context.cuff_allocator,
        "allocate_wrenches_batch",
        None,
    )
    if allocate_batch is not None:
        return np.asarray(
            allocate_batch(
                actions_nm,
                context.estimated_state[:2],
                context.human_model,
            ),
            dtype=float,
        )
    return np.vstack(
        [
            np.asarray(
                context.cuff_allocator.allocate(
                    action,
                    context.estimated_state[:2],
                    context.human_model,
                )["wrench_world"],
                dtype=float,
            )
            for action in actions_nm
        ]
    )


def filter_executable_commands_batch(
    context: ExecutableForceFilterContext,
    actions_nm: np.ndarray,
) -> ExecutableForceFilterBatchResult:
    """Project an action batch along null(B), preserving every Human torque."""

    started = perf_counter()
    actions = np.asarray(actions_nm, dtype=float)
    if (
        actions.ndim != 2
        or actions.shape[1] != 2
        or not np.all(np.isfinite(actions))
    ):
        raise ValueError("actions_nm must be a finite Nx2 matrix")
    nominal_wrenches = _nominal_wrenches(context, actions)
    if nominal_wrenches.shape != (len(actions), 6):
        raise ValueError("allocator batch must return an Nx6 wrench matrix")
    sagittal, _, _, _ = np.linalg.lstsq(
        context.world_mapping,
        nominal_wrenches.T,
        rcond=None,
    )
    nominal_sagittal = sagittal.T
    nominal_world_residual = np.linalg.norm(
        nominal_wrenches
        - np.einsum("ij,kj->ki", context.world_mapping, nominal_sagittal),
        axis=1,
    )
    nominal_torque_residual = np.linalg.norm(
        np.einsum("ij,kj->ki", context.allocation_matrix, nominal_sagittal)
        - actions,
        axis=1,
    )
    nominal_commands = preview_executable_commands_batch(
        context.command_context,
        nominal_wrenches,
    )
    statuses = np.full(len(actions), FILTER_INFEASIBLE, dtype="<U20")
    lambdas = np.zeros(len(actions))
    valid_nominal = (
        np.isfinite(nominal_world_residual)
        & (nominal_world_residual <= 1.0e-10)
        & np.isfinite(nominal_torque_residual)
        & (nominal_torque_residual <= 1.0e-9)
    )
    unchanged = valid_nominal & nominal_commands.feasible
    statuses[unchanged] = SAFE_UNCHANGED

    direction = context.world_null_wrench[:3]
    quadratic = float(direction @ direction)
    unsafe = np.flatnonzero(valid_nominal & ~nominal_commands.feasible)
    if quadratic > 1.0e-15 and len(unsafe):
        force = nominal_commands.force_total_n[unsafe]
        linear = 2.0 * np.einsum("ij,j->i", force, direction)
        constant = np.einsum("ij,ij->i", force, force) - (
            CUFF_TRANSLATIONAL_FORCE_GATE_N**2
        )
        discriminant = linear**2 - 4.0 * quadratic * constant
        recoverable = discriminant >= -1.0e-9
        recoverable_indices = unsafe[recoverable]
        if len(recoverable_indices):
            root = np.sqrt(np.maximum(discriminant[recoverable], 0.0))
            lower = (-linear[recoverable] - root) / (2.0 * quadratic)
            upper = (-linear[recoverable] + root) / (2.0 * quadratic)
            projected = np.where(lower > 0.0, lower, upper)
            inward = np.maximum(1.0e-9, 1.0e-12 * np.abs(projected))
            projected = np.where(
                projected > 0.0,
                np.minimum(projected + inward, upper),
                np.maximum(projected - inward, lower),
            )
            lambdas[recoverable_indices] = projected

    filtered_sagittal = (
        nominal_sagittal
        + lambdas[:, np.newaxis] * context.sagittal_null_vector
    )
    filtered_wrenches = np.einsum(
        "ij,kj->ki",
        context.world_mapping,
        filtered_sagittal,
    )
    # Preserve the identity branch bit for bit, including its Stage-3 input.
    filtered_wrenches[unchanged] = nominal_wrenches[unchanged]
    filtered_sagittal[unchanged] = nominal_sagittal[unchanged]
    filtered_commands = preview_executable_commands_batch(
        context.command_context,
        filtered_wrenches,
    )
    torque_residuals = np.linalg.norm(
        np.einsum(
            "ij,kj->ki",
            context.allocation_matrix,
            filtered_sagittal,
        )
        - actions,
        axis=1,
    )
    torque_preserved = torque_residuals <= 1.0e-9
    rescued = (
        valid_nominal
        & ~nominal_commands.feasible
        & (lambdas != 0.0)
        & filtered_commands.feasible
        & torque_preserved
    )
    statuses[rescued] = SAFE_FILTERED
    difference = filtered_wrenches - nominal_wrenches
    elapsed_ms = 1000.0 * (perf_counter() - started)
    return ExecutableForceFilterBatchResult(
        actions_nm=actions.copy(),
        statuses=statuses,
        nominal_wrenches_world=nominal_wrenches,
        filtered_wrenches_world=filtered_wrenches,
        nominal_sagittal_wrenches=nominal_sagittal,
        filtered_sagittal_wrenches=filtered_sagittal,
        null_sagittal_wrench=context.sagittal_null_vector.copy(),
        lambdas=lambdas,
        intervention_coordinate_norms=np.linalg.norm(difference, axis=1),
        force_intervention_norms_n=np.linalg.norm(difference[:, :3], axis=1),
        moment_intervention_norms_nm=np.linalg.norm(difference[:, 3:], axis=1),
        torque_residuals_nm=torque_residuals,
        torque_exactly_preserved=torque_preserved,
        nominal_commands=nominal_commands,
        filtered_commands=filtered_commands,
        computation_ms=elapsed_ms,
    )


def filter_executable_command(
    context: ExecutableForceFilterContext,
    action_nm: np.ndarray,
) -> ExecutableForceFilterResult:
    """Scalar torque-preserving safety-filter result."""

    batch = filter_executable_commands_batch(
        context,
        np.asarray(action_nm, dtype=float)[np.newaxis, :],
    )
    return batch.result(0, context.allocation_matrix)


class Stage4ExecutableForceFilter:
    """Callable CEM batch previewer with exact selected-result carry-forward."""

    def __init__(self, context: ExecutableForceFilterContext) -> None:
        self.context = context
        self.last_actions: np.ndarray | None = None
        self.last_batch: ExecutableForceFilterBatchResult | None = None

    def __call__(
        self,
        actions_nm: np.ndarray,
    ) -> ExecutableForceFilterBatchResult:
        actions = np.asarray(actions_nm, dtype=float)
        result = filter_executable_commands_batch(self.context, actions)
        self.last_actions = actions.copy()
        self.last_batch = result
        return result

    def selected_result(
        self,
        action_nm: np.ndarray,
    ) -> ExecutableForceFilterResult:
        action = np.asarray(action_nm, dtype=float)
        if (
            self.last_actions is None
            or self.last_batch is None
            or self.last_actions.shape != (1, 2)
            or not np.array_equal(self.last_actions[0], action)
        ):
            raise RuntimeError("selected safety-filter result was not carried forward")
        return self.last_batch.result(0, self.context.allocation_matrix)


def make_stage4_executable_force_filter(
    *,
    plant: Any,
    measurement: Any,
    estimated_state: np.ndarray,
    human_model: Any,
    cuff_allocator: Any,
    reference: CuffPoseReference,
) -> Stage4ExecutableForceFilter:
    return Stage4ExecutableForceFilter(
        prepare_executable_force_filter_context(
            plant=plant,
            measurement=measurement,
            estimated_state=estimated_state,
            human_model=human_model,
            cuff_allocator=cuff_allocator,
            reference=reference,
        )
    )
