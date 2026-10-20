from pathlib import Path
import json,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_autonomous_multitrack_v1')
ledger=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()]
rows=[json.loads(x) for x in (S/'RESULTS.jsonl').read_text().splitlines()] if (S/'RESULTS.jsonl').exists() else []
dis=[r for r in rows if r['id'].startswith('discovery_') and r['candidate_id']!='Frozen_M2' and r['stage']!='RETURN_DIAGNOSTIC']
eligible=[r for r in dis if r['comparison']['eligible']]
motion=[r for r in dis if r['comparison']['acceptance_pass'] and r['comparison']['actual_nonzero_count']>0]
mode='H2' if any(r['event']=='START' and r['id'].startswith('H2_') for r in ledger) else 'H1' if any(r['event']=='START' and r['id'].startswith('H1_') for r in ledger) else 'resume'
log=S/'logs'/(mode+'.log');progress=[]
for x in log.read_text().splitlines():
 if x.startswith('{'):
  try:progress.append(json.loads(x))
  except json.JSONDecodeError:pass
def brief(r):return None if r is None else dict(id=r['candidate_id'],gain_percent=r['comparison']['gain_percent'],motion=r['comparison']['acceptance_pass'])
start=[r for r in ledger if r['event']=='START'];ended={r['id'] for r in ledger if r['event']=='END'}
validation=[dict(id=r['id'],gain_percent=r['comparison']['gain_percent'],motion=r['comparison']['acceptance_pass'],eligible=r['comparison']['eligible']) for r in rows if r['id'].startswith(('H1_','H2_'))]
completed_validation=[dict(id=r['id'],task_valid=json.loads((S/'output'/(r['id']+'_DATA.json')).read_text())['metric']['task_valid']) for r in start if r['id'].startswith(('H1_','H2_')) and (S/'output'/(r['id']+'_DATA.json')).exists()]
print(json.dumps(dict(mode=mode,last_progress=progress[-2:],attempts=len(start),active=[r['id'] for r in start if r['id'] not in ended],task_failure_count=len(list((S/'reports').glob('*_TASK_FAILURE.json'))),eligible_count=len(eligible),best_eligible=brief(max(eligible,key=lambda r:r['comparison']['gain_percent'])) if eligible else None,best_motion=brief(max(motion,key=lambda r:r['comparison']['gain_percent'])) if motion else None,validation_results=validation,completed_validation=completed_validation,elapsed_h=(time.time()-json.loads((S/'RUN_PLAN.json').read_text())['t0_unix'])/3600)),flush=True)
