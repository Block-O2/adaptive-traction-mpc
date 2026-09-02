"""Unified trust/force reference timing without estimator or MPC modification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

import numpy as np

from traction_mpc_stage3.human import CUFF_TRANSLATIONAL_FORCE_GATE_N
from traction_mpc_stage3.reference import CuffPoseReference

from .estimator_v2 import DYNAMIC_BASE_PARAMETER_NAMES
from .minimal_adaptation import EstimatorConfidence, regression_confidence
from .safety_filter import FILTER_INFEASIBLE, SAFE_FILTERED, SAFE_UNCHANGED


GEOMETRY_PARAMETER_NAMES = (
    "hip_plane_x_normalized",
    "hip_plane_z_normalized",
    "thigh_length_normalized",
    "cuff_alignment_x_normalized",
    "cuff_alignment_z_normalized",
)


@dataclass(frozen=True)
class ConfidenceAwareExecutionConfig:
    """Registered execution-only settings for the engineering comparison."""

    minimum_speed_scale: float = 0.50
    nominal_speed_scale: float = 1.00
    recovery_rate_per_s: float = 0.25
    slowdown_rate_per_s: float = 1.00
    model_confidence_filter_time_constant_s: float = 0.75
    high_confidence_enter_threshold: float = 0.75
    high_confidence_exit_threshold: float = 0.25

    def __post_init__(self) -> None:
        if not 0.0 < self.minimum_speed_scale <= self.nominal_speed_scale:
            raise ValueError("speed scales must satisfy 0 < minimum <= nominal")
        if self.nominal_speed_scale > 1.0:
            raise ValueError("confidence execution may not exceed nominal speed")
        if self.recovery_rate_per_s <= 0.0 or self.slowdown_rate_per_s <= 0.0:
            raise ValueError("speed-scale rates must be positive")
        if self.model_confidence_filter_time_constant_s <= 0.0:
            raise ValueError("confidence filter time constant must be positive")
        if not (
            0.0
            <= self.high_confidence_exit_threshold
            < self.high_confidence_enter_threshold
            <= 1.0
        ):
            raise ValueError("confidence hysteresis thresholds are invalid")

    def as_dict(self) -> dict[str, float]:
        return {
            "minimum_speed_scale": self.minimum_speed_scale,
            "nominal_speed_scale": self.nominal_speed_scale,
            "recovery_rate_per_s": self.recovery_rate_per_s,
            "slowdown_rate_per_s": self.slowdown_rate_per_s,
            "model_confidence_filter_time_constant_s": (
                self.model_confidence_filter_time_constant_s
            ),
            "high_confidence_enter_threshold": self.high_confidence_enter_threshold,
            "high_confidence_exit_threshold": self.high_confidence_exit_threshold,
        }


@dataclass(frozen=True)
class ReferenceManagerForceDecision:
    """Result of one causal Safety-Filter input to the shared reference clock."""

    filter_status: str
    alpha_force: float | None
    force_severity: float | None
    brake_required: bool


def _unavailable_confidence(parameter_names: tuple[str, ...]) -> EstimatorConfidence:
    dimension = len(parameter_names)
    return EstimatorConfidence(
        parameter_names=parameter_names,
        sample_count=0,
        parameter_dimension=dimension,
        rank=0,
        condition_number=float("inf"),
        residual_rms=float("nan"),
        covariance=np.full((dimension, dimension), np.nan),
        standard_deviation=np.full(dimension, np.nan),
        accepted=False,
        reasons=("not_attempted",),
    )


def _diagnostic_reasons(diagnostics: dict[str, Any]) -> tuple[str, ...]:
    reason = str(diagnostics.get("reason", "unspecified"))
    return () if reason == "accepted" else tuple(item for item in reason.split(",") if item)


class ExistingEstimatorConfidenceMonitor:
    """Build confidence payloads from the unchanged estimator's retained data."""

    def __init__(self) -> None:
        self.geometry = _unavailable_confidence(GEOMETRY_PARAMETER_NAMES)
        self.dynamics = _unavailable_confidence(
            tuple(f"{name}_normalized" for name in DYNAMIC_BASE_PARAMETER_NAMES)
        )

    def update(
        self,
        estimator: Any,
        geometry_diagnostics: dict[str, Any],
        dynamic_diagnostics: dict[str, Any],
    ) -> None:
        if geometry_diagnostics.get("attempted", False):
            identifier = estimator.geometry_identifier
            _, plane_x, plane_z, _, _ = identifier._axis_and_basis()
            positions, rotations = identifier._data_arrays(plane_x, plane_z)
            matrix = identifier._numerical_jacobian(
                identifier.last_valid, positions, rotations
            )
            residual = identifier._radial_residual(
                identifier.last_valid, positions, rotations
            )
            self.geometry = regression_confidence(
                matrix,
                residual,
                GEOMETRY_PARAMETER_NAMES,
                accepted=bool(geometry_diagnostics.get("accepted", False)),
                reasons=_diagnostic_reasons(geometry_diagnostics),
            )

        if dynamic_diagnostics.get("attempted", False):
            identifier = estimator.dynamic_identifier
            matrix, target, _ = identifier._integral_blocks(
                estimator.raw_history, estimator.geometry
            )
            if len(target):
                residual = matrix @ identifier.last_valid - target
                self.dynamics = regression_confidence(
                    matrix * identifier.span,
                    residual,
                    tuple(
                        f"{name}_normalized"
                        for name in DYNAMIC_BASE_PARAMETER_NAMES
                    ),
                    accepted=bool(dynamic_diagnostics.get("accepted", False)),
                    reasons=_diagnostic_reasons(dynamic_diagnostics),
                )


