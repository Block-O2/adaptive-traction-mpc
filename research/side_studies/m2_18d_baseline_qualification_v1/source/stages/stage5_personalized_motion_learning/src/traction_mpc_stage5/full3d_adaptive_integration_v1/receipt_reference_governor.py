"""Causal path-progress selection against all receipt-owned 20 ms ZOH anchors.

Only reference progress changes. Original certified geometry, task clocks,
limits, goal and emitted polynomial q/dq values remain unchanged.
"""
import numpy as np


def velocity_box(history, acceleration_limits):
    now = float(history.clock())
    limits=np.asarray(acceleration_limits,dtype=float)
    if limits.shape!=(2,) or not np.all(np.isfinite(limits)) or np.any(limits<=0):
        raise ValueError("finite positive original acceleration limits required")
    status = history.status(now)
    last = history.last_reference()
    if last is None:
        raise RuntimeError('REFERENCE_GOVERNOR_NO_APPLIED_ORIGIN')
    if not np.all(np.isfinite(last[1])):raise ValueError("nonfinite applied reference")
    if not status.valid:
        return last[1].copy(),last[1].copy()
    anchors=[status.anchor_dq_rad_s]
    for stamp,q,dq in reversed(history.samples):
        if stamp<=now-history.window_s+1e-12:break
        anchors.append(dq)
    anchors.append(last[1])
    values=np.asarray(anchors)
    if not np.all(np.isfinite(values)):
        raise ValueError("nonfinite applied reference history")
    delta=np.asarray(acceleration_limits)*history.window_s
    return np.max(values-delta,axis=0),np.min(values+delta,axis=0)


class ReceiptReferenceGovernor:
    def __init__(self):
        self.schedule=None
        self.progress_s=0.
        self.records=[]

    def is_complete(self,schedule):
        return self.schedule is schedule and self.progress_s>=schedule.duration_s-1e-12

    def select(self,schedule,desired_progress_s,history,acceleration_limits,*,first=False):
        if not np.isfinite(desired_progress_s):raise ValueError("nonfinite reference progress")
        previous=self.progress_s if self.schedule is schedule else 0.
        desired=0. if first else min(schedule.duration_s,max(previous,float(desired_progress_s)))
        lower,upper=velocity_box(history,acceleration_limits)
        def valid(sample):
            return bool(np.all(sample.dq_rad_s>=lower-history.window_s*1e-12) and np.all(sample.dq_rad_s<=upper+history.window_s*1e-12))
        sample=schedule.sample(previous)
        if not valid(sample):
            raise RuntimeError('REFERENCE_GOVERNOR_APPLIED_ORIGIN_OUTSIDE_HISTORY_BOX')
        selected=previous
        # No jump to a later feasible island after an inadmissible velocity.
        # Only the actually selected sample is emitted; the full geometric
        # path was independently certified by the unchanged scheduler.
        count=max(1,int(np.ceil((desired-previous)/.005)))
        for index in range(1,count+1):
            progress=previous+(desired-previous)*index/count
            proposal=schedule.sample(progress)
            if not valid(proposal):break
            selected,sample=progress,proposal
        proposal={'time_s':float(history.clock()),'previous_progress_s':previous,
                'desired_progress_s':desired,'selected_progress_s':selected,
                'delay_added_s':desired-selected,'lower_dq_rad_s':lower.copy(),
                'upper_dq_rad_s':upper.copy(),'selected_dq_rad_s':sample.dq_rad_s.copy()}
        return sample,proposal

    def commit(self,schedule,proposal,receipt):
        self.schedule=schedule
        self.progress_s=proposal['selected_progress_s']
        if proposal['delay_added_s']>1e-12:
            self.records.append({**proposal,'receipt_apply_ns':receipt['apply_ns'],
                                 'effective_physics_s':receipt['start_physics_s']})
