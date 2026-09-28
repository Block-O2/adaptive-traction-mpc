"""Opt-in monotonic request accounting and isolated task planning.

Only the main thread observes/controls MuJoCo. The worker receives an immutable
serialized snapshot of deployable inputs, never the runtime or plant. Physical
time is deliberately separate from the monotonic wall clock used for expiry.
"""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, ProcessPoolExecutor
from copy import copy, deepcopy
from dataclasses import dataclass
import pickle
import multiprocessing
from threading import Lock
from time import monotonic_ns
from typing import Any, Callable


@dataclass(frozen=True)
class PlanRequest:
    request_id: int
    stage: str
    source_sample_time_s: float
    sensor_capture_ns: int
    request_ns: int
    asynchronous: bool


def snapshot_task_call(adaptive_planner: Any, arguments: dict[str, Any]) -> bytes:
    """Copy only the planner graph, excluding growing decision history.

    Scheduler, clearance geometry, model, belief and numeric states are all
    serialized by value. Main-thread estimator/scheduler updates cannot race
    with worker reads. Bytes are made locally; no external pickle is accepted.
    """
    snapshot = copy(adaptive_planner)
    snapshot.planner = copy(adaptive_planner.planner)
    snapshot.planner.decisions = []
    snapshot.belief_sequences_used = []
    return pickle.dumps((snapshot, arguments), protocol=pickle.HIGHEST_PROTOCOL)


def execute_task_snapshot(payload: bytes) -> Any:
    planner, arguments = pickle.loads(payload)
    decision = planner.decide(**arguments)
    if getattr(planner.planner, "safe_fallback_enabled", False):
        from .safe_fallback import prepare_decision
        decision = prepare_decision(decision, planner.planner, arguments["belief"])
    return decision


def _warm_planner_process() -> int:
    # Import before the physical epoch. No plant or observed state is passed.
    from . import runtime, terminal_reference  # noqa: F401
    return monotonic_ns()


def _process_task_snapshot(payload: bytes) -> dict[str, Any]:
    started = monotonic_ns()
    try:
        value = execute_task_snapshot(payload)
        result = {"value": value}
    except BaseException as error:
        result = {"worker_exception": f"{type(error).__name__}:{error}"}
        if hasattr(error, "terminal_reference_selection"):
            result["terminal_reference_selection"] = error.terminal_reference_selection
    result.update(worker_start_ns=started, compute_finish_ns=monotonic_ns())
    return result


