"""One bounded diagnostic identity replay; zero physics and no fitting."""
from pathlib import Path
import os,sys,json,time,datetime,hashlib,subprocess,resource
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');ID='CRITIC_SENSITIVITY_REPLAY01';start=time.time();hard=json.loads((P/'ACTIVATION.json').read_text())['hard_stop_unix'];assert start+60<hard
def put(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def tick(pid):return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
before=json.loads((P/'analysis/CRITIC_FEATURE_SENSITIVITY.json').read_text());(P/'audit/CRITIC_FEATURE_SENSITIVITY_INITIAL.json').write_text(json.dumps(before,ensure_ascii=False,indent=2)+'\n');usage=resource.getrusage(resource.RUSAGE_CHILDREN);code=None;reason='BOUNDED_DIAGNOSTIC_REPLAY_COMPLETED';child=None
put('owned/'+ID+'_START.json',dict(pid=os.getpid(),start_ticks=tick(os.getpid()),started_unix=start,maximum_wall_s=45,deadline_unix=min(start+45,hard),source_sha256=sha(Path(__file__)),diagnostic_source_sha256=sha(P/'source/v5_critic_feature_sensitivity.py'),protocol_sha256=sha(P/'experiments/CRITIC_FEATURE_SENSITIVITY_PROTOCOL.json'),maximum_new_physical_START=0))
try:
 env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
 with (P/'logs'/(ID+'.log')).open('w') as log:
  child=subprocess.Popen([sys.executable,'-B',str(P/'source/v5_critic_feature_sensitivity.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
  put('owned/'+ID+'_CHILD.json',dict(pid=child.pid,start_ticks=tick(child.pid)))
  try:code=child.wait(timeout=40)
  except subprocess.TimeoutExpired:
   os.killpg(child.pid,15)
   try:child.wait(timeout=3)
   except subprocess.TimeoutExpired:os.killpg(child.pid,9);child.wait(timeout=2)
   raise TimeoutError('DIAGNOSTIC_REPLAY_LOCAL_STOP')
 assert code==0,'DIAGNOSTIC_REPLAY_FAILED'
 after=json.loads((P/'analysis/CRITIC_FEATURE_SENSITIVITY.json').read_text());assert before['rows']==after['rows'],'DIAGNOSTIC_REPLAY_CHANGED_VALUES';assert before['protected_artifact_sha256']==after['protected_artifact_sha256'],'ORIGINAL_MODEL_CHANGED'
 use=resource.getrusage(resource.RUSAGE_CHILDREN)
 put('audit/CRITIC_FEATURE_SENSITIVITY_RUN_IDENTITY.json',dict(status='PASS',job_id=ID,source_sha256=sha(P/'source/v5_critic_feature_sensitivity.py'),protocol_sha256=sha(P/'experiments/CRITIC_FEATURE_SENSITIVITY_PROTOCOL.json'),replayed_result_rows=len(after['rows']),all_diagnostic_values_exactly_replayed=True,original_frozen_artifacts_unchanged=True,wall_s=time.time()-start,child_cpu_user_s=use.ru_utime-usage.ru_utime,child_cpu_system_s=use.ru_stime-usage.ru_stime,child_peak_rss_kib=use.ru_maxrss,new_physical_START=0,new_native_steps=0,first_direct_execution_PID='NOT_RECORDED; initial derived result preserved and this finite identity replay reproduced it exactly'))
except BaseException as error:reason=type(error).__name__+':'+str(error);raise
finally:put('owned/'+ID+'_END.json',dict(pid=os.getpid(),start_ticks=tick(os.getpid()),ended_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),reason=reason,child_returncode=code,wall_s=time.time()-start,all_children_joined=bool(child is not None and child.poll() is not None),new_physical_START=0))
print('DIAGNOSTIC_IDENTITY_REPLAY_PASS')
