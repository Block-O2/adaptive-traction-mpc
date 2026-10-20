"""Versioned envelope adapter: original C13 TASK worker and native authority.

No live plant is sent to this worker. Q ranks exact same-state candidates;
native feasibility, prepare_decision, proof preparation and main admission stay.
"""
import os,time,pickle,hashlib,functools,json,traceback
from types import SimpleNamespace
from dataclasses import replace
TAG='B_NATIVE_Q_EXISTING_TASK_WORKER_V1'
COORD=None;CONFIG=None;FINAL_PAYLOAD=None
def warm(config):
 global COORD,CONFIG
 if COORD is not None:return
 import study_common as sc,shared_nominal,certified_snapshot_v2 as cert,q_first_method
 CONFIG=dict(config)
 assert sc.sha(sc.Path(config['weights'])/'weights.npz')==config['weights_sha256']
 shared_nominal.install();q_first_method.native_local=cert.native_local
 
 if config.get('coordination_table') is not None:
  from exploration_coordinator import TableCoordinator
  COORD=TableCoordinator(config)
 else:
  COORD=q_first_method.QFirstInterface({**config,'delay_replay':False})
 assert COORD.K==3
 assert not any(k in sc.sys.modules for k in ('planning','known_model'))
def task_with_certificates(payload):
 global FINAL_PAYLOAD
 import study_common as sc,fast_task_owner as fast,task_decode_once,admission_certificates
 import shared_nominal,certified_snapshot_v2 as cert,certified_apply
 from traction_mpc_stage4 import estimator_v2 as ma
 decoded=pickle.loads(payload)
 if isinstance(decoded,tuple) and len(decoded)==2:
  # The native initial TASK capture precedes the modifiable coordination
  # boundary. It owns no Q proposal and must use unchanged original C13.
  assert isinstance(decoded[1],dict) and hasattr(decoded[0],'decide')
  FINAL_PAYLOAD=payload
  return fast.task_with_certificates(payload)
 started=time.monotonic_ns();before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
 scope=dict(cache={},hits=0,misses=0);token=fast.SCOPE.set(scope)
 result={};native_finish=started
 try:
  tag,raw,hint=decoded;assert tag==TAG
  req=hint['request'];assert req.stage=='TASK' and hashlib.sha256(raw).hexdigest()==hint['base_payload_sha256']
  adaptive,args=pickle.loads(raw)
  class Observation:
   def as_array(self):return hint['observation'].copy()
  b=dict(adaptive_planner=adaptive,planner=adaptive.planner,arguments=args,request=req,belief=args['belief'],observation=Observation(),spec=hint['spec'],task_state=hint['task_state'],physical_now=hint['physical_now'],task_start_time=hint['task_start_time'],reference_acceleration=hint['reference_acceleration'],interface=SimpleNamespace(measured_force_world_n=hint['measured_force_world_n'],measured_moment_world_nm=hint['measured_moment_world_nm']),sac_hooks=SimpleNamespace(force_integral=hint['force_integral'],moment_integral=hint['moment_integral']))
  prior_carry=COORD.carry.copy();prior_count=COORD.count.copy();nrows=len(COORD.search_rows)
  selection=None;late_carry=False
  with cert.boundary(b),shared_nominal.boundary(b):
   COORD.decision_boundary(b)
   selection=COORD.search_rows[-1] if len(COORD.search_rows)>nrows else None
   def prepared():
    global FINAL_PAYLOAD
    certified_apply.ensure(cert,b)
    FINAL_PAYLOAD=cert.snapshot_task_call(adaptive,args);key=hashlib.sha256(FINAL_PAYLOAD).hexdigest()
    planner,decision=pickle.loads(cert.LOCAL.build['certificates'][key])
    if getattr(planner.planner,'safe_fallback_enabled',False):
     from traction_mpc_stage5.full3d_adaptive_integration_v1.safe_fallback import prepare_decision
     decision=prepare_decision(decision,planner.planner,args['belief'])
    return decision,key
   decision,final_hash=prepared()
   scientific=CONFIG['execution_mode']=='SCIENTIFIC_SIMULATION'
   deadline=min(40.,55.-float(CONFIG.get('activation_reserve_ms',36.))) if CONFIG.get('strict55_guard',True) else 40.
   age_before=(time.monotonic_ns()-req.sensor_capture_ns)/1e6
   proposed=selection['applied_plan'].copy() if selection is not None else None
   if not scientific and selection is not None and age_before>deadline:
    c=selection['context'];phase=c['phase'];i=prior_count[phase]
    action=prior_carry[('OUTBOUND','RETURN').index(phase),i] if i<5 else sc.np.zeros(3)
    COORD.carry=prior_carry.copy();COORD.table=prior_carry.copy();COORD.apply(b,c,action,sc.np.zeros(3))
    selection.update(applied_plan=prior_carry.copy(),plan_changed=False,late=True,late_discard=True,selection_budget_s=deadline/1000.,delay_mode='immutable source worker guard; original physical bridge40 retained')
    decision,final_hash=prepared();late_carry=True
   native_finish=time.monotonic_ns()
   e=dict(request_id=req.request_id,source_capture_ns=req.sensor_capture_ns,base_payload_sha256=hint['base_payload_sha256'],final_payload_sha256=final_hash,source_inputs=sc.clean(hint),selection_row=selection,proposed_plan=proposed,method=CONFIG['method'],coordinator_location='original C13 TASK worker',worker_elapsed_ms=(native_finish-started)/1e6,source_age_at_worker_return_ms=(native_finish-req.sensor_capture_ns)/1e6,admission=dict(strict55_guard=CONFIG.get('strict55_guard',True),worker_return_deadline_age_ms=deadline,source_age_before_admission_ms=age_before,late_carry=late_carry,bridge_ms=40,generic_expiry_ms=100,scientific=scientific),Q_calls=0 if COORD.network is None else COORD.network.Q_calls,G_calls=0,P_performance_calls=0)
   # This metadata grants no command authority; the original lifecycle decides.
   decision=replace(decision,executed=replace(decision.executed,execution_screen={**decision.executed.execution_screen,'_E5_worker_evidence':e}))
   result={'value':decision,'m2_worker_evidence':e}
   result['multirate_mechanics_certificates']=task_decode_once.PREPARE((adaptive,args),decision)
   result['multirate_mechanics_certificates']['worker_exact_reuse']=dict(hits=scope['hits'],misses=scope['misses'],key='complete raw self/belief/candidate/schedule bytes; one immutable request only')
 except BaseException as error:
  native_finish=time.monotonic_ns();result={'worker_exception':f'{type(error).__name__}:{error}','adapter_traceback':traceback.format_exc()}
  if hasattr(error,'terminal_reference_selection'):result['terminal_reference_selection']=error.terminal_reference_selection
 finally:fast.SCOPE.reset(token)
 finished=time.monotonic_ns()
 result.update(worker_start_ns=started,native_decision_finish_ns=native_finish,proposal_ready_ns=finished,compute_finish_ns=finished,research_model_invocations=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,model_counter_scope='entire coordinator plus native decision and original proof preparation')
 return result

