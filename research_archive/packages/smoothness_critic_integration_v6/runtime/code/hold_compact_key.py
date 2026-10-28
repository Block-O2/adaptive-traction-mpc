"""C10: exact inputs of the pure HOLD sample sequence, without resampling.

The original evaluator reads candidate.label and inclusive sample q/dq/ddq.
Exact class, unchanged sample function, complete screen/belief, coefficients
and duration determine that entire sequence. No certificate or decision is
admitted here. Changed sample implementation disables this cache.
"""
import io,pickle
INSTALLED=False
EXPECTED_SAMPLE=None
def key(screen,belief,candidate,schedule):
 from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedule as Q
 from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22 as M
 if type(schedule) is not Q or type(screen) is not M or candidate.phase.value!='HOLD' or Q.sample is not EXPECTED_SAMPLE:return None
 from loaded_context_reuse import raw
 stream=io.BytesIO();encoder=pickle.Pickler(stream,protocol=5);encoder.fast=True
 encoder.dump(raw((screen,belief,candidate.label,schedule.duration_s,schedule.coefficients)))
 return stream.getvalue()
def install():
 global INSTALLED,EXPECTED_SAMPLE
 if INSTALLED:return
 import hold_static_mechanics as cache
 from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedule as Q
 EXPECTED_SAMPLE=Q.sample;cache.key=key
 original=cache.evidence
 def evidence():return original()|dict(key_mode='complete original sample inputs, no repeated 21-sample materialization',sample_function_unchanged=Q.sample is EXPECTED_SAMPLE)
 cache.evidence=evidence;INSTALLED=True
