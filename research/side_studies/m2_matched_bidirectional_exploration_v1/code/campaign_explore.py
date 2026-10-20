from explore_common import *
import subprocess,signal,traceback
PY='/home/hank/envs/adaptive-online-rl-v1/bin/python'
def attempts():return [json.loads(l) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines()] if (S/'ATTEMPTS.jsonl').exists() else []
def event(row):
 with (S/'ATTEMPTS.jsonl').open('a') as f:f.write(json.dumps(dict(unix=time.time(),**row))+'\n')
def run(cfg):
 p=load(S/'EXPERIMENT_PROTOCOL.json');assert time.time()<p['dispatch_cutoff_unix'],'DISPATCH_CUTOFF';assert sum(r['event']=='START' for r in attempts())<24,'ATTEMPT_CAP'
 ident=cfg['id'];assert not any(r.get('id')==ident for r in attempts()),'NO_REPLAY';save(S/'queue'/(ident+'.json'),cfg)
 event(dict(event='START',id=ident,config=cfg,code_manifest_sha256=sha(S/'CODE_MANIFEST.json')))
 child=None;rc=None
 try:
  with (S/'logs'/(ident+'.log')).open('w') as log:
   child=subprocess.Popen([PY,'-B','-u',str(S/'code/run_one.py'),str(S/'queue'/(ident+'.json'))],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,cwd=S)
   save(S/'CURRENT_WORKER.json',dict(id=ident,pid=child.pid,runner_pid=os.getpid()))
   remaining=max(1,min(1200,p['deadline_unix']-time.time()-600))
   try:rc=child.wait(timeout=remaining)
   except subprocess.TimeoutExpired:
    os.killpg(child.pid,signal.SIGINT)
    try:rc=child.wait(timeout=30)
    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGTERM);rc=child.wait(timeout=20)
  event(dict(event='END',id=ident,returncode=rc,joined=True))
  result=load(S/'output'/(ident+'_RESULT.json'));assert result['status']=='COMPLETE','WORKER_FAILED:'+str(result.get('error'))
  with (S/'logs'/(ident+'_review.log')).open('w') as log:
   subprocess.run([PY,'-B',str(S/'code/review_attempt.py'),ident],stdout=log,stderr=subprocess.STDOUT,check=True,cwd=S,timeout=180)
  axis=load(S/'reports'/(ident+'_AXES.json'));assert axis['PHYSICAL_TASK_VALID']=='PASS','NATIVE_PHYSICAL_FAILURE';assert axis['HOST_EXECUTION_CAUSAL_VALID']=='PASS','CAUSAL_OWNERSHIP_FAILURE'
  a=analyze(ident);print(json.dumps(dict(completed=ident,J_F=a['J_F_N_s'],nonzero=a['axes']['nonzero_execution_count'],elapsed_s=time.time()-p['start_unix'])),flush=True);return a
 except BaseException as e:
  if child and child.poll() is None:
   os.killpg(child.pid,signal.SIGINT);child.wait(timeout=30)
  if not any(r['event']=='END' and r.get('id')==ident for r in attempts()):event(dict(event='END',id=ident,returncode=rc,joined=True,error=str(e)))
  save(S/'BLOCKER.json',dict(id=ident,error=str(e),traceback=traceback.format_exc(),unix=time.time(),stop='related experiments stopped; no threshold or native contract repair'))
  raise
