"""Independent saved rollout and optimizer/RNG comparison; no physics."""
import os,sys,json
from pathlib import Path
from research_common import ROOT,RUNTIME,atomic
import numpy as np
seed=int(sys.argv[1]);job=sys.argv[2]
history=ROOT.parent/'rl_b_autonomous_replication_v1'
historical=[json.loads(s) for s in (history/'ALL_TRAINING_LOG.jsonl').read_text().splitlines()]
out=RUNTIME/'jobs'/job;rows=[]
for i in range(1,6):
    new=json.loads((out/f'episode_{i:03d}/RESULT.json').read_text())
    old=next(x for x in historical if x['training_seed']==seed and x['index']==50+i)
    a=np.load(out/f'episode_{i:03d}/ppo_rollout.npz');b=np.load(history/old['run']/'ppo_rollout.npz')
    checks={k:np.array_equal(a[k],b[k]) for k in b.files}
    checks.update(policy_before=new['policy_before']==old['policy_before'],policy_after=new['policy_after']==old['policy_after'],
                  runtime_status=new['status']==old['status'],duration=abs(new['task_s']-old['task_s'])<1e-10,
                  force=abs(new['JF']-old['JF'])<1e-8,moment=abs(new['JM']-old['JM'])<1e-8)
    rows.append(dict(continuation_episode=i,historical_episode=50+i,checks=checks,pass_=all(checks.values())))
a=json.loads((out/'checkpoints/episode_005.json').read_text())
b=json.loads((history/f'seeds/{seed}/stage1/checkpoints/episode_055.json').read_text())
checks={k:a['state_snapshot'][k]==v for k,v in b['state_snapshot'].items()}
result=dict(seed=seed,job=job,episodes=rows,final_state_checks=checks,
            pass_=all(x['pass_'] for x in rows) and all(checks.values()),
            source='Saved original and new rollouts; exact equality, not outcome-only matching')
atomic(ROOT/'audit'/f'CONTROL_IDENTITY_{seed}.json',result)
print(json.dumps(result));raise SystemExit(0 if result['pass_'] else 1)
