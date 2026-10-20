from pathlib import Path
import json,sys,time,traceback,resource,os,random,importlib.abc
class NoPerformanceP(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in ('planning','known_model'):
   raise RuntimeError('FORBIDDEN_ADDED_P_IMPORT:'+fullname)
def main():
 request=json.loads(Path(sys.argv[1]).read_text());start=time.time();sys.meta_path.insert(0,NoPerformanceP())
 try:
  from study_common import run,save,sha,STUDY,clean,Interface
  for path,expected in request.get('algorithm_sources',{}).items():assert sha(Path(path))==expected,'FROZEN_MATRIX_ALGORITHM_CHANGED:'+path
  if request.get('weights_sha256'):assert sha(Path(request['weights'])/'weights.npz')==request['weights_sha256'],'FROZEN_WEIGHTS_CHANGED'
  import numpy as np
  random.seed(request.get('seed',2026100610));np.random.seed(request.get('seed',2026100610))
  from interfaces import TableInterface
  import call_audit
  call_audit.install()
  if request.get('mode')=='diagnostic':
   if request.get('replay_rows'):
    from replay_diagnostic import ReplayDiagnosticInterface as DiagnosticInterface
   else:
    from native_diagnostic import DiagnosticInterface
   interface=DiagnosticInterface(request)
  elif request.get('mode')=='branches':
   from native_data import BranchInterface
   interface=BranchInterface(request)
  elif request.get('mode')=='select':
   from native_method import NativeInterface,PrefixBInterface
   interface=PrefixBInterface(request) if request.get('method')=='M0' else NativeInterface(request)
  else:interface=Interface() if request.get('original') else TableInterface(request.get('table'))
  metric=run(request['id'],interface,original=request.get('original',False),execution_mode=request.get('execution_mode','SCIENTIFIC_SIMULATION'))
  if interface.child is not None:os._exit(0)
  sources={name:str(mod.__file__) for name,mod in sys.modules.items() if getattr(mod,'__file__',None) and ('traction_mpc' in name or name in ('sac_env','campaign_r2','coordination_adapter','representation','fork_core'))}
  assert all(str(STUDY) in p for p in sources.values()),'UNFROZEN_IMPORT'
  assert 'planning' not in sys.modules and 'known_model' not in sys.modules
  result=dict(id=request['id'],status='COMPLETE',metric=metric,wall_seconds=time.time()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,inputs=request,import_sources=sources,P_full_performance_calls=0,P_import_blocker=True,call_audit=call_audit.evidence())
 except BaseException as e:
  result=dict(id=request['id'],status='FAILED',error=str(e),traceback=traceback.format_exc(),wall_seconds=time.time()-start,inputs=request)
  if 'interface' in locals() and interface.child is not None:
   name=interface.child['label']+'_'+interface.child['kind'];save(name+'_BRANCH_ERROR.json',result);os._exit(1)
 path=Path(request['result_path']);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(clean(result) if 'clean' in locals() else result,indent=2)+'\n');tmp.replace(path)
 print(json.dumps({k:result.get(k) for k in ('id','status','error','wall_seconds')}),flush=True)
if __name__=='__main__':main()