def main():
 save(S/'RUNNER_PID.json',dict(pid=os.getpid(),unix=time.time()));measurements=[];comparisons=[]
 try:
  configs=[load(p) for p in sorted((S/'queue').glob('*.json'))];assert len(configs)==14
  b=run(configs[0]);measurements.append(b);m2=run(configs[1]);measurements.append(m2);comparisons.append(compare(m2,b))
  for cfg in configs[2:]:
   a=run(cfg);measurements.append(a);c=compare(a,b);comparisons.append(c)
   save(S/'SEARCH_RESULTS.json',dict(status='DISCOVERY_IN_PROGRESS',attempts=attempts(),comparisons=comparisons,measured_ids=[r['id'] for r in measurements],not_run=[r['id'] for r in configs if r['id'] not in [a['id'] for a in measurements]]))
  eligible=[c for c in comparisons[1:] if c['acceptance_pass'] and c['gain_percent']>=.5 and next(r for r in measurements if r['id']==c['candidate'])['axes']['nonzero_execution_count']>0]
  valuable=[]
  for c in eligible:
   a=next(r for r in measurements if r['id']==c['candidate']);metrics=[('velocity_deg_s','p95_abs'),('acceleration_deg_s2','p95_abs'),('acceleration_deg_s2','rms')]
   smoother=all(a['motion']['raw']['full'][sig][met][1]<=.95*m2['motion']['raw']['full'][sig][met][1] for sig,met in metrics)
   if a['J_F_N_s']<m2['J_F_N_s'] or smoother:valuable.append(c)
  chosen=min(valuable,key=lambda c:(-c['gain_N_s'],c['candidate'])) if valuable else None
  save(S/'CANDIDATE_SELECTION.json',dict(registered_rule='lowest J_F among prospective eligible discovery tables, ID tie; no final-test selection',selected=chosen,eligible_ids=[c['candidate'] for c in eligible],unix=time.time(),discovery_only=True))
  save(S/'SEARCH_RESULTS.json',dict(status='DISCOVERY_COMPLETE',attempts=attempts(),comparisons=comparisons,measured_ids=[r['id'] for r in measurements],not_run=[],candidate_count=12,baseline_count=2))
  validation=[]
  if chosen:
   template=load(S/'queue'/(chosen['candidate']+'.json'));counter=15
   for seed,order in [(2026100902,['B','candidate','M2']),(2026100903,['M2','candidate','B'])]:
    rr={}
    for arm in order:
     cfg=dict(configs[1] if arm=='M2' else configs[0] if arm=='B' else template);cfg.update(id=f'{counter:03d}_validation_{seed}_{arm}',seed=seed,split='validation',pair_id='nominal_'+str(seed));counter+=1
     rr[arm]=run(cfg);measurements.append(rr[arm])
    c=compare(rr['candidate'],rr['B']);cm=compare(rr['M2'],rr['B']);validation.append(dict(seed=seed,candidate=c,M2=cm,candidate_minus_M2_J_F_N_s=rr['candidate']['J_F_N_s']-rr['M2']['J_F_N_s'],commissioning={k:v['commissioning'] for k,v in rr.items()}))
    save(S/'VALIDATION_RESULTS.json',dict(status='VALIDATION_IN_PROGRESS',selection=chosen,pairs=validation))
   status='VALIDATED_B_RELATIVE_RESEARCH' if all(r['candidate']['acceptance_pass'] and r['candidate']['gain_percent']>=.5 for r in validation) else 'DISCOVERY_NOT_VALIDATED'
   save(S/'VALIDATION_RESULTS.json',dict(status=status,selection=chosen,pairs=validation,independent_seeds=True,same_Human=True,unseen_Human=False,no_reselection=True))
  else:save(S/'VALIDATION_RESULTS.json',dict(status='NOT_RUN_NO_ELIGIBLE_DISCOVERY',selection=None,pairs=[],independent_validation=False))
 except BaseException:
  if not (S/'VALIDATION_RESULTS.json').exists():save(S/'VALIDATION_RESULTS.json',dict(status='NOT_RUN_BLOCKED',pairs=[]))
 finally:
  save(S/'CAMPAIGN_STOP.json',dict(unix=time.time(),attempts=attempts(),elapsed_s=time.time()-load(S/'EXPERIMENT_PROTOCOL.json')['start_unix'],runner_pid=os.getpid(),status='BLOCKED' if (S/'BLOCKER.json').exists() else 'FINISHED',no_auto_resume=True))
if __name__=='__main__':main()
