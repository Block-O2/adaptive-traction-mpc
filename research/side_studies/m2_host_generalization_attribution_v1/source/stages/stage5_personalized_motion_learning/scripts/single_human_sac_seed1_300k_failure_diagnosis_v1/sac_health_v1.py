"""Read-only replay/networks/optimizer audit. No learn(), train(), backward(), or step()."""
from inventory_v1 import *
import pickle, gc, zipfile, collections, shutil
import torch
from stable_baselines3 import SAC
torch.set_num_threads(1)
def describe(a):
    a=np.asarray(a,float).reshape(-1)
    return dict(n=len(a),finite=bool(np.all(np.isfinite(a))),min=float(np.min(a)),p05=float(np.quantile(a,.05)),median=float(np.median(a)),mean=float(np.mean(a)),p95=float(np.quantile(a,.95)),max=float(np.max(a)))
def run():
    seed=S/'results/single_human_sac_seed1_continuation_v2_guardfix_attempt3/seed_20261003'
    with (seed/'final_replay_buffer.pkl').open('rb') as h:b=pickle.load(h)
    assert b.size()==100000 and b.full
    obs=b.observations[:,0];nobs=b.next_observations[:,0];act=b.actions[:,0];rew=b.rewards[:,0];done=b.dones[:,0]
    indices=np.random.default_rng(20261003).choice(len(obs),4096,replace=False)
    phase=np.argmax(obs[:,41:44],axis=1);qdeg=obs[:,:2]*125
    delta=np.abs(act-nobs[:,51:53]);nonterm=done==0
    bins=[]
    for joint in range(2):
        count,edge=np.histogram(act[:,joint],bins=20,range=(-1,1));bins.append(dict(joint=joint,edges=edge.tolist(),counts=count.tolist()))
    coverage=dict(size=b.size(),capacity=b.buffer_size,n_envs=b.n_envs,position=b.pos,phase_counts={k:int(np.sum(phase==i)) for i,k in enumerate(['OUTBOUND','HOLD','RETURN'])},phase_onehot_valid=bool(np.all(np.sum(obs[:,41:44],axis=1)==1)),done_count=int(np.sum(done)),positive_completion_rewards=int(np.sum(rew>100)),failure_reward_count=int(np.sum(rew<-900)),reward=describe(rew),timeouts_stored_count=int(np.sum(b.timeouts)),handle_timeout_termination=b.handle_timeout_termination,q_est_deg=[describe(qdeg[:,i]) for i in range(2)],elapsed_task_s=describe(obs[:,44]*30),max_causal_mean_progress=float(np.max(np.mean(np.clip((qdeg-[5,10])/[115,110],0,1),axis=1))),action=[describe(act[:,i]) for i in range(2)],raw_saturation_any_rate=float(np.mean(np.any(np.abs(act)>=.95,axis=1))),raw_action_histograms=bins,previous_rejection_rate=float(np.mean(obs[:,53]>.5)),executed_target_discrepancy_nonterminal_mean_abs=np.mean(delta[nonterm],axis=0).tolist(),raw_nextobs_consistency_max_nonterminal=float(np.max(np.abs(act[nonterm]-nobs[nonterm,49:51]))),observation_max_abs_per_feature=np.max(np.abs(obs),axis=0).tolist(),terminal_bootstrap_disabled=bool(not b.handle_timeout_termination and np.all(b.timeouts==0)),scope='final100k cyclic replay (mostly200k-300k); raw proposal actions, not physical torque or reference trajectory',truth_access=False)
    save('REPLAY_COVERAGE.json',coverage)
    candidates=[(12194,S/'results/single_human_sac_expert_v1_r2/seed_20261003/step_0012194.zip')]
    old=S/'results/single_human_sac_seed1_continuation_v1_attempt2/saved_bundles'
    for step in (50000,100000,150000,200000,225000,250000):candidates.append((step,old/f'step_{step:07d}_periodic'/f'step_{step:07d}.zip'))
    candidates.append((300000,seed/'step_0300000.zip'))
    rows=[];ob=torch.as_tensor(obs[indices]);next_ob=torch.as_tensor(nobs[indices]);actions=torch.as_tensor(act[indices]);reward=torch.as_tensor(rew[indices,None]);dones=torch.as_tensor(done[indices,None])
    torch.manual_seed(20261003)
    for step,cp in candidates:
        if not cp.exists():
            rows.append(dict(step=step,missing_checkpoint=str(cp)));continue
        model=SAC.load(cp,device='cpu');model.policy.set_training_mode(False)
        all_finite=all(bool(torch.isfinite(p).all()) for p in model.policy.parameters())
        with torch.no_grad():
            mean,logstd,kwargs=model.actor.get_action_dist_params(ob)
            deterministic=model.actor(ob,deterministic=True)
            sample,logp=model.actor.action_log_prob(ob)
            next_action,next_logp=model.actor.action_log_prob(next_ob)
            alpha=torch.exp(model.log_ent_coef) if model.log_ent_coef is not None else model.ent_coef_tensor
            q=torch.cat(model.critic(ob,actions),dim=1);pq=torch.cat(model.critic(ob,sample),dim=1).min(dim=1,keepdim=True).values
            nextq=torch.cat(model.critic_target(next_ob,next_action),dim=1).min(dim=1,keepdim=True).values-alpha*next_logp.reshape(-1,1)
            target=reward+(1-dones)*model.gamma*nextq
            td=q-target;critic_loss=.5*sum(torch.mean((q[:,j:j+1]-target)**2).item() for j in range(q.shape[1]))
            actor_loss=float(torch.mean(alpha*logp.reshape(-1,1)-pq))
        optimizers={}
        for name,opt in [('actor',model.actor.optimizer),('critic',model.critic.optimizer),('alpha',model.ent_coef_optimizer)]:
            state=opt.state_dict();tensors=[v for x in state['state'].values() for v in x.values() if isinstance(v,torch.Tensor)]
            optimizers[name]=dict(states=len(state['state']),finite=all(bool(torch.isfinite(t).all()) for t in tensors),max_abs_tensor=max(float(t.abs().max()) for t in tensors),steps=sorted(set(float(v['step']) for v in state['state'].values())))
        item=dict(step=step,checkpoint=str(cp),checkpoint_sha256=sha(cp),updates=model._n_updates,all_policy_parameters_finite=all_finite,alpha=float(alpha),target_entropy=float(model.target_entropy),mean_log_probability=float(logp.mean()),sample_differential_entropy=float(-logp.mean()),mean_presquash_std=torch.exp(logstd).mean(dim=0).tolist(),deterministic_action_std_across_states=deterministic.std(dim=0).tolist(),deterministic_saturation_any_rate=float(torch.any(deterministic.abs()>=.95,dim=1).float().mean()),Q_raw_replay=describe(q.numpy()),Q_policy=describe(pq.numpy()),Q_target=describe(target.numpy()),td_residual=describe(td.numpy()),frozen_sample_critic_loss=critic_loss,frozen_sample_actor_loss=actor_loss,optimizer_states=optimizers,measurement_scope='4096 identical final-replay observations across checkpoints; historical checkpoint results include later/OOD states. Losses are fresh frozen diagnostic estimates, not recorded training losses.',historical_loss_time_series_available=False)
        rows.append(item);save('SAC_HEALTH_SNAPSHOTS.json',rows)
        print(json.dumps({k:item[k] for k in ('step','alpha','sample_differential_entropy','frozen_sample_critic_loss','frozen_sample_actor_loss','Q_raw_replay')}),flush=True)
        del model;gc.collect()
    save('SAC_HEALTH_SNAPSHOTS.json',rows);shutil.copy2(Path(__file__),P/Path(__file__).name)
if __name__=='__main__':run()
