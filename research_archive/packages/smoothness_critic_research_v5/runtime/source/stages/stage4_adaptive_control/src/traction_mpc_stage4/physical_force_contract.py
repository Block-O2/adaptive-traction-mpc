"""Pure physical cuff-force contracts for runtime and offline trace replay.

The transient policy is an opt-in simulation-engineering criterion.  It is not
a clinical safety claim and does not replace the independent 200 N executable
command-force limit.  The canonical runtime policy remains strict by default.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

import numpy as np


STRICT_PHYSICAL_FORCE_V1 = "strict_physical_force_v1"
SIMULATION_ENGINEERING_TRANSIENT_V1 = "simulation_engineering_transient_v1"

STRICT_PASS = "STRICT_PASS"
TRANSIENT_ENGINEERING_QUALIFIED = "TRANSIENT_ENGINEERING_QUALIFIED"
HARD_PHYSICAL_VIOLATION = "HARD_PHYSICAL_VIOLATION"
NUMERICALLY_UNRESOLVED = "NUMERICALLY_UNRESOLVED"

FINE_REPLAY_CONFIRMED = "fine_replay_confirmed"
EXACT_REPLAY_UNAVAILABLE = "exact_replay_unavailable"
RUNTIME_OBSERVATION = "runtime_observation"

RULE_TRANSIENT_CEILING = "absolute_transient_ceiling"
RULE_CONTIGUOUS_DURATION = "maximum_contiguous_duration"
RULE_ROLLING_DURATION = "rolling_100ms_exceedance_duration"
RULE_EXCESS_IMPULSE = "rolling_100ms_excess_impulse"
RULE_TRAILING_MEAN = "causal_trailing_20ms_mean"
RULE_STRICT_SAMPLE = "strict_sample_above_200_n"
STRICT_RUNTIME_ROUNDOFF_TOLERANCE_N = 1.0e-9


@dataclass(frozen=True)
class TransientForceContract:
    continuous_force_reference_n: float = 200.0
    absolute_transient_ceiling_n: float = 220.0
    maximum_contiguous_duration_s: float = 0.005
    rolling_window_s: float = 0.100
    maximum_rolling_exceedance_duration_s: float = 0.005
    maximum_rolling_excess_impulse_ns: float = 0.10
    trailing_mean_window_s: float = 0.020
    maximum_trailing_mean_n: float = 200.0
    diagnostic_mean_window_s: float = 0.005
    numerical_confirmation_peak_n: float = 198.0
    fine_replay_timestep_s: float = 0.00025


TRANSIENT_FORCE_CONTRACT_V1 = TransientForceContract()


def _exceeds(value: float, limit: float) -> bool:
    """Strict comparison with only roundoff-scale equality protection."""

    return bool(value > limit and not np.isclose(value, limit, rtol=0.0, atol=1.0e-12))


@dataclass(frozen=True)
class ForceEvent:
    start_time_s: float
    end_time_s: float
    duration_s: float
    peak_force_n: float
    open_at_trace_end: bool


@dataclass(frozen=True)
class PhysicalForceReport:
    policy_id: str
    classification: str
    mechanical_classification: str
    violated_rule: str | None
    violated_rules: tuple[str, ...]
    runtime_stop_required: bool
    numerical_confirmation_required: bool
    numerical_confirmation: str
    sample_count: int
    start_time_s: float
    end_time_s: float
    peak_force_n: float
    maximum_contiguous_exceedance_duration_s: float
    maximum_rolling_exceedance_duration_s: float
    maximum_rolling_excess_impulse_ns: float
    maximum_causal_trailing_5ms_mean_n: float | None
    maximum_causal_trailing_20ms_mean_n: float | None
    event_count: int
    events: tuple[ForceEvent, ...]
    diagnostics_without_hard_thresholds: dict[str, float | None]

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["simulation_engineering_only_not_clinical_safety"] = True
        return result


def _validated_trace(
    timestamps_s: Iterable[float],
    force: np.ndarray | Iterable[float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    time = np.asarray(tuple(timestamps_s), dtype=float)
    values = np.asarray(force, dtype=float)
    if time.ndim != 1 or not len(time) or not np.all(np.isfinite(time)):
        raise ValueError("timestamps must be a finite nonempty vector")
    if len(time) > 1 and np.any(np.diff(time) <= 0.0):
        raise ValueError("timestamps must be strictly increasing")
    vectors: np.ndarray | None
    if values.ndim == 1:
        if values.shape != time.shape:
            raise ValueError("scalar force must match timestamps")
        norms = values
        vectors = None
    elif values.ndim == 2 and values.shape == (len(time), 3):
        norms = np.linalg.norm(values, axis=1)
        vectors = values
    else:
        raise ValueError("force must be an N-vector of norms or an N by 3 vector")
    if not np.all(np.isfinite(values)) or np.any(norms < 0.0):
        raise ValueError("force must be finite and nonnegative")
    return time, norms, vectors


def _signal_at(time: np.ndarray, values: np.ndarray, query: float) -> float:
    if query <= time[0]:
        return float(values[0])
    if query >= time[-1]:
        return float(values[-1])
    index = int(np.searchsorted(time, query, side="right") - 1)
    fraction = (query - time[index]) / (time[index + 1] - time[index])
    return float(values[index] + fraction * (values[index + 1] - values[index]))


def _threshold_crossings(
    time: np.ndarray, values: np.ndarray, threshold: float
) -> np.ndarray:
    crossings: list[float] = []
    for index in range(len(time) - 1):
        left = values[index] - threshold
        right = values[index + 1] - threshold
        if left * right < 0.0:
            fraction = -left / (right - left)
            crossings.append(float(time[index] + fraction * (time[index + 1] - time[index])))
        elif left == 0.0 and right != 0.0:
            crossings.append(float(time[index]))
        elif right == 0.0 and left != 0.0:
            crossings.append(float(time[index + 1]))
    return np.asarray(sorted(set(crossings)), dtype=float)


def _piecewise_nodes(
    time: np.ndarray,
    values: np.ndarray,
    *,
    threshold: float | None = None,
    excess: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    nodes = time
    if threshold is not None:
        nodes = np.unique(np.concatenate([time, _threshold_crossings(time, values, threshold)]))
    node_values = np.asarray([_signal_at(time, values, item) for item in nodes])
    if excess:
        assert threshold is not None
        node_values = np.maximum(node_values - threshold, 0.0)
    return nodes, node_values


class _PiecewiseLinearIntegral:
    def __init__(self, time: np.ndarray, values: np.ndarray) -> None:
        self.time = time
        self.values = values
        areas = 0.5 * (values[:-1] + values[1:]) * np.diff(time)
        self.prefix = np.concatenate([[0.0], np.cumsum(areas)])

    def value(self, query: float) -> float:
        if query <= self.time[0]:
            return 0.0
        if query >= self.time[-1]:
            return float(self.prefix[-1])
        index = int(np.searchsorted(self.time, query, side="right") - 1)
        dt = query - self.time[index]
        segment_dt = self.time[index + 1] - self.time[index]
        slope = (self.values[index + 1] - self.values[index]) / segment_dt
        return float(self.prefix[index] + self.values[index] * dt + 0.5 * slope * dt**2)

    def values_at(self, query: np.ndarray) -> np.ndarray:
        points = np.asarray(query, dtype=float)
        clipped = np.clip(points, self.time[0], self.time[-1])
        indices = np.searchsorted(self.time, clipped, side="right") - 1
        indices = np.clip(indices, 0, len(self.time) - 2)
        dt = clipped - self.time[indices]
        segment_dt = self.time[indices + 1] - self.time[indices]
        slope = (self.values[indices + 1] - self.values[indices]) / segment_dt
        result = self.prefix[indices] + self.values[indices] * dt + 0.5 * slope * dt**2
        result = np.where(points <= self.time[0], 0.0, result)
        result = np.where(points >= self.time[-1], self.prefix[-1], result)
        return result

    def interval(self, start: float, end: float) -> float:
        return self.value(end) - self.value(start)


def _rolling_integral_maximum(
    nodes: np.ndarray,
    values: np.ndarray,
    window_s: float,
    *,
    require_full_window: bool,
) -> float | None:
    if len(nodes) < 2:
        return None
    start = float(nodes[0])
    end = float(nodes[-1])
    domain_start = start + window_s if require_full_window else start
    if domain_start > end:
        return None
    integral = _PiecewiseLinearIntegral(nodes, values)
    breakpoints = {domain_start, end}
    breakpoints.update(float(item) for item in nodes if domain_start <= item <= end)
    breakpoints.update(
        float(item + window_s)
        for item in nodes
        if domain_start <= item + window_s <= end
    )
    ordered = np.asarray(sorted(breakpoints), dtype=float)
    left = ordered[:-1]
    right = ordered[1:]
    width = right - left
    valid = width > 1.0e-15
    probe_left = left[valid] + 0.25 * width[valid]
    probe_right = left[valid] + 0.75 * width[valid]

    def derivative(points: np.ndarray) -> np.ndarray:
        current = np.interp(points, nodes, values)
        previous = np.interp(points - window_s, nodes, values)
        result = current - previous
        if not require_full_window:
            result = np.where(points < start + window_s, current, result)
        return result

    d_left = derivative(probe_left)
    d_right = derivative(probe_right)
    denominator = probe_right - probe_left
    slopes = np.zeros_like(denominator)
    calculable = denominator > 0.0
    slopes[calculable] = (
        d_right[calculable] - d_left[calculable]
    ) / denominator[calculable]
    roots = np.full_like(probe_left, np.nan)
    nonzero = np.abs(slopes) > 1.0e-15
    roots[nonzero] = probe_left[nonzero] - d_left[nonzero] / slopes[nonzero]
    roots = roots[
        np.isfinite(roots)
        & (roots > left[valid])
        & (roots < right[valid])
    ]
    candidates = np.unique(np.concatenate([ordered, roots]))
    window_start = np.maximum(start, candidates - window_s)
    rolling = integral.values_at(candidates) - integral.values_at(window_start)
    return float(np.max(rolling))


def _events(
    time: np.ndarray, values: np.ndarray, threshold: float
) -> tuple[ForceEvent, ...]:
    if len(time) == 1:
        if values[0] > threshold:
            return (ForceEvent(float(time[0]), float(time[0]), 0.0, float(values[0]), True),)
        return ()
    result: list[ForceEvent] = []
    active_start: float | None = float(time[0]) if values[0] > threshold else None
    active_peak = float(values[0]) if active_start is not None else -np.inf
    for index in range(len(time) - 1):
        t0, t1 = float(time[index]), float(time[index + 1])
        f0, f1 = float(values[index]), float(values[index + 1])
        if active_start is None and f1 > threshold:
            active_start = t0 if f0 == threshold else t0 + (threshold - f0) * (t1 - t0) / (f1 - f0)
            active_peak = f1
        elif active_start is not None:
            active_peak = max(active_peak, f1)
            if f1 <= threshold:
                event_end = t1 if f1 == threshold else t0 + (threshold - f0) * (t1 - t0) / (f1 - f0)
                result.append(
                    ForceEvent(
                        float(active_start),
                        float(event_end),
                        float(event_end - active_start),
                        float(active_peak),
                        False,
                    )
                )
                active_start = None
                active_peak = -np.inf
    if active_start is not None:
        result.append(
            ForceEvent(
                float(active_start),
                float(time[-1]),
                float(time[-1] - active_start),
                float(active_peak),
                True,
            )
        )
    return tuple(result)


def _maximum_rolling_event_duration(
    events: tuple[ForceEvent, ...], start: float, end: float, window_s: float
) -> float:
    if not events:
        return 0.0
    candidates = {start, end}
    for event in events:
        candidates.update((event.start_time_s, event.end_time_s))
        candidates.update((event.start_time_s + window_s, event.end_time_s + window_s))

    def overlap(window_end: float) -> float:
        window_start = max(start, window_end - window_s)
        return sum(
            max(0.0, min(window_end, event.end_time_s) - max(window_start, event.start_time_s))
            for event in events
        )

    return float(max(overlap(item) for item in candidates if start <= item <= end))


def _rate_peak(time: np.ndarray, values: np.ndarray | None) -> float | None:
    if values is None or len(time) < 2:
        return None
    rates = np.diff(values, axis=0) / np.diff(time)[:, None]
    return float(np.max(np.linalg.norm(rates, axis=1)))


def _optional_vector_diagnostics(
    time: np.ndarray,
    force_vectors: np.ndarray | None,
    moment_vectors: np.ndarray | None,
    surface_proxy_n: np.ndarray | None,
) -> dict[str, float | None]:
    if moment_vectors is not None:
        moment_vectors = np.asarray(moment_vectors, dtype=float)
        if moment_vectors.shape != (len(time), 3) or not np.all(np.isfinite(moment_vectors)):
            raise ValueError("moment vectors must be a finite N by 3 array")
    if surface_proxy_n is not None:
        surface_proxy_n = np.asarray(surface_proxy_n, dtype=float)
        if surface_proxy_n.shape != time.shape or not np.all(np.isfinite(surface_proxy_n)):
            raise ValueError("surface proxy must be a finite N-vector")
    return {
        "peak_physical_cuff_moment_nm": (
            None if moment_vectors is None else float(np.max(np.linalg.norm(moment_vectors, axis=1)))
        ),
        "peak_physical_cuff_moment_rate_nm_s": _rate_peak(time, moment_vectors),
        "peak_physical_cuff_force_rate_n_s": _rate_peak(time, force_vectors),
        "peak_surface_proxy_n": (
            None if surface_proxy_n is None else float(np.max(surface_proxy_n))
        ),
    }


def _analyze(
    time: np.ndarray,
    force_norm: np.ndarray,
    *,
    policy_id: str,
    numerical_confirmation: str,
    force_vectors: np.ndarray | None,
    moment_vectors: np.ndarray | None,
    surface_proxy_n: np.ndarray | None,
    contract: TransientForceContract,
) -> PhysicalForceReport:
    if policy_id not in {STRICT_PHYSICAL_FORCE_V1, SIMULATION_ENGINEERING_TRANSIENT_V1}:
        raise ValueError("unknown physical-force policy")
    peak = float(np.max(force_norm))
    events = _events(time, force_norm, contract.continuous_force_reference_n)
    maximum_contiguous = max((item.duration_s for item in events), default=0.0)
    maximum_rolling_duration = _maximum_rolling_event_duration(
        events, float(time[0]), float(time[-1]), contract.rolling_window_s
    )
    if events:
        excess_nodes, excess_values = _piecewise_nodes(
            time,
            force_norm,
            threshold=contract.continuous_force_reference_n,
            excess=True,
        )
        maximum_impulse = _rolling_integral_maximum(
            excess_nodes,
            excess_values,
            contract.rolling_window_s,
            require_full_window=False,
        ) or 0.0
    else:
        maximum_impulse = 0.0
    force_nodes, force_values = _piecewise_nodes(time, force_norm)
    mean_5_integral = _rolling_integral_maximum(
        force_nodes,
        force_values,
        contract.diagnostic_mean_window_s,
        require_full_window=True,
    )
    mean_20_integral = _rolling_integral_maximum(
        force_nodes,
        force_values,
        contract.trailing_mean_window_s,
        require_full_window=True,
    )
    mean_5 = None if mean_5_integral is None else mean_5_integral / contract.diagnostic_mean_window_s
    mean_20 = None if mean_20_integral is None else mean_20_integral / contract.trailing_mean_window_s

    violated: list[str] = []
    if _exceeds(peak, contract.absolute_transient_ceiling_n):
        violated.append(RULE_TRANSIENT_CEILING)
    if _exceeds(maximum_contiguous, contract.maximum_contiguous_duration_s):
        violated.append(RULE_CONTIGUOUS_DURATION)
    if _exceeds(maximum_rolling_duration, contract.maximum_rolling_exceedance_duration_s):
        violated.append(RULE_ROLLING_DURATION)
    if _exceeds(maximum_impulse, contract.maximum_rolling_excess_impulse_ns):
        violated.append(RULE_EXCESS_IMPULSE)
    if mean_20 is not None and _exceeds(mean_20, contract.maximum_trailing_mean_n):
        violated.append(RULE_TRAILING_MEAN)

    strict_exceeded = bool(
        np.any(
            force_norm
            > contract.continuous_force_reference_n
            + STRICT_RUNTIME_ROUNDOFF_TOLERANCE_N
        )
    )
    if policy_id == STRICT_PHYSICAL_FORCE_V1:
        mechanical = HARD_PHYSICAL_VIOLATION if strict_exceeded else STRICT_PASS
        strict_violated = (RULE_STRICT_SAMPLE,) if strict_exceeded else ()
        violated_rules = strict_violated
    else:
        violated_rules = tuple(violated)
        if violated_rules:
            mechanical = HARD_PHYSICAL_VIOLATION
        elif strict_exceeded:
            mechanical = TRANSIENT_ENGINEERING_QUALIFIED
        else:
            mechanical = STRICT_PASS

    confirmation_required = peak >= contract.numerical_confirmation_peak_n or strict_exceeded
    if confirmation_required and numerical_confirmation == EXACT_REPLAY_UNAVAILABLE:
        classification = NUMERICALLY_UNRESOLVED
    elif confirmation_required and numerical_confirmation not in {
        FINE_REPLAY_CONFIRMED,
        RUNTIME_OBSERVATION,
    }:
        classification = NUMERICALLY_UNRESOLVED
    else:
        classification = mechanical
    first_rule = violated_rules[0] if violated_rules else None
    diagnostics = _optional_vector_diagnostics(
        time, force_vectors, moment_vectors, surface_proxy_n
    )
    return PhysicalForceReport(
        policy_id=policy_id,
        classification=classification,
        mechanical_classification=mechanical,
        violated_rule=first_rule,
        violated_rules=violated_rules,
        runtime_stop_required=mechanical == HARD_PHYSICAL_VIOLATION,
        numerical_confirmation_required=confirmation_required,
        numerical_confirmation=numerical_confirmation,
        sample_count=len(time),
        start_time_s=float(time[0]),
        end_time_s=float(time[-1]),
        peak_force_n=peak,
        maximum_contiguous_exceedance_duration_s=float(maximum_contiguous),
        maximum_rolling_exceedance_duration_s=float(maximum_rolling_duration),
        maximum_rolling_excess_impulse_ns=float(maximum_impulse),
        maximum_causal_trailing_5ms_mean_n=mean_5,
        maximum_causal_trailing_20ms_mean_n=mean_20,
        event_count=len(events),
        events=events,
        diagnostics_without_hard_thresholds=diagnostics,
    )


def evaluate_physical_force_trace(
    timestamps_s: Iterable[float],
    force: np.ndarray | Iterable[float],
    *,
    policy_id: str = STRICT_PHYSICAL_FORCE_V1,
    numerical_confirmation: str = EXACT_REPLAY_UNAVAILABLE,
    moment_vectors_nm: np.ndarray | None = None,
    surface_proxy_n: np.ndarray | None = None,
    contract: TransientForceContract = TRANSIENT_FORCE_CONTRACT_V1,
) -> PhysicalForceReport:
    """Evaluate a saved trace with the same pure logic used by the supervisor."""

    time, force_norm, force_vectors = _validated_trace(timestamps_s, force)
    return _analyze(
        time,
        force_norm,
        policy_id=policy_id,
        numerical_confirmation=numerical_confirmation,
        force_vectors=force_vectors,
        moment_vectors=moment_vectors_nm,
        surface_proxy_n=surface_proxy_n,
        contract=contract,
    )


class PhysicalForceSupervisor:
    """Runtime-facing recorder; strict is the unchanged default policy."""

    def __init__(
        self,
        policy_id: str = STRICT_PHYSICAL_FORCE_V1,
        *,
        contract: TransientForceContract = TRANSIENT_FORCE_CONTRACT_V1,
    ) -> None:
        if policy_id not in {STRICT_PHYSICAL_FORCE_V1, SIMULATION_ENGINEERING_TRANSIENT_V1}:
            raise ValueError("unknown physical-force policy")
        self.policy_id = policy_id
        self.contract = contract
        self._time: list[float] = []
        self._force: list[np.ndarray] = []
        self._moment: list[np.ndarray] = []
        self._surface: list[float] = []
        self.stop_required = False
        self.stop_rule: str | None = None

    def update(
        self,
        timestamp_s: float,
        force_vector_n: np.ndarray,
        *,
        moment_vector_nm: np.ndarray | None = None,
        surface_proxy_n: float | None = None,
    ) -> bool:
        """Record one causal sample and return whether runtime must stop now."""

        timestamp = float(timestamp_s)
        force = np.asarray(force_vector_n, dtype=float)
        if not np.isfinite(timestamp) or force.shape != (3,) or not np.all(np.isfinite(force)):
            raise ValueError("runtime timestamp and force must be finite")
        if self._time and timestamp <= self._time[-1]:
            raise ValueError("runtime timestamps must be strictly increasing")
        moment = np.full(3, np.nan) if moment_vector_nm is None else np.asarray(moment_vector_nm, dtype=float)
        if moment.shape != (3,) or (moment_vector_nm is not None and not np.all(np.isfinite(moment))):
            raise ValueError("runtime moment must be a finite 3-vector when supplied")
        surface = np.nan if surface_proxy_n is None else float(surface_proxy_n)
        if surface_proxy_n is not None and not np.isfinite(surface):
            raise ValueError("runtime surface proxy must be finite when supplied")
        self._time.append(timestamp)
        self._force.append(force.copy())
        self._moment.append(moment.copy())
        self._surface.append(surface)

        force_norm = float(np.linalg.norm(force))
        if self.policy_id == STRICT_PHYSICAL_FORCE_V1:
            if (
                force_norm
                > self.contract.continuous_force_reference_n
                + STRICT_RUNTIME_ROUNDOFF_TOLERANCE_N
            ):
                self.stop_required = True
                self.stop_rule = RULE_STRICT_SAMPLE
            return self.stop_required

        # Runtime decisions are made causally at observed samples.  Final trace
        # reporting evaluates continuous rolling-window extrema exactly.
        time = np.asarray(self._time, dtype=float)
        values = np.linalg.norm(np.asarray(self._force), axis=1)
        lookback = max(self.contract.rolling_window_s, self.contract.trailing_mean_window_s)
        start_index = max(0, int(np.searchsorted(time, timestamp - lookback, side="left")) - 1)
        local_time = time[start_index:]
        local_values = values[start_index:]
        if _exceeds(force_norm, self.contract.absolute_transient_ceiling_n):
            self.stop_required = True
            self.stop_rule = RULE_TRANSIENT_CEILING
        local_events = _events(local_time, local_values, self.contract.continuous_force_reference_n)
        if _exceeds(
            max((item.duration_s for item in local_events), default=0.0),
            self.contract.maximum_contiguous_duration_s,
        ):
            self.stop_required = True
            self.stop_rule = self.stop_rule or RULE_CONTIGUOUS_DURATION
        if _maximum_rolling_event_duration(
            local_events, float(local_time[0]), float(local_time[-1]), self.contract.rolling_window_s
        ) > self.contract.maximum_rolling_exceedance_duration_s + 1.0e-12:
            self.stop_required = True
            self.stop_rule = self.stop_rule or RULE_ROLLING_DURATION
        excess_nodes, excess_values = _piecewise_nodes(
            local_time,
            local_values,
            threshold=self.contract.continuous_force_reference_n,
            excess=True,
        )
        excess_integral = _PiecewiseLinearIntegral(excess_nodes, excess_values)
        rolling_start = max(float(local_time[0]), timestamp - self.contract.rolling_window_s)
        if _exceeds(
            excess_integral.interval(rolling_start, timestamp),
            self.contract.maximum_rolling_excess_impulse_ns,
        ):
            self.stop_required = True
            self.stop_rule = self.stop_rule or RULE_EXCESS_IMPULSE
        if timestamp - time[0] >= self.contract.trailing_mean_window_s:
            force_integral = _PiecewiseLinearIntegral(local_time, local_values)
            mean = force_integral.interval(timestamp - self.contract.trailing_mean_window_s, timestamp) / self.contract.trailing_mean_window_s
            if _exceeds(mean, self.contract.maximum_trailing_mean_n):
                self.stop_required = True
                self.stop_rule = self.stop_rule or RULE_TRAILING_MEAN
        return self.stop_required

    def report(
        self, *, numerical_confirmation: str = RUNTIME_OBSERVATION
    ) -> PhysicalForceReport:
        if not self._time:
            raise RuntimeError("cannot report an empty physical-force stream")
        moment = np.asarray(self._moment)
        moment_vectors = None if np.all(np.isnan(moment)) else moment
        if moment_vectors is not None and np.any(np.isnan(moment_vectors)):
            raise ValueError("moment diagnostics must be supplied for every sample or none")
        surface = np.asarray(self._surface)
        surface_values = None if np.all(np.isnan(surface)) else surface
        if surface_values is not None and np.any(np.isnan(surface_values)):
            raise ValueError("surface diagnostics must be supplied for every sample or none")
        return evaluate_physical_force_trace(
            self._time,
            np.asarray(self._force),
            policy_id=self.policy_id,
            numerical_confirmation=numerical_confirmation,
            moment_vectors_nm=moment_vectors,
            surface_proxy_n=surface_values,
            contract=self.contract,
        )
