"""E3: same-request, exact-byte snapshot decision reuse; native prep retained."""
import threading,pickle,hashlib,time,contextlib,traceback
import shared_nominal
from native_core import np,graph_action,snapshot_task_call
LOCK=threading.Lock();PENDING=None;EVENTS=[];LOCAL=threading.local();INSTALLED=False
@contextlib.contextmanager
def boundary(b):
 global PENDING
 req=b['request'];slot=dict(owner=req.request_id,source_capture_ns=req.sensor_capture_ns,certificates={})
 with LOCK:PENDING=None
 assert getattr(LOCAL,'build',None) is None
 LOCAL.build=slot
 try:yield
 finally:
  LOCAL.build=None
  with LOCK:PENDING=slot
def native_local(b,c,table,count):
 clone,args=pickle.loads(snapshot_task_call(b['adaptive_planner'],b['arguments']));phase=c['phase'];i=count[phase];a=table[('OUTBOUND','RETURN').index(phase),i] if i<5 else np.zeros(3)
 clone.planner.residual_spec={phase:graph_action(a*.2,c['start_m'])}
 pre=snapshot_task_call(clone,args);key=hashlib.sha256(pre).hexdigest();t=time.monotonic();decision=clone.decide(**args);e=decision.executed;meta=e.execution_screen.get('coordination_residual_v2',{})
 slot=getattr(LOCAL,'build',None)
 if slot is not None:slot['certificates'][key]=pickle.dumps((clone,decision),protocol=5)
 return dict(feasible=bool(e.feasible),proposal_accepted=not meta or meta.get('status')=='ACCEPTED',S=float(e.total_cost),selection_mode=decision.selection_mode,reason=meta.get('reason'),native_wall_s=time.monotonic()-t,duration_s=e.schedule.duration_s if e.schedule else None,target=e.target_q_rad,call_stack=traceback.format_stack(limit=5))
def install():
 global INSTALLED
 if INSTALLED:return
 INSTALLED=True
 import q_first_method
 q_first_method.native_local=native_local
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 original_compute=op.PlanLifecycle.compute;original_execute=op.execute_task_snapshot
 def compute(self,request,operation,*args):
  LOCAL.request=request
  try:return original_compute(self,request,operation,*args)
  finally:LOCAL.request=None
 def execute(payload):
  global PENDING
  req=getattr(LOCAL,'request',None);key=hashlib.sha256(payload).hexdigest();cert=None;reason='NO_PENDING_CERTIFICATE';expected=[]
  with LOCK:
   slot=PENDING
   if slot is not None:
    expected=list(slot['certificates']);reason='OWNERSHIP_MISMATCH'
    if req is not None and req.request_id==slot['owner'] and req.sensor_capture_ns==slot['source_capture_ns']:
     reason='EXACT_SNAPSHOT_HASH_MISS'
     if time.monotonic_ns()-req.sensor_capture_ns>=100_000_000:reason='SOURCE_ALREADY_EXPIRED'
     elif key in slot['certificates']:cert=slot['certificates'][key];reason='EXACT_SNAPSHOT_SAME_REQUEST_HIT'
     PENDING=None
  EVENTS.append(dict(request_id=None if req is None else req.request_id,source_capture_ns=None if req is None else req.sensor_capture_ns,payload_sha256=key,certificate_payload_hashes=expected,reason=reason,decision_reused=cert is not None,checked_ns=time.monotonic_ns(),native_safe_fallback_prepare_retained=True,current_model_activation_revalidation_retained=True))
  if cert is None:return original_execute(payload)
  planner,decision=pickle.loads(cert)
  if getattr(planner.planner,'safe_fallback_enabled',False):
   from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import prepare_decision
   _,args=pickle.loads(payload);decision=prepare_decision(decision,planner.planner,args['belief'])
  return decision
 op.PlanLifecycle.compute=compute;op.execute_task_snapshot=execute
