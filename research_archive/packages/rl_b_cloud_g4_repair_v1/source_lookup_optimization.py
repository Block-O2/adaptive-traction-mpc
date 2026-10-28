"""Opt-in exact fast path for append-only native sample timestamps.

No timestamp is synthesized, rounded, refreshed or cached as a new source.
Missing future queries retain the original call to the host profiling clock.
"""
from traction_mpc_stage5.full3d_adaptive_integration_v1.scientific_scheduler import ScientificPhysicsSession
ORIGINAL_SOURCE_NS=ScientificPhysicsSession.source_ns

def fast_source_ns(self,time_s):
    t=float(time_s)
    if self.samples:
        last=self.samples[-1]
        delta=t-last['sample_time_s']
        if abs(delta)<=1e-12:
            return int(last['source_capture_ns'])
        # Native physics time is strictly increasing inside one session, and
        # capture appends immutable samples. A new acquisition has no source
        # row yet. Avoid scanning the entire past merely to return clock().
        if delta>1e-12:
            return self.clock()
    return ORIGINAL_SOURCE_NS(self,t)

def install():
    ScientificPhysicsSession.source_ns=fast_source_ns
