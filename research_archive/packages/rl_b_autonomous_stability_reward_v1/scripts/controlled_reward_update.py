"""First actual PPO update under exactly shared prestate and physical inputs."""
from pathlib import Path
import ast,hashlib,json
import numpy as np
import torch
from stable_baselines3 import PPO
from research_common import ROOT,read,atomic,sha,now

torch.set_num_threads(1)
torch.set_num_interop_threads(1)
torch.set_grad_enabled(False)


def distribution(model,obs):
    d=model.policy.get_distribution(torch.tensor(obs,dtype=torch.float32)).distribution
    return d.mean.numpy(),d.stddev.numpy()


def hyper(model):
    return {k:getattr(model,k) for k in ['learning_rate','n_epochs','batch_size','gamma',
            'gae_lambda','vf_coef','ent_coef','max_grad_norm','target_kl']}|{'clip_range':model.clip_range(1.)}


def main():
    rows=[json.loads(s) for s in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    cases=[]
    for seed in [1495656323,1630784693]:
        found={b:next((x for x in rows if x['seed']==seed and x['branch']==b and x['update']),None)
               for b in ['H2_AGG64','REWARD_R1','REWARD_R2']}
        if any(x is None for x in found.values()):
            cases.append(dict(seed=seed,status='AWAITING_R2_FIRST_UPDATE'));continue
        runs={b:Path(x['run']) for b,x in found.items()}
        pre={b:read(p/'before_update_checkpoint.json') for b,p in runs.items()}
        base=pre['H2_AGG64']['state_snapshot']
        state_checks={b:{k:v==base[k] for k,v in m['state_snapshot'].items()} for b,m in pre.items()}
        zs={b:np.load(p/'ppo_rollout.npz') for b,p in runs.items()}
        z0=zs['H2_AGG64'];inputs={b:{k:bool(np.array_equal(z0[k],z[k])) for k in
               ['obs','raw_actions','values','log_probs','episode_starts']} for b,z in zs.items()}
        implementations={};sources={};effects=[];models={}
        for branch,x in found.items():
            ident=read(ROOT/'jobs'/x['job_id']/'SOURCE_IDENTITY.json')
            worker=Path(ident['path'])/'worker.py'
            update=next(n for n in ast.parse(worker.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='update')
            implementations[branch]=hashlib.sha256(ast.dump(update,include_attributes=False).encode()).hexdigest()
            before_path=runs[branch]/'before_update_checkpoint.zip'
            after_path=Path(x['checkpoint_after']).with_suffix('.zip')
            postmeta=read(after_path.with_suffix('.json'))
            file_checks=dict(pre_zip_sha=sha(before_path)==pre[branch]['model_sha256'],
                             post_zip_sha=sha(after_path)==postmeta['model_sha256'])
            assert all(file_checks.values()),file_checks
            before=PPO.load(before_path,device='cpu');after=PPO.load(after_path,device='cpu')
            before.policy.set_training_mode(False);after.policy.set_training_mode(False)
            models[branch]=hyper(before)
            obs=z0['obs'][:,0];mu0,sd0=distribution(before,obs);mu,sd=distribution(after,obs)
            kl=np.sum(np.log(sd/sd0)+(sd0**2+(mu0-mu)**2)/(2*sd**2)-.5,axis=1)
            squares={'actor':0.,'critic':0.,'other':0.}
            for name,value in after.policy.state_dict().items():
                group='actor' if name.startswith(('mlp_extractor.policy_net','action_net')) or name=='log_std' else 'critic' if name.startswith(('mlp_extractor.value_net','value_net')) else 'other'
                squares[group]+=float(((value-before.policy.state_dict()[name])**2).sum())
            effects.append(dict(branch=branch,actual_Adam=x['gradient_updates'],actual_PPO_epochs=x['update']['epochs'],
                actor_parameter_l2_change=float(np.sqrt(squares['actor'])),critic_parameter_l2_change=float(np.sqrt(squares['critic'])),
                mean_absolute_Gaussian_mean_change=np.abs(mu-mu0).mean(0).tolist(),
                mean_Gaussian_KL_pre_to_post=float(kl.mean()),initial_mean_pre=mu0[0].tolist(),initial_mean_post=mu[0].tolist(),
                std_pre=sd0[0].tolist(),std_post=sd[0].tolist(),file_checks=file_checks))
            sources[branch]=dict(rollout=str(runs[branch]/'ppo_rollout.npz'),rollout_sha256=sha(runs[branch]/'ppo_rollout.npz'),
                                before_model=str(before_path),before_model_sha256=sha(before_path),after_model=str(after_path),after_model_sha256=sha(after_path),
                                worker=str(worker),worker_sha256=sha(worker))
        checks=dict(full_prestate=all(all(x.values()) for x in state_checks.values()),
                    physical_inputs=all(all(x.values()) for x in inputs.values()),
                    actual_update_implementation=len(set(implementations.values()))==1,
                    PPO_hyperparameters=all(v==models['H2_AGG64'] for v in models.values()),
                    actual_Adam_counts=len({x['actual_Adam'] for x in effects})==1)
        cases.append(dict(seed=seed,status='CONTROLLED_FIRST_UPDATE' if all(checks.values()) else 'DIFFERENCE_REQUIRES_REVIEW',
             checks=checks,prestate_checks=state_checks,input_checks=inputs,update_implementation_AST_sha256=implementations,
             PPO_hyperparameters=models,effects=effects,sources=sources))
    atomic(ROOT/'audit/CONTROLLED_FIRST_REWARD_UPDATE.json',dict(time_utc=now(),source_sha256=sha(Path(__file__)),
        category='SAVED_ACTUAL_TRAINED_UPDATE_NO_NEW_PHYSICS_NO_ADAM',cases=cases,physics_attempts=0,Adam_updates=0,
        scope='Actual saved model changes after the first controlled PPO update; the listed actual Adam work occurred in the original training jobs, not in this read-only audit.',
        limits='A local first-update reward effect on identical inputs/state is distinct from the unique cause of later closed-loop degeneration, task robustness or heldout generalization. Gaussian proposals are not applied physical commands.'))
    print(json.dumps([dict(seed=x['seed'],status=x['status']) for x in cases]))


if __name__=='__main__':main()
