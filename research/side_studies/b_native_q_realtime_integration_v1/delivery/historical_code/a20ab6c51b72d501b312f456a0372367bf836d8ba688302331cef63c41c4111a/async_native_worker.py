"""E5 current-request computation in the already existing prewarmed process."""
import time,pickle,hashlib
from dataclasses import replace
from types import SimpleNamespace
COORD=None;ORIGINAL_EXECUTE=None;CONFIG=None
class Observation:
 def __init__(self,value):self.value=value
 def as_array(self):return self.value.copy()
def warm(config):
 global COORD,ORIGINAL_EXECUTE,CONFIG
 import study_common as sc
 import call_audit,profiling_instrumentation as profile,batched_mechanics,shared_nominal,certified_snapshot_v2 as cert,q_first_method
 from native_method import NativeInterface
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 CONFIG=dict(config);assert sc.sha(sc.Path(config['weights'])/'weights.npz')==config['weights_sha256']
 if config.get('pipeline_batch'):batched_mechanics.install({**config,'public_version':'C2'})
 call_audit.install();profile.install();shared_nominal.install();q_first_method.native_local=cert.native_local
 class Coordinator(NativeInterface):
  def choose(self,b,c):return q_first_method.QFirstInterface.choose(self,b,c)
 COORD=Coordinator({**config,'delay_replay':False})
 ORIGINAL_EXECUTE=op.execute_task_snapshot;op.execute_task_snapshot=execute
 assert not any(x in sc.sys.modules for x in ('planning','known_model'))
 return time.monotonic_ns()
def execute(payload):
 obj=pickle.loads(payload)
 if not(isinstance(obj,tuple) and len(obj)==3 and obj[0]=='B_NATIVE_Q_EXISTING_TASK_WORKER_V1'):return ORIGINAL_EXECUTE(payload)
 _,raw,hint=obj;req=hint['request'];start=time.monotonic_ns();assert hashlib.sha256(raw).hexdigest()==hint['base_payload_sha256'] and req.stage=='TASK'
 import study_common as sc,shared_nominal,certified_snapshot_v2 as cert,certified_apply,profiling_instrumentation as profile,batched_mechanics
 profile.EVENTS.clear();batched_mechanics.EVENTS.clear();certified_apply.EVENTS.clear();shared_nominal.EVENTS.clear()
 adaptive,args=pickle.loads(raw);b=dict(adaptive_planner=adaptive,planner=adaptive.planner,arguments=args,request=req,belief=args['belief'],observation=Observation(hint['observation']),spec=hint['spec'],task_state=hint['task_state'],physical_now=hint['physical_now'],task_start_time=hint['task_start_time'],reference_acceleration=hint['reference_acceleration'],interface=SimpleNamespace(measured_force_world_n=hint['measured_force_world_n'],measured_moment_world_nm=hint['measured_moment_world_nm']),sac_hooks=SimpleNamespace(force_integral=hint['force_integral'],moment_integral=hint['moment_integral']))
 prior_carry=COORD.carry.copy();prior_counts=COORD.count.copy();nrows=len(COORD.search_rows);nlabels=len(COORD.labels);scientific=CONFIG.get('execution_mode')=='SCIENTIFIC_SIMULATION';admission=dict(scientific=scientific,late_carry=False,activation_reserve_ms=CONFIG.get('activation_reserve_ms'),generic_expiry_ms=100,bridge_ms=40,evaluator_activation_ms=55)
 with cert.boundary(b):
  with shared_nominal.boundary(b):
   COORD.decision_boundary(b)
   selection=COORD.search_rows[-1] if len(COORD.search_rows)>nrows else None
   certified_apply.ensure(cert,b)
   slot=cert.LOCAL.build
   def prepared():
    current=cert.snapshot_task_call(adaptive,args);key=hashlib.sha256(current).hexdigest();planner,decision=pickle.loads(slot['certificates'][key])
    if getattr(planner.planner,'safe_fallback_enabled',False):
     from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import prepare_decision
     decision=prepare_decision(decision,planner.planner,args['belief'])
    return decision,key
   decision,final_hash=prepared();age_ms=(time.monotonic_ns()-req.sensor_capture_ns)/1e6
   if not scientific:
    reserve=float(CONFIG['activation_reserve_ms']);deadline=min(40.,55.-reserve)
    admission.update(worker_return_deadline_age_ms=deadline,source_age_before_admission_ms=age_ms)
    if selection is not None and age_ms>deadline:
     # Prospective proposal only: it has not left the worker or actuated.
     # Retain the previously declared valid carry and recertify that exact
     # snapshot; no timestamp changes or retroactive action writes.
     c=selection['context'];phase=c['phase'];i=prior_counts[phase];action=prior_carry[('OUTBOUND','RETURN').index(phase),i] if i<5 else sc.np.zeros(3)
     COORD.carry=prior_carry.copy();COORD.table=prior_carry.copy();COORD.apply(b,c,action,sc.np.zeros(3))
     if len(COORD.labels)>nlabels:COORD.labels[nlabels:]=COORD.labels[-1:]
     selection.update(applied_plan=prior_carry.copy(),plan_changed=False,late=True,late_discard=True,selection_budget_s=deadline/1000.,delay_mode='actual immutable-source worker deadline with registered downstream reserve')
     certified_apply.ensure(cert,b);decision,final_hash=prepared();admission['late_carry']=True
   elapsed=(time.monotonic_ns()-start)/1e6;age_ms=(time.monotonic_ns()-req.sensor_capture_ns)/1e6
   if selection is not None:
    selection['coordinator_location']='existing native task worker';selection['full_worker_elapsed_ms']=elapsed;selection['source_age_at_worker_return_ms']=age_ms
   evidence=dict(request_id=req.request_id,source_capture_ns=req.sensor_capture_ns,base_payload_sha256=hint['base_payload_sha256'],final_payload_sha256=final_hash,worker_elapsed_ms=elapsed,source_age_at_worker_return_ms=age_ms,admission=admission,selection_row=selection,profile=profile.evidence()['summary'],batch_component_evaluations=sum(e['sample_count'] for e in batched_mechanics.EVENTS),P_performance_calls=0,Q_calls=COORD.network.Q_calls,G_calls=0,declared_suffix_labels=None)
   assert not any(x in sc.sys.modules for x in ('planning','known_model'))
   e=replace(decision.executed,execution_screen={**decision.executed.execution_screen,'_E5_worker_evidence':evidence});return replace(decision,executed=e)
