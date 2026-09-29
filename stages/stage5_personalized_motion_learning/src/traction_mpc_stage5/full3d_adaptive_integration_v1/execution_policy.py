"""Mode-specific lifecycle validity. Controller mathematics is mode agnostic."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import sleep
from typing import Any, Callable

from .online_planning import PlanLifecycle, PlanRequest


class ExecutionMode(str, Enum):
    REALTIME_CHARACTERIZATION = "REALTIME_CHARACTERIZATION"
    SCIENTIFIC_SIMULATION = "SCIENTIFIC_SIMULATION"


@dataclass(frozen=True)
class SimulationVersion:
    episode_epoch: str
    state_version: int
    physics_step: int
    sim_time_s: float
    phase_version: int
    human_model_version: str
    reference_version: str


class ScientificPlanLifecycle(PlanLifecycle):
    """Wait at the submission epoch; only the main owner advances physics."""

    def __init__(self, session, *, version_provider: Callable[[], SimulationVersion],
                 process_worker: bool = False, host_delay_s: float = 0.0,
                 sleeper: Callable[[float], None] = sleep):
        super().__init__(process_worker=process_worker)
        if host_delay_s < 0:
            raise ValueError("negative host delay")
        self.session = session
        self.version_provider = version_provider
        self.host_delay_s = float(host_delay_s)
        self.sleeper = sleeper
        self.source_versions: dict[int, SimulationVersion] = {}
        self.receipt_versions: dict[int, SimulationVersion] = {}
        self.activation_versions: dict[int, SimulationVersion] = {}

    def request(self, stage: str, sample_time_s: float, *, asynchronous: bool) -> PlanRequest:
        request = super().request(stage, sample_time_s, asynchronous=asynchronous)
        self.source_versions[request.request_id] = self.version_provider()
        return request

    def mark(self, request: PlanRequest, event: str, at_ns: int | None = None) -> int:
        value = super().mark(request, event, at_ns)
        if event == "compute_finish_ns" and not request.asynchronous:
            receipt = self.version_provider()
            if receipt != self.source_versions[request.request_id]:
                self.finish(request, "REJECTED", "SCIENTIFIC_EPOCH_CHANGED_DURING_COMPUTE")
                raise RuntimeError("SCIENTIFIC_EPOCH_CHANGED_DURING_COMPUTE")
            self.receipt_versions[request.request_id] = receipt
            self.mark_once(request, "scientific_receipt_ns")
        return value

    def submit(self, request: PlanRequest, payload: bytes):
        source = self.source_versions[request.request_id]
        future = super().submit(request, payload)
        # Blocking here guarantees a result exists before any native step.
        # Exception ownership remains with the normal result collection path.
        try:
            future.result()
        except BaseException:
            pass
        if self.host_delay_s:
            self.sleeper(self.host_delay_s)
        receipt = self.version_provider()
        if receipt != source:
            self.finish(request, "REJECTED", "SCIENTIFIC_EPOCH_CHANGED_DURING_WORKER")
            raise RuntimeError("SCIENTIFIC_EPOCH_CHANGED_DURING_WORKER")
        self.receipt_versions[request.request_id] = receipt
        self.mark_once(request, "scientific_receipt_ns")
        return future

    def compute(self, request: PlanRequest, operation: Callable[..., Any], *args: Any):
        # Synchronous commissioning/recovery work is called by the main owner.
        # Async thread workers must not read the live session or plant.
        if request.asynchronous:
            return super().compute(request, operation, *args)
        source = self.source_versions[request.request_id]
        value = super().compute(request, operation, *args)
        receipt = self.version_provider()
        if receipt != source:
            self.finish(request, "REJECTED", "SCIENTIFIC_EPOCH_CHANGED_DURING_COMPUTE")
            raise RuntimeError("SCIENTIFIC_EPOCH_CHANGED_DURING_COMPUTE")
        self.receipt_versions[request.request_id] = receipt
        self.mark_once(request, "scientific_receipt_ns")
        return value

    def expired(self, request: PlanRequest) -> bool:
        if request.request_id not in self.receipt_versions:
            return False
        source = self.source_versions[request.request_id]
        if self.version_provider().episode_epoch != source.episode_epoch:
            return True
        return float(self.session.plant.data.time) - request.source_sample_time_s >= .100 - 1e-12

    def activate(self, request: PlanRequest, apply: Callable[[], None], *,
                 effective_activation_ns: int | None = None,
                 applied_receipt: dict | None = None) -> None:
        self.mark(request, "validation_finish_ns")
        self.mark(request, "activation_check_ns")
        source = self.source_versions[request.request_id]
        current = self.version_provider()
        if (request.request_id not in self.receipt_versions
                or current.episode_epoch != source.episode_epoch
                or self.expired(request)):
            self.finish(request, "EXPIRED", "SCIENTIFIC_SOURCE_OR_EPOCH_STALE")
            raise RuntimeError("SCIENTIFIC_SOURCE_OR_EPOCH_STALE")
        self.activation_versions[request.request_id] = current
        try:
            apply()
        except BaseException as error:
            receipt = applied_receipt or getattr(error, "applied_receipt", None)
            if receipt is not None and receipt.get("applied"):
                self.mark(request, "activation_ns", receipt["apply_ns"])
                self.finish(request, "ACTIVATED_COMMIT_FAILED",
                            f"POST_WRITE_COMMIT:{type(error).__name__}:{error}")
            else:
                self.finish(request, "FAILED", f"COMMAND_APPLICATION:{type(error).__name__}:{error}")
            raise
        self.mark(request, "activation_ns")
        self.finish(request, "ACTIVATED")

    def records(self) -> list[dict[str, Any]]:
        rows = super().records()
        for row in rows:
            request_id = row["request_id"]
            row["execution_mode"] = ExecutionMode.SCIENTIFIC_SIMULATION.value
            row["source_simulation_version"] = vars(self.source_versions[request_id])
            if request_id in self.receipt_versions:
                row["receipt_simulation_version"] = vars(self.receipt_versions[request_id])
            if request_id in self.activation_versions:
                row["activation_simulation_version"] = vars(self.activation_versions[request_id])
            row["host_delay_injection_s"] = self.host_delay_s
        return rows
