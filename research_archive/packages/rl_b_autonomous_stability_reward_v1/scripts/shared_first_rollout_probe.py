"""R0/R1 gradient competition on their byte-identical first physical samples."""
from pathlib import Path
import json
import numpy as np
import torch
from stable_baselines3 import PPO
from research_common import ROOT, read, atomic, now, sha

torch.set_num_threads(1)
torch.set_num_interop_threads(1)


def main():
    rows = [json.loads(s) for s in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    cases = []
    for seed in [1495656323,1630784693]:
        runs = {}
        for branch in ['H2_AGG64','REWARD_R1']:
            first = next((x for x in rows if x['branch']==branch and x['seed']==seed and x['update']),None)
            if first is not None:
                runs[branch] = Path(first['run'])
        if len(runs)!=2:
            continue
        zs = {b:np.load(p/'ppo_rollout.npz') for b,p in runs.items()}
        a,b = zs.values()
        checks = {k:np.array_equal(a[k],b[k]) for k in ['obs','raw_actions','values','log_probs','episode_starts']}
        checks['preupdate_policy'] = len({read(p/'before_update_checkpoint.json')['policy_sha256'] for p in runs.values()})==1
        assert all(checks.values()),checks
        n = len(a['rewards'])
        order = np.random.default_rng(2026102100).permutation(n)
        batches = [order[i:i+16] for i in range(0,n,16)]
        if len(batches)>1 and len(batches[-1])==1:
            batches[-2]=np.concatenate([batches[-2],batches[-1]]);batches.pop()
        gradients = []
        for branch,run in runs.items():
            z = zs[branch]
            model = PPO.load(run/'before_update_checkpoint.zip',device='cpu')
            model.policy.set_training_mode(True)
            def forbidden(*args,**kwargs):
                raise RuntimeError('SAVED_GRADIENT_PROBE_FORBIDS_ADAM')
            model.policy.optimizer.step = forbidden
            for ids in batches:
                tensor = lambda key:torch.tensor(z[key][ids,0],dtype=torch.float32)
                values,logp,_ = model.policy.evaluate_actions(tensor('obs'),tensor('raw_actions'))
                adv = tensor('advantages')
                if len(ids)>1:
                    adv=(adv-adv.mean())/(adv.std()+1e-8)
                ratio=torch.exp(logp-tensor('log_probs'))
                actor=-torch.min(adv*ratio,adv*torch.clamp(ratio,.8,1.2)).mean()
                critic=torch.nn.functional.mse_loss(values.flatten(),tensor('returns'))
                model.policy.optimizer.zero_grad()
                (actor+.5*critic).backward()
                actor2=critic2=other2=0.
                for name,p in model.policy.named_parameters():
                    if p.grad is None:continue
                    square=float((p.grad.detach()**2).sum())
                    if name.startswith(('mlp_extractor.policy_net','action_net')) or name=='log_std':actor2+=square
                    elif name.startswith(('mlp_extractor.value_net','value_net')):critic2+=square
                    else:other2+=square
                norm=float(np.sqrt(actor2+critic2+other2));factor=min(1.,.5/(norm+1e-6))
                gradients.append(dict(branch=branch,indices=ids.tolist(),value_loss=float(critic),
                    actor_gradient_norm=float(np.sqrt(actor2)),critic_gradient_norm=float(np.sqrt(critic2)),
                    critic_squared_norm_fraction=critic2/norm**2 if norm else 0.,
                    joint_clip_factor=factor,actor_gradient_after_joint_clip=float(np.sqrt(actor2)*factor)))
        cases.append(dict(seed=seed,transitions=n,shared_input_checks=checks,
            sources={b:dict(run=str(p),rollout_sha256=sha(p/'ppo_rollout.npz'),
                           preupdate_model_sha256=sha(p/'before_update_checkpoint.zip')) for b,p in runs.items()},
            gradient_cases=gradients))
    atomic(ROOT/'audit/SHARED_FIRST_ROLLOUT_REWARD_PROBE.json',dict(time_utc=now(),
        source_sha256=sha(Path(__file__)),cases=cases,physics_attempts=0,Adam_updates=0,
        scope='Both actually trained reward arms share first physical rollout observations/actions/old predictions. Gradients use saved actual reward targets and identical fixed minibatches at unupdated initial parameters.',
        limitations='Fixed diagnostic permutation, not a reconstruction of actual shuffled minibatch order. Later Adam/momentum/multiple epochs and closed-loop trajectories are not simulated; this cannot establish a unique training cause or task qualification.'))
    print('shared physical first-rollout comparisons',len(cases),'new physics=0 Adam=0')


if __name__=='__main__':
    main()
