"""Diagnostic same-boundary timestamps; original return values unchanged."""
import time,sys
ROWS=[]
def install():
 import study_common as sc
 from interfaces import SACExpertEnv
 orig_allowed=SACExpertEnv.transition_allowed
 def allowed(self,state):
  start=time.monotonic_ns();out=orig_allowed(self,state)
  if state.phase.value=='HOLD':ROWS.append(dict(event='ACTUAL_SHARED_MINIMUM_CHECK',start_ns=start,finish_ns=time.monotonic_ns(),before_phase_elapsed_s=state.phase_elapsed_s,allowed=bool(out)))
  return out
 SACExpertEnv.transition_allowed=allowed
 clock=sc.rt.SensorSupportedTaskClock.transition
 def sensor(self,*args,**kw):
  start=time.monotonic_ns();out=clock(self,*args,**kw);before=args[1]
  if before.phase.value=='HOLD':ROWS.append(dict(event='ACTUAL_SENSOR_DWELL_CHECK',start_ns=start,finish_ns=time.monotonic_ns(),source_sample_s=kw.get('sample_time_s'),physical_time_s=kw.get('physical_time_s'),before_phase_elapsed_s=before.phase_elapsed_s,before_dwell_s=before.hold_elapsed_s,proposed_phase=out.phase.value,proposed_dwell_s=out.hold_elapsed_s))
  return out
 sc.rt.SensorSupportedTaskClock.transition=sensor
 safe=sc.rt.reference_safe_task_transition
 def transition(*args,**kw):
  start=time.monotonic_ns();out=safe(*args,**kw);before=args[1]
  if before.phase.value=='HOLD':
   f=sys._getframe(1).f_locals;g=f.get('reference_governor');runtime=f['runtime'];wall=runtime['wall_session']
   ROWS.append(dict(event='ACTUAL_GUARDED_HOLD_RETURN_CHECK',start_ns=start,finish_ns=time.monotonic_ns(),before_phase_elapsed_s=before.phase_elapsed_s,proposed_phase=args[2].phase.value,result_phase=out.phase.value,merged_ready=bool(args[4]),active_segment_complete=f.get('active_segment_complete'),reference_progress_s=None if g is None else g.progress_s,schedule_start_s=f.get('schedule_start_time'),physical_now_s=f.get('physical_now'),source_sample_s=float(f['observation'].sample_timestamp_s),source_capture_ns=wall.source_ns(f['observation'].sample_timestamp_s),current_receipt_index=wall.active_receipt_index,model_sequence=runtime.get('model_sequence'),reference_q=f['reference_state'][:2].tolist(),reference_dq=f['reference_state'][2:].tolist(),reference_ddq=f['reference_acceleration'].tolist(),original_return_values_unchanged=True))
  return out
 sc.rt.reference_safe_task_transition=transition
def finish(ident):
 import study_common as sc
 sc.save(ident+'_CRITICAL_TRACE.json',dict(rows=ROWS,diagnostic_only=True,original_return_values_unchanged=True))
