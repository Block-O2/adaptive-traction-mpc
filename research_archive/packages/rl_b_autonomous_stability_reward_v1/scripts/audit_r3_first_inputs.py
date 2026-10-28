"""Exact saved first-rollout control across R0/H2, R1, R2 and the optional R3."""
from pathlib import Path
import json
import numpy as np
from research_common import ROOT,read,atomic,sha,now


def main():
    rows=[json.loads(s) for s in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    cases=[]
    for seed in [1495656323,1630784693]:
        found={b:next((x for x in rows if x['seed']==seed and x['branch']==b and x['update']),None)
               for b in ['H2_AGG64','REWARD_R1','REWARD_R2','REWARD_R3']}
        if any(x is None for x in found.values()):
            cases.append(dict(seed=seed,status='AWAITING_R3_FIRST_UPDATE',
                              available_branches=[b for b,x in found.items() if x]))
            continue
        arrays={b:np.load(Path(x['run'])/'ppo_rollout.npz') for b,x in found.items()}
        base=arrays['H2_AGG64']
        checks={b:{k:bool(np.array_equal(base[k],z[k])) for k in
                   ['obs','raw_actions','values','log_probs','episode_starts']} for b,z in arrays.items()}
        policies={b:read(Path(x['run'])/'before_update_checkpoint.json')['policy_sha256'] for b,x in found.items()}
        same_policy=len(set(policies.values()))==1
        cases.append(dict(seed=seed,
            status='PASS' if same_policy and all(all(c.values()) for c in checks.values()) else 'DIFFERENCE_REQUIRES_REVIEW',
            transitions=len(base['obs']),checks=checks,preupdate_policy_equal=same_policy,policies=policies,
            sources={b:dict(run=x['run'],rollout_sha256=sha(Path(x['run'])/'ppo_rollout.npz')) for b,x in found.items()}))
    atomic(ROOT/'audit/FOUR_REWARD_FIRST_ROLLOUT_IDENTITY.json',dict(time_utc=now(),
        source_sha256=sha(Path(__file__)),category='SAVED_FIRST_ROLLOUT_IDENTITY_NO_PHYSICS_NO_ADAM',
        cases=cases,physics_attempts=0,Adam_updates=0,
        scope='Exact first physical inputs and predictions before any branch-specific update; later closed-loop trajectories are not expected equal. Waiting is explicitly different from a successful comparison.'))
    print(json.dumps([dict(seed=x['seed'],status=x['status']) for x in cases]))


if __name__=='__main__':
    main()
