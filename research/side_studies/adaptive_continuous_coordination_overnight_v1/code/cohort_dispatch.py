"""Serial cold/reused-interpreter runs, each with its own durable attempt.

Each run creates a new physical plant. Reused interpreter is explicitly NOT a
persistent physical/adaptive session. One run/one plant owner is active at once.
"""
from pathlib import Path
import os,sys,json,time,multiprocessing,fcntl,signal,hashlib,contextlib,traceback
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_overnight_v1');sys.path.insert(0,str(S/'code'))
def worker(conn):
 os.setsid()
 import run_one
 ordinal=0
 while True:
  cfg=conn.recv()
  if cfg is None:break
  ident=cfg['id'];error=None
  with (S/'logs'/(ident+'.log')).open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
   try:run_one.main(cfg_override=cfg,reuse=ordinal>0)
   except BaseException as e:error=f'{type(e).__name__}:{e}';traceback.print_exc()
  conn.send(dict(id=ident,pid=os.getpid(),ordinal=ordinal,error=error));ordinal+=1
 conn.close()
def main():
 assert not (S/'PACKAGE_CLOSED.json').exists(),'PACKAGE_CLOSED: no additional physical cohort'
 import fast_dispatch as d,runner,resource_guard
 lock=(S/'runner.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 group=json.loads(Path(sys.argv[1]).read_text());plan=json.loads((S/'RUN_PLAN.json').read_text());ledger=json.loads((S/'TASK_LEDGER.json').read_text())
 configs=group['configs'];reuse=bool(group['same_interpreter']);proc=None;conn=None;group_rows=[]
 assert len({c['id'] for c in configs})==len(configs)
 assert not any(c['id'] in ledger for c in configs),'NO_REPLAY_ATTEMPTED_IDS'
 group_started=time.time()
 try:
  for ordinal,cfg in enumerate(configs):
   ident=cfg['id'];assert time.time()<plan['dispatch_cutoff_unix'],'DISPATCH_CUTOFF'
   starts=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines() if json.loads(x)['event']=='START']
   assert len(starts)<plan['physics_budget'],'PHYSICS_BUDGET'
   for dep in cfg.get('dependencies',[]):assert ledger[dep]['status']=='COMPLETE',dep
   for gate in cfg.get('required_gates',[]):assert json.loads((S/gate).read_text())['status']=='PASS',gate
   resource=resource_guard.before_dispatch(plan,runner.sample)
   stored=S/'queue'/(ident+'.json');assert not stored.exists();stored.write_text(json.dumps(cfg,indent=2)+'\n')
   row=dict(id=ident,status='RUNNING',version=cfg['fast_version'],config=cfg,input_sha256=hashlib.sha256(stored.read_bytes()).hexdigest(),durable_input_path=str(stored),dependencies=cfg.get('dependencies',[]),budget_attempts=1,result_path=str(S/'output'/(ident+'_RESULT.json')),started_unix=time.time(),cohort_id=group['id'],same_interpreter=reuse,plant_reset_between_runs=True)
   row['dispatcher_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
   row['cohort_registration_sha256']=hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()
   row['code_manifest']={str(p.relative_to(S)):hashlib.sha256(p.read_bytes()).hexdigest() for root in ('source','deps','code','native','build') for p in (S/root).rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'results' not in p.relative_to(S).parts}
   ledger[ident]=row;d.save(S/'TASK_LEDGER.json',ledger);d.event(dict(event='START',id=ident,unix=time.time(),cfg=cfg,input_sha256=row['input_sha256'],cohort_id=group['id']))
   d.save(S/'STATE.json',dict(status='ACTIVE',phase='COHORT_PHYSICS',t0_unix=plan['t0_unix'],physics_attempts=len(starts)+1,active=[ident],cohort=group['id'],updated_unix=time.time()))
   if proc is None:
    conn,childconn=multiprocessing.get_context('spawn').Pipe();proc=multiprocessing.get_context('spawn').Process(target=worker,args=(childconn,),name='bounded-fast-reuse-owner');proc.start();childconn.close()
   row['interpreter_pid']=proc.pid;conn.send(cfg);last=time.time();history=[resource];signaled=False;reply=None
   print('START',ident,'owner',proc.pid,'reused',reuse and ordinal>0,flush=True)
   while proc.is_alive():
    if conn.poll(.5):reply=conn.recv();assert reply['id']==ident;break
    if time.time()-last>=45:
     resource=runner.sample(owner=proc.pid);last=time.time();history.append(resource)
     critical=resource_guard.critical(resource,history[-2] if len(history)>1 else None)
     if critical or resource_guard.pressure(history):
      d.save(S/'RESOURCE_STATE.json',dict(status='PAUSE_DISPATCH',since=time.time(),row=resource,level=0,next_check_unix=time.time()+300,healthy_samples=0))
     if critical and not signaled:os.killpg(proc.pid,signal.SIGINT);signaled=True
    if time.time()>=plan['hard_stop_unix']-180 and not signaled:os.killpg(proc.pid,signal.SIGINT);signaled=True
   result=Path(row['result_path']);r=json.loads(result.read_text()) if result.exists() else dict(status='FAILED_NO_RESULT',error=None if reply is None else reply['error'])
   row.update(status='COMPLETE' if result.exists() else 'FAILED_NO_RESULT',worker_status=r['status'],error=r.get('error'),ended_unix=time.time(),interpreter_ordinal=None if reply is None else reply['ordinal'],worker_reply=reply)
   metric=r.get('metric',{});partial=S/'output'/(ident+'_PARTIAL_COMPUTE.json')
   if partial.exists():metric=json.loads(partial.read_text())
   row['compute']={k:metric.get(k) for k in ('native_physics_steps','simulation_seconds','main_model_inverse_dynamics_api_calls','native_worker_model_inverse_dynamics_api_calls')}
   if isinstance(r.get('main_model_API_delta'),int):row['compute']['main_model_inverse_dynamics_api_calls']=r['main_model_API_delta']
   artifact=S/'source/results'/ident/'runtime_artifacts.json.gz'
   if artifact.exists():
    from stream_runtime_evidence import array_items
    count=sum(x.get('native_steps',0) for x in array_items(artifact,'command_receipts'));row['compute'].update(trace_native_physics_steps=row['compute']['native_physics_steps'],native_physics_steps=count,simulation_seconds=count*plan['physical_dt_s'],native_step_count_authority='all actual receipts including final catch-up')
   if result.exists():row['result_sha256']=hashlib.sha256(result.read_bytes()).hexdigest()
   row['wall_seconds']=row['ended_unix']-row['started_unix'];ledger[ident]=row;d.save(S/'TASK_LEDGER.json',ledger);d.event(dict(event='END',id=ident,unix=time.time(),status=r['status'],compute=row['compute'],wall_seconds=row['wall_seconds'],cohort_id=group['id']));group_rows.append(row)
   d.save(S/'reports'/(group['id']+'_PROGRESS.json'),dict(id=group['id'],rows=group_rows,same_interpreter=reuse,physical_session_continuous=False))
   with (S/'PROGRESS.md').open('a') as f:f.write(f'\n{time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime())} UTC: {ident} {r["status"]}; cohort {group["id"]}; attempts {len(starts)+1}/{plan["physics_budget"]}; interpreter {proc.pid}, ordinal {row["interpreter_ordinal"]}.\n')
   print('END',ident,r['status'],r.get('error'),flush=True);runner.sample(owner='COHORT_RUN_COMPLETE')
   if not reuse or r['status']!='COMPLETE' or signaled:
    if proc.is_alive():conn.send(None)
    proc.join(timeout=30);assert not proc.is_alive(),'OWNED_COHORT_JOIN_TIMEOUT';conn.close();proc=None;conn=None
   if r['status']!='COMPLETE' or signaled:break
 finally:
  if proc is not None:
   if proc.is_alive():conn.send(None)
   proc.join(timeout=30)
   if proc.is_alive():proc.terminate();proc.join(timeout=10)
   assert not proc.is_alive(),'OWNED_COHORT_JOIN_TIMEOUT'
   conn.close()
 d.save(S/'reports'/(group['id']+'_DISPATCH.json'),dict(status='COMPLETE' if len(group_rows)==len(configs) else 'STOPPED',id=group['id'],rows=group_rows,wall_seconds=time.time()-group_started,same_interpreter=reuse,physical_session_continuous=False,owned_worker_joined=True))
 d.save(S/'STATE.json',dict(status='ACTIVE',phase='ANALYSIS',t0_unix=plan['t0_unix'],physics_attempts=len(ledger),active=[],updated_unix=time.time(),next_action='Review frozen cohort; no automatic M2 promotion.'))
if __name__=='__main__':main()
