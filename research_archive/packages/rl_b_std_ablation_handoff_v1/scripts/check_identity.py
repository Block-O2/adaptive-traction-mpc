from pathlib import Path
import json,sys
from research_common import ROOT,atomic,read,sha,now
sys.path.insert(0,str(ROOT/'runtime'))
import numpy as np
H=ROOT.parent/'rl_b_autonomous_stability_reward_v1';old=[json.loads(s) for s in (H/'ALL_ATTEMPTS.jsonl').read_text().splitlines()];plan=read(ROOT/'configs/STD_PLAN_v3.json');rows=[]
for item in plan['plans']:
 if item['split']!='identity':continue
 cfg=read(item['config']);end=read(ROOT/'jobs'/cfg['job_id']/'END.json');assert end and end['success']
 r=read(ROOT/'runtime/jobs'/cfg['job_id']/'RESULT.json')['rows'][0];h=next(x for x in old if x['seed']==r['seed'] and x['branch']=='RETENTION_R1' and x['index']==61 and x['policy_mode']=='deterministic' and 'final' not in x['job_id'])
 a=read(Path(r['run'])/'RESEARCH_TRANSITIONS.json');b=read(Path(h['run'])/'RESEARCH_TRANSITIONS.json')
 check=dict(policy_identity=r['policy_before']==h['policy_before'],runtime_complete=r['success'] and h['success'],same_duration=abs(r['task_s']-h['task_s'])<1e-10,JF=abs(r['JF']-h['JF'])<1e-8,JM=abs(r['JM']-h['JM'])<1e-8,same_decisions=len(a)==len(b),actor_mean_identical=all(np.array_equal(x['mean'],y['mean']) for x,y in zip(a,b)),actions_identical=all(np.array_equal(x['action'],y['action']) for x,y in zip(a,b)),observations_identical=all(np.array_equal(x['obs'],y['obs']) and np.array_equal(x['next_obs'],y['next_obs']) for x,y in zip(a,b)),zero_gradients=r['gradient_updates']==0)
 rows.append(dict(seed=r['seed'],new_run=r['run'],historical_run=h['run'],source_sha256={str(Path(r['run'])/'RESEARCH_TRANSITIONS.json'):sha(Path(r['run'])/'RESEARCH_TRANSITIONS.json'),str(Path(h['run'])/'RESEARCH_TRANSITIONS.json'):sha(Path(h['run'])/'RESEARCH_TRANSITIONS.json')},checks=check,pass_=all(check.values())))
assert len(rows)==2
result=dict(time_utc=now(),cases=rows,pass_=all(x['pass_'] for x in rows));atomic(ROOT/'audit/IDENTITY_REGRESSION.json',result);print(json.dumps(result));assert result['pass_']
