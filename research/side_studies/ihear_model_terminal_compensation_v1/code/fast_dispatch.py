"""Durable, bounded single-run dispatcher. Never implicitly repeats an attempted ID."""
from pathlib import Path
import os,sys,time,json,hashlib,subprocess,fcntl,signal
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_model_terminal_compensation_v1')
sys.path.insert(0,str(S/'code'))
def save(p,x):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2)+'\n');t.replace(p)
def event(x):
 with (S/'ATTEMPTS.jsonl').open('a') as f:f.write(json.dumps(x)+'\n');f.flush();os.fsync(f.fileno())
def main():
 assert not (S/'PACKAGE_CLOSED.json').exists(),'PACKAGE_CLOSED: read-only recovery; a new physical package needs a new explicit scope'
 lock=(S/'runner.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);lock.write(str(os.getpid()));lock.flush()
 cfg=json.loads(Path(sys.argv[1]).read_text());ident=cfg['id'];plan=json.loads((S/'RUN_PLAN.json').read_text());ledger=json.loads((S/'TASK_LEDGER.json').read_text())
 if ident in ledger:raise RuntimeError('ALREADY_ATTEMPTED_ID: inspect/resume explicit new retry only')
 assert time.time()<plan['dispatch_cutoff_unix'],'DISPATCH_CUTOFF'
 starts=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines() if json.loads(x)['event']=='START']
 assert len(starts)<plan['physics_budget'],'PHYSICS_BUDGET'
 for dep in cfg.get('dependencies',[]):assert ledger[dep]['status']=='COMPLETE',dep
 import runner
 import resource_guard
 resource=resource_guard.before_dispatch(plan,runner.sample)
 row=dict(id=ident,status='RUNNING',version=cfg.get('fast_version','R3_CONTROL'),input_sha256=hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest(),dependencies=cfg.get('dependencies',[]),budget_attempts=1,result_path=str(S/'output'/(ident+'_RESULT.json')),started_unix=time.time(),config=cfg)
 stored=S/'queue'/(ident+'.json')
 if not stored.exists():stored.write_bytes(Path(sys.argv[1]).read_bytes())
 row['durable_input_path']=str(stored)
 row['code_manifest']={str(p.relative_to(S)):hashlib.sha256(p.read_bytes()).hexdigest() for root in ('source','deps','code','native','build') for p in (S/root).rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'results' not in p.relative_to(S).parts}
 for gate in cfg.get('required_gates',[]):assert json.loads((S/gate).read_text())['status']=='PASS',gate
 ledger[ident]=row;save(S/'TASK_LEDGER.json',ledger);event(dict(event='START',id=ident,unix=time.time(),cfg=cfg,input_sha256=row['input_sha256']))
 save(S/'STATE.json',dict(status='ACTIVE',phase='PHYSICS',t0_unix=plan['t0_unix'],updated_unix=time.time(),physics_attempts=len(starts)+1,active=[ident],completed=[k for k,v in ledger.items() if v['status']=='COMPLETE']))
 print('START',ident,flush=True)
 with (S/'logs'/(ident+'.log')).open('w') as log:
  entry=S/'code'/cfg.get('entry','run_one.py');assert entry.resolve().is_relative_to((S/'code').resolve())
  child=subprocess.Popen([sys.executable,'-u',str(entry),str(Path(sys.argv[1]))],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  last=time.time();history=[resource];pause_since=None;signal_sent=False
  while child.poll() is None:
   if time.time()-last>=45:
    resource=runner.sample(owner=child.pid);resource['cpu_load']=os.getloadavg();last=time.time();history.append(resource)
    immediate=resource_guard.critical(resource,history[-2] if len(history)>1 else None)
    pressure=resource_guard.pressure(history)
    if immediate or pressure:
     if pause_since is None:pause_since=time.time()
     save(S/'RESOURCE_STATE.json',dict(status='PAUSE_DISPATCH',since=pause_since,row=resource,level=0,next_check_unix=pause_since+300,healthy_samples=0))
    if immediate and not signal_sent:os.killpg(child.pid,signal.SIGINT);signal_sent=True
   if time.time()>=plan['hard_stop_unix']-180 and not signal_sent:os.killpg(child.pid,signal.SIGINT);signal_sent=True
   time.sleep(.5)
  code=child.wait()
 result=Path(row['result_path']);r=json.loads(result.read_text()) if result.exists() else dict(status='FAILED_NO_RESULT')
 row.update(status='COMPLETE' if result.exists() else 'FAILED_NO_RESULT',worker_status=r['status'],error=r.get('error'),returncode=code,ended_unix=time.time())
 if result.exists():row['result_sha256']=hashlib.sha256(result.read_bytes()).hexdigest()
 metric=r.get('metric',{});partial=S/'output'/(ident+'_PARTIAL_COMPUTE.json')
 if partial.exists():metric=json.loads(partial.read_text())
 row['compute']={k:metric.get(k) for k in ('native_physics_steps','simulation_seconds','main_model_inverse_dynamics_api_calls','native_worker_model_inverse_dynamics_api_calls')};row['wall_seconds']=row['ended_unix']-row['started_unix']
 if isinstance(r.get('main_model_API_delta'),int):row['compute']['main_model_inverse_dynamics_api_calls']=r['main_model_API_delta']
 artifact=S/'source/results'/ident/'runtime_artifacts.json.gz'
 if artifact.exists():
  from stream_runtime_evidence import array_items
  count=sum(record.get('native_steps',0) for record in array_items(artifact,'command_receipts'))
  row['compute']['trace_native_physics_steps']=row['compute']['native_physics_steps'];row['compute']['native_physics_steps']=count;row['compute']['simulation_seconds']=count*plan['physical_dt_s'];row['compute']['native_step_count_authority']='sum of every actual physical receipt, including final catch-up'
 ledger[ident]=row;save(S/'TASK_LEDGER.json',ledger);event(dict(event='END',id=ident,unix=time.time(),status=r['status'],returncode=code,compute=row['compute'],wall_seconds=row['wall_seconds']))
 save(S/'STATE.json',dict(status='ACTIVE',phase='ANALYSIS',t0_unix=plan['t0_unix'],updated_unix=time.time(),physics_attempts=len(starts)+1,active=[],completed=[k for k,v in ledger.items() if v['status']=='COMPLETE'],next_action='Inspect result; dispatch changed evidence-supported branch only.'))
 with (S/'PROGRESS.md').open('a') as f:f.write(f'\n{time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime())} UTC: {ident} {r["status"]}, attempts {len(starts)+1}/{plan["physics_budget"]}; elapsed {(time.time()-plan["t0_unix"])/3600:.3f}h.\n')
 runner.sample(owner='JOINED_FAST_DISPATCH');print('END',ident,r['status'],r.get('error'),flush=True)
if __name__=='__main__':main()
