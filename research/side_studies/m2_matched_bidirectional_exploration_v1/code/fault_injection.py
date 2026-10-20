"""Bounded, prospective diagnostic faults; original admission/carry/abort only.

No live model, source timestamp, mask, control law or safety limit is modified.
COMMISSIONING ID3 and TASK ID6/packet1 are distinct registered populations.
"""
import time,pickle,copy
CONFIG=None;ROWS=[]
def altered_result(result,cfg):
 out=dict(result);before=time.monotonic_ns();kind=cfg['kind']
 if kind in ('worker_delay','expired_result'):
  delay=cfg['delay_ms']/1000.;assert 0<=delay<=.120
  time.sleep(delay)
 elif kind=='model_version_mismatch':
  # Deliberately invalidate ALL proof identities; original native admission
  # must recompute against the unchanged actual current belief/model.
  cert=copy.deepcopy(out['multirate_mechanics_certificates'])
  cert['proofs']={'REGISTERED_WRONG_MODEL_IDENTITY_'+k:v for k,v in cert['proofs'].items()}
  cert['model_sequence']+=1;out['multirate_mechanics_certificates']=cert
 elif kind=='explicit_native_rejection':
  if cfg['stage']=='COMMISSIONING':
   value,args,kwargs=pickle.loads(out['payload']);value['feasible']=False
   value['attempts'].append(dict(feasible=False,reason='REGISTERED_EXPLICIT_REJECTION_DIAGNOSTIC'))
   out['payload']=pickle.dumps((value,args,kwargs),protocol=5)
  # TASK explicit rejection is applied only after the original current check.
 else:raise ValueError('UNKNOWN_REGISTERED_FAULT')
 after=time.monotonic_ns()
 out['fault_injection']=dict(config=cfg,actual_begin_ns=before,actual_finish_ns=after,
  original_compute_finish_ns=result.get('compute_finish_ns',result.get('proposal_ready_ns')),
  original_worker_start_ns=result.get('worker_start_ns'),source_timestamp_rewritten=False,
  actual_live_model_modified=False,known_invalid_action_written=False)
 if cfg['stage']=='TASK':out.update(compute_finish_ns=after,proposal_ready_ns=after)
 else:out['proposal_ready_ns']=after
 return out
def task_result(result,identity,cfg):
 if cfg is None or cfg['stage']!='TASK' or identity!=cfg['packet_identity']:return result
 return altered_result(result,cfg)
def slow_execute(kind,payload,cfg):
 import slow_owner
 return altered_result(slow_owner.execute(kind,payload),cfg)
class FaultFuture:
 def __init__(self,future):self.future=future;self.recorded=False
 def done(self):return self.future.done()
 def result(self,timeout=None):
  out=self.future.result(timeout=timeout)
  if not self.recorded:
   ROWS.append(dict(event='COMMISSIONING_FAULT_RESULT_RECEIVED',receive_ns=time.monotonic_ns(),details=out['fault_injection']));self.recorded=True
  return out
class CommissioningPool:
 def __init__(self,pool,cfg):self.pool=pool;self.cfg=cfg
 def submit(self,fn,*args):
  import multirate
  runtime=multirate.RUNTIME;life=None if runtime is None else runtime.get('plan_lifecycle');request=None if life is None else life._outstanding
  if (fn.__name__=='execute' and args and args[0]=='commissioning_target' and request is not None and request.stage=='COMMISSIONING' and request.request_id==self.cfg['request_id']):
   ROWS.append(dict(event='COMMISSIONING_FAULT_DISPATCH',request_id=request.request_id,source_capture_ns=request.sensor_capture_ns,request_ns=request.request_ns))
   return FaultFuture(self.pool.submit(slow_execute,*args,self.cfg))
  return self.pool.submit(fn,*args)
 def shutdown(self,*args,**kwargs):return self.pool.shutdown(*args,**kwargs)
def verify_task_submission(executor,args):
 if CONFIG is None or CONFIG['stage']!='TASK' or not args:return
 if executor.sequence+1!=CONFIG['packet_identity']:return
 import multirate
 request=multirate.RUNTIME['plan_lifecycle']._outstanding
 assert request.stage=='TASK' and request.request_id==CONFIG['request_id'],'REGISTERED_FAULT_REQUEST_MAPPING_CHANGED'
 ROWS.append(dict(event='TASK_FAULT_DISPATCH',request_id=request.request_id,packet_identity=executor.sequence+1,source_capture_ns=request.sensor_capture_ns,request_ns=request.request_ns))
def install(cfg):
 global CONFIG
 CONFIG=dict(cfg['fault_injection']);CONFIG['run_id']=cfg['id'];ROWS.clear()
 assert CONFIG['stage'] in ('COMMISSIONING','TASK')
 assert CONFIG['kind'] in ('worker_delay','expired_result','model_version_mismatch','explicit_native_rejection')
 if CONFIG['stage']=='COMMISSIONING':
  assert CONFIG['kind']!='model_version_mismatch','NO_VERSIONED_MODEL_CERTIFICATE_IN_COMMISSIONING_SELECTOR'
  import commissioning_owner as c
  c.POOL=CommissioningPool(c.POOL,CONFIG)
 else:
  import fast_task_ipc as ipc
  ipc.DirectExecutor.fault_config=CONFIG
  if CONFIG['kind']=='explicit_native_rejection':
   import study_common as sc,multirate
   original=sc.rt.validate_activation
   def validate(**kwargs):
    out=original(**kwargs);life=multirate.RUNTIME['plan_lifecycle'];request=life._outstanding
    if request is not None and request.request_id==CONFIG['request_id']:
     out=dict(out,original_feasible_before_injected_rejection=out['feasible'],feasible=False,registered_explicit_rejection=True)
     ROWS.append(dict(event='ORIGINAL_CURRENT_CHECK_THEN_REGISTERED_REJECTION',request_id=request.request_id,at_ns=time.monotonic_ns(),original_feasible=out['original_feasible_before_injected_rejection']))
    return out
   sc.rt.validate_activation=validate
   sc.rt._run_executed_case.__globals__['validate_activation']=validate
