"""Same-cycle HOLD handoff attribution; all original return values retained."""
import time
ROWS=[]
def install():
 import fast_attribution as a,study_common as sc
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 from traction_mpc_stage5 import human_waypoint_feedback_mpc as fb
 for cls,name,category in ((op.PlanLifecycle,'submit','TASK_submit_snapshot_enqueue'),(op.PlanLifecycle,'result','TASK_packet_collect_and_proof_install'),(fb.HumanWaypointFeedbackDecisionV1,'record','decision_record_materialize'),(fb.FeedbackCandidateEvaluationV1,'record','candidate_record_materialize')):a.wrap(cls,name,category)
 original_clock=sc.rt.SensorSupportedTaskClock.transition
 def transition(self,*args,**kwargs):
  before=args[1];start=time.monotonic_ns();result=original_clock(self,*args,**kwargs)
  if a.CURRENT is not None:a.CURRENT['task_phase']=before.phase.value
  if before.phase.value=='HOLD' or result.phase.value=='HOLD' and before.phase is not result.phase:
   ROWS.append(dict(event='ORIGINAL_SENSOR_TASK_CLOCK',host_ns=start,finish_ns=time.monotonic_ns(),before_phase=before.phase.value,proposed_phase=result.phase.value,before_phase_elapsed_s=before.phase_elapsed_s,before_dwell_s=before.hold_elapsed_s,proposed_dwell_s=result.hold_elapsed_s,physical_dt_s=args[4],sample_time_s=kwargs.get('sample_time_s'),physical_time_s=kwargs.get('physical_time_s')))
  return result
 sc.rt.SensorSupportedTaskClock.transition=transition
 original=sc.rt.reference_safe_task_transition
 def safe(*args,**kwargs):
  start=time.monotonic_ns();result=original(*args,**kwargs);spec,before,proposed,dt,ready=args
  if before.phase.value=='HOLD' or result.phase.value=='HOLD' and before.phase is not result.phase:
   ROWS.append(dict(event='ORIGINAL_REFERENCE_SAFE_TASK_TRANSITION',host_ns=start,finish_ns=time.monotonic_ns(),before_phase=before.phase.value,proposed_phase=proposed.phase.value,result_phase=result.phase.value,reference_ready=bool(ready),continuous_hold=bool(kwargs.get('continuous_hold')),before_phase_elapsed_s=before.phase_elapsed_s,proposed_phase_elapsed_s=proposed.phase_elapsed_s,result_phase_elapsed_s=result.phase_elapsed_s,proven_original_dwell=spec.hold_duration_s,physical_dt_s=dt,deferred=before.phase.value=='HOLD' and proposed.phase.value=='RETURN' and result.phase.value=='HOLD'))
  return result
 sc.rt.reference_safe_task_transition=safe
def finish(ident):
 import study_common as sc
 sc.save(ident+'_HOLD_HANDOFF_ATTRIBUTION.json',dict(rows=ROWS,attribution_only=True,original_return_values_unchanged=True,not_qualification=True))
