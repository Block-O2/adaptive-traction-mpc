"""Fresh native SB3 SAC, fixed mixed replay, qualified actor initialization."""
from common import *
from stable_baselines3 import SAC
from stable_baselines3.common.buffers import ReplayBuffer
from stable_baselines3.common.type_aliases import ReplayBufferSamples
from dagger import rollout
import pickle
class MixedReplayBuffer(ReplayBuffer):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.demo=None;self.demo_fraction=.25;self.draws=0;self.rounding_residual=0.
    def sample(self,batch_size,env=None):
        assert self.demo is not None and len(self.demo['actions'])>0
        # First 50k: precisely 64 of 256. At 10%, systematic 25/26
        # quantization gives exactly 128 of each 1280 draws, without random ratio drift.
        ideal=batch_size*self.demo_fraction+self.rounding_residual;nd=int(np.floor(ideal+1e-9));self.rounding_residual=ideal-nd
        online=super().sample(batch_size-nd,env)
        ids=np.random.randint(len(self.demo['actions']),size=nd)
        d=self.demo
        demo=ReplayBufferSamples(self.to_torch(d['observations'][ids]),self.to_torch(d['actions'][ids]),
            self.to_torch(d['next_observations'][ids]),self.to_torch(d['dones'][ids].reshape(-1,1)),self.to_torch(d['rewards'][ids].reshape(-1,1)))
        values=[torch.cat([getattr(demo,k),getattr(online,k)],0) for k in ReplayBufferSamples._fields]
        self.draws+=1;return ReplayBufferSamples(*values)
def replay_arrays(path):
    z=np.load(path);return dict(observations=np.asarray(z['observations'],np.float32),actions=np.asarray(z['actions'],np.float32),
        next_observations=np.asarray(z['next_observations'],np.float32),rewards=np.asarray(z['rewards'],np.float32),
        dones=np.asarray(z['terminated']|z['truncated'],np.float32))
def seed_online(buffer,path):
    data=replay_arrays(path)
    for i in range(len(data['actions'])):
        buffer.add(data['observations'][i],data['next_observations'][i],data['actions'][i],data['rewards'][i],data['dones'][i],[{}])
def snapshot(model,label,extra):
    folder=O/'sac'/label;folder.mkdir(parents=True,exist_ok=True)
    model.save(folder/'model');model.save_replay_buffer(folder/'replay.pkl')
    torch.save(dict(numpy_rng=np.random.get_state(),python_rng=random.getstate(),torch_rng=torch.get_rng_state(),
                    cuda_rng=torch.cuda.get_rng_state_all(),num_timesteps=model.num_timesteps,extra=extra),folder/'resume.pt')
    save('SAC_LATEST_CHECKPOINT.json',dict(path=folder,online_steps=model.num_timesteps,model_sha256=sha(folder/'model.zip'),
         replay_sha256=sha(folder/'replay.pkl'),rng_sha256=sha(folder/'resume.pt'),optimizer_saved_in_native_SAC=True,**extra))
    return folder
def evaluate(model,step):
    cpu=actor(read('PREREGISTRATION.json')['seed']);cpu.load_state_dict(model.actor.state_dict());cpu.eval();rows=[]
    for scope in ('NATIVE','MATCHED'):
        for j in range(3):
            row,_=rollout(cpu,f'sac/evaluation_{step:06d}_{scope}_{j+1}',scope=scope);rows.append(row)
    return rows,cpu