def information_confidence_level(
    confidence: EstimatorConfidence, maximum_condition_number: float
) -> float:
    """Report whether the latest data are informative enough for an update.

    Candidate acceptance is deliberately not part of this signal.  A bound or
    physical-validity rejection can leave the data informative while the
    retained last-valid model remains unchanged.
    """

    covariance_finite = bool(np.all(np.isfinite(confidence.covariance)))
    return float(
        confidence.full_rank
        and np.isfinite(confidence.condition_number)
        and confidence.condition_number <= float(maximum_condition_number)
        and np.isfinite(confidence.residual_rms)
        and covariance_finite
    )


def _current_model_valid(estimator: Any) -> tuple[bool, bool]:
    """Validate only the retained model, never a rejected candidate."""

    geometry_identifier = estimator.geometry_identifier
    geometry = estimator.geometry
    geometry_arrays = (
        geometry.origin_world_m,
        geometry.plane_x_world,
        geometry.joint_axis_world,
        geometry.plane_z_world,
        geometry.hip_plane_m,
        geometry.knee_to_cuff_in_cuff_m,
        geometry_identifier.last_valid,
    )
    geometry_valid = bool(
        geometry_identifier.trustworthy_time_s is not None
        and all(np.all(np.isfinite(item)) for item in geometry_arrays)
        and geometry.thigh_length_m > 0.0
        and geometry.cuff_distance_m > 0.0
    )

    dynamic_identifier = estimator.dynamic_identifier
    try:
        minimum_mass_eigenvalue = estimator.model.minimum_mass_matrix_eigenvalue()
    except (ValueError, FloatingPointError, np.linalg.LinAlgError):
        minimum_mass_eigenvalue = float("nan")
    dynamic_valid = bool(
        dynamic_identifier.trustworthy_time_s is not None
        and np.all(np.isfinite(dynamic_identifier.last_valid))
        and np.isfinite(minimum_mass_eigenvalue)
        and minimum_mass_eigenvalue > 1e-6
    )
    return geometry_valid, dynamic_valid


