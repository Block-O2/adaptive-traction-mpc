"""Serial orchestration; no autonomous final campaign or next package."""
from pathlib import Path
import json,subprocess,os,time,signal,traceback,hashlib
R=Path(__file__).resolve().parent;PY=R.parent/'rl_b_cloud_v1/.venv/bin/python'
def put(p,x):p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def lines(p):return [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []
def main():
 cfg=json.loads((R/'PPO_TRAINING_CONFIG.json').read_text());seeds=cfg['seeds'];start=time.time();error=None;proc=None
 put(R/'audit/MANAGER_START.json',{'unix':start,'pid':os.getpid(),'scope':'Stage1 replication only; Stage2 needs a separate frozen gate','command':[str(PY),str(R/'campaign_manager.py')]})
 def run(mode,seed,target=None,kind=None,checkpoint=None):
  nonlocal proc
  if time.time()>=cfg['no_new_physics_after_unix']:raise RuntimeError('NO_NEW_PHYSICS_WINDOW')
  name=f'{seed}_{mode}'+(f'_{target}' if target else '')+(f'_{kind}' if kind else '')
  args=[str(PY),str(R/'replication_run.py'),'--mode',mode,'--seed',str(seed)]
  if target:args+=['--target',str(target)]
  if kind:args+=['--kind',kind]
  if checkpoint:args+=['--checkpoint',checkpoint]
  seconds=min(14400,max(1,cfg['no_new_physics_after_unix']-time.time()))
  command=[str(PY),str(R/'resource_guard.py'),'--out',str(R/'audit/guards'/name),'--seconds',str(seconds),'--',*args]
  print(json.dumps({'event':'PROGRAM_START','name':name,'unix':time.time()}),flush=True)
  proc=subprocess.Popen(command,cwd=R,start_new_session=True)
  try:rc=proc.wait(timeout=seconds+75)
  except subprocess.TimeoutExpired:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=10)
   raise RuntimeError('OUTER_PROCESS_TIMEOUT')
  finally:proc=None
  if rc:raise RuntimeError('GUARDED_PROGRAM_FAILED:'+name)
  print(json.dumps({'event':'PROGRAM_END','name':name,'unix':time.time(),'returncode':rc}),flush=True)
 try:
  for seed in seeds:
   run('initialize',seed)
   run('evaluate',seed,kind='initial_deterministic')
  run('evaluate',seeds[0],kind='fixed_legal_plus_one')
  for seed in seeds:run('train',seed,target=20)
  for seed in seeds:run('evaluate',seed,kind='checkpoint020')
  audit20=[]
  for seed in seeds:
   p=R/'seeds'/str(seed)/'stage1';gate=json.loads((p/'PHASE_GATE_020.json').read_text());rows=lines(p/'TRAINING_LOG.jsonl')
   meaningful=any(x['success'] or x['task_s']>=9. for x in rows)
   audit20.append({'seed':seed,**gate,'meaningful_runtime_progress':meaningful})
  allow=all(x['all_audits_pass'] and x['finite_nonzero_updates'] and x['meaningful_runtime_progress'] for x in audit20) and time.time()<cfg['no_new_physics_after_unix']-3600
  put(R/'A1_RESOURCE_AND_PROGRESS_AUDIT.json',{'unix':time.time(),'seeds':audit20,'allow_A2':allow,'rule':'All three stable audited rollouts with nonzero updates and >=9s task progress, plus >=60min before no-new-physics.'})
  if not allow:raise RuntimeError('A1_NO_FURTHER_TRAINING_RESEARCH_VALUE_OR_TIME')
  for seed in seeds:run('train',seed,target=50)
  for seed in seeds:
   run('evaluate',seed,kind='checkpoint050_first')
   run('evaluate',seed,kind='checkpoint050_repeat')
  train=lines(R/'ALL_TRAINING_LOG.jsonl');ev=lines(R/'ALL_EVALUATION_LOG.jsonl')
  improving=sum(sum(x['success'] for x in train if x['training_seed']==s and x['index']>40)>sum(x['success'] for x in train if x['training_seed']==s and x['index']<=10) for s in seeds)
  allfinal=all(all(x['success'] for x in ev if x['training_seed']==s and x['kind'] in ['checkpoint050_first','checkpoint050_repeat']) for s in seeds)
  ledger=json.loads((R/'LEDGER.json').read_text());extend=improving>=2 and not allfinal and time.time()<cfg['no_new_physics_after_unix']-5400 and cfg['native_steps_hard_cap']-ledger['native_steps']>12000000
  put(R/'EXTENSION_DECISION.json',{'unix':time.time(),'allow':extend,'improving_seed_count':improving,'all_final_repeated_runtime_success':allfinal,'rule':'Frozen protocol; ALL seeds or none. No seed or reward selection.'})
  if extend:
   for seed in seeds:run('train',seed,target=80)
   for seed in seeds:
    run('evaluate',seed,kind='checkpoint080_first')
    run('evaluate',seed,kind='checkpoint080_repeat')
  put(R/'STAGE1_COMPLETE.json',{'unix':time.time(),'target':80 if extend else 50,'seeds':seeds,'status':'COMPLETED','final_campaign_started':False})
 except BaseException as e:
  error={'error':repr(e),'traceback':traceback.format_exc()};put(R/'audit/MANAGER_FAILURE.json',error);raise
 finally:
  if proc is not None and proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=10)
  put(R/'audit/MANAGER_END.json',{'unix':time.time(),'pid':os.getpid(),'error':error,'wall_s':time.time()-start,'owned_child_joined':proc is None or proc.poll() is not None})
if __name__=='__main__':main()