def run():
    qualification=read('DAGGER_QUALIFICATION.json');assert qualification['status']=='PASS';check();resource('SAC_INITIALIZATION')
    cfg=read('PREREGISTRATION.json');sc=cfg['sac'];case,options=load_case_options()
    env=SACExpertEnv(O/'sac/online',case,options,.02,'NATIVE',False)
    model=SAC('MlpPolicy',env,device='cuda',seed=cfg['seed'],verbose=0,learning_rate=sc['learning_rate'],
        batch_size=sc['batch_size'],buffer_size=sc['buffer_size'],learning_starts=0,train_freq=1,gradient_steps=1,
        gamma=sc['gamma'],tau=sc['tau'],ent_coef=sc['ent_coef'],target_entropy=sc['target_entropy'],
        policy_kwargs=dict(net_arch=[256,256]),replay_buffer_class=MixedReplayBuffer,
        replay_buffer_kwargs=dict(handle_timeout_termination=False))
    ck=torch.load(O/'qualified_actor.pt',map_location='cpu',weights_only=False)
    student=actor(cfg['seed']);student.load_state_dict(ck['state_dict']);student.eval()
    critic_initial={k:v.detach().cpu().clone() for k,v in model.critic.state_dict().items()}
    assert len(model.actor.optimizer.state)==len(model.critic.optimizer.state)==len(model.ent_coef_optimizer.state)==0
    model.actor.load_state_dict(student.state_dict())
    # Initial exploration is local to the known competent mean; this is frozen prospectively.
    with torch.no_grad():model.actor.log_std.weight.zero_();model.actor.log_std.bias.fill_(sc['log_std_init'])
    model.actor.log_std.requires_grad_(True)
    probe=np.load(O/'qualified_aggregated.npz')['observations']
    a,_=student.predict(probe,deterministic=True);b,_=model.predict(probe,deterministic=True)
    np.testing.assert_allclose(a,b,atol=2e-6,rtol=0)
    assert all(torch.equal(critic_initial[k],v.detach().cpu()) for k,v in model.critic.state_dict().items())
    assert model.critic is not model.critic_target
    assert all(torch.equal(v,model.critic_target.state_dict()[k]) for k,v in model.critic.state_dict().items())
    save('SAC_INITIALIZATION.json',dict(status='PASS',observation_count=len(probe),actor_max_difference=float(np.max(np.abs(a-b))),
        mean_exact_weights=True,critic_unchanged_since_fresh_initialization=True,target_fresh=True,optimizers_fresh=True,
        old_scratch_or_demo_critic_loaded=False,initial_log_std=sc['log_std_init'],uniform_random_warmup_steps=0,
        late_ratio_quantization='25 and 26 demo items per 256 batch via deterministic residual; exactly 128/1280 per five batches'))
    # Qualification NATIVE repeats already provide the student baseline.
    # Add the required MATCHED comparator sequentially before opening SAC physics.
    matched_student=[]
    for j in range(3):
        baseline,_=rollout(student,f'qualified_student_MATCHED_{j+1}',scope='MATCHED')
        matched_student.append(baseline)
    save('QUALIFIED_STUDENT_MATCHED_COMPARATOR.json',dict(rows=matched_student,
         baseline_only=True,no_learning_updates=True,actor_mean_identity_unchanged=True))
    model.replay_buffer.demo=replay_arrays(O/'qualified_aggregated.npz')
    # Seed the online portion with the qualified student's actual successful rollouts.
    rounds=read('DAGGER_RESULTS.json')['rounds'][-2:]
    for rd in rounds:
        for row in rd['evaluations']:
            assert row['valid'] and row['teacher_execution_count']==0;seed_online(model.replay_buffer,row['transitions'])
    seeded=model.replay_buffer.size();assert seeded>0
    rows=[];history=[];lost=0;last_good=snapshot(model,'qualified_start',dict(qualified=True,demo_fraction=.25))
    best={};state('SAC_FINE_TUNING',sac_started=True,online_steps=0,replay_seed_steps=seeded)
    try:
        for step in range(10000,sc['max_online_steps']+1,10000):
            check();resource('SAC_'+str(step-10000))
            stable=len(history)>=2 and all(h['native_valid']==3 for h in history[-2:])
            fraction=.10 if model.num_timesteps>=50000 and stable else .25
            model.replay_buffer.demo_fraction=fraction
            # Preserve scalar ratio residual when the schedule changes.
            print(json.dumps(dict(phase='SAC_COLLECTION',from_step=model.num_timesteps,to_step=step,demo_fraction=fraction)),flush=True)
            # One physics owner. Finish/close training owner before any evaluation owner.
            class Guard(__import__('stable_baselines3').common.callbacks.BaseCallback):
                def _on_step(self):
                    if self.num_timesteps%1000==0:
                        check();resource('ONLINE_'+str(self.num_timesteps))
                        snapshot(self.model,'resume_latest',dict(demo_fraction=fraction,evaluation_pending=True))
                        state('SAC_FINE_TUNING',online_steps=self.num_timesteps)
                    return True
            model.learn(total_timesteps=10000,reset_num_timesteps=False,callback=Guard())
            assert model.num_timesteps==step
            env.close();model._last_obs=None # New cold reset is explicit between training chunks.
            checkpoint_path=snapshot(model,f'step_{step:06d}',dict(demo_fraction=fraction,evaluation_pending=True))
            eval_rows,cpu=evaluate(model,step);rows.extend(eval_rows)
            native=[r for r in eval_rows if r['scope']=='NATIVE'];matched=[r for r in eval_rows if r['scope']=='MATCHED']
            nv=sum(r['valid'] for r in native);mv=sum(r['valid'] for r in matched)
            history.append(dict(step=step,native_valid=nv,matched_valid=mv,demo_fraction=fraction,checkpoint=checkpoint_path))
            lost=lost+1 if nv<=1 else 0
            if nv==3:last_good=checkpoint_path
            for scope in ('NATIVE','MATCHED'):
                valid=[r for r in eval_rows if r['scope']==scope and r['valid']]
                if valid:
                    candidate=min(valid,key=lambda r:r['J_F'])
                    if scope not in best or candidate['J_F']<best[scope]['J_F']:
                        confirmation,_=rollout(cpu,f'sac/confirmation_{step:06d}_{scope}',scope=scope)
                        confirmed=confirmation['valid'] and abs(confirmation['J_F']-candidate['J_F'])<=1e-6
                        save(f'SAC_CONFIRMATION_{step:06d}_{scope}.json',dict(pass_=confirmed,candidate=candidate,confirmation=confirmation))
                        assert confirmed,'EVIDENCE_CORRUPTION_REPLAY_DIFFERENCE'
                        best[scope]=dict(**candidate,online_steps=step,confirmed=True,checkpoint=checkpoint_path)
            save('SAC_RESULTS.json',dict(evaluations=rows,checkpoints=history,best=best,last_good_checkpoint=last_good,consecutive_ability_loss=lost))
            state('SAC_CHECKPOINT_EVALUATED',online_steps=step,native_success=f'{nv}/3',matched_success=f'{mv}/3',last_good_checkpoint=last_good)
            if lost>=2:
                model.actor.requires_grad_(False)
                snapshot(model,'ability_loss_stop',dict(actor_frozen=True,last_good_checkpoint=last_good))
                state('SAC_ABILITY_LOST',next_action='Diagnose two successive losses; preserve last good checkpoint and STOP actor fine-tuning.');return
        state('DAGGER_TO_SAC_EXPERT_V1_COMPLETE',next_action='Report confirmed VALID-only rankings; STOP.')
    except BaseException as e:
        env.close();snapshot(model,'interruption_saved',dict(exception=str(e),last_good_checkpoint=last_good))
        raise
    finally:env.close()
if __name__=='__main__':run()
