"""Same original TASK process; exact per-request mechanics reuse only."""
import os,time,pickle,contextvars
SCOPE=contextvars.ContextVar('exact_worker_request',default=None);INSTALLED=False
def install_kernels():
 global INSTALLED
 if INSTALLED:return
 import native_vectors
 native_vectors.install(expanded=True)
 from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveMechanicsScreenV22 as C
 original=C.evaluate
 def evaluate(self,belief,candidate,schedule):
  scope=SCOPE.get()
  if scope is None:return original(self,belief,candidate,schedule)
  # Complete raw dataclasses, including all screen limits, belief, geometry,
  # residual weights, candidate fields, schedule coefficients and certificates.
  key=pickle.dumps((self,belief,candidate,schedule),protocol=5)
  if key in scope['cache']:
   scope['hits']+=1;return pickle.loads(scope['cache'][key])
  value=original(self,belief,candidate,schedule);scope['cache'][key]=pickle.dumps(value,protocol=5);scope['misses']+=1;return value
 C.evaluate=evaluate;INSTALLED=True
def warm():
 import slow_owner
 ready=slow_owner.warm();install_kernels()
 if os.environ.get('FAST_NATIVE_SMALL_KERNELS')=='N5':
  import native_small_kernels
  native_small_kernels.install()
 if os.environ.get('FAST_ADMISSION_KEY')=='RAW_A1':
  import admission_key
  admission_key.install()
 if os.environ.get('FAST_NATIVE_GEOMETRY')=='N6':
  import native_geometry
  native_geometry.install()
 if os.environ.get('FAST_NATIVE_VALUE_TREE')=='N8':
  import native_value_tree
  native_value_tree.install()
 if os.environ.get('FAST_NATIVE_QUINTIC')=='N9':
  import native_quintic
  native_quintic.install()
 if os.environ.get('FAST_NATIVE_INTERVALS')=='N12':
  import native_intervals
  native_intervals.install()
 if os.environ.get('FAST_NATIVE_BOOL_REDUCTIONS')=='N13':
  import native_bool_reductions
  native_bool_reductions.install()
 if os.environ.get('FAST_GEOMETRY_TRANSACTION')=='GEO1':
  import geometry_transaction_reuse
  geometry_transaction_reuse.install()
 if os.environ.get('FAST_WORKER_NUMERICAL_REUSE')=='W2':
  import worker_numeric_reuse
  worker_numeric_reuse.install()
 if os.environ.get('FAST_TASK_DECODE_ONCE')=='C13':
  import task_decode_once
  task_decode_once.install()
 ready.update(fast_task_owner='W1_EXACT_REQUEST_PROOF_REUSE',plant_owner=False,worker_numeric_reuse=os.environ.get('FAST_WORKER_NUMERICAL_REUSE','OFF'),native_small_kernels=os.environ.get('FAST_NATIVE_SMALL_KERNELS','OFF'));return ready
def task_with_certificates(payload):
 warm()
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 from traction_mpc_stage4 import estimator_v2 as ma
 import admission_certificates
 started=time.monotonic_ns();before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS;scope=dict(cache={},hits=0,misses=0);token=SCOPE.set(scope)
 geo_token=None
 if os.environ.get('FAST_GEOMETRY_TRANSACTION')=='GEO1':
  import geometry_transaction_reuse as geo
  geo_token=geo.SCOPE.set({})
 try:
  try:
   decoded=pickle.loads(payload) if os.environ.get('FAST_TASK_DECODE_ONCE')=='C13' else None
   if decoded is not None:
    import task_decode_once
    value=task_decode_once.EXECUTE(decoded)
   else:value=op.execute_task_snapshot(payload)
   result={'value':value};native_finish=time.monotonic_ns()
   result['multirate_mechanics_certificates']=(task_decode_once.PREPARE(decoded,value) if decoded is not None else admission_certificates.prepare(payload,value))
   if decoded is not None:result['decode_once_evidence']=task_decode_once.EVIDENCE
   result['multirate_mechanics_certificates']['worker_exact_reuse']=dict(hits=scope['hits'],misses=scope['misses'],key='complete raw self/belief/candidate/schedule bytes; one immutable request only',numeric_counts=scope.get('numerical_counts',{}))
  except BaseException as error:
   native_finish=time.monotonic_ns();result={'worker_exception':f'{type(error).__name__}:{error}'}
   if hasattr(error,'terminal_reference_selection'):result['terminal_reference_selection']=error.terminal_reference_selection
  finished=time.monotonic_ns()
  result.update(worker_start_ns=started,native_decision_finish_ns=native_finish,proposal_ready_ns=finished,compute_finish_ns=finished,research_model_invocations=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,model_counter_scope='entire original decision plus selected/escape mechanics preparation')
  return result
 finally:
  SCOPE.reset(token)
  if geo_token is not None:geo.SCOPE.reset(geo_token)
def install_parent():
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 op._warm_planner_process=warm;op._process_task_snapshot=task_with_certificates
