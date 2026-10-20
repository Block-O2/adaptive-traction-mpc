"""Base interfaces for Spring2D MPC controllers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from traction_mpc.common.types import Spring2DObservation


class BaseMPC(ABC):
    """Small controller interface used by Spring2D experiment scripts."""

    def __init__(self, model_params: dict[str, Any], mpc_params: dict[str, Any]):
        self.model_params = dict(model_params)
        self.mpc_params = dict(mpc_params)

    @abstractmethod
    def reset(self) -> None:
        """Clear controller state before a new rollout."""

    @abstractmethod
    def act(self, observation: Spring2DObservation) -> np.ndarray:
        """Return action as [F_tan, F_rad]."""
