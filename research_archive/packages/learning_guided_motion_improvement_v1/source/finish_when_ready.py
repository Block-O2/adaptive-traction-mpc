"""Bounded continuation: wait for frozen queue, validate, audit, analyze. No restart."""
from pathlib import Path
import os,sys,time,json,hashlib,subprocess,datetime,traceback
P=Path(__file__).resolve().parents[1];PY='/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/cpu-env/bin/python';start=json.loads((P/'START.json').read_text());deadline=datetime.datetime.fromisoformat(start['deadline_utc']).timestamp();cutoff=datetime.datetime.fromisoformat(start['no_new_large_physics_after_utc']).timestamp();env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLBACKEND='Agg')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def put(n,x):
 f=P/n;tmp=f.with_suffix(f.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n');tmp.replace(f)
def run(name,script,timeout):
 assert time.time()<deadline,'ORIGINAL_DEADLINE'
 with (P/'logs'/name).open('x') as f:
  proc=subprocess.Popen([PY,'-B',str(P/'source'/script)],stdout=f,stderr=subprocess.STDOUT,env=env,start_new_session=True)
  put('audit/SUPERVISOR_CHILD.json',{'pid':proc.pid,'script':script,'started_unix':time.time(),'deadline_utc':start['deadline_utc']})
  try:code=proc.wait(timeout=min(timeout,max(1,deadline-time.time())))
  except BaseException:
   try:os.killpg(proc.pid,__import__('signal').SIGINT)
   except ProcessLookupError:pass
   try:proc.wait(timeout=30)
   except subprocess.TimeoutExpired:
    os.killpg(proc.pid,__import__('signal').SIGTERM);proc.wait(timeout=15)
   raise
  assert code==0,'POSTRUN_SCRIPT_FAILED:'+script+':'+str(code)
  put('audit/SUPERVISOR_CHILD_END.json',{'pid':proc.pid,'script':script,'returncode':code,'joined':True,'unix':time.time()})
def main():
 assert not (P/'audit/SUPERVISOR_START.json').exists(),'NO_SECOND_SUPERVISOR'
 put('audit/SUPERVISOR_START.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256':sha(Path(__file__)),'only_next_steps':['frozen new prefix','independent raw audit','post-run analysis and plots'],'no_report_seal_before_root_review':True})
 while not (P/'audit/OPTIMIZATION_DONE.json').exists():
  assert time.time()<deadline,'ORIGINAL_DEADLINE'
  assert not (P/'STOP_REQUESTED').exists(),'EXPLICIT_STOP'
  time.sleep(5)
 done=json.loads((P/'audit/OPTIMIZATION_DONE.json').read_text());assert done['status']=='PASS_EXECUTED','OPTIMIZATION_NOT_CLOSED_VALIDLY'
 assert not (P/'STOP_REQUESTED').exists(),'EXPLICIT_STOP'
 if time.time()+900<cutoff:
  lock=json.loads((P/'FINAL_SELECTION_BEFORE_VALIDATION.json').read_text());files={rel:sha(P/rel) for rel in ['FINAL_SELECTION_BEFORE_VALIDATION.json','THREE_ARM_RESULTS.json','models/NOMINAL_PROXY_TABLE.json']}
  for arm,row in lock['locked'].items():
   if row is None:continue
   rel='predictions/'+row['id']+'.json';files[rel]=sha(P/rel)
   model=row['prediction'].get('learned_model_path')
   if model:assert (P/model).resolve().is_relative_to(P);files[model]=sha(P/model)
  put('VALIDATION_INPUT_LOCK.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':files,'all_candidates_and_models_locked_before_new_prefix':True,'no_updates':True})
  run('frozen_new_prefix.log','validation_worker.py',2400)
 else:put('audit/FROZEN_NEW_PREFIX_NOT_RUN.json',{'reason':'original final45min/wall reserve','no_budget_extension':True})
 run('independent_raw_audit.log','independent_audit.py',1200)
 run('analysis.log','analyze_results.py',300)
 run('posthoc_mechanism.log','posthoc_mechanism.py',300)
 put('audit/SUPERVISOR_DONE.json',{'status':'ANALYSIS_COMPLETE_AWAITING_ROOT_FINAL_REVIEW','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_owned_children_joined':True,'pid':os.getpid()})
excepted=False
try:main()
except BaseException as error:
 excepted=True;put('audit/SUPERVISOR_ERROR.json',{'status':'PRESERVED_REQUIRES_ROOT_REVIEW','error':str(error),'traceback':traceback.format_exc(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()});raise
finally:put('audit/SUPERVISOR_EXIT.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'error':excepted})
