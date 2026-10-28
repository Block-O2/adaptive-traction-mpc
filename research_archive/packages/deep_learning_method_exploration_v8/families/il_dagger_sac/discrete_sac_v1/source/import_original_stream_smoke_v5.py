"""主审批准IMPORT_ONLY：原helper完整import，绝不读raw或调用array_items。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import resource
import sys
import time
import traceback
sys.dont_write_bytecode=True
P=Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8');R=P/'families/il_dagger_sac/discrete_sac_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 approval=json.loads((R/'MAIN_APPROVAL_IMPORT_ONLY_V5.json').read_text());assert approval['status']=='APPROVED_BY_MAIN_AGENT_IMPORT_ONLY'
 assert sha(__file__)==approval['source_sha256']
 out=R/'analysis/IMPORT_ONLY_V5.json';assert not out.exists(),'NO_AUTO_REPEAT'
 os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_CPU,(30,30))
 initial=resource.getrusage(resource.RUSAGE_SELF);start=time.time();result={'status':'FAILED_IMPORT_ONLY','error':None}
 try:
  for rel,h in approval['required_source_sha256'].items():assert sha(P/rel)==h
  directory=P/'runtime/code';sys.path.insert(0,str(directory))
  spec=importlib.util.spec_from_file_location('_sac_original_stream_import_only',directory/'stream_runtime_evidence.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
  bootstrap=sys.modules['task_bootstrap'];assert Path(bootstrap.__file__).resolve()==(directory/'task_bootstrap.py').resolve()
  assert sha(bootstrap.__file__)==approval['required_source_sha256']['runtime/code/task_bootstrap.py']
  assert Path(helper.__file__).resolve()==(directory/'stream_runtime_evidence.py').resolve()
  result.update(status='PASS_IMPORT_ONLY_NO_FUNCTION_CALL',actual_python={'version':sys.version,'sys_executable':sys.executable,'resolved_binary':str(Path(sys.executable).resolve()),'binary_sha256':sha(Path(sys.executable).resolve())},actual_numpy={'version':helper.np.__version__,'module_file':str(Path(helper.np.__file__).resolve()),'module_file_sha256':sha(Path(helper.np.__file__).resolve())},actual_task_bootstrap={'module_file':str(Path(bootstrap.__file__).resolve()),'sha256':sha(bootstrap.__file__)},actual_stream_helper={'module_file':str(Path(helper.__file__).resolve()),'sha256':sha(helper.__file__)})
 except BaseException as e:result['error']={'text':str(e),'traceback':traceback.format_exc()};raise
 finally:
  final=resource.getrusage(resource.RUSAGE_SELF);result.update(initial={'wall_unix':start,'CPU_user_s':initial.ru_utime,'CPU_system_s':initial.ru_stime,'RSS_KiB':initial.ru_maxrss},final={'wall_unix':time.time(),'CPU_user_s':final.ru_utime,'CPU_system_s':final.ru_stime,'RSS_peak_KiB':final.ru_maxrss},wall_s=time.time()-start,raw_reads=0,array_items_calls=0,learner_init=0,model_forward=0,fit=0,physics=0,sealed_reads=0,automatic_retry=False)
  with out.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2,sort_keys=True);f.write('\n')
  print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
