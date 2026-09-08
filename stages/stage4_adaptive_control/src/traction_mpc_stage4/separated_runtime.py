"""Non-blocking fast/slow runtime boundary for Stage-4 estimator trust."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Lock, Thread
from time import perf_counter
from typing import Any

import numpy as np

from .confidence_execution import ReferenceExecutionLayer
from .estimator_v2 import BaseParameterHumanModel
from .measurement import ControllerMeasurement


@dataclass(frozen=True)
class ValidatedIncumbentSnapshot:
    """Atomically published control-facing result of one slow-path update."""

    publication_index: int
    input_index: int
    sample_time_s: float
    arrival_time_s: float
    model: BaseParameterHumanModel
    estimator_state: np.ndarray
    geometry_diagnostics: dict[str, Any]
    dynamic_diagnostics: dict[str, Any]
    reference_execution: ReferenceExecutionLayer | None
    incumbent_epoch: int
    qualification_count: int
    published_monotonic_s: float
    slow_compute_s: float


@dataclass(frozen=True)
class SlowPathRecord:
    input_index: int
    sample_time_s: float
    arrival_time_s: float
    started_monotonic_s: float
    finished_monotonic_s: float
    compute_s: float
    queue_depth_after: int
    incumbent_epoch: int
    qualification_count: int


@dataclass(frozen=True)
class SnapshotActivation:
    control_cycle_index: int
    control_time_s: float
    publication_index: int
    input_index: int
    source_sample_time_s: float
    incumbent_epoch: int
    publication_to_activation_s: float


@dataclass(frozen=True)
class _WorkItem:
    input_index: int
    measurement: ControllerMeasurement


def _copy_measurement(measurement: ControllerMeasurement) -> ControllerMeasurement:
    return ControllerMeasurement(
        arrival_time_s=float(measurement.arrival_time_s),
        sample_time_s=float(measurement.sample_time_s),
        robot_q_rad=measurement.robot_q_rad.copy(),
        robot_dq_rad_s=measurement.robot_dq_rad_s.copy(),
        attachment_position_m=measurement.attachment_position_m.copy(),
        attachment_rotation_matrix=measurement.attachment_rotation_matrix.copy(),
        attachment_velocity_m_s=measurement.attachment_velocity_m_s.copy(),
        attachment_angular_velocity_rad_s=(
            measurement.attachment_angular_velocity_rad_s.copy()
        ),
        cuff_force_vector_n=measurement.cuff_force_vector_n.copy(),
        cuff_moment_vector_nm=measurement.cuff_moment_vector_nm.copy(),
        new_sample=bool(measurement.new_sample),
        control_robot_q_rad=(
            None
            if measurement.control_robot_q_rad is None
            else measurement.control_robot_q_rad.copy()
        ),
        control_robot_dq_rad_s=(
            None
            if measurement.control_robot_dq_rad_s is None
            else measurement.control_robot_dq_rad_s.copy()
        ),
        control_velocity_sample_time_s=measurement.control_velocity_sample_time_s,
    )


def _copy_model(model: BaseParameterHumanModel) -> BaseParameterHumanModel:
    return deepcopy(model)


class SeparatedEstimatorTrustRuntime:
    """Own one estimator on a FIFO slow thread and publish immutable snapshots.

    The worker is the sole estimator/reference-execution writer.  It constructs
    each snapshot before taking the publication lock, so the fast path never
    waits for fitting, validation, or confidence calculations.
    """

    def __init__(
        self,
        estimator: Any,
        *,
        reference_execution: ReferenceExecutionLayer | None = None,
    ) -> None:
        if not hasattr(estimator, "observe_measurement"):
            raise TypeError("separated runtime requires observe_measurement()")
        self.estimator = estimator
        self.reference_execution = reference_execution
        self._queue: Queue[_WorkItem | None] = Queue()
        self._publication_lock = Lock()
        self._failure_lock = Lock()
        self._failure: BaseException | None = None
        self._next_input_index = 0
        self._last_submitted_sample_time_s: float | None = None
        self._active_publication_index = -1
        self._maximum_backlog = 0
        self.slow_records: list[SlowPathRecord] = []
        self.activation_records: list[SnapshotActivation] = []
        self._published = self._make_snapshot(
            publication_index=0,
            input_index=-1,
            sample_time_s=float(estimator.stream_start_sample_time_s),
            arrival_time_s=float(estimator.stream_start_sample_time_s),
            estimator_state=estimator.last_state,
            diagnostics={
                "geometry": estimator.geometry_identifier.last_diagnostics,
                "dynamics": estimator.dynamic_identifier.last_diagnostics,
            },
            slow_compute_s=0.0,
        )
        self._thread = Thread(
            target=self._worker_main,
            name="stage4-estimator-trust",
            daemon=True,
        )
        self._thread.start()

    def _make_snapshot(
        self,
        *,
        publication_index: int,
        input_index: int,
        sample_time_s: float,
        arrival_time_s: float,
        estimator_state: np.ndarray,
        diagnostics: dict[str, Any],
        slow_compute_s: float,
    ) -> ValidatedIncumbentSnapshot:
        return ValidatedIncumbentSnapshot(
            publication_index=publication_index,
            input_index=input_index,
            sample_time_s=float(sample_time_s),
            arrival_time_s=float(arrival_time_s),
            model=_copy_model(self.estimator.model),
            estimator_state=np.asarray(estimator_state, dtype=float).copy(),
            geometry_diagnostics=deepcopy(diagnostics["geometry"]),
            dynamic_diagnostics=deepcopy(diagnostics["dynamics"]),
            reference_execution=(
                deepcopy(self.reference_execution)
                if self.reference_execution is not None
                else None
            ),
            incumbent_epoch=len(self.estimator.control_promotions),
            qualification_count=len(self.estimator.qualifications),
            published_monotonic_s=perf_counter(),
            slow_compute_s=float(slow_compute_s),
        )

    def _set_failure(self, error: BaseException) -> None:
        with self._failure_lock:
            self._failure = error

    def raise_if_failed(self) -> None:
        with self._failure_lock:
            error = self._failure
        if error is not None:
            raise RuntimeError("separated estimator/trust worker failed") from error

    def _worker_main(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                started = perf_counter()
                state, diagnostics = self.estimator.observe_measurement(
                    item.measurement
                )
                if self.reference_execution is not None:
                    self.reference_execution.update_from_estimator(
                        float(item.measurement.arrival_time_s),
                        self.estimator,
                        diagnostics["geometry"],
                        diagnostics["dynamics"],
                    )
                finished = perf_counter()
                with self._publication_lock:
                    publication_index = self._published.publication_index + 1
                snapshot = self._make_snapshot(
                    publication_index=publication_index,
                    input_index=item.input_index,
                    sample_time_s=item.measurement.sample_time_s,
                    arrival_time_s=item.measurement.arrival_time_s,
                    estimator_state=state,
                    diagnostics=diagnostics,
                    slow_compute_s=finished - started,
                )
                with self._publication_lock:
                    self._published = snapshot
                queue_depth = self._queue.qsize()
                self.slow_records.append(
                    SlowPathRecord(
                        input_index=item.input_index,
                        sample_time_s=float(item.measurement.sample_time_s),
                        arrival_time_s=float(item.measurement.arrival_time_s),
                        started_monotonic_s=started,
                        finished_monotonic_s=finished,
                        compute_s=finished - started,
                        queue_depth_after=queue_depth,
                        incumbent_epoch=snapshot.incumbent_epoch,
                        qualification_count=snapshot.qualification_count,
                    )
                )
            except BaseException as error:
                self._set_failure(error)
                while True:
                    try:
                        self._queue.get_nowait()
                    except Empty:
                        break
                    else:
                        self._queue.task_done()
                return
            finally:
                self._queue.task_done()

    def submit(self, measurement: ControllerMeasurement) -> int:
        """Append one estimator input without waiting for slow computation."""

        self.raise_if_failed()
        sample_time = float(measurement.sample_time_s)
        if (
            self._last_submitted_sample_time_s is not None
            and sample_time < self._last_submitted_sample_time_s - 1.0e-12
        ):
            raise ValueError("estimator measurements must be submitted causally")
        input_index = self._next_input_index
        self._next_input_index += 1
        self._last_submitted_sample_time_s = sample_time
        self._queue.put(_WorkItem(input_index, _copy_measurement(measurement)))
        self._maximum_backlog = max(self._maximum_backlog, self._queue.qsize())
        return input_index

    def activate_latest(
        self,
        *,
        control_cycle_index: int,
        control_time_s: float,
    ) -> ValidatedIncumbentSnapshot:
        """Read one complete publication at a clean control-cycle boundary."""

        self.raise_if_failed()
        activated_at = perf_counter()
        with self._publication_lock:
            snapshot = self._published
        if snapshot.publication_index != self._active_publication_index:
            self._active_publication_index = snapshot.publication_index
            self.activation_records.append(
                SnapshotActivation(
                    control_cycle_index=int(control_cycle_index),
                    control_time_s=float(control_time_s),
                    publication_index=snapshot.publication_index,
                    input_index=snapshot.input_index,
                    source_sample_time_s=snapshot.sample_time_s,
                    incumbent_epoch=snapshot.incumbent_epoch,
                    publication_to_activation_s=max(
                        0.0, activated_at - snapshot.published_monotonic_s
                    ),
                )
            )
        return snapshot

    def drain(self) -> None:
        """Wait outside the fast path until every submitted input is processed."""

        self._queue.join()
        self.raise_if_failed()

    def close(self) -> None:
        self.drain()
        self._queue.put(None)
        self._thread.join()
        self.raise_if_failed()

    @property
    def maximum_backlog(self) -> int:
        return self._maximum_backlog

    def timing_summary(self) -> dict[str, Any]:
        durations_ms = 1000.0 * np.asarray(
            [record.compute_s for record in self.slow_records], dtype=float
        )
        backlogs = np.asarray(
            [record.queue_depth_after for record in self.slow_records], dtype=int
        )
        if not len(durations_ms):
            return {
                "count": 0,
                "maximum_backlog": self.maximum_backlog,
            }
        return {
            "count": int(len(durations_ms)),
            "mean_ms": float(np.mean(durations_ms)),
            "median_ms": float(np.median(durations_ms)),
            "p95_ms": float(np.percentile(durations_ms, 95.0)),
            "max_ms": float(np.max(durations_ms)),
            "over_20_ms_count": int(np.count_nonzero(durations_ms > 20.0)),
            "maximum_backlog": self.maximum_backlog,
            "maximum_backlog_after_work": int(np.max(backlogs)),
        }
