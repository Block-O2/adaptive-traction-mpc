"""External execution-owner adapters. Frozen controller sources remain intact."""
import time,pickle,hashlib,os
from dataclasses import dataclass

ROWS={'fast':[],'sensor_capture':[],'planner':[],'admission':[],'commissioning':[],'model':[]}
RUNTIME=None

@dataclass(frozen=True)
class Snapshot:
 request_id:int
 source_capture_ns:int
 model_version:int
 reference_version:str
 phase:str
 snapshot_created_ns:int
 payload:bytes
 sha256:str

def install(revision,mode):
 import study_common as sc
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op,wall_physics as wp,activation_validation as av
 rt=sc.rt
 original_load=sc.load_case_options
 def load():
  case,options=original_load();options=dict(options)
  if revision!='BASE':options['planner_process_worker']=True
  return case,options
 sc.load_case_options=load
 original_capture=rt._capture_boundary
 def capture(runtime):
  global RUNTIME
  RUNTIME=runtime
  started=time.monotonic_ns();value=original_capture(runtime);finished=time.monotonic_ns()
  wall=runtime.get('wall_session')
  if wall is not None:
   runtime['_mr_latest_capture']=dict(start_ns=started,finish_ns=finished,source_sample_time_s=float(value[1].sample_time_s))
   ROWS['sensor_capture'].append(dict(capture_start_ns=started,capture_finish_ns=finished,source_sample_time_s=float(value[1].sample_time_s),source_capture_ns=wall.source_ns(value[1].sample_time_s),model_version=runtime.get('model_sequence')))
  return value
 rt._capture_boundary=capture
 original_interval=rt._execute_interval
 def interval(runtime,**kwargs):
  wall=runtime.get('wall_session');row=None
  if wall is not None:
   captured=runtime.get('_mr_latest_capture',{});started=captured.get('start_ns',time.monotonic_ns())
   if not hasattr(wall,'_mr_due'):wall._mr_due=wall.epoch_ns
   due=wall._mr_due;skipped=max(0,(started-due)//5_000_000)
   # Two services within one scheduled period are extra real services, never
   # synthetic future ticks. Keep them separate and do not advance a future due.
   extra=started<due
   if not extra:wall._mr_due=due+(skipped+1)*5_000_000
   row=dict(scheduled_tick_ns=due,service_start_ns=started,sensor_finish_ns=captured.get('finish_ns'),feedback_start_ns=time.monotonic_ns(),service_finish_ns=None,lateness_ns=started-due,skipped_periods=int(skipped),extra_service_within_period=extra,physics_start_s=float(wall.plant.data.time),current_receipt_index=wall.active_receipt_index,model_version=runtime.get('model_sequence'),phase=wall.phase_records[-1]['phase'])
   ROWS['fast'].append(row)
  try:return original_interval(runtime,**kwargs)
  finally:
   if row is not None:
    row['interval_finish_ns']=time.monotonic_ns()
    if row['service_finish_ns'] is None:row['service_finish_ns']=row['interval_finish_ns']
 rt._execute_interval=interval
 original_next=wp.WallPhysicsSession.next_control_tick
 def next_tick(self):
  now=time.monotonic_ns()
  if ROWS['fast'] and ROWS['fast'][-1]['service_finish_ns'] is None:
   r=ROWS['fast'][-1];r.update(service_finish_ns=now,physics_before_wait_s=float(self.plant.data.time),command_currently_applied=self.plant.last_joint_torque.copy(),receipt_index=self.active_receipt_index)
  start=self.steps
  try:return original_next(self)
  finally:
   if ROWS['fast']:ROWS['fast'][-1].update(physical_steps_in_tick=self.steps-start,physical_finish_s=float(self.plant.data.time),physical_finish_host_ns=time.monotonic_ns())
 wp.WallPhysicsSession.next_control_tick=next_tick
 original_snapshot=rt.snapshot_task_call
 last_snapshot={}
 def snapshot(planner,args):
  created=time.monotonic_ns();payload=original_snapshot(planner,args);finished=time.monotonic_ns()
  life=RUNTIME.get('plan_lifecycle') if RUNTIME else None;req=life._outstanding if life else None
  reference_version=hashlib.sha256(pickle.dumps(args['current_reference_state'],protocol=5)).hexdigest()
  snap=Snapshot(-1 if req is None else req.request_id,0 if req is None else req.sensor_capture_ns,int(args['belief'].sequence),reference_version,args['phase'].value,created,payload,hashlib.sha256(payload).hexdigest())
  last_snapshot[snap.request_id]=snap
  ROWS['planner'].append(dict(request_id=snap.request_id,source_capture_ns=snap.source_capture_ns,model_version=snap.model_version,reference_version=snap.reference_version,phase=snap.phase,snapshot_creation_ns=created,snapshot_finish_ns=finished,payload_bytes=len(payload),snapshot_sha256=snap.sha256,immutable=True))
  return payload
 rt.snapshot_task_call=snapshot
 original_result=op.PlanLifecycle.result
 def result(self,future):
  received=time.monotonic_ns();value=original_result(self,future)
  req=self._future_requests.get(future) if self.process_worker else self._outstanding
  if req is not None:
   snap=last_snapshot.get(req.request_id)
   for row in reversed(ROWS['planner']):
    if row['request_id']==req.request_id:
     row.update(proposal_receive_ns=received,transfer_finish_ns=time.monotonic_ns(),proposal_schedule_version=value.executed.schedule.version,original_source_identity_preserved=snap is not None and snap.source_capture_ns==req.sensor_capture_ns,ownership_request_id=req.request_id)
     break
  return value
 op.PlanLifecycle.result=result
 original_validate=rt.validate_activation
 def validate(**kwargs):
  started=time.monotonic_ns();out=original_validate(**kwargs)
  ROWS['admission'].append(dict(revalidation_start_ns=started,revalidation_finish_ns=time.monotonic_ns(),current_model_sequence=kwargs['belief'].sequence,request_sequence=kwargs['request_sequence'],phase=kwargs['phase'].value,feasible=out['feasible'],checks=out))
  return out
 rt.validate_activation=validate
 original_fit=rt._fit_and_replay_commissioning
 def fit(*args,**kwargs):
  data=time.monotonic_ns();value=original_fit(*args,**kwargs);ready=time.monotonic_ns()
  ROWS['commissioning'].append(dict(data_available_ns=data,worker_start_ns=data,estimate_ready_ns=ready,owner_pid=os.getpid(),sequence=value[1].sequence,synchronous=True))
  return value
 rt._fit_and_replay_commissioning=fit
 original_apply=wp.WallPhysicsSession.apply
 def apply(self,*args,**kwargs):
  start=time.monotonic_ns()
  try:return original_apply(self,*args,**kwargs)
  finally:
   if self.applied_commands:
    receipt=self.applied_commands[-1]
    ROWS['model'].append(dict(write_start_ns=start,write_finish_ns=time.monotonic_ns(),model_sequence=self.runtime.get('model_sequence'),receipt_index=self.active_receipt_index,source_capture_ns=receipt.get('source_capture_ns'),apply_ns=receipt.get('apply_ns'),activation_age_ms=receipt.get('sensor_age_at_apply_ms'),validation_model_version=receipt.get('validation_model_version')))
 wp.WallPhysicsSession.apply=apply

def evidence():
 import study_common as sc
 life=RUNTIME.get('plan_lifecycle') if RUNTIME else None
 return sc.clean(dict(rows=ROWS,native_requests=[] if life is None else life.records(),plant_owner_pid=os.getpid(),plant_count=1,Q_calls=0,G_calls=0,learning_updates=0))
