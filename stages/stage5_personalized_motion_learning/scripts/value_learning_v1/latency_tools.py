"""Opt-in descriptive high-level latency accounting; never a safety certificate.

All spans use one monotonic nanosecond clock. Record the observation epoch at
the caller, not at model inference. Candidate admission and reference activation
are separate events. In Scientific Simulation host time is profiling only.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import math
from time import perf_counter_ns
from typing import Callable


PIPELINE_STAGES = (
    "feature_construction", "candidate_proposal", "candidate_feasibility_scheduling",
    "value_evaluation", "final_selection", "reference_preparation_validation",
)


def distribution(values):
    """Linear-interpolated descriptive percentiles; rejects nonfinite evidence."""
    a = sorted(float(x) for x in values)
    if not a:
        return dict(count=0, median=None, p95=None, p99=None, maximum=None, mean=None)
    if not all(math.isfinite(x) and x >= 0.0 for x in a):
        raise ValueError("latency samples must be finite and nonnegative")
    def percentile(p):
        position = (len(a) - 1) * p
        lower = math.floor(position)
        upper = math.ceil(position)
        return a[lower] + (a[upper] - a[lower]) * (position - lower)
    return dict(count=len(a), median=percentile(.5), p95=percentile(.95),
                p99=percentile(.99), maximum=a[-1], mean=sum(a)/len(a))


@dataclass
class DecisionLatency:
    decision_id: str
    observation_ready_ns: int
    candidate_count: int
    model_version: str
    policy_version: str
    clock: Callable[[], int] = perf_counter_ns
    stages_ns: dict = field(default_factory=dict)
    events_ns: dict = field(default_factory=dict)
    outcome: str = "PENDING"
    error: str | None = None

    def __post_init__(self):
        if self.observation_ready_ns < 0 or self.candidate_count < 1:
            raise ValueError("invalid observation epoch or candidate count")
        self.events_ns["observation_ready"] = int(self.observation_ready_ns)

    @contextmanager
    def stage(self, name):
        if name not in PIPELINE_STAGES:
            raise ValueError("unknown decision stage: " + name)
        start = self.clock()
        try:
            yield
        finally:
            end = self.clock()
            if end < start:
                raise ValueError("monotonic clock went backwards")
            self.stages_ns.setdefault(name, []).append([start, end])

    def mark(self, name, at_ns=None):
        if name in self.events_ns:
            raise ValueError("event already recorded: " + name)
        at = self.clock() if at_ns is None else int(at_ns)
        if at < self.observation_ready_ns:
            raise ValueError("event precedes observation")
        self.events_ns[name] = at

    def finish(self, *, validated, at_ns=None, reason=None):
        if self.outcome != "PENDING":
            raise ValueError("decision already finished")
        self.mark("reference_ready_validated" if validated else "decision_failed", at_ns)
        self.outcome = "REFERENCE_READY_VALIDATED" if validated else "FAILED"
        self.error = reason

    def record(self):
        complete = self.outcome == "REFERENCE_READY_VALIDATED"
        end = self.events_ns.get("reference_ready_validated")
        missing = [x for x in PIPELINE_STAGES if x not in self.stages_ns]
        return dict(schema="value_learning_decision_latency_v1", decision_id=self.decision_id,
                    candidate_count=self.candidate_count, model_version=self.model_version,
                    policy_version=self.policy_version, outcome=self.outcome, error=self.error,
                    events_ns=dict(self.events_ns), stages_ns=dict(self.stages_ns),
                    stages_ms={name: sum(b-a for a,b in spans)/1e6
                               for name,spans in self.stages_ns.items()},
                    missing_stages=missing,
                    complete_pipeline_instrumentation=complete and not missing,
                    observation_to_reference_ready_validated_ms=(end-self.observation_ready_ns)/1e6
                        if complete else None,
                    hardware_realtime_qualified=False)


def summarize_decisions(records):
    records = list(records)
    complete = [r for r in records if r.get("complete_pipeline_instrumentation")]
    groups = {}
    for record in complete:
        groups.setdefault(str(record["candidate_count"]), []).append(record)
    return dict(schema="value_learning_latency_summary_v1", evidence_category="descriptive_algorithm_profile",
                total_count=len(records), complete_count=len(complete),
                incomplete_or_failed_count=len(records)-len(complete),
                full_online_decision_latency_ms=distribution(
                    r["observation_to_reference_ready_validated_ms"] for r in complete),
                components_ms={name: distribution(r["stages_ms"][name] for r in complete)
                               for name in PIPELINE_STAGES},
                candidate_count_scaling={n: dict(full_ms=distribution(
                    r["observation_to_reference_ready_validated_ms"] for r in group),
                    count=len(group)) for n,group in groups.items()},
                warning="Scientific Simulation host profiles do not qualify hardware or wall-causal execution.",
                runtime_assurance_status="RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS")


def preliminary_budget(*, maximum_source_age_s=.100, source_age_at_ready_s=0.,
                       reference_commit_progress_s=None, current_reference_progress_s=0.,
                       activation_reserve_s=0., remaining_phase_s=None,
                       proposed_schedule_duration_s=0.):
    """An explicit caller-supplied reserve; no invented global 5 ms deadline.

    The reference-progress opportunity is not a wall-clock execution guarantee.
    Return the raw ceiling and reserve separately. Expiration remains STRICT.
    """
    numbers = [maximum_source_age_s,source_age_at_ready_s,current_reference_progress_s,
               activation_reserve_s,proposed_schedule_duration_s]
    numbers.extend(x for x in (reference_commit_progress_s,remaining_phase_s) if x is not None)
    if not all(math.isfinite(x) and x >= 0 for x in numbers):
        raise ValueError("budget arguments must be finite and nonnegative")
    limits = {"source_age": max(0.,maximum_source_age_s-source_age_at_ready_s)}
    if reference_commit_progress_s is not None:
        limits["reference_fork_progress"] = max(0.,reference_commit_progress_s-current_reference_progress_s)
    if remaining_phase_s is not None:
        limits["phase_schedule_slack"] = max(0.,remaining_phase_s-proposed_schedule_duration_s)
    ceiling = min(limits.values())
    return dict(raw_ceiling_s=ceiling, components_s=limits,
                measured_activation_reserve_s=activation_reserve_s,
                preliminary_producer_budget_s=max(0.,ceiling-activation_reserve_s),
                strict_before_ceiling=True,
                qualification="preliminary architecture opportunity, not WCET or hardware assurance")
