import os,sys,time,json,traceback,random
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
sys.dont_write_bytecode=True
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_matched_bidirectional_exploration_v1')
sys.path.insert(0,str(S/'code'))
def main(cfg_override=None,reuse=False):
 cfg=cfg_override if cfg_override is not None else json.loads(Path(sys.argv[1]).read_text());ident=cfg['id'];start=time.time()
 import lean_instrumentation
 lean_instrumentation.prime()
 import study_common as sc
 import numpy as np
 random.seed(cfg['seed']);np.random.seed(cfg['seed'])
 import multirate
 if not reuse:multirate.install(cfg['revision'],cfg['execution_mode'])
 else:
  for rows in multirate.ROWS.values():rows.clear()
  multirate.RUNTIME=None
 import fast_runtime
 fast_runtime.install(cfg)
 if cfg['revision'] in ('R2','R3'):
  import commissioning_owner
  if not reuse:commissioning_owner.install(cfg['revision'],cfg['execution_mode'])
  else:commissioning_owner.reopen()
 if cfg['revision']=='R3':
  import deferred_evaluation
  deferred_evaluation.install()
  import admission_certificates
  if not reuse:admission_certificates.install()
  else:
   deferred_evaluation.INSTANCES.clear()
   admission_certificates.CACHE.clear();admission_certificates.ROWS.clear()
 if cfg.get('fast_task_owner'):
  import fast_task_owner
  fast_task_owner.install_parent()
 if cfg.get('task_transport')=='DIRECT_D1':
  import fast_task_ipc
  fast_task_ipc.install(fast=cfg.get('fast_task_owner',False),scientific=cfg['execution_mode']=='SCIENTIFIC_SIMULATION',transport_warm=cfg.get('bidirectional_transport_warm',False))
 if cfg.get('fault_injection'):
  assert not reuse,'Registered fault diagnostics use independent fresh owners'
  import fault_injection
  fault_injection.install(cfg)
 if cfg.get('low_overhead_diagnostic'):
  import low_overhead_timing
  low_overhead_timing.install()
 from native_method import PrefixBInterface
 if cfg.get('host_coordinator'):
  import host_adapter
  cfg['durable_config_path']=str(S/'queue'/(ident+'.json'))
  interface=host_adapter.make_interface(cfg)
 else:
  interface=PrefixBInterface(dict(method='M0',prefix=cfg.get('prefix',{}),execution_mode=cfg['execution_mode']))
 from traction_mpc_stage4 import estimator_v2 as ma
 model_before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
 try:
  metric=sc.run(ident,interface,original=False,execution_mode=cfg['execution_mode'])
  metric['actual_new_main_model_inverse_dynamics_api_calls']=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-model_before
  result=dict(id=ident,status='COMPLETE',metric=metric,wall_seconds=time.time()-start,inputs=cfg,main_model_API_delta=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-model_before)
 except BaseException as e:
  result=dict(id=ident,status='FAILED',error=str(e),traceback=traceback.format_exc(),wall_seconds=time.time()-start,inputs=cfg,main_model_API_delta=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-model_before)
 finally:
  if cfg['revision'] in ('R2','R3'):
   commissioning_owner.close()
   sc.save(ident+'_COMMISSIONING_OWNER.json',commissioning_owner.evidence())
  if cfg['revision']=='R3':deferred_evaluation.finish(ident)
  if cfg['revision']=='R3':sc.save(ident+'_ADMISSION_CERTIFICATES.json',dict(rows=admission_certificates.ROWS,current_state_checks_unchanged=True))
  if cfg.get('low_overhead_diagnostic'):low_overhead_timing.finish(ident)
  fast_runtime.finish(ident)
  sc.save(ident+'_MULTIRATE.json',multirate.evidence())
  sc.save(ident+'_RESULT.json',result)
  sc.save(ident+'_IMPORTED_SOURCES.json',{str(m.__file__):sc.sha(Path(m.__file__)) for m in list(sys.modules.values()) if getattr(m,'__file__',None) and str(m.__file__).startswith(str(S)) and Path(m.__file__).is_file()})
 print(json.dumps({k:result.get(k) for k in ('id','status','error','wall_seconds')}),flush=True)
if __name__=='__main__':main()
