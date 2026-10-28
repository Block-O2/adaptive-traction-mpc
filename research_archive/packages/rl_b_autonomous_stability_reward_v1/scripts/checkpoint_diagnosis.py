"""Saved-policy comparison on common legal causal observations, no physics."""
from pathlib import Path
import json,sys,os
from research_common import ROOT,RUNTIME,atomic,read,sha,now
sys.path.insert(0,str(RUNTIME))
import common
import numpy as np,torch
from stable_baselines3 import PPO
torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
HISTORY=ROOT.parent/'rl_b_autonomous_replication_v1'

def distribution(model,obs):
    with torch.no_grad():
        d=model.policy.get_distribution(torch.as_tensor(obs,dtype=torch.float32))
        return d.distribution.mean.numpy(),d.distribution.stddev.numpy(),d.entropy().numpy()
def main():
    rows=[json.loads(x) for x in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    cases=[]
    for seed in [1495656323,1630784693]:
        parent=HISTORY/f'seeds/{seed}/stage1/checkpoints/episode_050'
        data=next(json.loads(x) for x in (HISTORY/'ALL_EVALUATION_LOG.jsonl').read_text().splitlines()
                  if json.loads(x)['training_seed']==seed and json.loads(x)['kind']=='checkpoint050_first')
        run=HISTORY/data['run'];paths=list(run.glob('transitions_*.npz'));assert len(paths)==1
        obs=np.load(paths[0])['obs'];base=PPO.load(parent.with_suffix('.zip'),device='cpu');base.policy.set_training_mode(False)
        mu0,sd0,h0=distribution(base,obs)
        checkpoints={str(parent):dict(branch='ORIGINAL_050',episode=0)}
        for ep in [60,70,80]:checkpoints[str(HISTORY/f'seeds/{seed}/stage1/checkpoints/episode_{ep:03d}')]=dict(branch='ORIGINAL_CONTROL',episode=ep-50)
        for row in rows:
            if row['seed']==seed and row['mode']=='evaluation':
                meta=read(Path(row['parent']).with_suffix('.json'))
                checkpoints[row['parent']]=dict(branch=row['branch'],episode=meta.get('continuation_episodes'))
        for path,info in checkpoints.items():
            p=Path(path);meta=read(p.with_suffix('.json'));model=PPO.load(p.with_suffix('.zip'),device='cpu');model.policy.set_training_mode(False)
            mu,sd,h=distribution(model,obs)
            kl=np.sum(np.log(sd/sd0)+(sd0**2+(mu0-mu)**2)/(2*sd**2)-.5,axis=1)
            actor_keys=[k for k in model.policy.state_dict() if k.startswith('mlp_extractor.policy_net') or k.startswith('action_net') or k=='log_std']
            critic_keys=[k for k in model.policy.state_dict() if k.startswith('mlp_extractor.value_net') or k.startswith('value_net')]
            def norm(keys):return float(np.sqrt(sum(float(((model.policy.state_dict()[k]-base.policy.state_dict()[k])**2).sum()) for k in keys)))
            cases.append(dict(seed=seed,checkpoint=path,**info,policy_sha256=meta['policy_sha256'],
                model_sha256=sha(p.with_suffix('.zip')),shared_observations=len(obs),
                observation_source=str(paths[0]),observation_source_sha256=sha(paths[0]),
                mean_absolute_drift=np.mean(np.abs(mu-mu0),axis=0).tolist(),
                initial_mean=mu[0].tolist(),initial_std=sd[0].tolist(),mean_entropy=float(h.mean()),
                mean_Gaussian_KL_parent_to_candidate=float(kl.mean()),max_Gaussian_KL_parent_to_candidate=float(kl.max()),
                actor_parameter_l2_drift=norm(actor_keys),critic_parameter_l2_drift=norm(critic_keys),
                std_log=model.policy.log_std.detach().numpy().tolist(),
                clipped_mean_absolute_drift=np.mean(np.abs(np.clip(mu,-1,1)-np.clip(mu0,-1,1)),axis=0).tolist(),
                PPO_epochs=meta['updates'],decisions=meta['decisions']))
            del model
    atomic(ROOT/'CHECKPOINT_POLICY_DIAGNOSTICS.json',dict(time_utc=now(),category='SAVED_POLICY_NO_PHYSICS',cases=cases,
        scope='Gaussian KL and mean drift on common original050 legal observations; not a new environment trial or a unique causal attribution'))
    print('diagnosed checkpoints',len(cases))
if __name__=='__main__':main()