class UnifiedReferenceManager:
    """Own the single path phase/rate controlled by trust and force caps."""

    def __init__(
        self,
        base_reference: Callable[[float], CuffPoseReference],
        *,
        confidence_aware: bool,
        config: ConfidenceAwareExecutionConfig = ConfidenceAwareExecutionConfig(),
        initial_wall_time_s: float = 0.0,
    ) -> None:
        self.base_reference = base_reference
        self.confidence_aware = bool(confidence_aware)
        self.config = config
        self.monitor = ExistingEstimatorConfidenceMonitor()
        self.wall_anchor_s = float(initial_wall_time_s)
        self.last_confidence_update_wall_time_s = float(initial_wall_time_s)
        self.phase_anchor_s = 0.0
        initial_speed_scale = (
            config.minimum_speed_scale
            if self.confidence_aware
            else config.nominal_speed_scale
        )
        self.speed_anchor_scale = initial_speed_scale
        self.speed_target_scale = initial_speed_scale
        self.speed_scale_rate_per_s = 0.0
        self.alpha_trust = initial_speed_scale
        self.alpha_force = config.nominal_speed_scale
        self.force_severity = 0.0
        self.last_force_filter_status = SAFE_UNCHANGED
        self.last_force_margin_n = CUFF_TRANSLATIONAL_FORCE_GATE_N
        self.last_force_intervention_norm_n = 0.0
        self.last_moment_intervention_norm_nm = 0.0
        self.last_wrench_intervention_coordinate_norm = 0.0
        self.force_update_count = 0
        self.force_filtered_count = 0
        self.force_infeasible_count = 0
        self.geometry_model_confidence = 0.0
        self.dynamic_model_confidence = 0.0
        self.combined_model_confidence_raw = 0.0
        self.geometry_information_confidence = 0.0
        self.dynamic_information_confidence = 0.0
        self.combined_information_confidence = 0.0
        self.filtered_model_confidence = 0.0
        self.execution_confidence_high = 0.0
        self.update_count = 0

    @property
    def mode(self) -> str:
        return "confidence_aware" if self.confidence_aware else "fixed_speed"

    @property
    def speed_scale(self) -> float:
        """Speed at the most recent causal clock anchor."""

        return self.speed_anchor_scale

    @property
    def alpha_cmd(self) -> float:
        return min(
            self.config.nominal_speed_scale,
            self.alpha_trust,
            self.alpha_force,
        )

    def _clock_state(self, wall_time_s: float) -> tuple[float, float, float]:
        """Return phase, phase rate, and phase acceleration at wall time."""

        wall_time = float(wall_time_s)
        if wall_time < self.wall_anchor_s - 1e-12:
            raise ValueError("reference execution time must be monotonic")
        elapsed = max(0.0, wall_time - self.wall_anchor_s)
        speed_0 = self.speed_anchor_scale
        target = self.speed_target_scale
        rate = self.speed_scale_rate_per_s
        if abs(rate) <= 1e-15:
            return self.phase_anchor_s + speed_0 * elapsed, speed_0, 0.0

        ramp_duration = (target - speed_0) / rate
        if ramp_duration <= 1e-15:
            return self.phase_anchor_s + target * elapsed, target, 0.0
        ramp_elapsed = min(elapsed, ramp_duration)
        phase = (
            self.phase_anchor_s
            + speed_0 * ramp_elapsed
            + 0.5 * rate * ramp_elapsed**2
        )
        if elapsed < ramp_duration - 1e-12:
            speed = speed_0 + rate * elapsed
            return phase, float(speed), float(rate)
        phase += target * (elapsed - ramp_duration)
        return phase, float(target), 0.0

    def phase_time_s(self, wall_time_s: float) -> float:
        return self._clock_state(wall_time_s)[0]

    def _set_speed_target(self, wall_time_s: float, target: float) -> None:
        wall_time = float(wall_time_s)
        phase_now, speed_now, _ = self._clock_state(wall_time)
        target = float(
            np.clip(
                target,
                0.0,
                self.config.nominal_speed_scale,
            )
        )
        if target > speed_now + 1e-15:
            rate = self.config.recovery_rate_per_s
        elif target < speed_now - 1e-15:
            rate = -self.config.slowdown_rate_per_s
        else:
            rate = 0.0
        self.phase_anchor_s = phase_now
        self.wall_anchor_s = wall_time
        self.speed_anchor_scale = float(speed_now)
        self.speed_target_scale = target
        self.speed_scale_rate_per_s = float(rate)

    def update_from_confidence(
        self,
        wall_time_s: float,
        geometry: EstimatorConfidence,
        dynamics: EstimatorConfidence,
        *,
        geometry_model_valid: bool,
        dynamic_model_valid: bool,
        geometry_maximum_condition_number: float = float("inf"),
        dynamic_maximum_condition_number: float = float("inf"),
    ) -> None:
        self.monitor.geometry = geometry
        self.monitor.dynamics = dynamics
        self.geometry_model_confidence = float(bool(geometry_model_valid))
        self.dynamic_model_confidence = float(bool(dynamic_model_valid))
        self.combined_model_confidence_raw = min(
            self.geometry_model_confidence, self.dynamic_model_confidence
        )
        self.geometry_information_confidence = information_confidence_level(
            geometry, geometry_maximum_condition_number
        )
        self.dynamic_information_confidence = information_confidence_level(
            dynamics, dynamic_maximum_condition_number
        )
        self.combined_information_confidence = min(
            self.geometry_information_confidence,
            self.dynamic_information_confidence,
        )

        elapsed = max(
            0.0,
            float(wall_time_s) - self.last_confidence_update_wall_time_s,
        )
        alpha = -np.expm1(
            -elapsed / self.config.model_confidence_filter_time_constant_s
        )
        self.filtered_model_confidence += float(alpha) * (
            self.combined_model_confidence_raw - self.filtered_model_confidence
        )
        if (
            self.execution_confidence_high < 0.5
            and self.filtered_model_confidence
            >= self.config.high_confidence_enter_threshold
        ):
            self.execution_confidence_high = 1.0
        elif (
            self.execution_confidence_high >= 0.5
            and self.filtered_model_confidence
            <= self.config.high_confidence_exit_threshold
        ):
            self.execution_confidence_high = 0.0
        self.alpha_trust = (
            self.config.nominal_speed_scale
            if self.execution_confidence_high >= 1.0
            else self.config.minimum_speed_scale
        )
        if not self.confidence_aware:
            self.alpha_trust = self.config.nominal_speed_scale
        self._set_speed_target(wall_time_s, self.alpha_cmd)
        self.last_confidence_update_wall_time_s = float(wall_time_s)
        self.update_count += 1

    def update_from_safety_filter(
        self,
        wall_time_s: float,
        filter_result: Mapping[str, Any] | Any,
    ) -> ReferenceManagerForceDecision:
        """Update the force cap from one causal executable-force result.

        ``SAFE_UNCHANGED`` is the exact nominal identity.  For
        ``SAFE_FILTERED``, the force part of the null-space intervention is
        normalized only by the unchanged 200 N executable-force limit.  This
        adds no trajectory-specific threshold or future-force prediction.
        """

        metadata = (
            filter_result
            if isinstance(filter_result, Mapping)
            else filter_result.metadata()
        )
        status = str(metadata["status"])
        if status not in {SAFE_UNCHANGED, SAFE_FILTERED, FILTER_INFEASIBLE}:
            raise ValueError("unexpected executable-force filter status")
        self.last_force_filter_status = status
        self.force_update_count += 1
        self.last_force_margin_n = float(
            metadata.get("executable_force_margin_n", float("nan"))
        )
        self.last_force_intervention_norm_n = float(
            metadata.get("force_intervention_norm_n", 0.0)
        )
        self.last_moment_intervention_norm_nm = float(
            metadata.get("moment_intervention_norm_nm", 0.0)
        )
        self.last_wrench_intervention_coordinate_norm = float(
            metadata.get("intervention_coordinate_norm", 0.0)
        )
        if status == FILTER_INFEASIBLE:
            self.force_infeasible_count += 1
            return ReferenceManagerForceDecision(
                filter_status=status,
                alpha_force=None,
                force_severity=None,
                brake_required=True,
            )

        if status == SAFE_UNCHANGED:
            severity = 0.0
        else:
            self.force_filtered_count += 1
            severity = float(
                np.clip(
                    self.last_force_intervention_norm_n
                    / CUFF_TRANSLATIONAL_FORCE_GATE_N,
                    0.0,
                    1.0,
                )
            )
        self.force_severity = severity
        self.alpha_force = 1.0 - severity
        self._set_speed_target(wall_time_s, self.alpha_cmd)
        return ReferenceManagerForceDecision(
            filter_status=status,
            alpha_force=self.alpha_force,
            force_severity=severity,
            brake_required=False,
        )

    def update_from_estimator(
        self,
        wall_time_s: float,
        estimator: Any,
        geometry_diagnostics: dict[str, Any],
        dynamic_diagnostics: dict[str, Any],
    ) -> None:
        self.monitor.update(estimator, geometry_diagnostics, dynamic_diagnostics)
        geometry_model_valid, dynamic_model_valid = _current_model_valid(estimator)
        self.update_from_confidence(
            wall_time_s,
            self.monitor.geometry,
            self.monitor.dynamics,
            geometry_model_valid=geometry_model_valid,
            dynamic_model_valid=dynamic_model_valid,
            geometry_maximum_condition_number=(
                estimator.geometry_identifier.config.maximum_condition_number
            ),
            dynamic_maximum_condition_number=(
                estimator.dynamic_identifier.config.maximum_condition_number
            ),
        )

    def reference(self, wall_time_s: float) -> CuffPoseReference:
        phase, scale, scale_rate = self._clock_state(wall_time_s)
        base = self.base_reference(phase)
        return CuffPoseReference(
            q_rad=base.q_rad.copy(),
            dq_rad_s=scale * base.dq_rad_s,
            ddq_rad_s2=(
                scale**2 * base.ddq_rad_s2 + scale_rate * base.dq_rad_s
            ),
            world_from_cuff=base.world_from_cuff,
        )

    def status(self, wall_time_s: float) -> dict[str, float]:
        phase, scale, scale_rate = self._clock_state(wall_time_s)
        return {
            "reference_phase_time_s": phase,
            "speed_scale": scale,
            "speed_scale_rate_per_s": scale_rate,
            "alpha_cmd": self.alpha_cmd,
            "alpha_trust": self.alpha_trust,
            "alpha_force": self.alpha_force,
            "force_severity": self.force_severity,
            "force_margin_n": self.last_force_margin_n,
            "force_intervention_norm_n": (
                self.last_force_intervention_norm_n
            ),
            "moment_intervention_norm_nm": (
                self.last_moment_intervention_norm_nm
            ),
            "wrench_intervention_coordinate_norm": (
                self.last_wrench_intervention_coordinate_norm
            ),
            "geometry_model_confidence": self.geometry_model_confidence,
            "dynamic_model_confidence": self.dynamic_model_confidence,
            "combined_model_confidence_raw": self.combined_model_confidence_raw,
            "filtered_model_confidence": self.filtered_model_confidence,
            "execution_confidence_high": self.execution_confidence_high,
            "geometry_information_confidence": (
                self.geometry_information_confidence
            ),
            "dynamic_information_confidence": self.dynamic_information_confidence,
            "combined_information_confidence": (
                self.combined_information_confidence
            ),
            # Backward-compatible meaning: the hysteretic confidence actually
            # used by reference execution, not latest-candidate acceptance.
            "geometry_confidence": self.geometry_model_confidence,
            "dynamic_confidence": self.dynamic_model_confidence,
            "combined_confidence": self.execution_confidence_high,
        }

    def summary(self, wall_time_s: float) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "config": self.config.as_dict(),
            "final_status": self.status(wall_time_s),
            "confidence_update_count": self.update_count,
            "latest_geometry_confidence": self.monitor.geometry.to_dict(),
            "latest_dynamic_confidence": self.monitor.dynamics.to_dict(),
            "speed_signal": "min(1, alpha_trust, alpha_force)",
            "rate_limited_speed_output": "s_dot=speed_scale",
            "single_reference_manager": True,
            "path_state": "s=reference_phase_time_s, s_dot=speed_scale",
            "alpha_trust_semantics": (
                "unchanged_filtered_hysteretic_current_model_confidence"
            ),
            "alpha_force_rule": (
                "SAFE_UNCHANGED:1; SAFE_FILTERED:"
                "1-clip(force_intervention_norm_n/force_gate_n,0,1); "
                "FILTER_INFEASIBLE:BRAKE_REQUIRED_without_alpha_update"
            ),
            "last_force_filter_status": self.last_force_filter_status,
            "force_update_count": self.force_update_count,
            "force_filtered_count": self.force_filtered_count,
            "force_infeasible_count": self.force_infeasible_count,
            "time_warp_kinematics": (
                "qdot=q_s*s_dot; qddot=q_ss*s_dot^2+q_s*s_ddot"
            ),
            "information_confidence_affects_speed": False,
            "rejected_candidate_invalidates_current_model": False,
            "estimator_modified": False,
            "mpc_modified": False,
            "safety_limits_modified": False,
            "tube_mpc": False,
        }

    def brake_reentry_checkpoint(self, wall_time_s: float) -> dict[str, Any]:
        """Expose the minimal future re-entry boundary without recovering."""

        phase, speed, acceleration = self._clock_state(wall_time_s)
        return {
            "reference_phase_time_s": phase,
            "reference_phase_rate": speed,
            "reference_phase_acceleration": acceleration,
            "automatic_return_to_track_implemented": False,
            "required_future_boundary": (
                "re-anchor s and s_dot to the stable BRAKE endpoint before TRACK"
            ),
        }


# Backward-compatible import name.  This is an alias, not a second manager.
ReferenceExecutionLayer = UnifiedReferenceManager
