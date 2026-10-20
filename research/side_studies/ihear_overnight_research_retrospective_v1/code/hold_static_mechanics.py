"""C8: pure HOLD mechanics precomputation, no plan or command authority.

The key binds the complete screen/belief, candidate label and all original
sampled q/dq/ddq bytes. Current native tracking-offset screening and planner
selection still execute on the actual request. No predicted physical state.
"""
import pickle,time,collections,hashlib,io
CACHE=collections.OrderedDict();ROWS=[];COUNTS=collections.Counter();INSTALLED=False;PREPARING=False
def key(screen,belief,candidate,schedule):
 import numpy as np
 from traction_mpc_stage5.human_waypoint_scheduler import QuinticHumanWaypointSchedule
 from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22
 if type(schedule) is not QuinticHumanWaypointSchedule or type(screen) is not AdaptiveMechanicsScreenV22 or candidate.phase.value!='HOLD':return None
 # These are exactly the same inclusive sample inputs used by original evaluate.
 samples=[]
 for elapsed in np.linspace(0.,schedule.duration_s,screen.sample_count):
  v=schedule.sample(float(elapsed));samples.append((v.q_rad,v.dq_rad_s,v.ddq_rad_s2))
 from loaded_context_reuse import raw
 stream=io.BytesIO();encoder=pickle.Pickler(stream,protocol=5);encoder.fast=True
 encoder.dump(raw((screen,belief,candidate.label,schedule.duration_s,samples)))
 return stream.getvalue()
def install():
 global INSTALLED
 if INSTALLED:return
 from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22 as C
 original=C.evaluate
 def evaluate(self,belief,candidate,schedule):
  k=key(self,belief,candidate,schedule)
  if k is None:return original(self,belief,candidate,schedule)
  if k in CACHE:
   COUNTS['prepare_hit' if PREPARING else 'actual_request_hit']+=1;CACHE.move_to_end(k);return pickle.loads(CACHE[k])
  COUNTS['prepare_miss' if PREPARING else 'actual_request_miss']+=1
  out=original(self,belief,candidate,schedule);CACHE[k]=pickle.dumps(out,protocol=5)
  if len(CACHE)>8:CACHE.popitem(last=False)
  return out
 C.evaluate=evaluate;INSTALLED=True
def prepare(payload,value):
 global PREPARING
 import numpy as np
 from traction_mpc_stage5.task import TaskPhase
 from traction_mpc_stage4 import estimator_v2 as ma
 planner,args=pickle.loads(payload);schedule=value.executed.schedule
 if args['phase'] not in (TaskPhase.OUTBOUND,TaskPhase.HOLD):return
 if np.any(np.abs(schedule.candidate.dq_waypoint_rad_s)>1e-12):return
 # Only a known stationary OUT endpoint in the original terminal box can lead
 # into HOLD. This derives reference structure, never future physical q/dq.
 from traction_mpc_stage5.full3d_adaptive_integration_v1.terminal_reference import in_original_terminal_box
 spec=planner.planner.spec
 if not in_original_terminal_box(spec,schedule.candidate.q_waypoint_rad,spec.outbound_goal_target_rad):return
 endpoint=schedule.sample(schedule.duration_s);reference=np.r_[endpoint.q_rad,endpoint.dq_rad_s]
 original_state=np.asarray(args['current_deployable_state']).copy()
 args=dict(args,current_reference_state=reference,phase=TaskPhase.HOLD,phase_elapsed_s=0.,phase_remaining_s=spec.phase_timeout_s)
 snapshot=dict(planner.planner.tracking_reference_snapshot)
 snapshot.update(q_ref_rad=reference[:2].copy(),dq_ref_rad_s=reference[2:].copy(),proposed_schedule_origin_rad_rad_s=reference.copy(),source_state_rad_rad_s=original_state.copy())
 planner.planner.tracking_reference_snapshot=snapshot;planner.planner.residual_spec={}
 begin=time.monotonic_ns();before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS;counts=dict(COUNTS);PREPARING=True
 row=dict(event='NON_AUTHORITATIVE_HOLD_MECHANICS_PREPARATION',begin_ns=begin,model_sequence=args['belief'].sequence,original_past_state=original_state.tolist(),known_reference_endpoint=reference.tolist(),source_snapshot=snapshot.get('source_sample_time_s'),payload_sha256=hashlib.sha256(payload).hexdigest(),phase_assumption_is_provisional=True,actuation_authority=False,no_new_lifecycle_request=True)
 try:
  advisory=planner.decide(**args)
  row.update(status='PREPARED',selected_label=advisory.executed.label,result_discarded=True)
 except BaseException as error:row.update(status='DISCARDED',error=f'{type(error).__name__}:{error}')
 finally:
  PREPARING=False;row.update(finish_ns=time.monotonic_ns(),model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,cache_count=len(CACHE),counter_delta={k:v-counts.get(k,0) for k,v in COUNTS.items()});ROWS.append(row)
def evidence():return dict(rows=ROWS.copy(),counters=dict(COUNTS),cache_entries=len(CACHE),no_actuation_authority=True)
def prepare_guarded(payload,value):
 from traction_mpc_stage4 import estimator_v2 as ma
 start=time.monotonic_ns();before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
 try:return prepare(payload,value)
 except BaseException as error:
  ROWS.append(dict(event='NON_AUTHORITATIVE_PREPARATION_DISCARDED',begin_ns=start,finish_ns=time.monotonic_ns(),error=f'{type(error).__name__}:{error}',model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,actuation_authority=False,original_TASK_channel_preserved=True))
