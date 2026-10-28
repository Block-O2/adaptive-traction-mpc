"""Root已明确批准V6的一次真实offline fit外部资源wrapper，无物理。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import resource
import signal
import sys
import time
import traceback
sys.dont_write_bytecode=True
P=Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8');R=P/'families/il_dagger_sac/discrete_sac_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def put(p,d):
 with Path(p).open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def timeout_handler(signum,frame):raise TimeoutError('EXTERNAL_FINITE_RESOURCE_SIGNAL:'+str(signum))
def main():
 approval_path=R/'MAIN_APPROVAL_REAL_FIT_V6.json';a=load(approval_path)
 assert a['status']=='APPROVED_BY_MAIN_AGENT_FOR_REAL_OFFLINE_SAC_FIT'
 assert sha(__file__)==a['execution_wrapper_sha256']
 assert a['contract_sha256']=='4533aacbb2c3be9e248918341f9cedcc72e16228ea5aec65e4855c7abd7d71e6' and sha(P/a['contract_path'])==a['contract_sha256']
 contract=load(P/a['contract_path']);assert sha(P/contract['source_manifest_path'])=='7058c52b991776fac9561cc326ba887baca63f95db05d8b4099dc4894c9496e2'
 assert sha(P/contract['fit_runner_path'])=='a67c6904db066083968d9ebf9ce4065a515cff2851bb06cad9e71c4cf5d258ca'
 assert sha(Path(sys.executable).resolve())==a['actual_interpreter']['binary_sha256'] and sys.version==a['actual_interpreter']['sys_version']
 assert time.time()<1793114740.0 and not (P/contract['output_directory']).exists()
 os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_CPU,(180,180))
 signal.signal(signal.SIGTERM,timeout_handler);signal.signal(signal.SIGXCPU,timeout_handler)
 initial=resource.getrusage(resource.RUSAGE_SELF);started=time.time();status='FAILED';error=None
 put(R/'analysis/REAL_FIT_INITIAL_RESOURCE_V6.json',{'started_unix':started,'CPU_user_s':initial.ru_utime,'CPU_system_s':initial.ru_stime,'RSS_KiB':initial.ru_maxrss,'PID':os.getpid(),'affinity':sorted(os.sched_getaffinity(0)),'approval_sha256':sha(approval_path),'actual_interpreter':a['actual_interpreter'],'NumPy_SciPy':'NOT_IMPORTED_OR_USED_BY_LEARNER','external_timeout_s':180,'new_physics':0})
 print('REAL_OFFLINE_SAC_FIT_V6_STARTED',started,flush=True)
 try:
  path=P/contract['fit_runner_path'];spec=importlib.util.spec_from_file_location('_root_approved_sac_fit_v6',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  m.run(P,str(approval_path.relative_to(P)));status='COMPLETED';print('REAL_OFFLINE_SAC_FIT_V6_COMPLETED',flush=True)
 except BaseException as e:error={'error':str(e),'traceback':traceback.format_exc()};print('REAL_OFFLINE_SAC_FIT_V6_FAILED',str(e),flush=True);raise
 finally:
  final=resource.getrusage(resource.RUSAGE_SELF)
  put(R/'analysis/REAL_FIT_INITIAL_FINAL_RESOURCE_V6.json',{'status':status,'error':error,'initial':{'wall_unix':started,'CPU_user_s':initial.ru_utime,'CPU_system_s':initial.ru_stime,'RSS_KiB':initial.ru_maxrss},'final':{'wall_unix':time.time(),'CPU_user_s':final.ru_utime,'CPU_system_s':final.ru_stime,'RSS_peak_KiB':final.ru_maxrss},'wall_s':time.time()-started,'CPU_user_s':final.ru_utime-initial.ru_utime,'CPU_system_s':final.ru_stime-initial.ru_stime,'automatic_retry':False,'source_model_files_unmodified':True,'new_physics':0,'sealed_or_active_H2_reads':0})
if __name__=='__main__':main()