def install_parent(config):
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 # DirectExecutor calls its own worker. The env names only this frozen input.
 os.environ['FAST_M2_CONFIG']=config['durable_config_path']
 original=op._process_task_snapshot
 def _process_task_snapshot(payload):return original(payload)
 op._process_task_snapshot=_process_task_snapshot

def make_interface(config):
 from async_native_main import AsyncNativeInterface
 from study_common import Interface,rt
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 # AsyncNativeInterface binds immutable hints and original source timestamps.
 # Its old warm callback is unused by DirectExecutor; C13 warming stays intact.
 original_runtime_snapshot=rt._run_executed_case.__globals__['snapshot_task_call']
 interface=AsyncNativeInterface(config)
 interface.original_snapshot=original_runtime_snapshot
 # commissioning_owner compiles the unchanged loop into a copied namespace.
 # Bind this actual caller too; retaining its original multirate snapshot
 # preserves source identity and existing immutable snapshot telemetry.
 rt._run_executed_case.__globals__['snapshot_task_call']=rt.snapshot_task_call
 install_parent(config)
 def finish(env,metric):
  Interface.finish(interface,env,metric)
  import fast_task_ipc,study_common as sc
  rows=[r['m2_worker_evidence'] for r in fast_task_ipc.ROWS if 'm2_worker_evidence' in r]
  sc.save(metric['name']+'_HOST_COORDINATOR.json',dict(method=config['method'],rows=rows,hints=interface.hints,config=config,all_collected_requests_including_rejected=True))
  sc.save(metric['name']+'_SELECTIONS.json',dict(method=config['method'],rows=[r['selection_row'] for r in rows if r.get('selection_row')],network_Q_calls=max([r['Q_calls'] for r in rows] or [0]),network_G_calls=0,P_performance_calls=0))
 interface.finish=finish
 return interface
