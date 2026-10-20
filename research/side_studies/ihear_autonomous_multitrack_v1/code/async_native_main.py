"""E5: freeze causal inputs; compute Q in the existing native TASK worker."""
from study_common import *
import pickle,functools,hashlib
from types import SimpleNamespace
TAG='B_NATIVE_Q_EXISTING_TASK_WORKER_V1'
class AsyncNativeInterface(Interface):
 def __init__(self,request):
  super().__init__();self.request=request;self.method=request.get('method','M2');self.search_rows=[];self.labels=[];self.skips=[];self.network=None;self.hints=[];self.pending=None
  from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
  import async_native_worker,batched_mechanics
  self.original_snapshot=op.snapshot_task_call
  op._warm_planner_process=functools.partial(async_native_worker.warm,request)
  if request.get('pipeline_batch'):batched_mechanics.install({**request,'public_version':'C2'})
  def snapshot(adaptive,args):
   raw=self.original_snapshot(adaptive,args);pending=self.pending
   if pending is None or pending['adaptive_id']!=id(adaptive) or pending['args_id']!=id(args):return raw
   self.pending=None;hint=pending['hint'];hint['base_payload_sha256']=hashlib.sha256(raw).hexdigest()
   self.hints.append({k:hint[k] for k in ('request','base_payload_sha256')})
   return pickle.dumps((TAG,raw,hint),protocol=5)
  op.snapshot_task_call=snapshot;rt.snapshot_task_call=snapshot
 def decision_boundary(self,b):
  req=b['request'];assert req.stage=='TASK';assert self.pending is None,'UNCONSUMED_NATIVE_REQUEST_HINT'
  # Only current deployable observations, commissioned belief via base
  # snapshot, current reference and current task/cost history are sent.
  hint=dict(request=req,spec=b['spec'],task_state=b['task_state'],physical_now=float(b['physical_now']),task_start_time=float(b['task_start_time']),observation=b['observation'].as_array().copy(),reference_acceleration=np.asarray(b['reference_acceleration']).copy(),measured_force_world_n=np.asarray(b['interface'].measured_force_world_n).copy(),measured_moment_world_nm=np.asarray(b['interface'].measured_moment_world_nm).copy(),force_integral=float(b['sac_hooks'].force_integral),moment_integral=float(b['sac_hooks'].moment_integral))
  b['planner'].residual_spec={};self.pending=dict(adaptive_id=id(b['adaptive_planner']),args_id=id(b['arguments']),hint=hint)
 def finish(self,env,metric):
  super().finish(env,metric);rows=[];other=[]
  for item in env.summary.get('learning_records',[]):
   e=item.get('selected_plan',{}).get('execution_screen',{}).get('_E5_worker_evidence')
   if not e:continue
   if e.get('selection_row'):rows.append(e['selection_row'])
   other.append(dict(request_id=e['request_id'],snapshot_hash=e['base_payload_sha256'],source_capture_ns=e['source_capture_ns'],compute_payload_hash=e['final_payload_sha256'],worker_elapsed_ms=e['worker_elapsed_ms'],source_age_at_worker_return_ms=e['source_age_at_worker_return_ms'],admission=e['admission'],profile=e['profile'],batch_component_evaluations=e['batch_component_evaluations'],selected_plan_activated=item.get('selected_plan_activated'),current_model_revalidation_retained=True,original_safe_fallback_prepare_retained=True))
  self.search_rows=rows
  save(metric['name']+'_SELECTIONS.json',dict(method='M2',rows=rows,network_Q_calls=max([r.get('Q_calls',0) for r in rows] or [0]),network_G_calls=0,P_performance_calls=0,delay_replay=self.request.get('execution_mode')=='REALTIME_CHARACTERIZATION',coordinator_location='existing native task worker, current immutable request'))
  save(metric['name']+'_ASYNC_NATIVE_WORKER.json',dict(rows=other,hints=self.hints,preparation='Only frozen Q parameters and imports prewarm offline; all state-dependent context/Q/native certificates use current request snapshot',authority='original native TASK request and original worker/activation/expiry chain',no_future_state=True,no_free_physics_pause_for_actual_wall=True))
