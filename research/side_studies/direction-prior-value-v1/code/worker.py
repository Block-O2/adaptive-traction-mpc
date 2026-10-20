from pathlib import Path
import json,sys,time,traceback,resource,os,random
def main():
 request=json.loads(Path(sys.argv[1]).read_text());start=time.time()
 try:
  from study_common import run,save,sha,STUDY,clean,R
  loaded_code_manifest_sha256=sha(STUDY/'CODE_MANIFEST.json')
  for path,expected in request.get('algorithm_sources',{}).items():assert sha(Path(path))==expected,'FROZEN_TEST_ALGORITHM_SOURCE_CHANGED:'+path
  import numpy as np
  global_seed=request.get('seed',2026100600);random.seed(global_seed);np.random.seed(global_seed)
  from interfaces import TableInterface,ProbeInterface
  if request.get('mode')=='synergy':
   from known_synergy import SynergyInterface
   interface=SynergyInterface(request['table'],request['weights'])
  elif request.get('mode')=='audit':
   from snapshot_audit import AuditInterface
   interface=AuditInterface(request['group'],request['weights'],request['seed'],request.get('table'),request['targets'])
  elif request.get('mode')=='branches':
   from data_collection import BranchInterface
   interface=BranchInterface(request['group'],request['split'],request.get('table'),request.get('candidates',8),request.get('targets'))
  elif request.get('mode')=='search':
   from planning import SearchInterface
   interface=SearchInterface(request.get('method','P'),request.get('seed',202610060),request.get('weights'),request.get('prefix'),request.get('value_scale',1.))
  else:interface=(ProbeInterface if request.get('mode')=='probe' else TableInterface)(request.get('table'))
  interface.loaded_code_manifest_sha256=loaded_code_manifest_sha256
  loaded_import_hashes={str(mod.__file__):sha(Path(mod.__file__)) for name,mod in sys.modules.items() if hasattr(mod,'__file__') and mod.__file__ and str(STUDY) in str(mod.__file__) and Path(mod.__file__).is_file()}
  interface.loaded_import_hashes=loaded_import_hashes
  metric=run(request['id'],interface)
  if interface.child is not None:os._exit(0)
  result=dict(id=request['id'],status='COMPLETE',metric=metric,wall_seconds=time.time()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,inputs=request,loaded_code_manifest_sha256=loaded_code_manifest_sha256,loaded_import_hashes=loaded_import_hashes,import_sources={name:str(mod.__file__) for name,mod in sys.modules.items() if hasattr(mod,'__file__') and mod.__file__ and ('traction_mpc' in name or name in ('sac_env','campaign_r2','coordination_adapter','representation'))})
  assert all(str(STUDY) in p for p in result['import_sources'].values()),'UNFROZEN_IMPORT'
 except BaseException as e:
  result=dict(id=request['id'],status='FAILED',error=str(e),traceback=traceback.format_exc(),wall_seconds=time.time()-start,inputs=request)
  result['partial_physical_time_s']=getattr(interface,'last_physical_time_s',None) if 'interface' in locals() else None
  if 'interface' in locals() and interface.child is not None:
   branch_name=interface.child['label']+'_'+interface.child['kind'];result['id']=branch_name;save(branch_name+'_BRANCH_ERROR.json',result);os._exit(1)
 path=Path(request['result_path']);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(clean(result) if 'clean' in locals() else result,indent=2)+'\n');tmp.replace(path)
 print(json.dumps({k:result.get(k) for k in ('id','status','error','wall_seconds')}),flush=True)
if __name__=='__main__':main()
