"""A4只定义未来一次批准执行的资源wrapper；当前不运行。"""
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
ROOT=Path(__file__).resolve().parents[1];P=ROOT.parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def put(p,d):
 with Path(p).open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
def main():
 approval_path=ROOT/'MAIN_APPROVAL_V1.json';approval=load(approval_path);contract_path=ROOT/'contracts/FIT_CONTRACT_FINAL_V1.json';contract=load(contract_path)
 assert approval['status']=='APPROVED_BY_MAIN_AGENT' and approval['contract_sha256']==sha(contract_path)
 assert approval['source_manifest_sha256']==sha(ROOT/'SOURCE_CANDIDATE_MANIFEST_V1.json')
 assert sha(Path(sys.executable).resolve())==approval['actual_interpreter']['binary_sha256'] and sys.version==approval['actual_interpreter']['sys_version']
 assert time.time()<1793114740. and not (ROOT/contract['output_directory']).exists()
 os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_CPU,(180,180))
 before=resource.getrusage(resource.RUSAGE_SELF);start=time.time();error=None;status='FAILED'
 put(ROOT/'analysis/EXECUTION_INITIAL_RESOURCE_V1.json',{'PID':os.getpid(),'start_unix':start,'CPU_user_s':before.ru_utime,'CPU_system_s':before.ru_stime,'RSS_KiB':before.ru_maxrss,'actual_interpreter':approval['actual_interpreter'],'affinity':sorted(os.sched_getaffinity(0)),'approval_sha256':sha(approval_path),'external_timeout_s':180,'new_physics':0})
 try:
  sys.path.insert(0,str(ROOT/'source'));path=ROOT/'source/run_training_candidate.py';spec=importlib.util.spec_from_file_location('_a4_approved_single_fit',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.run(approval_path);status='COMPLETED'
 except BaseException as failure:error={'error':str(failure),'traceback':traceback.format_exc()};raise
 finally:
  final=resource.getrusage(resource.RUSAGE_SELF);put(ROOT/'analysis/EXECUTION_INITIAL_FINAL_RESOURCE_V1.json',{'status':status,'error':error,'initial':{'wall_unix':start,'CPU_user_s':before.ru_utime,'CPU_system_s':before.ru_stime,'RSS_KiB':before.ru_maxrss},'final':{'wall_unix':time.time(),'CPU_user_s':final.ru_utime,'CPU_system_s':final.ru_stime,'RSS_peak_KiB':final.ru_maxrss},'wall_s':time.time()-start,'new_physics':0,'auto_retry':False,'sealed_or_active_H2_read':False})
if __name__=='__main__':main()
