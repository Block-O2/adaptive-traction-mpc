"""Deployable hard-table envelope checks for planned Human/cuff references.

Only calibrated collider dimensions, effective geometry and causal cuff
observations are permitted here. No physical Human truth or hidden case enters.
The old scientific model and dynamics update laws are not modified.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any

import numpy as np

from traction_mpc_stage3.coupled import (
    BED_HEIGHT_M, SHANK_RADIUS_M, THIGH_RADIUS_M,
    SLEEVE_HALF_LENGTH_M, SLEEVE_OUTER_RADIUS_M,
)
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry

from ..geometry import STAGE5_GEOMETRY
from ..human_waypoint_scheduler import _quintic_coefficients


def _cylinder_gap(a_z: np.ndarray, b_z: np.ndarray,
                  axis_z: np.ndarray, radius_m: float) -> np.ndarray:
    radial_z = radius_m * np.sqrt(np.maximum(0.0, 1.0 - axis_z**2))
    return np.minimum(a_z, b_z) - radial_z - BED_HEIGHT_M


@dataclass(frozen=True)
class RigidTableReferenceEnvelopeV1:
    """Model-predicted limb/tool margins; not an oracle collision detector."""

    geometry: PlanarCuffGeometry
    shank_length_upper_m: float = 0.46
    existing_shank_margin_m: float = 0.001
    registered_proximal_installation_gap_lower_m: float = 0.0001
    sample_count: int = 1201
    cuff_reference_translation_world_m: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        if self.shank_length_upper_m <= 0 or self.sample_count < 2:
            raise ValueError("invalid envelope sampling configuration")
        offset = np.asarray(self.cuff_reference_translation_world_m, dtype=float)
        if offset.shape != (3,) or not np.all(np.isfinite(offset)):
            raise ValueError("cuff reference translation must be finite")

    def with_causal_cuff_reference_origin(
        self, q_hat: np.ndarray, cuff_position_world_m: np.ndarray, *,
        state_sample_time_s: float, interface_sample_time_s: float,
        current_time_s: float,
    ) -> "RigidTableReferenceEnvelopeV1":
        """Align only the tool-reference center using the existing observer.

        This constant prediction offset does not identify or move hip/knee
        geometry. The caller freezes it once for commissioning; fitted-model
        recovery constructs a new envelope without this offset.
        """
        times = np.asarray([state_sample_time_s, interface_sample_time_s, current_time_s])
        if (not np.all(np.isfinite(times))
                or abs(state_sample_time_s-interface_sample_time_s) > 1e-12
                or current_time_s-state_sample_time_s < -1e-12
                or current_time_s-state_sample_time_s > .100):
            raise ValueError("cuff reference origin requires aligned causal current samples")
        measured = np.asarray(cuff_position_world_m, dtype=float)
        q = np.asarray(q_hat, dtype=float)
        if q.shape != (2,) or measured.shape != (3,) or not np.all(np.isfinite(measured)):
            raise ValueError("invalid causal cuff reference origin")
        delta = measured-self.cuff_centers(q)[0]
        offset = np.asarray(self.cuff_reference_translation_world_m)+delta
        return replace(self, cuff_reference_translation_world_m=tuple(float(x) for x in offset))

    def anchored_to_observation(self, q_hat: np.ndarray,
                                cuff_position_world_m: np.ndarray) -> "RigidTableReferenceEnvelopeV1":
        """Translate the prior to a measured cuff center, without hidden q."""
        predicted = self.cuff_centers(np.asarray(q_hat, dtype=float))[0]
        measured = np.asarray(cuff_position_world_m, dtype=float)
        if measured.shape != (3,) or not np.all(np.isfinite(measured)):
            raise ValueError("causal cuff position must be a finite world three-vector")
        shifted = replace(self.geometry,
                          origin_world_m=np.asarray(self.geometry.origin_world_m)
                          + measured - predicted)
        return replace(self, geometry=shifted)

    def cuff_centers(self, q: np.ndarray) -> np.ndarray:
        rows = np.atleast_2d(np.asarray(q, dtype=float))
        if rows.shape[1] != 2 or not np.all(np.isfinite(rows)):
            raise ValueError("q must be finite (N,2)")
        phi = rows[:, 0] - rows[:, 1]
        g = self.geometry
        hip = (np.asarray(g.origin_world_m)[None, :]
               + g.hip_plane_m[0] * g.plane_x_world[None, :]
               + g.hip_plane_m[1] * g.plane_z_world[None, :])
        thigh = (np.cos(rows[:, 0, None]) * g.plane_x_world[None, :]
                 + np.sin(rows[:, 0, None]) * g.plane_z_world[None, :])
        shank = (np.cos(phi[:, None]) * g.plane_x_world[None, :]
                 + np.sin(phi[:, None]) * g.plane_z_world[None, :])
        return (hip + g.thigh_length_m * thigh + g.cuff_distance_m * shank
                + np.asarray(self.cuff_reference_translation_world_m))

    def margins(self, q: np.ndarray) -> dict[str, np.ndarray]:
        rows = np.atleast_2d(np.asarray(q, dtype=float))
        if rows.shape[1] != 2 or not np.all(np.isfinite(rows)):
            raise ValueError("q must be finite (N,2)")
        g = self.geometry
        phi = rows[:, 0] - rows[:, 1]
        px_z = float(g.plane_x_world[2])
        pz_z = float(g.plane_z_world[2])
        hip_z = (float(g.origin_world_m[2])
                 + g.hip_plane_m[0] * px_z + g.hip_plane_m[1] * pz_z)
        thigh_axis_z = np.cos(rows[:, 0]) * px_z + np.sin(rows[:, 0]) * pz_z
        shank_axis_z = np.cos(phi) * px_z + np.sin(phi) * pz_z
        knee_z = hip_z + g.thigh_length_m * thigh_axis_z
        ankle_z = knee_z + self.shank_length_upper_m * shank_axis_z
        cuff_z = (knee_z + g.cuff_distance_m * shank_axis_z
                  + self.cuff_reference_translation_world_m[2])
        sleeve_a_z = cuff_z - SLEEVE_HALF_LENGTH_M * shank_axis_z
        sleeve_b_z = cuff_z + SLEEVE_HALF_LENGTH_M * shank_axis_z
        bar_half = 0.5 * STAGE5_GEOMETRY.cuff_bar_length_m
        bar_a_z = cuff_z - bar_half * shank_axis_z
        bar_b_z = cuff_z + bar_half * shank_axis_z
        # The registered cuff bar is collinear with the provisional shank
        # axis; the sleeve is separately checked although collision-disabled.
        # The fitted effective hip is a control parameter, not a certified
        # anatomical collider transform. The versioned setup generator has
        # already required a positive fixed proximal installation gap. In
        # the registered nonnegative q1 domain, knee height cannot be below
        # the fixed hip, so this structural bound is the deployable guarantee.
        proximal_gap = (np.full(len(rows), self.registered_proximal_installation_gap_lower_m)
                         if (np.all(rows[:, 0] >= 0.0)
                             and np.all(rows[:, 0] <= math.pi)
                             and abs(px_z) < 1e-9
                             and pz_z > 0.0)
                         else np.minimum(hip_z, knee_z)
                         - THIGH_RADIUS_M - BED_HEIGHT_M)
        result = {
            "proximal_thigh_m": proximal_gap,
            "distal_shank_m": np.minimum(knee_z, ankle_z)
                - SHANK_RADIUS_M - BED_HEIGHT_M - self.existing_shank_margin_m,
            "sleeve_m": _cylinder_gap(sleeve_a_z, sleeve_b_z,
                                      shank_axis_z, SLEEVE_OUTER_RADIUS_M),
            "cuff_bar_m": _cylinder_gap(bar_a_z, bar_b_z,
                                        shank_axis_z, STAGE5_GEOMETRY.cuff_bar_radius_m),
        }
        # The adapter is a calibrated rigid cylinder between the cuff and
        # provisional flange; its orientation follows the cuff/shank frame.
        cuff_frame_z_axis_z = -np.sin(phi) * px_z + np.cos(phi) * pz_z
        cuff_frame_y_axis_z = float(np.cross(g.plane_z_world, g.plane_x_world)[2])
        e_from_c = STAGE5_GEOMETRY.end_effector_from_cuff
        t = np.asarray(e_from_c.translation, dtype=float)
        connector_length = max(0.0, float(np.linalg.norm(t)) - SLEEVE_OUTER_RADIUS_M)
        if connector_length > 0.0:
            tool_offset_in_cuff = np.asarray(e_from_c.rotation).T @ t
            e_to_c_z = (shank_axis_z * tool_offset_in_cuff[0]
                        + cuff_frame_y_axis_z * tool_offset_in_cuff[1]
                        + cuff_frame_z_axis_z * tool_offset_in_cuff[2])
            flange_z = cuff_z - e_to_c_z
            connector_z = flange_z + connector_length / np.linalg.norm(t) * e_to_c_z
            connector_axis_z = e_to_c_z / np.linalg.norm(t)
            result["cuff_adapter_m"] = _cylinder_gap(
                flange_z, connector_z, connector_axis_z, 0.018)
        else:
            result["cuff_adapter_m"] = cuff_z - 0.018 - BED_HEIGHT_M
        return result

    def measured_sleeve_gap(self, cuff_position_world_m: np.ndarray,
                            cuff_rotation_world: np.ndarray) -> float:
        center = np.asarray(cuff_position_world_m, dtype=float)
        rotation = np.asarray(cuff_rotation_world, dtype=float)
        if center.shape != (3,) or rotation.shape != (3, 3):
            raise ValueError("invalid causal cuff pose")
        axis_z = float(rotation[2, 0])
        return float(center[2] - SLEEVE_HALF_LENGTH_M * abs(axis_z)
                     - SLEEVE_OUTER_RADIUS_M * math.sqrt(max(0.0, 1.0 - axis_z**2))
                     - BED_HEIGHT_M)

    def check_quintic(self, coefficients: np.ndarray, duration_s: float) -> dict[str, Any]:
        """Sample a C2 segment; include a conservative inter-sample bound."""
        c = np.asarray(coefficients, dtype=float)
        if c.shape != (2, 6) or duration_s <= 0:
            raise ValueError("invalid quintic segment")
        s = np.linspace(0.0, 1.0, self.sample_count)
        powers = np.stack([s**i for i in range(6)])
        q = (c @ powers).T
        margins = self.margins(q)
        g = self.geometry
        # Polynomial derivative extrema give a true global Lipschitz bound
        # between the nearest grid point and any unsampled point. The normal
        # 1201-node grid is cheap but is not misrepresented as exact geometry.
        def derivative_max(coef: np.ndarray) -> float:
            deriv = np.polynomial.polynomial.polyder(coef)
            accel = np.polynomial.polynomial.polyder(deriv)
            roots = np.polynomial.polynomial.polyroots(accel)
            inside = [float(root.real) for root in roots
                      if abs(float(root.imag)) < 1e-10 and 0.0 <= float(root.real) <= 1.0]
            return max(abs(float(np.polynomial.polynomial.polyval(t, deriv)))
                       for t in (0.0, 1.0, *inside))

        max_q1_deriv = derivative_max(c[0])
        max_phi_deriv = derivative_max(c[0] - c[1])
        half_cell = 0.5 / (self.sample_count - 1)
        thigh_bound = half_cell * g.thigh_length_m * max_q1_deriv
        limb_bound = half_cell * (
            g.thigh_length_m * max_q1_deriv
            + (self.shank_length_upper_m + SLEEVE_OUTER_RADIUS_M)
            * max_phi_deriv)
        # On a segment where the knee stays above the hip, the proximal
        # capsule's support point is the fixed hip, so its gap is constant.
        hip = (np.asarray(g.origin_world_m)
               + g.hip_plane_m[0] * g.plane_x_world
               + g.hip_plane_m[1] * g.plane_z_world)
        knee_z = (hip[2] + g.thigh_length_m * (
            np.cos(q[:, 0]) * g.plane_x_world[2]
            + np.sin(q[:, 0]) * g.plane_z_world[2]))
        # The knee stays above the fixed hip throughout 0 <= q1 <= pi,
        # including the High-ROM range beyond 90 deg. Check polynomial
        # extrema, not just grid nodes, before using the structural gap.
        q1_derivative = np.polynomial.polynomial.polyder(c[0])
        q1_roots = np.polynomial.polynomial.polyroots(q1_derivative)
        q1_extrema = [0.0, 1.0, *(float(r.real) for r in q1_roots
            if abs(float(r.imag)) < 1e-10 and 0.0 <= float(r.real) <= 1.0)]
        q1_values = [float(np.polynomial.polynomial.polyval(t, c[0])) for t in q1_extrema]
        if (min(q1_values) >= 0.0 and max(q1_values) <= math.pi
                and abs(float(g.plane_x_world[2])) < 1e-9
                and float(g.plane_z_world[2]) > 0.0):
            thigh_bound = 0.0
        elif float(np.min(knee_z - hip[2])) - thigh_bound >= 0.0:
            thigh_bound = 0.0
        minima = {name: float(np.min(value)) for name, value in margins.items()}
        lower = {name: value - (thigh_bound if name == "proximal_thigh_m"
                                else limb_bound) for name, value in minima.items()}
        return {"feasible": bool(all(value >= -1e-9 for value in lower.values())),
                "minimum_sampled_m": minima,
                "conservative_continuous_lower_m": lower,
                "adjacent_lipschitz_bound_m": limb_bound,
                "sample_count": self.sample_count,
                "duration_s": float(duration_s)}


def choose_feedback_commissioning_target(
    *, envelope: RigidTableReferenceEnvelopeV1,
    reference_origin_q_rad: np.ndarray,
    estimated_current_q_rad: np.ndarray,
    prescribed_previous_q_rad: np.ndarray,
    prescribed_next_q_rad: np.ndarray,
    q_bounds_rad: Any,
    velocity_limits_rad_s: Any,
    acceleration_limits_rad_s2: Any,
    duration_s: float,
    final_return: bool,
) -> dict[str, Any]:
    """Retain an informative prescribed change, projecting only if needed.

    The fresh estimated state changes the target, while the *emitted* prior
    reference remains the C2 origin. No true Human state or hidden geometry
    participates. A one-dimensional hip lift is the smallest local repair for
    a shank-downward waypoint in the registered sagittal q domain.
    """
    origin = np.asarray(reference_origin_q_rad, dtype=float)
    current = np.asarray(estimated_current_q_rad, dtype=float)
    prescribed_previous = np.asarray(prescribed_previous_q_rad, dtype=float)
    prescribed_next = np.asarray(prescribed_next_q_rad, dtype=float)
    bounds = np.asarray(q_bounds_rad, dtype=float)
    velocity = np.asarray(velocity_limits_rad_s, dtype=float)
    acceleration = np.asarray(acceleration_limits_rad_s2, dtype=float)
    if any(array.shape != (2,) for array in (origin, current, prescribed_previous,
                                             prescribed_next, velocity, acceleration)):
        raise ValueError("commissioning vectors must be 2-D")
    if bounds.shape != (2, 2) or duration_s <= 0:
        raise ValueError("invalid commissioning bounds/duration")
    if not np.all(np.isfinite(np.r_[origin, current, prescribed_previous,
                                     prescribed_next, velocity, acceleration])):
        raise ValueError("nonfinite commissioning input")
    attempted: list[dict[str, Any]] = []
    fractions = (1.0,) if final_return else (1.0, 0.75, 0.5, 0.25)
    for fraction in fractions:
        desired = (prescribed_next.copy() if final_return else
                   current + fraction * (prescribed_next - prescribed_previous))
        desired[1] = min(max(desired[1], bounds[1, 0]), bounds[1, 1])
        if (float(envelope.margins(origin)["distal_shank_m"][0]) < 0.0
                and desired[0] > origin[0]):
            # Preserve or raise the shank angle during a prior-supported
            # clearance escape; tiny state-estimation offsets must not make
            # an otherwise coordinated lift lower the ankle.
            desired[1] = min(desired[1], desired[0] - (origin[0] - origin[1]))

        def assess(target: np.ndarray) -> dict[str, Any]:
            if np.any(target < bounds[:, 0] - 1e-12) or np.any(target > bounds[:, 1] + 1e-12):
                return {"feasible": False, "reason": "registered ROM bounds"}
            delta = np.abs(target - origin)
            # Quintic with zero endpoint velocity/acceleration has max
            # normalized velocity 1.875 and acceleration 10/sqrt(3)/?;
            # use a conservative 6.0 coefficient for acceleration.
            if np.any(1.875 * delta / duration_s > velocity + 1e-12):
                return {"feasible": False, "reason": "registered velocity limit"}
            if np.any(6.0 * delta / duration_s**2 > acceleration + 1e-12):
                return {"feasible": False, "reason": "registered acceleration limit"}
            coefficients = _quintic_coefficients(
                origin, np.zeros(2), target, np.zeros(2), duration_s)
            result = envelope.check_quintic(coefficients, duration_s)
            if not result["feasible"]:
                lower = result["conservative_continuous_lower_m"]
                only_shank = (lower["distal_shank_m"] < 0.0 and
                              all(value >= -1e-9 for name, value in lower.items()
                                  if name != "distal_shank_m"))
                g = envelope.geometry
                phi_origin = origin[0] - origin[1]
                phi_target = target[0] - target[1]
                # A structural upper-length prior can pessimistically put
                # the ankle below the support even when the measured cuff
                # and sleeve are clear. Permit *only* a geometrically
                # monotone escape: q1 and phi both rise in the upright
                # sagittal quadrant, so knee and ankle heights cannot fall.
                # This is not allowed in the task/recovery planner.
                escape = bool(
                    only_shank and lower["distal_shank_m"] < 0.0
                    and target[0] >= origin[0] - 1e-12
                    and phi_target >= phi_origin - 1e-12
                    and 0.0 <= origin[0] <= target[0] <= math.pi / 2
                    and -math.pi / 2 <= phi_origin <= phi_target <= math.pi / 2
                    and abs(float(g.plane_x_world[2])) < 1e-9
                    and float(g.plane_z_world[2]) > 0.0
                    and float(envelope.margins(target)["distal_shank_m"][0])
                    > float(envelope.margins(origin)["distal_shank_m"][0]) + 1e-9
                )
                if escape:
                    result["feasible"] = True
                    result["conservative_nonworsening_shank_escape"] = True
            return {**result, "coefficients": coefficients}

        initial = assess(desired)
        attempted.append({"fraction": fraction, "hip_lift_rad": 0.0,
                          "target_q_rad": desired.tolist(),
                          "feasible": initial["feasible"],
                          "reason": initial.get("reason"),
                          "margins": initial.get("conservative_continuous_lower_m")})
        if initial["feasible"]:
            return {"feasible": True, "target_q_rad": desired,
                    "coefficients": initial["coefficients"], "path": initial,
                    "selected_fraction": fraction, "hip_lift_rad": 0.0,
                    "attempts": attempted}
        # Search a monotone hip-upward direction only inside the registered
        # q range. If even the upper bound fails, shrink the intended motion
        # with each rejection visible; never silently skip a segment.
        reachable_upper = min(
            bounds[0, 1],
            origin[0] + velocity[0] * duration_s / 1.875,
            origin[0] + acceleration[0] * duration_s**2 / 6.0,
        )
        if desired[0] >= reachable_upper - 1e-12:
            continue
        raised = desired.copy()
        raised[0] = reachable_upper
        upper = assess(raised)
        attempted.append({"fraction": fraction,
                          "hip_lift_rad": float(raised[0] - desired[0]),
                          "target_q_rad": raised.tolist(),
                          "feasible": upper["feasible"],
                          "reason": upper.get("reason"),
                          "margins": upper.get("conservative_continuous_lower_m")})
        if not upper["feasible"]:
            continue
        low, high = float(desired[0]), float(raised[0])
        # Bisection is applied only after the full upper-bound path passes;
        # every final accepted path is independently rechecked.
        for _ in range(18):
            mid = 0.5 * (low + high)
            trial = desired.copy()
            trial[0] = mid
            result = assess(trial)
            if result["feasible"]:
                high = mid
            else:
                low = mid
        selected = desired.copy()
        selected[0] = high
        confirmed = assess(selected)
        if confirmed["feasible"]:
            attempted.append({"fraction": fraction,
                              "hip_lift_rad": high - float(desired[0]),
                              "target_q_rad": selected.tolist(),
                              "feasible": True,
                              "margins": confirmed["conservative_continuous_lower_m"]})
            return {"feasible": True, "target_q_rad": selected,
                    "coefficients": confirmed["coefficients"], "path": confirmed,
                    "selected_fraction": fraction,
                    "hip_lift_rad": high - float(desired[0]),
                    "attempts": attempted}
    return {"feasible": False, "reason": "NO_RIGID_TABLE_FEASIBLE_COMMISSIONING_SEGMENT",
            "attempts": attempted}


@dataclass(frozen=True)
class CombinedRigidTableClearanceV1:
    """Retain the old shank margin and add calibrated envelope restrictions."""

    shank_contract: Any
    envelope: RigidTableReferenceEnvelopeV1
    use_monotonic_certificate: bool = False

    def __post_init__(self) -> None:
        if (self.shank_contract.geometry is not self.envelope.geometry
                or self.shank_contract.shank_length_upper_m != self.envelope.shank_length_upper_m
                or self.shank_contract.margin_m != self.envelope.existing_shank_margin_m):
            raise ValueError("combined shank/envelope must share one session geometry and margin")

    def __call__(self, q: np.ndarray) -> np.ndarray | float:
        return self.evaluate(q)

    def evaluate(self, q: np.ndarray) -> np.ndarray | float:
        rows = np.asarray(q, dtype=float)
        existing = np.atleast_1d(np.asarray(self.shank_contract.evaluate(rows), dtype=float))
        margins = self.envelope.margins(rows)
        result = np.minimum.reduce([existing, *margins.values()])
        return float(result[0]) if rows.ndim == 1 else result

    def certified_minimum(self, coefficients: np.ndarray, duration_s: float) -> float:
        """Conservative continuous minimum for the same combined geometry.

        The retained shank contract and envelope distal-shank formula are
        identical by the constructor invariant. The envelope's derivative
        bound therefore also certifies the retained shank component.
        """
        certificate = self.envelope.check_quintic(coefficients, duration_s)
        lower = certificate["conservative_continuous_lower_m"]
        proof = {"general_certificate":certificate}
        if self.use_monotonic_certificate:
            from .monotonic_clearance import monotonic_certificate
            specialized = monotonic_certificate(self.envelope, coefficients)
            proof["monotonic_certificate"] = specialized
            lower = {key:max(value, specialized["lowers"].get(key, -np.inf)) for key,value in lower.items()}
        if not all(np.isfinite(v) for v in lower.values()):
            raise ValueError("nonfinite continuous lower bound")
        proof["combined_body_lowers_m"] = dict(lower)
        object.__setattr__(self, "last_certificate", proof)
        return float(min(lower.values()))

    def record(self) -> dict[str, Any]:
        return {"schema": "dev_d_combined_rigid_table_clearance_v1",
                "common_progress_monotonic_certificate":self.use_monotonic_certificate,
                "existing_shank_contract": self.shank_contract.record(),
                "additional_checked_bodies": ["proximal_thigh", "distal_shank",
                                              "sleeve", "cuff_bar", "cuff_adapter"],
                "sleeve_collision_pair_disabled_in_plant": True,
                "geometry_source": "CAUSAL_ACCEPTED_EFFECTIVE_GEOMETRY_AND_CALIBRATED_TOOL",
                "proximal_thigh_source": "REGISTERED_POSITIVE_GAP_INSTALLATION_CONTRACT",
                "hidden_geometry_consumed": False}
