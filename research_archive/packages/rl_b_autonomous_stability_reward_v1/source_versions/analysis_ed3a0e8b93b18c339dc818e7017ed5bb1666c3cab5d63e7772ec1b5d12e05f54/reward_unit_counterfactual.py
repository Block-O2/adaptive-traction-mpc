"""One prejustified reward-unit ablation on saved R1 first physical rollouts."""
from pathlib import Path
import json
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.buffers import RolloutBuffer
from research_common import ROOT, read, atomic, sha, now

torch.set_num_threads(1)
torch.set_num_interop_threads(1)


def main():
    rows=[json.loads(s) for s in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    cases=[]
    for seed in [1495656323,1630784693]:
        x=next(x for x in rows if x['branch']=='REWARD_R1' and x['seed']==seed and x['update'])
        run=Path(x['run']);z=np.load(run/'ppo_rollout.npz');n=len(z['rewards'])
        permutation=np.random.default_rng(2026102100).permutation(n)
        batches=[permutation[i:i+16] for i in range(0,n,16)]
        if len(batches)>1 and len(batches[-1])==1:
            batches[-2]=np.concatenate([batches[-2],batches[-1]]);batches.pop()
        comparisons=[]
        for divisor in [1.,30.]:
            model=PPO.load(run/'before_update_checkpoint.zip',device='cpu')
            model.policy.set_training_mode(True)
            def forbidden(*args,**kwargs):
                raise RuntimeError('REWARD_UNIT_PROBE_FORBIDS_ADAM')
            model.policy.optimizer.step=forbidden
            buf=RolloutBuffer(n,model.observation_space,model.action_space,device='cpu',
                              gamma=1.,gae_lambda=.95,n_envs=1)
            for i in range(n):
                buf.add(z['obs'][i],z['raw_actions'][i],z['rewards'][i]/divisor,
                        z['episode_starts'][i],torch.tensor(z['values'][i]),torch.tensor(z['log_probs'][i]))
            buf.compute_returns_and_advantage(last_values=torch.zeros(1),dones=np.array([True]))
            baseline_reconstruction=None
            if divisor==1.:
                baseline_reconstruction={k:bool(np.array_equal(getattr(buf,k),z[k])) for k in ['returns','advantages']}
                assert all(baseline_reconstruction.values())
            gradients=[]
            for ids in batches:
                values,logp,_=model.policy.evaluate_actions(torch.tensor(z['obs'][ids,0]),torch.tensor(z['raw_actions'][ids,0]))
                adv=torch.tensor(buf.advantages[ids,0]);adv=(adv-adv.mean())/(adv.std()+1e-8)
                ratio=torch.exp(logp-torch.tensor(z['log_probs'][ids,0]))
                actor=-torch.min(adv*ratio,adv*torch.clamp(ratio,.8,1.2)).mean()
                critic=torch.nn.functional.mse_loss(values.flatten(),torch.tensor(buf.returns[ids,0]))
                model.policy.optimizer.zero_grad();(actor+.5*critic).backward()
                actor2=critic2=other2=0.
                for name,p in model.policy.named_parameters():
                    if p.grad is None:continue
                    norm2=float((p.grad.detach()**2).sum())
                    if name.startswith(('mlp_extractor.policy_net','action_net')) or name=='log_std':actor2+=norm2
                    elif name.startswith(('mlp_extractor.value_net','value_net')):critic2+=norm2
                    else:other2+=norm2
                total=float(np.sqrt(actor2+critic2+other2));factor=min(1.,.5/(total+1e-6))
                gradients.append(dict(indices=ids.tolist(),value_loss=float(critic),
                    critic_squared_norm_fraction=critic2/total**2 if total else 0.,
                    actor_after_joint_clip=float(np.sqrt(actor2)*factor),joint_clip_factor=factor))
            comparisons.append(dict(reward_divisor=divisor,baseline_reconstruction=baseline_reconstruction,
                stored_old_values_unchanged=True,terminal_and_episode_boundaries_unchanged=True,
                return_target_range=[float(buf.returns.min()),float(buf.returns.max())],gradients=gradients,
                mean_actor_after_joint_clip=float(np.mean([g['actor_after_joint_clip'] for g in gradients])),
                mean_critic_squared_norm_fraction=float(np.mean([g['critic_squared_norm_fraction'] for g in gradients]))))
        cases.append(dict(seed=seed,transitions=n,run=str(run),
            rollout_sha256=sha(run/'ppo_rollout.npz'),preupdate_model_sha256=sha(run/'before_update_checkpoint.zip'),
            comparisons=comparisons))
    atomic(ROOT/'audit/REWARD_UNIT_COUNTERFACTUAL.json',dict(time_utc=now(),source_sha256=sha(Path(__file__)),
        category='OFFLINE_UNIT_ABLATION_NO_NEW_REWARD_TRAINING',cases=cases,physics_attempts=0,Adam_updates=0,
        divisor_rationale='30 = absolute configured R1 failure penalty15 + failure cost floor15, independent of unseen test outcomes; only this one normalization was tested.',
        causal_scope='Saved realized R1 transitions and original preupdate model; recompute complete-episode GAE after scaling rewards, do not simply divide old returns.',
        limitations='Old critic is intentionally unchanged. Reward units, pretrained value mismatch and joint clipping interact; no unique attribution, later Adam simulation, runtime success, formal new Reward version or holdout use. Any physical normalization study requires a separate version and evidence-gated decision.'))
    print('single-normalization saved-data comparisons',len(cases),'new physics=0 Adam=0')


if __name__=='__main__':
    main()
