"""Finite, causal transfer of accepted Human-model control effect.

The accepted model is immediately available to estimation and planning.  Only
its inverse-dynamics *action* is introduced gradually.  Allocation, executable
filtering, loaded supervision, and the physical plant remain downstream.
"""

from __future__ import annotations

import copy
from typing import Any, Callable

import numpy as np


def _signature(model: Any) -> tuple[bytes, bytes, float]:
    beta = np.asarray(model.beta, dtype=float)
    residual = np.asarray(model.residual_weights_nm, dtype=float)
    limit = float(model.residual_limit_nm)
    if (beta.shape != (11,) or residual.shape != (2, 5)
            or not np.all(np.isfinite(beta)) or not np.all(np.isfinite(residual))
            or not np.isfinite(limit) or limit <= 0):
        raise ValueError("accepted Human model has invalid dynamic parameters")
    return beta.tobytes(), residual.tobytes(), limit


class BumplessHumanActionTransfer:
    """One finite transfer; newer accepted updates queue behind its locked target."""

    def __init__(self, initial_model: Any, *, initial_version: str,
                 duration_s: float, small_direct_action_change_nm: float,
                 duration_policy: dict[str, float | str] | None = None,
                 output_envelope: dict[str, float | int] | None = None) -> None:
        if not np.isfinite(duration_s) or duration_s <= 0:
            raise ValueError("duration_s must be positive and finite")
        if not np.isfinite(small_direct_action_change_nm) or small_direct_action_change_nm < 0:
            raise ValueError("small_direct_action_change_nm must be nonnegative and finite")
        _signature(initial_model)
        self.duration_s = float(duration_s)
        self.duration_policy = None if duration_policy is None else dict(duration_policy)
        if self.duration_policy is not None:
            p = self.duration_policy
            if p.get("kind") != "action_gap_scaled_quintic_rate":
                raise ValueError("unknown model-transfer duration policy")
            fields = ("minimum_duration_s", "quintic_max_slope",
                      "conservative_robot_to_human_action_mapping", "engineering_factor",
                      "ordinary_robot_step_max_nm", "robot_step_gate_nm")
            if any(not np.isfinite(float(p[key])) for key in fields):
                raise ValueError("nonfinite model-transfer duration policy")
            if (any(float(p[key]) <= 0 for key in fields)
                    or float(p["robot_step_gate_nm"]) <= float(p["ordinary_robot_step_max_nm"])):
                raise ValueError("invalid model-transfer duration policy")
        self.current_duration_s = self.duration_s
        self.output_envelope = None if output_envelope is None else dict(output_envelope)
        if self.output_envelope is not None:
            keys = ("human_action_step_nm", "desired_force_step_n",
                    "desired_moment_step_nm", "cr12_torque_step_nm",
                    "max_duration_multiplier")
            if any(not np.isfinite(float(self.output_envelope[key]))
                   or float(self.output_envelope[key]) <= 0 for key in keys):
                raise ValueError("invalid control-output envelope")
        self.last_applied_fraction = 0.0
        self.small_direct_action_change_nm = float(small_direct_action_change_nm)
        self.active_model = copy.deepcopy(initial_model)
        self.active_version = str(initial_version)
        self.accepted_model = self.active_model
        self.accepted_version = self.active_version
        self.source_model = self.active_model
        self.source_version = self.active_version
        self.transfer_target_model = self.active_model
        self.transfer_target_version = self.active_version
        self.source_action_offset_nm = np.zeros(2)
        self.start_time_s: float | None = None
        self.last_command_time_s: float | None = None
        self.invalid_reason: str | None = None
        self.events: list[dict[str, Any]] = []
        self.last_record: dict[str, Any] | None = None
        self._previous_output: dict[str, np.ndarray] | None = None
        # The initial model generated the immediately preceding commissioning
        # command.  Later promotions must earn an unchanged TRACK realization.
        self.last_realized_version: str | None = self.active_version

    @property
    def transitioning(self) -> bool:
        return self.start_time_s is not None

    def offer(self, model: Any, *, version: str, time_s: float) -> None:
        """Accept an estimator promotion; invalid candidates fail closed at command."""
        if not np.isfinite(time_s):
            self.invalid_reason = "nonfinite accepted-model timestamp"
            return
        try:
            new_signature = _signature(model)
        except (AttributeError, TypeError, ValueError) as error:
            self.invalid_reason = str(error)
            self.events.append({"event": "REJECTED_INVALID", "time_s": float(time_s),
                                "version": str(version), "reason": self.invalid_reason})
            return
        self.invalid_reason = None
        if new_signature == _signature(self.accepted_model):
            self.accepted_version = str(version)
            self.events.append({"event": "NO_EFFECT_UPDATE", "time_s": float(time_s),
                                "version": str(version)})
            return
        superseded = self.accepted_version if self.transitioning else None
        self.accepted_model = copy.deepcopy(model)
        self.accepted_version = str(version)
        self.events.append({"event": "QUEUED_SUPERSEDE" if self.transitioning else "ACCEPTED",
                            "time_s": float(time_s), "version": str(version),
                            "superseded_version": superseded,
                            "locked_transfer_target_version": (
                                self.transfer_target_version if self.transitioning else None),
                            "transition_start_time_s": self.start_time_s})

    def apply(self, state: np.ndarray, desired_acceleration: np.ndarray,
              accepted_action: np.ndarray, time_s: float,
              *, previous_executed_action_nm: np.ndarray | None = None,
              previous_action_verified: bool = True,
              output_preview: Callable[[np.ndarray], dict[str, np.ndarray]] | None = None,
              previous_executed_output: dict[str, np.ndarray] | None = None) -> np.ndarray:
        """Return the Human action that must enter the existing safety path."""
        if self.invalid_reason is not None:
            raise RuntimeError(f"MODEL_TRANSFER_REJECTED:{self.invalid_reason}")
        if (not np.isfinite(time_s) or
                (self.last_command_time_s is not None and time_s <= self.last_command_time_s - 1e-12)):
            raise RuntimeError("MODEL_TRANSFER_NONCAUSAL_TIMESTAMP")
        x = np.asarray(state, dtype=float)
        a = np.asarray(desired_acceleration, dtype=float)
        target = np.asarray(accepted_action, dtype=float)
        if (x.shape != (4,) or a.shape != (2,) or target.shape != (2,)
                or not np.all(np.isfinite(x)) or not np.all(np.isfinite(a))
                or not np.all(np.isfinite(target))):
            raise ValueError("model-transfer inputs must be finite deployable states/actions")
        expected = np.asarray(self.accepted_model.inverse_dynamics(x[:2], x[2:], a), dtype=float)
        if expected.shape != (2,) or not np.all(np.isfinite(expected)):
            raise ValueError("accepted Human action is invalid")
        if not np.allclose(target, expected, rtol=0, atol=1e-9):
            raise ValueError("execution model differs from accepted transfer target")
        if self.transitioning and not previous_action_verified:
            raise RuntimeError("MODEL_TRANSFER_UNVERIFIED_PREVIOUS_ACTION")
        event = "UNCHANGED"
        if (not self.transitioning and self.active_version != self.accepted_version
                and _signature(self.active_model) == _signature(self.accepted_model)):
            was_realized = self.last_realized_version == self.active_version
            self.active_model = self.accepted_model
            self.active_version = self.accepted_version
            if was_realized:
                self.last_realized_version = self.active_version
            self.events.append({"event": "NO_EFFECT_VERSION_ACTIVE", "time_s": float(time_s),
                                "version": self.active_version})
        wait_for_realization = False
        if not self.transitioning and _signature(self.active_model) != _signature(self.accepted_model):
            source = np.asarray(self.active_model.inverse_dynamics(x[:2], x[2:], a), dtype=float)
            if source.shape != (2,) or not np.all(np.isfinite(source)):
                raise ValueError("retained Human action is invalid")
            if self.last_realized_version != self.active_version:
                wait_for_realization = True
                event = "WAITING_FOR_REALIZATION"
            elif np.linalg.norm(target - source) <= self.small_direct_action_change_nm:
                self.active_model = self.accepted_model
                self.active_version = self.accepted_version
                self.events.append({"event": "DIRECT_SMALL_CHANGE", "time_s": float(time_s),
                                    "version": self.active_version,
                                    "same_state_action_delta_nm": float(np.linalg.norm(target-source))})
                event = "DIRECT_SMALL_CHANGE"
            else:
                if not previous_action_verified:
                    raise RuntimeError("MODEL_TRANSFER_UNVERIFIED_PREVIOUS_ACTION")
                self.source_model = self.active_model
                self.source_version = self.active_version
                if previous_executed_action_nm is None:
                    self.source_action_offset_nm = np.zeros(2)
                else:
                    previous = np.asarray(previous_executed_action_nm, dtype=float)
                    if previous.shape != (2,) or not np.all(np.isfinite(previous)):
                        raise ValueError("previous executed Human action must be finite")
                    self.source_action_offset_nm = previous - source
                    source = previous.copy()
                self.transfer_target_model = self.accepted_model
                self.transfer_target_version = self.accepted_version
                self.start_time_s = float(time_s)
                self.last_applied_fraction = 0.0
                action_gap = float(np.linalg.norm(target-source))
                self.current_duration_s = self.duration_s
                if self.duration_policy is not None:
                    p = self.duration_policy
                    scaled = (float(p["engineering_factor"])
                              * float(p["quintic_max_slope"]) * 0.005
                              * float(p["conservative_robot_to_human_action_mapping"])
                              * action_gap
                              / (float(p["robot_step_gate_nm"])
                                 - float(p["ordinary_robot_step_max_nm"])))
                    self.current_duration_s = max(float(p["minimum_duration_s"]), scaled)
                self.events.append({"event": "START", "time_s": float(time_s),
                                    "source_version": self.source_version,
                                    "target_version": self.accepted_version,
                                    "same_state_action_delta_nm": action_gap,
                                    "duration_s": self.current_duration_s,
                                    "source_action_anchor_offset_nm": self.source_action_offset_nm.copy()})
                event = "START"
        if self.transitioning:
            assert self.start_time_s is not None
            s = float(np.clip((time_s - self.start_time_s) / self.current_duration_s, 0.0, 1.0))
            fraction = 10.0*s**3 - 15.0*s**4 + 6.0*s**5
            source = (np.asarray(self.source_model.inverse_dynamics(x[:2], x[2:], a), dtype=float)
                      + self.source_action_offset_nm)
            locked_target = np.asarray(
                self.transfer_target_model.inverse_dynamics(x[:2], x[2:], a), dtype=float
            )
            if locked_target.shape != (2,) or not np.all(np.isfinite(locked_target)):
                raise ValueError("locked transfer target action is invalid")
            fraction = max(self.last_applied_fraction, fraction)
            if self.output_envelope is not None:
                if output_preview is None or previous_executed_output is None:
                    raise RuntimeError("MODEL_TRANSFER_OUTPUT_PREVIEW_UNAVAILABLE")
                fractions = np.asarray([self.last_applied_fraction, fraction])
                actions = (source[np.newaxis, :]
                           + fractions[:, np.newaxis]
                           * (locked_target-source)[np.newaxis, :])
                preview = output_preview(actions)
                gate_fields = (
                    ("action", "human_action_step_nm", actions),
                    ("force", "desired_force_step_n", preview["force"]),
                    ("moment", "desired_moment_step_nm", preview["moment"]),
                    ("torque", "cr12_torque_step_nm", preview["torque"]),
                )
                lower_lambda, upper_lambda = 0.0, 1.0
                endpoint_steps = {}
                for name, gate, values in gate_fields:
                    array = np.asarray(values, dtype=float)
                    predecessor = np.asarray(previous_executed_output[name], dtype=float)
                    if array.shape != (2, len(predecessor)) or not np.all(np.isfinite(array)):
                        raise RuntimeError("MODEL_TRANSFER_INVALID_OUTPUT_PREVIEW")
                    origin = array[0] - predecessor
                    direction = array[1] - array[0]
                    endpoint_steps[name] = [float(np.linalg.norm(origin)),
                                            float(np.linalg.norm(array[1]-predecessor))]
                    quadratic = float(direction @ direction)
                    linear = float(2.0 * origin @ direction)
                    constant = float(origin @ origin - float(self.output_envelope[gate])**2)
                    if quadratic <= 1e-24:
                        if constant > 1e-10:
                            self.events.append({"event": "OUTPUT_ENVELOPE_INFEASIBLE",
                                                "time_s": float(time_s),
                                                "gate": name,
                                                "endpoint_steps": endpoint_steps})
                            raise RuntimeError("MODEL_TRANSFER_NO_OUTPUT_CONTINUOUS_ACTION")
                        continue
                    discriminant = linear**2 - 4.0*quadratic*constant
                    if discriminant < -1e-10:
                        self.events.append({"event": "OUTPUT_ENVELOPE_INFEASIBLE",
                                            "time_s": float(time_s),
                                            "gate": name,
                                            "endpoint_steps": endpoint_steps})
                        raise RuntimeError("MODEL_TRANSFER_NO_OUTPUT_CONTINUOUS_ACTION")
                    root = float(np.sqrt(max(0.0, discriminant)))
                    lower_lambda = max(lower_lambda, (-linear-root)/(2.0*quadratic))
                    upper_lambda = min(upper_lambda, (-linear+root)/(2.0*quadratic))
                if upper_lambda < lower_lambda - 1e-10 or upper_lambda < 0:
                    self.events.append({"event": "OUTPUT_ENVELOPE_INFEASIBLE",
                                        "time_s": float(time_s),
                                        "gate": "INTERSECTION",
                                        "endpoint_steps": endpoint_steps,
                                        "feasible_lambda_interval": [lower_lambda, upper_lambda]})
                    raise RuntimeError("MODEL_TRANSFER_NO_OUTPUT_CONTINUOUS_ACTION")
                chosen_lambda = float(np.clip(upper_lambda, 0.0, 1.0))
                if chosen_lambda < 1.0:
                    chosen_lambda = max(0.0, chosen_lambda - 1e-7)
                fraction = float(fractions[0] + chosen_lambda * (fractions[1]-fractions[0]))
                selected_action = ((1.0-fraction)*source + fraction*locked_target)
                selected_preview = output_preview(selected_action[np.newaxis, :])
                for name, gate, _ in gate_fields:
                    selected = (selected_action if name == "action" else
                                np.asarray(selected_preview[name][0], dtype=float))
                    if np.linalg.norm(selected-np.asarray(previous_executed_output[name])) > (
                            float(self.output_envelope[gate]) + 1e-8):
                        raise RuntimeError("MODEL_TRANSFER_PREVIEW_NONLINEAR_OR_INCONSISTENT")
                self._previous_output = {
                    name: np.asarray(previous_executed_output[name], dtype=float).copy()
                    for name in ("action", "force", "moment", "torque")
                }
                if (time_s - self.start_time_s
                        > float(self.output_envelope["max_duration_multiplier"])
                        * self.current_duration_s + 1e-12
                        and fraction < 1.0-1e-12):
                    raise RuntimeError("MODEL_TRANSFER_OUTPUT_ENVELOPE_DEADLINE")
            actual = (1.0-fraction)*source + fraction*locked_target
            self.last_applied_fraction = fraction
            if fraction >= 1.0 - 1e-12:
                self.active_model = self.transfer_target_model
                self.active_version = self.transfer_target_version
                self.start_time_s = None
                self.events.append({"event": "COMPLETE", "time_s": float(time_s),
                                    "version": self.active_version,
                                    "queued_latest_version": self.accepted_version})
                actual = locked_target.copy()
                fraction = 1.0
                event = "COMPLETE"
            elif event != "START":
                event = "TRANSFERRING"
        else:
            if wait_for_realization:
                actual = source.copy()
                locked_target = source.copy()
            else:
                source = target.copy()
                locked_target = target.copy()
                actual = target.copy()
            fraction = 1.0
        self.last_command_time_s = float(time_s)
        self.last_record = {
            "event": event, "time_s": float(time_s), "fraction_new": float(fraction),
            "transition_duration_s": self.current_duration_s,
            "output_envelope_active": self.output_envelope is not None and event in {
                "START", "TRANSFERRING", "COMPLETE"},
            "transitioning": self.transitioning,
            "source_version": self.source_version if self.transitioning else self.active_version,
            "accepted_version": self.accepted_version,
            "locked_target_version": self.transfer_target_version,
            "fully_active_version": self.active_version,
            "source_action_nm": source.copy(), "accepted_action_nm": target.copy(),
            "locked_target_action_nm": locked_target.copy(),
            "applied_action_nm": actual.copy(),
            "same_state_action_gap_nm": float(np.linalg.norm(locked_target-source)),
            "realized_track": False,
        }
        return actual.copy()

    def note_execution(self, mode: str, robot_torque_nm: np.ndarray, *,
                       actuation_enabled: bool, filter_unchanged: bool,
                       torque_unsaturated: bool,
                       desired_force_n: np.ndarray | None = None,
                       desired_moment_nm: np.ndarray | None = None) -> None:
        if self.last_record is None:
            raise RuntimeError("model transfer was not evaluated before execution")
        torque = np.asarray(robot_torque_nm, dtype=float)
        self.last_record["safety_mode"] = str(mode)
        self.last_record["robot_torque_nm"] = torque.copy()
        self.last_record["filter_unchanged"] = bool(filter_unchanged)
        self.last_record["torque_unsaturated"] = bool(torque_unsaturated)
        if self.last_record["output_envelope_active"] and mode == "TRACK":
            if (self._previous_output is None or desired_force_n is None
                    or desired_moment_nm is None):
                raise RuntimeError("MODEL_TRANSFER_OUTPUT_CHECK_UNAVAILABLE")
            current = {
                "action": np.asarray(self.last_record["applied_action_nm"], dtype=float),
                "force": np.asarray(desired_force_n, dtype=float),
                "moment": np.asarray(desired_moment_nm, dtype=float),
                "torque": torque,
            }
            gates = {"action": "human_action_step_nm", "force": "desired_force_step_n",
                     "moment": "desired_moment_step_nm", "torque": "cr12_torque_step_nm"}
            steps = {
                name: float(np.linalg.norm(value-self._previous_output[name]))
                for name, value in current.items()
            }
            self.last_record["actual_output_step"] = steps
            if any(steps[name] > float(self.output_envelope[gate])+1e-10
                   for name, gate in gates.items()):
                raise RuntimeError("MODEL_TRANSFER_OUTPUT_STEP_LIMIT")
        realized = bool(actuation_enabled and mode == "TRACK" and filter_unchanged
                        and torque_unsaturated and self.last_record["fraction_new"] == 1.0)
        self.last_record["realized_track"] = realized
        if realized and self.last_realized_version != self.active_version:
            self.last_realized_version = self.active_version
            self.events.append({"event": "FULLY_REALIZED", "time_s": self.last_command_time_s,
                                "version": self.active_version})

    def snapshot(self) -> dict[str, Any] | None:
        if self.last_record is None:
            return None
        result = dict(self.last_record)
        for name in ("source_action_nm", "accepted_action_nm", "locked_target_action_nm",
                     "applied_action_nm", "robot_torque_nm"):
            if name in result:
                result[name] = result[name].copy()
        return result
