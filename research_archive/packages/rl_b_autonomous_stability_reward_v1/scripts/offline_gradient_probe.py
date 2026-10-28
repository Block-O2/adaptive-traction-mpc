"""Counterfactual first-minibatch gradients on saved development transitions.

No simulator, no Adam.step, no checkpoint write. This probes gradient competition
under the original joint norm clipping; it is not a replacement training result.
"""
from pathlib import Path
import sys,json
from research_common import ROOT,RUNTIME,atomic,sha,now,read
sys.path.insert(0,str(RUNTIME))
import common
import numpy as np,torch
from stable_baselines3 import PPO
from stable_baselines3.common.buffers import RolloutBuffer
from rewards import transition
torch.set_num_threads(1);torch.set_num_interop_threads(1)

def main():
    result=[]
    for seed,job in [(1495656323,'control_seed1495656323_first5__repair1'),
                     (1630784693,'CONTROL_IDENTITY_seed1630784693_to005')]:
        for episode in [1,2]:
            run=RUNTIME/'jobs'/job/f'episode_{episode:03d}'
            saved=read(run/'RESEARCH_TRANSITIONS.json')
            parent=ROOT.parent/f'rl_b_autonomous_replication_v1/seeds/{seed}/stage1/checkpoints/episode_050' if episode==1 else RUNTIME/'jobs'/job/f'checkpoints/episode_{episode-1:03d}'
            model=PPO.load(parent.with_suffix('.zip'),device='cpu');model.policy.set_training_mode(True)
            model.policy.optimizer.step=lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('OFFLINE_PROBE_FORBIDS_ADAM_STEP'))
            indices=np.random.default_rng(2026102100).permutation(len(saved))[:16]
            for version in ['R0','R1','R2']:
                buf=RolloutBuffer(len(saved),model.observation_space,model.action_space,device='cpu',gamma=1.,gae_lambda=.95,n_envs=1)
                reward_values=[]
                for s in saved:
                    reward,_=transition(version,s['reward_before'],s['reward_after'],s['terminal'],s['success'],s['baseline_reward'])
                    reward_values.append(reward)
                    buf.add(np.asarray(s['obs'],np.float32).reshape(1,-1),np.asarray(s['raw_action'],np.float32).reshape(1,-1),
                         np.array([reward]),np.array([s['episode_start']]),torch.tensor([s['value']]),torch.tensor([s['logp']]))
                buf.compute_returns_and_advantage(last_values=torch.zeros(1),dones=np.array([True]))
                obs=torch.tensor(buf.observations[indices,0],dtype=torch.float32)
                actions=torch.tensor(buf.actions[indices,0],dtype=torch.float32)
                advantages=torch.tensor(buf.advantages[indices,0],dtype=torch.float32)
                returns=torch.tensor(buf.returns[indices,0],dtype=torch.float32)
                oldlog=torch.tensor(buf.log_probs[indices,0],dtype=torch.float32)
                values,logp,entropy=model.policy.evaluate_actions(obs,actions);values=values.flatten()
                if len(indices)>1:advantages=(advantages-advantages.mean())/(advantages.std()+1e-8)
                ratio=torch.exp(logp-oldlog)
                actor_loss=-torch.min(advantages*ratio,advantages*torch.clamp(ratio,.8,1.2)).mean()
                critic_loss=torch.nn.functional.mse_loss(returns,values)
                loss=actor_loss+.5*critic_loss;model.policy.optimizer.zero_grad();loss.backward()
                actor2=critic2=other2=0.
                for name,p in model.policy.named_parameters():
                    if p.grad is None:continue
                    n=float((p.grad.detach()**2).sum())
                    if name.startswith(('mlp_extractor.policy_net','action_net')) or name=='log_std':actor2+=n
                    elif name.startswith(('mlp_extractor.value_net','value_net')):critic2+=n
                    else:other2+=n
                total=np.sqrt(actor2+critic2+other2);factor=min(1.,.5/(total+1e-6))
                result.append(dict(seed=seed,run=str(run),parent=str(parent),episode=episode,
                    observed_success=saved[-1]['success'],reward=version,transitions=len(saved),batch=len(indices),
                    trajectory_return=sum(reward_values),value_loss=float(critic_loss),actor_loss=float(actor_loss),
                    actor_gradient_l2=float(np.sqrt(actor2)),critic_gradient_l2=float(np.sqrt(critic2)),
                    total_gradient_l2=float(total),original_joint_clip_factor=float(factor),
                    actor_gradient_after_original_joint_clip=float(np.sqrt(actor2)*factor),
                    critic_squared_norm_fraction=float(critic2/(total**2)) if total else 0.,
                    advantage_RMS=float(np.sqrt(np.mean(buf.advantages**2))),return_RMS=float(np.sqrt(np.mean(buf.returns**2))),
                    source_transitions_sha256=sha(run/'RESEARCH_TRANSITIONS.json'),Adam_updates=0))
            del model
    atomic(ROOT/'audit/OFFLINE_REWARD_GRADIENT_PROBE.json',dict(time_utc=now(),source_sha256=sha(Path(__file__)),
          cases=result,category='OFFLINE_COUNTERFACTUAL_GRADIENT_DIAGNOSTIC_NO_PHYSICS_NO_ADAM',
          limitations='Same saved trajectories and old critic; first fixed minibatch only. Does not identify the unique training cause, predict task success, or substitute real MuJoCo training. Counterfactual reward targets are not a held-out evaluation.'))
    print('offline gradient cases',len(result),'Adam updates 0')
if __name__=='__main__':main()