class PlanLifecycle:
    """One outstanding request; all timestamps are write-once events."""

    maximum_age_ns = 100_000_000

    def __init__(self, *, clock: Callable[[], int] = monotonic_ns, process_worker: bool = False) -> None:
        self.clock = clock
        self._lock = Lock()
        self._captures: dict[float, int] = {}
        self._requests: list[PlanRequest] = []
        self._events: list[dict[str, Any]] = []
        self._executor: ThreadPoolExecutor | None = None
        self._future: Future | None = None
        self._future_requests: dict[Future, PlanRequest] = {}
        self._outstanding: PlanRequest | None = None
        self.closed = False
        self.process_worker = bool(process_worker)
        self.prewarm_record = None
        if self.process_worker:
            start = self.clock()
            self._executor = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"))
            worker_ready = self._executor.submit(_warm_planner_process).result()
            self.prewarm_record = {"start_ns": start, "worker_ready_ns": worker_ready,
                                   "finish_ns": self.clock(), "scope": "offline before active physical epoch"}

    def capture(self, sample_time_s: float, capture_ns: int) -> None:
        # Held/repeated observations keep their original capture forever.
        self._captures.setdefault(float(sample_time_s), int(capture_ns))

    def request(self, stage: str, sample_time_s: float, *, asynchronous: bool) -> PlanRequest:
        if self.closed or self._outstanding is not None or (self._future is not None and not self._future.done()):
            raise RuntimeError("planner lifecycle is closed or already has a pending request")
        source = float(sample_time_s)
        request = PlanRequest(len(self._requests), stage, source,
                              self._captures[source], self.clock(), asynchronous)
        self._requests.append(request)
        self._events.append({"outcome": "PENDING", "reason": None,
                             "fallback_intervals": 0, "fallback_physics_s": 0.0,
                             "fallback_supervisor_modes": []})
        self._outstanding = request
        return request

    def mark(self, request: PlanRequest, event: str, at_ns: int | None = None) -> int:
        value = self.clock() if at_ns is None else int(at_ns)
        with self._lock:
            row = self._events[request.request_id]
            if event in row:
                raise RuntimeError(f"immutable event already recorded: {event}")
            row[event] = value
        return value

    def mark_once(self, request: PlanRequest, event: str) -> None:
        with self._lock:
            self._events[request.request_id].setdefault(event, self.clock())

    def compute(self, request: PlanRequest, operation: Callable[..., Any], *args: Any) -> Any:
        self.mark(request, "worker_start_ns")
        try:
            return operation(*args)
        except BaseException as error:
            with self._lock:
                self._events[request.request_id]["worker_exception"] = f"{type(error).__name__}:{error}"
                if hasattr(error, "terminal_reference_selection"):
                    self._events[request.request_id]["terminal_reference_selection"] = error.terminal_reference_selection
            self.finish(request, "FAILED", f"{type(error).__name__}:{error}")
            raise
        finally:
            self.mark(request, "compute_finish_ns")

    def submit(self, request: PlanRequest, payload: bytes) -> Future:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stage5-task-planner")
        self.mark(request, "enqueue_ns")
        if self.process_worker:
            self._future = self._executor.submit(_process_task_snapshot, payload)
            self._future_requests[self._future] = request
            self._future.add_done_callback(lambda future: self._harvest_process(request, future))
        else:
            self._future = self._executor.submit(self.compute, request, execute_task_snapshot, payload)
        return self._future

    def _harvest_process(self, request: PlanRequest, future: Future) -> None:
        if future.cancelled():
            return
        try:
            result = future.result()
        except BaseException as error:
            result = {"worker_exception": f"PROCESS_TRANSPORT:{type(error).__name__}:{error}"}
        with self._lock:
            row = self._events[request.request_id]
            for key in ("worker_start_ns", "compute_finish_ns", "worker_exception", "terminal_reference_selection"):
                if key in result:
                    row.setdefault(key, result[key])
        if "worker_exception" in result:
            self.finish(request, "FAILED", result["worker_exception"])

    def result(self, future: Future) -> Any:
        result = future.result()
        if not self.process_worker:
            return result
        self._harvest_process(self._future_requests[future], future)
        if "worker_exception" in result:
            error = RuntimeError(result["worker_exception"])
            if "terminal_reference_selection" in result:
                error.terminal_reference_selection = result["terminal_reference_selection"]
            raise error
        return result["value"]

    def expired(self, request: PlanRequest) -> bool:
        return self.clock() - request.sensor_capture_ns >= self.maximum_age_ns

    def finish(self, request: PlanRequest, outcome: str, reason: str | None = None) -> None:
        with self._lock:
            row = self._events[request.request_id]
            if row["outcome"] != "PENDING":
                return
            row.update(outcome=outcome, reason=reason, disposition_ns=self.clock())
            if self._outstanding == request:
                self._outstanding = None

    def discard(self, request: PlanRequest, outcome: str, reason: str) -> None:
        with self._lock:
            row = self._events[request.request_id]
            row.setdefault("cancel_requested_ns", self.clock())
        cancelled = bool(self._future is not None and self._future.cancel())
        with self._lock:
            self._events[request.request_id]["future_cancel_succeeded"] = cancelled
        self.finish(request, outcome, reason)

    def activate(self, request: PlanRequest, apply: Callable[[], None], *, effective_activation_ns: int | None = None, applied_receipt: dict | None = None) -> None:
        """Check after command construction/safety validation, at actual apply.

        Post-apply timing is also measured. A scheduler interruption within the
        very short command write is reported as a miss, never hidden as a pass.
        The caller aborts before another physics step on such an overrun.
        """
        self.mark(request, "validation_finish_ns")
        checked = self.mark(request, "activation_check_ns")
        if effective_activation_ns is not None:
            self.mark(request, "effective_activation_ns", effective_activation_ns)
        if max(checked, effective_activation_ns or checked) - request.sensor_capture_ns >= self.maximum_age_ns:
            self.finish(request, "EXPIRED", "STALE_PLAN_MAXIMUM_AGE")
            raise RuntimeError("STALE_PLAN_MAXIMUM_AGE")
        try:
            apply()
        except BaseException as error:
            applied_receipt = applied_receipt or getattr(error, "applied_receipt", None)
            if applied_receipt is not None and applied_receipt.get("applied"):
                activated = self.mark(request, "activation_ns", applied_receipt["apply_ns"])
                miss = max(activated, effective_activation_ns or activated)-request.sensor_capture_ns >= self.maximum_age_ns
                self.finish(request, "ACTIVATION_DEADLINE_MISS" if miss else "ACTIVATED_COMMIT_FAILED",
                            f"POST_WRITE_COMMIT:{type(error).__name__}:{error}")
            else:
                self.finish(request, "FAILED", f"COMMAND_APPLICATION:{type(error).__name__}:{error}")
            raise
        activated = self.mark(request, "activation_ns")
        if max(activated, effective_activation_ns or activated) - request.sensor_capture_ns >= self.maximum_age_ns:
            self.finish(request, "ACTIVATION_DEADLINE_MISS", "COMMAND_WRITE_CROSSED_EXPIRATION")
            raise RuntimeError("COMMAND_WRITE_CROSSED_EXPIRATION")
        self.finish(request, "ACTIVATED")

    def fallback(self, request: PlanRequest, duration_s: float, supervisor_mode: str) -> None:
        with self._lock:
            row = self._events[request.request_id]
            row["fallback_intervals"] += 1
            row["fallback_physics_s"] += duration_s
            if supervisor_mode not in row["fallback_supervisor_modes"]:
                row["fallback_supervisor_modes"].append(supervisor_mode)

    def fail_pending(self, reason: str) -> None:
        request = self._outstanding
        if request is not None:
            # Synchronous caller exceptions can occur before returning a plan.
            event = self._events[request.request_id]
            if not request.asynchronous and "worker_start_ns" in event and "compute_finish_ns" not in event:
                self.mark(request, "compute_finish_ns")
            self.finish(request, "FAILED", reason)

    def close(self, reason: str = "RUN_ENDED_BEFORE_ACTIVATION") -> None:
        if self.closed:
            return
        if self._outstanding is not None:
            self.discard(self._outstanding, "CANCELLED", reason)
        # Candidate searches are finite. Running Python threads cannot be killed;
        # join their finite work so no worker outlives the run or contaminates the
        # next timing experiment. Preserve late finish/exception timestamps.
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=True)
        self.closed = True

    def records(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = []
            for request, event in zip(self._requests, self._events):
                row = {**request.__dict__, **deepcopy(event)}
                for name, start, end in (
                    ("acquisition_to_request_ms", "sensor_capture_ns", "request_ns"),
                    ("queue_and_snapshot_ms", "request_ns", "worker_start_ns"),
                    ("snapshot_ms", "request_ns", "snapshot_finish_ns"),
                    ("queue_ms", "enqueue_ns", "worker_start_ns"),
                    ("compute_ms", "worker_start_ns", "compute_finish_ns"),
                    ("completion_to_validation_ms", "compute_finish_ns", "validation_finish_ns"),
                    ("worker_to_main_scheduling_ms", "compute_finish_ns", "result_collected_ns"),
                    ("validation_and_command_construction_ms", "validation_start_ns", "validation_finish_ns"),
                    ("validation_scheduling_ms", "result_collected_ns", "validation_start_ns"),
                    ("validation_to_activation_ms", "validation_finish_ns", "activation_ns"),
                    ("activation_age_ms", "sensor_capture_ns", "activation_ns"),
                    ("disposition_age_ms", "sensor_capture_ns", "disposition_ns"),
                ):
                    row[name] = ((row[end] - row[start]) / 1e6
                                 if start in row and end in row else None)
                if "activation_ns" in row:
                    row["conservative_activation_ns"] = max(row["activation_ns"], row.get("effective_activation_ns", row["activation_ns"]))
                    row["activation_age_ms"] = (row["conservative_activation_ns"]-row["sensor_capture_ns"])/1e6
                rows.append(row)
            return rows
