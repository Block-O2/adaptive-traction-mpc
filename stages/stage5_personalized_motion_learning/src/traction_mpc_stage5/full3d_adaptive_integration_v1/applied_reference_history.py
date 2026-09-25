"""Receipt-backed reference history for actual delayed command delivery.

Sparse command receipts define a known zero-order hold, not missing controller
outputs. Attempted command construction never commits an emitted reference.
"""
import numpy as np
from ..human_waypoint_shadow import (CausalScheduledReferenceMotionHistory,
                                     ScheduledReferenceHistoryStatus)


class AppliedReferenceMotionHistory(CausalScheduledReferenceMotionHistory):
    def __init__(self, clock, initial_q, initial_dq, initial_time_s):
        super().__init__(sample_period_s=.005, window_s=.020)
        self.clock = clock
        self.valid_since = float(initial_time_s)
        self.commit_applied(initial_time_s, initial_q, initial_dq)
        self.attempt_commit_count = 0

    def commit(self, timestamp_s, q_reference_rad, dq_reference_rad_s):
        # The unchanged contract invokes this while constructing a command.
        # Only the actual apply receipt below is an emission event.
        self.attempt_commit_count += 1

    def commit_applied(self, timestamp_s, q_reference_rad, dq_reference_rad_s):
        super().commit(timestamp_s, q_reference_rad, dq_reference_rad_s)

    def invalidate(self, timestamp_s):
        # A BRAKE target is not the proposed TRACK reference.
        self.valid_since = float(timestamp_s)
        self.samples.clear()

    def status(self, timestamp_s):
        # Reference-window time is actual execution time. The sensor timestamp
        # argument remains immutable and is not relabeled as this clock.
        now = float(self.clock())
        target = now-self.window_s
        anchor = next(((q.copy(), dq.copy()) for t, q, dq in reversed(self.samples)
                       if t <= target+1e-12), None)
        valid = bool(anchor is not None and target >= self.valid_since-1e-12)
        return ScheduledReferenceHistoryStatus(
            valid=valid, contiguous=valid, coverage_s=max(0., now-self.valid_since),
            sample_count=len(self.samples), maximum_gap_s=None,
            anchor_q_rad=None if anchor is None else anchor[0],
            anchor_dq_rad_s=None if anchor is None else anchor[1])

    def validate_at_apply(self, q, dq, acceleration_limits):
        status = self.status(self.clock())
        previous = self.last_reference()
        held = previous is not None and np.allclose(q,previous[0],rtol=0,atol=1e-12) and np.allclose(dq,previous[1],rtol=0,atol=1e-12)
        if not status.valid and not held:
            raise RuntimeError("ACTUAL_REFERENCE_HISTORY_INCOMPLETE")
        acceleration = self.acceleration_rad_s2(dq,status) if status.valid else np.zeros(2)
        if np.any(np.abs(acceleration) > np.asarray(acceleration_limits)+1e-12):
            raise RuntimeError("ACTUAL_REFERENCE_20MS_ACCELERATION_LIMIT")
        return {"execution_time_s":float(self.clock()), "reference_source":"actual apply receipts with ZOH",
                "anchor_dq_rad_s":status.anchor_dq_rad_s,
                "acceleration_rad_s2":acceleration, "history_valid":status.valid, "held":held}
