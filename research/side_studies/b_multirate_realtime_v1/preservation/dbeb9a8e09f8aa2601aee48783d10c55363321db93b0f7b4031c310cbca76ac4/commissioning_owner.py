"""Separate slow computation while the one plant owner services legal carry."""
import time,pickle,hashlib,concurrent.futures as cf,multiprocessing as mp,inspect
from pathlib import Path
import numpy as np
POOL=None;READY=None;LAST=None;SERVICING=False;ROWS=[];PUBLICATIONS=[]

def install(revision,mode):
 global POOL,READY
 import study_common as sc,multirate,slow_owner
 rt=sc.rt
 POOL=cf.ProcessPoolExecutor(max_workers=1,mp_context=mp.get_context('spawn'))
 created=time.monotonic_ns();READY=POOL.submit(slow_owner.warm).result(timeout=90);READY.update(created_ns=created,collected_ns=time.monotonic_ns(),scope='Before physical epoch')
 original_interval=rt._execute_interval
 def interval(runtime,**kwargs):
  global LAST
  result=original_interval(runtime,**kwargs)
  if not SERVICING:LAST=dict(candidate=kwargs['candidate'],mapped_override=kwargs.get('mapped_override'),actuation_enabled=kwargs['actuation_enabled'])
  return result
 rt._execute_interval=interval
 def service():
  global SERVICING
  runtime=multirate.RUNTIME;assert runtime is not None and LAST is not None,'NO_LEGAL_CARRY_AVAILABLE'
  assert runtime.get('plan_to_activate') is None,'CARRY_CANNOT_OWN_NEW_PROPOSAL_ACTIVATION'
  SERVICING=True
  try:
   truth,measurement=rt._capture_boundary(runtime)
   observation,interface=runtime['observer'].update(measurement,runtime['model'],human_model_version=str(runtime.get('model_sequence','population_prior_v1')))
   original_interval(runtime,observation=observation,interface=interface,measurement=measurement,**LAST)
  finally:SERVICING=False
 def restore_mutated_arrays(original,returned):
  if isinstance(original,np.ndarray):
   assert original.shape==returned.shape
   if not np.array_equal(original,returned,equal_nan=True):original[...] = returned
  elif isinstance(original,dict):
   for k in original:
    if k in returned:restore_mutated_arrays(original[k],returned[k])
  elif isinstance(original,(tuple,list)):
   for a,b in zip(original,returned):restore_mutated_arrays(a,b)
 def offload(kind,original,args,kwargs):
  data=time.monotonic_ns();payload=pickle.dumps((args,kwargs),protocol=5);snapshot=time.monotonic_ns();enqueued=time.monotonic_ns();future=POOL.submit(slow_owner.execute,kind,payload)
  services=0;runtime=multirate.RUNTIME;wall=None if runtime is None else runtime.get('wall_session')
  real=mode=='REALTIME_CHARACTERIZATION' and wall is not None and wall.active
  try:
   while not future.done():
    if real:
     due=wall.epoch_ns+(wall.steps//wall.sensor_steps+1)*5_000_000
     if time.monotonic_ns()>=due:
      service();services+=1
     else:time.sleep(min(.0005,max(0.,(due-time.monotonic_ns())/1e9)))
    else:time.sleep(.0005)
   result=future.result(timeout=90);received=time.monotonic_ns();value,newargs,newkwargs=pickle.loads(result['payload'])
   restore_mutated_arrays(args,newargs);restore_mutated_arrays(kwargs,newkwargs)
   row=dict(kind=kind,data_available_ns=data,snapshot_finish_ns=snapshot,enqueue_ns=enqueued,worker_start_ns=result['worker_start_ns'],estimate_ready_ns=result['proposal_ready_ns'],receive_ns=received,worker_pid=result['pid'],payload_bytes=len(payload),response_bytes=len(result['payload']),payload_sha256=hashlib.sha256(payload).hexdigest(),fast_services_while_pending=services,physics_paused_waiting=not real,model_version=None if runtime is None else runtime.get('model_sequence'),source_timestamp_rewritten=False)
   ROWS.append(row)
   if kind=='commissioning_fit':
    fit,updater,updates=value;validation=time.monotonic_ns();belief=updater.snapshot();valid=bool(fit.accepted and np.all(np.isfinite(belief.beta)) and np.all(np.isfinite(belief.state_residual_weights_nm)))
    assert valid,'PRIVATE_MODEL_VALIDATION_FAILED'
    # Publish the complete serialized fit/updater tuple in one owner-local return;
    # no live model/updater is exposed while estimate computation is in progress.
    PUBLICATIONS.append(dict(version=belief.sequence,validate_start_ns=validation,validate_finish_ns=time.monotonic_ns(),publish_ns=time.monotonic_ns(),immutable_belief_sha256=hashlib.sha256(pickle.dumps(belief,protocol=5)).hexdigest(),valid=True,estimator_math_unchanged=True))
   return value
  except BaseException as error:
   ROWS.append(dict(kind=kind,data_available_ns=data,enqueue_ns=enqueued,exception=str(error),fast_services_while_pending=services,disposition_ns=time.monotonic_ns()))
   raise
 target=rt.choose_feedback_commissioning_target
 rt.choose_feedback_commissioning_target=lambda *a,**kw:offload('commissioning_target',target,a,kw)
 if revision=='R3':
  fit=rt._fit_and_replay_commissioning
  rt._fit_and_replay_commissioning=lambda *a,**kw:offload('commissioning_fit',fit,a,kw)
 # After slow target computation, refresh actual admission/controller state.
 # The original PlanRequest source capture is deliberately not changed.
 source=inspect.getsource(rt._run_executed_case)
 anchor='            if commissioning_terminal_selection is not None and selection["feasible"]:'
 assert source.count(anchor)==1
 refresh='''            if not scientific:
                truth, measurement = _capture_boundary(runtime)
                observation, interface = observer.update(
                    measurement, runtime["model"],
                    human_model_version=str(runtime.get("model_sequence", "population_prior_v1")))
                measured_sleeve_gap_m = envelope.measured_sleeve_gap(
                    interface.human_position_world_m, interface.human_rotation_world)
'''
 source=source.replace(anchor,refresh+anchor)
 namespace=dict(rt.__dict__);exec(compile(source,'<multi-rate commissioning current-state refresh>','exec'),namespace)
 rt._run_executed_case=namespace['_run_executed_case']
 p=sc.STUDY/'versions'/(revision+'_INSTALLED_RUNTIME.py')
 if not p.exists():p.write_text(source)
 elif p.read_text()!=source:raise AssertionError('INSTALLED_RUNTIME_VERSION_CHANGED')

def close():
 global POOL
 if POOL is not None:POOL.shutdown(wait=True,cancel_futures=True);POOL=None
def evidence():return dict(worker_ready=READY,rows=ROWS,model_publications=PUBLICATIONS,closed=POOL is None,plant_in_worker=False)
