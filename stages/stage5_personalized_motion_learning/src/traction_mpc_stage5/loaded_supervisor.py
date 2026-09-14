"""Stage-5 adapter that keeps inherited TRACK/BRAKE under loaded authority."""

from __future__ import annotations

from typing import Any

import numpy as np

from traction_mpc_stage3.reference import CuffPoseReference
from traction_mpc_stage4.executable_command import Stage4ExecutableCommandPreview
from traction_mpc_stage4.track_brake import TrackBrakeSupervisor

from .controller_interface import EstimatedInterfaceState
from .loaded_execution import (
    Stage5LoadedExecutionTarget,
    build_stage5_loaded_execution_context,
)
from .task_observation import ControllerTaskObservation


class Stage5LoadedTrackBrakeSupervisor(TrackBrakeSupervisor):
    """Reuse Stage-4 supervisory logic without its unloaded pose adapter.

    TRACK normally carries the already-screened Stage-5 result.  If the
    inherited supervisor evaluates BRAKE candidates, this override realizes
    them through the same loaded robot-side context instead of reconstructing
    ``geometry.cuff_pose(reference.q)``.
    """

    def __init__(self) -> None:
        super().__init__()
        self._loaded_observation: ControllerTaskObservation | None = None
        self._loaded_interface_state: EstimatedInterfaceState | None = None
        self._loaded_target: Stage5LoadedExecutionTarget | None = None

    def bind_loaded_execution(
        self,
        observation: ControllerTaskObservation,
        interface_state: EstimatedInterfaceState,
        target: Stage5LoadedExecutionTarget,
    ) -> None:
        if interface_state.sample_timestamp_s != observation.sample_timestamp_s:
            raise ValueError("supervisor loaded state timestamps do not match")
        self._loaded_observation = observation
        self._loaded_interface_state = interface_state
        self._loaded_target = target

    def _preview(
        self,
        *,
        plant: Any,
        measurement: Any,
        estimated_state: np.ndarray,
        human_model: Any,
        cuff_allocator: Any,
        action_nm: np.ndarray,
        reference: CuffPoseReference,
    ) -> Stage4ExecutableCommandPreview:
        del estimated_state, reference
        if (
            self._loaded_observation is None
            or self._loaded_interface_state is None
            or self._loaded_target is None
        ):
            raise RuntimeError("Stage-5 supervisor requires a loaded context binding")
        context = build_stage5_loaded_execution_context(
            plant=plant,
            measurement=measurement,
            observation=self._loaded_observation,
            interface_state=self._loaded_interface_state,
            human_model=human_model,
            cuff_allocator=cuff_allocator,
            target=self._loaded_target,
        )
        force_filter = context.make_force_filter()
        force_filter(np.asarray(action_nm, dtype=float)[np.newaxis, :])
        return force_filter.selected_result(action_nm).filtered_preview


__all__ = ["Stage5LoadedTrackBrakeSupervisor"]
