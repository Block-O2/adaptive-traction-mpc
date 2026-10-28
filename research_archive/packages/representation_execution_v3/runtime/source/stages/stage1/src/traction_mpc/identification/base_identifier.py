"""Base interfaces for online parameter identifiers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class IdentifierResult:
    theta_hat: dict[str, float]
    prediction_error: float
    updated: bool
    num_samples: int
    success: bool


class BaseIdentifier(ABC):
    """Identifier interface for logging-only online estimation."""

    parameter_names: tuple[str, ...]

    @abstractmethod
    def reset(self) -> None:
        """Clear internal data and reset estimates."""

    @abstractmethod
    def add_transition(self, x_obs: np.ndarray, action: np.ndarray, x_next_obs: np.ndarray) -> IdentifierResult:
        """Add one transition and optionally update parameters."""

    @abstractmethod
    def get_parameter_estimate(self) -> dict[str, float]:
        """Return the current parameter estimate."""

    @abstractmethod
    def get_model_params(self) -> dict[str, Any]:
        """Return full model params with current estimates inserted."""
