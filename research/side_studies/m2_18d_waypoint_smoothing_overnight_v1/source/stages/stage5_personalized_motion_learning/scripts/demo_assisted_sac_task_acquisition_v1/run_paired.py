"""B then A, exactly 50k each; original SB3 SAC and R2 scientific semantics."""
from common import *
import threading, traceback, gc
from stable_baselines3.common.callbacks import BaseCallback
from final_qualification import compact_archive
from qualify import physical_audit
MODEL=None;ENV=None;ARM=None;PHASE='startup';WATCH_STOP=threading.Event();PRESSURE=None
RESOURCE=[];EVENTS=[];RESULTS={};EVALUATIONS={'A':[],'B':[]};HEALTH={'A':[],'B':[]}
ONLINE_PHASE={'A':np.zeros(3,np.int64),'B':np.zeros(3,np.int64)}
STATE=json.loads((D/'STATE.json').read_text()) if D.exists() else {}
LOCK=None

class StopCampaign(RuntimeError):pass
def event(arm,kind,step,rollout,scope='training',task_s=None,checkpoint=None):
    row=dict(arm=arm,event=kind,training_step=step,checkpoint=checkpoint,rollout_id=rollout,scope=scope,task_s=task_s)
    EVENTS.append(row);append('ACQUISITION_EVENTS.jsonl',row)
def state(status,**extras):
    STATE.update(status=status,phase=PHASE,arm=ARM,elapsed_s=time.time()-STATE['started_unix'],**extras)
    if MODEL is not None:STATE['steps'][ARM]=int(MODEL.num_timesteps)
    save('STATE.json',STATE)
def sample_resources(tag):
    global PRESSURE
    win=memory.windows();mem=memory.memfile('/proc/meminfo');proc=memory.processes()
    swap=mem['SwapTotal']-mem['SwapFree'];pss=sum(p.get('Pss',0) for p in proc['owned']);rss=sum(p.get('Rss',p.get('rss',0)) for p in proc['owned'])
    vm={k:int(v) for k,v in (x.split() for x in Path('/proc/vmstat').read_text().splitlines())}
    rs=[]
    if mem['MemAvailable']<1.5*2**30:rs.append('WSL_AVAILABLE_BELOW_1_5_GIB')
    if win['CommitLimit']-win['CommittedBytes']<2*2**30:rs.append('WINDOWS_COMMIT_HEADROOM_BELOW_2_GIB')
    if swap>16*2**20:rs.append('NEW_SWAP_OVER_16_MIB')
    if win['AvailableBytes']<256*2**20 and mem['MemAvailable']<2*2**30:rs.append('JOINT_LOW_MEMORY')
    if proc['other_heavy_python']:rs.append('OTHER_HEAVY_PYTHON')
    if win['ExternalVideoRender']:rs.append('EXTERNAL_VIDEO_RENDER')
    if pss>4.5*2**30:rs.append('TRAINING_TREE_OVER_4_5_GIB')
    past=RESOURCE[-3:]
    if len(past)==3 and all(b['swap_used_bytes']>a['swap_used_bytes'] or b['pswpout']>a['pswpout'] for a,b in zip(past,past[1:]+[dict(swap_used_bytes=swap,pswpout=vm['pswpout'])])):rs.append('SUSTAINED_SWAP_ACTIVITY')
    row=dict(unix=time.time(),tag=tag,arm=ARM,phase=PHASE,step=int(MODEL.num_timesteps) if MODEL else 0,windows=win,wsl=mem,swap_used_bytes=swap,pswpout=vm['pswpout'],tree_pss_bytes=pss,tree_rss_bytes=rss,processes=proc,gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip(),cuda_allocated=torch.cuda.memory_allocated(),cuda_reserved=torch.cuda.memory_reserved(),stop_reasons=rs)
    RESOURCE.append(row);RESOURCE[:]=RESOURCE[-500:];append('RESOURCE_WATCH.jsonl',row);PRESSURE=row
    return row
def watch():
    while not WATCH_STOP.wait(30):
        try:sample_resources('watch')
        except Exception as ex:PRESSURE_ERROR=dict(stop_reasons=['RESOURCE_MONITOR_FAILURE'],error=str(ex));globals()['PRESSURE']=PRESSURE_ERROR;append('RESOURCE_WATCH_ERRORS.jsonl',PRESSURE_ERROR)
def guard():
    if time.time()>=STATE['hard_cutoff_unix']:raise StopCampaign('HARD_9_HOUR_WALL_CAP')
    if PRESSURE and PRESSURE['stop_reasons']:raise StopCampaign('RESOURCE: '+str(PRESSURE['stop_reasons']))

class EvidenceEnv(SACExpertEnv):
    def reset(self,**kwargs):
        self.retain_trace=False
        obs,info=super().reset(**kwargs);self.evidence_previous=obs.copy()
        return obs,info
    def step(self,action):
        guard();prev=self.evidence_previous;obs,reward,term,trunc,info=super().step(action)
        step=MODEL.num_timesteps+1;rollout=f'{ARM}_online_episode_{self.episode_index:05d}'
        ONLINE_PHASE[ARM][prev[41:44].argmax()]+=1
        p=prev[41:44].argmax();n=obs[41:44].argmax() if obs[41:44].sum() else -1
        if p==0 and n==1:
            event(ARM,'settled_outbound',step,rollout,task_s=info['physics_task_s'])
            event(ARM,'hold_entry',step,rollout,task_s=info['physics_task_s'])
            # Runtime trace is already captured in RAM; preserve only phase-reaching episodes for audit.
            self.retain_trace=True
        if p==1 and n==2:
            event(ARM,'hold_completed',step,rollout,task_s=info['physics_task_s']);event(ARM,'return_entry',step,rollout,task_s=info['physics_task_s'])
        self.evidence_previous=obs.copy()
        if term or trunc:
            if self.retain_trace and info.get('success'):
                valid=physical_audit(self)['pass_'];info['independent_training_valid']=valid
                if valid:
                    event(ARM,'valid_complete',step,rollout,task_s=info['duration_s'])
                    if not (O/ARM/'FIRST_ONLINE_VALID_POLICY.zip').exists():
                        MODEL.save(O/ARM/'FIRST_ONLINE_VALID_POLICY.zip')
                    save(f'TRAINING_VALID_{ARM}_{step:07d}.json',dict(arm=ARM,step=step,rollout_id=rollout,audit=physical_audit(self),episode_dir=str(self.episode_dir)))
                compact_archive(self)
            # Summaries/actions contain scalar evidence for each episode; full raw retention decided at finish.
            if self.summary is not None:(self.episode_dir/'COMPACT_SUMMARY.json').write_text(json.dumps(clean(dict(status=self.summary['status'],abort_reason=self.summary.get('abort_reason'),task=self.summary['task'])),allow_nan=False))
        return obs,reward,term,trunc,info

def distribution(x):
    a=np.asarray(x,float);return dict(mean=float(a.mean()),min=float(a.min()),max=float(a.max()),rms=float(np.sqrt(np.mean(a*a))))
def health(model,step):
    rb=model.replay_buffer
    if rb.last_batch is None:return
    before=rng();opt=memory.optimizer_hash(model)
    try:
        batch=rb.last_batch
        with torch.no_grad():
            alpha=model.log_ent_coef.exp();pi,lp=model.actor.action_log_prob(batch.observations)
            na,nlp=model.actor.action_log_prob(batch.next_observations)
            q=torch.cat(model.critic(batch.observations,batch.actions),1)
            tq=torch.cat(model.critic_target(batch.next_observations,na),1).min(1,keepdim=True).values-alpha*nlp.reshape(-1,1)
            target=batch.rewards+(1-batch.dones)*model.gamma*tq
            td=q-target
            demo=np.load(O/'NATIVE_DEMO.npz');ob=torch.as_tensor(demo['observations'],device=model.device);da=torch.as_tensor(demo['actions'],device=model.device)
            di=np.random.default_rng(SEED).integers(0,rb.size(),len(da));failure_actions=torch.as_tensor(rb.actions[di,0],device=model.device)
            qdemo=torch.cat(model.critic(ob,da),1).min(1).values
            qalt=torch.cat(model.critic(ob,failure_actions),1).min(1).values
            actor=model.actor(ob,deterministic=True);qactor=torch.cat(model.critic(ob,actor),1).min(1).values
            discrepancy=(actor-da).abs()
        finite=all(torch.isfinite(p).all().item() for p in model.policy.parameters())
        row=dict(arm=ARM,step=step,updates=model._n_updates,finite=finite,alpha=float(alpha),sample_entropy=float(-lp.mean()),Q_scale=distribution(q.cpu()),TD_error=distribution(td.cpu()),td_abs_mean=float(td.abs().mean()),teacher_Q_mean=float(qdemo.mean()),same_teacher_states_online_action_Q_mean=float(qalt.mean()),teacher_minus_online_action_Q_mean=float((qdemo-qalt).mean()),teacher_preferred_rate=float((qdemo>qalt).float().mean()),actor_on_teacher_Q_mean=float(qactor.mean()),actor_teacher_action_MAE=discrepancy.mean(0).cpu().tolist(),actor_teacher_near_bound_rate=float((actor.abs()>=.95).any(1).float().mean()),online_phase=phases(rb.observations[:rb.size()]),demo_sample_phase=dict(zip(('OUTBOUND','HOLD','RETURN'),rb.demo_sample_counts.tolist())),online_sample_phase=dict(zip(('OUTBOUND','HOLD','RETURN'),rb.online_sample_counts.tolist())),critic_comparison_limit='Counterfactual raw actions sampled from online replay at identical teacher states; Q ranking alone is not physical success',losses={k:float(v) for k,v in model.logger.name_to_value.items() if k.startswith('train/') and np.isscalar(v)})
        assert finite and all(np.isfinite(v) for v in row['losses'].values())
        HEALTH[ARM].append(row);append(f'{ARM}_HEALTH.jsonl',row);save('SAC_HEALTH_COMPARISON.json',HEALTH)
    finally:restore(before)
    assert opt==memory.optimizer_hash(model)

def bundle(model,tag):
    folder=O/ARM/tag;folder.mkdir(parents=True,exist_ok=False)
    model.save(folder/'policy.zip');model.save_replay_buffer(folder/'online_and_sampler.pkl')
    with (folder/'global_rng.pkl').open('wb') as f:pickle.dump(rng(),f)
    if model.replay_buffer.demo:
        with (folder/'immutable_demo_buffer.pkl').open('wb') as f:pickle.dump(model.replay_buffer.demo,f)
    shutil.copy2(O/'SAC_OBSERVATION_NORMALIZATION.json',folder/'normalization.json')
    with (folder/'online_and_sampler.pkl').open('rb') as f:rb=pickle.load(f)
    assert rb.size()==model.replay_buffer.size() and rb.calls==model._n_updates
    receipt=dict(arm=ARM,step=int(model.num_timesteps),updates=model._n_updates,online_size=rb.size(),demo_size=rb.demo.size() if rb.demo else 0,policy_hash=policy_hash(model),optimizers=memory.optimizer_hash(model),sampler_calls=rb.calls,sampler_state=rb.sampler_rng.bit_generator.state,files={p.name:sha(p) for p in folder.iterdir() if p.is_file()},physics_resume='Cold reset required; paused physical mid-episode state is not serialized; never silently claim exact continuation')
    (folder/'BUNDLE.json').write_text(json.dumps(clean(receipt),indent=2));save(f'{ARM}_LATEST_BUNDLE.json',dict(path=str(folder),**receipt))
    return folder

def evaluate(model,step,scope,tag,checkpoint):
    global PHASE
    PHASE='evaluation';guard();check_lock();before=rng();opt=memory.optimizer_hash(model);ph=policy_hash(model);size=model.replay_buffer.size();calls=model.replay_buffer.calls;updates=model._n_updates
    parked_step_count=ENV.step_count if ENV is not None else None
    was_training=model.policy.training;model.policy.set_training_mode(False)
    case,options=load_case_options();out=O/'evaluation'/f'{ARM}_{step:07d}_{scope}_{tag}';env=SACExpertEnv(out,case,options,.02,scope,True)
    transitions=[];progress=0.;hold=False;returned=False
    try:
        obs,info=env.reset(seed=SEED);assert env.model_hash==LOCK['frozen_model_hash']
        for i in range(1600):
            guard();prev=obs.copy();p=info['phase']
            with torch.no_grad():action,_=model.predict(obs,deterministic=True)
            if p=='OUTBOUND':progress=max(progress,float(np.clip((prev[:2]*125-[5,10])/[115,110],0,1).min()))
            obs,reward,term,trunc,info=env.step(action)
            n=info.get('phase')
            if p=='OUTBOUND' and n=='HOLD':
                hold=True
                for ev in ('settled_outbound','hold_entry'):event(ARM,ev,step,out.name,scope,info['physics_task_s'],str(checkpoint))
            if p=='HOLD' and n=='RETURN':
                returned=True
                for ev in ('hold_completed','return_entry'):event(ARM,ev,step,out.name,scope,info['physics_task_s'],str(checkpoint))
            transitions.append((prev,action.copy(),reward,obs.copy(),term,trunc,p))
            if term or trunc:break
        assert env.summary is not None
        full=r2.metric(env,ARM,scope);valid=bool(full['valid'])
        if valid:event(ARM,'valid_complete',step,out.name,scope,full['duration_s'],str(checkpoint))
        # Settled semantics are actual task transition (position+velocity+reference readiness), not progress.
        rows=env.action_records;raw=np.asarray([r['raw'] for r in rows]);exe=np.asarray([r['executed'] for r in rows])
        with np.load(env.episode_dir/'trace.npz') as z:
            mask=z['stage']=='TASK';q=z['estimated_human_state_rad_rad_s'][mask,:2];ref=z['reference_q_rad'][mask];t=z['time_s'][mask]
            tracking=np.degrees(np.sqrt(np.mean((q-ref)**2,axis=0)))
            signed_lead=np.degrees(q[:,0]-q[:,1])
            dq=z['estimated_human_state_rad_rad_s'][mask,2:4]
            synchronized=float(np.clip((np.degrees(q)-[5,10])/[115,110],0,1).min(1).max()) if not hold else progress
        record={k:v for k,v in full.items() if k!='raw_actions'}
        record.update(arm=ARM,training_step=step,tag=tag,checkpoint=str(checkpoint),rollout_id=out.name,termination_reason=env.summary.get('abort_reason') or 'COMPLETE',failure_time_s=None if valid else full['duration_s'],max_synchronized_OUTBOUND_progress=max(progress,synchronized),settled_at_goal=hold,entered_HOLD=hold,HOLD_completed=returned,started_RETURN=returned,RETURN_completed=env.summary['status']=='COMPLETE',independent_VALID=valid,teacher_override=False,learning_frozen=True,exploration=False,normalization_updates=False,replay_written=False,tracking_RMSE_deg=tracking,lead_lag_deg=distribution(signed_lead),raw_action_mean=raw.mean(0),raw_action_std=raw.std(0),near_bound_action_rate=float((np.abs(raw)>=.95).any(1).mean()),action_modification_MAE=np.mean(np.abs(raw-exe),0),rejection_rate=env.rejections/max(1,len(raw)),reward_total=env.reward_total,phase_transitions=env.summary['task']['phase_transitions'])
        np.savez_compressed(env.episode_dir/'POLICY_TRANSITIONS.npz',observations=np.asarray([r[0] for r in transitions]),actions=np.asarray([r[1] for r in transitions]),rewards=np.asarray([r[2] for r in transitions]),next_observations=np.asarray([r[3] for r in transitions]),terminated=np.asarray([r[4] for r in transitions]),truncated=np.asarray([r[5] for r in transitions]),phase=np.asarray([r[6] for r in transitions]))
        EVALUATIONS[ARM].append(clean(record));save(f'EVALUATION_{out.name}.json',record)
        compact={k:v for k,v in record.items() if k not in ('physical_audit','model_beta','model_residual','initial_estimated_state','initial_reference','phase_transitions')}
        table(f'{ARM}_EVALUATION.csv',[{k:v for k,v in r.items() if k in compact} for r in EVALUATIONS[ARM]])
        compact_archive(env);print(json.dumps(clean({k:record[k] for k in ('arm','training_step','scope','valid','termination_reason','max_synchronized_OUTBOUND_progress','entered_HOLD','started_RETURN','duration_s')})),flush=True)
        return record
    finally:
        env.close();model.policy.set_training_mode(was_training);restore(before)
        assert policy_hash(model)==ph and memory.optimizer_hash(model)==opt and model.replay_buffer.size()==size and model.replay_buffer.calls==calls and model._n_updates==updates
        assert ENV is None or ENV.step_count==parked_step_count,'Training physics advanced during evaluation'
        PHASE='training'

class Callback(BaseCallback):
    def __init__(self):super().__init__();self.begin=time.monotonic();self.episodes=0;self.loss_rows=[];self.episode_rows=[];self.early_actions=[];self.last_health=0
    def _on_training_start(self):
        sample_resources('after_initial_reset');guard()
    def _on_step(self):
        step=self.model.num_timesteps;info=self.locals['infos'][0];assert info.get('model_hash')==LOCK['frozen_model_hash'];guard()
        if step<=5000:self.early_actions.append(self.locals['actions'][0].copy())
        if self.locals['dones'][0]:
            self.episodes+=1
            row=dict(arm=ARM,training_step=step,episode=self.episodes,**{k:info.get(k) for k in ('status','abort_reason','success','independent_training_valid','duration_s','steps','reward_total','J_F','force_peak','moment_peak','rejections','fallbacks')})
            self.episode_rows.append(row);append(f'{ARM}_EPISODES.jsonl',row)
        if step%100==0:
            rb=self.model.replay_buffer
            row=dict(arm=ARM,training_step=step,updates=self.model._n_updates,wall_s=time.monotonic()-self.begin,steps_s=step/(time.monotonic()-self.begin),episodes=self.episodes,**{k:float(v) for k,v in self.model.logger.name_to_value.items() if k.startswith('train/') and np.isscalar(v)})
            row.update(online_phase_counts=dict(zip(('OUTBOUND','HOLD','RETURN'),ONLINE_PHASE[ARM].tolist())),sampler_calls=rb.calls,demo_samples=int(rb.demo_sample_counts.sum()),online_samples=int(rb.online_sample_counts.sum()))
            self.loss_rows.append(row);append(f'{ARM}_LEARNING_CURVE.jsonl',row)
        if step%1000==0:
            health(self.model,step);table(f'{ARM}_LEARNING_CURVE.csv',self.loss_rows)
            state('FORMAL_TRAINING',steps_s=step/(time.monotonic()-self.begin),episodes=self.episodes,latest_health=HEALTH[ARM][-1] if HEALTH[ARM] else None)
            print(json.dumps(dict(arm=ARM,step=step,steps_s=step/(time.monotonic()-self.begin),updates=self.model._n_updates)),flush=True)
        return True
    def _on_rollout_end(self):
        step=self.model.num_timesteps
        if step in (10000,20000,30000,40000,50000):
            # Collected transition is now in replay; standard update for this step follows evaluation.
            folder=bundle(self.model,f'step_{step:07d}_periodic')
            state('DETERMINISTIC_EVALUATION',checkpoint=str(folder))
            for scope in ('NATIVE','MATCHED'):evaluate(self.model,step,scope,'periodic',folder/'policy.zip')
            guard()

def run():
    global MODEL,ENV,ARM,PHASE,LOCK
    assert STATE['status']=='READY_FOR_FORMAL_B_THEN_A'
    assert json.loads((D/'TEACHER_EXACT_REPRODUCTION.json').read_text())['status']=='PASS'
    LOCK=check_lock();assert torch.cuda.is_available()
    for p in (W/NAME).glob('*.py'):shutil.copy2(p,P/p.name)
    source_files=list(P.glob('*.py'))+[D/'A_SCRATCH_CONFIG.json',D/'B_DEMO_CONFIG.json',D/'DEMO_SAMPLING_CONTRACT.json',O/'NATIVE_DEMO.npz']
    save('EXPERIMENT_SOURCE_LOCK.json',dict(frozen_before_formal_steps=True,files={str(p):sha(p) for p in source_files},SAC_train_sha256=hashlib.sha256(__import__('inspect').getsource(SAC.train).encode()).hexdigest()))
    sample_resources('before_formal');guard()
    observer=threading.Thread(target=watch,name='resource_observer',daemon=True);observer.start()
    error=None
    try:
        for ARM in ('B','A'):
            PHASE='training';config=json.loads((D/('B_DEMO_CONFIG.json' if ARM=='B' else 'A_SCRATCH_CONFIG.json')).read_text());check_lock()
            case,options=load_case_options();ENV=EvidenceEnv(O/ARM/'training',case,options,.02,'NATIVE',False)
            MODEL=make_model(ENV,ARM,config);assert policy_hash(MODEL)==json.loads((D/'PAIRED_INITIALIZATION_AUDIT.json').read_text())['policy_sha256'][ARM]
            assert MODEL._n_updates==MODEL.num_timesteps==MODEL.replay_buffer.size()==0
            rb=MODEL.replay_buffer;rb.log_path=str(O/f'{ARM}_BATCH_SAMPLING.csv')
            with Path(rb.log_path).open('w',newline='') as f:csv.writer(f).writerow(['batch','online_steps','demo_count','online_count','demo_fraction','demo_OUTBOUND','demo_HOLD','demo_RETURN','online_OUTBOUND','online_HOLD','online_RETURN'])
            cb=Callback();state('FORMAL_TRAINING',initialization_verified=True)
            try:
                MODEL.learn(total_timesteps=TARGET,callback=cb,reset_num_timesteps=True)
                assert MODEL.num_timesteps==50000 and MODEL._n_updates==45000 and rb.calls==45000
                final=bundle(MODEL,'step_0050000_final');ENV.close()
                for scope in ('NATIVE','MATCHED'):evaluate(MODEL,50000,scope,'final',final/'policy.zip')
                health(MODEL,50000)
                online=rb.observations[:rb.size(),0];actions=rb.actions[:rb.size(),0]
                result=dict(arm=ARM,steps=MODEL.num_timesteps,updates=MODEL._n_updates,wall_s=time.monotonic()-cb.begin,steps_s=MODEL.num_timesteps/(time.monotonic()-cb.begin),episodes=cb.episodes,online_phase=phases(online),all_collected_phase=dict(zip(('OUTBOUND','HOLD','RETURN'),ONLINE_PHASE[ARM].tolist())),completion_rewards=int((rb.rewards[:rb.size()]>100).sum()),online_near_bound_action_rate=float((np.abs(actions)>=.95).any(1).mean()),online_action_mean=actions.mean(0),online_action_std=actions.std(0),previous_rejection_rate=float((online[:,53]>.5).mean()),sampling=dict(batches=rb.calls,demo_samples=int(rb.demo_sample_counts.sum()),online_samples=int(rb.online_sample_counts.sum()),demo_phase=dict(zip(('OUTBOUND','HOLD','RETURN'),rb.demo_sample_counts.tolist())),online_phase=dict(zip(('OUTBOUND','HOLD','RETURN'),rb.online_sample_counts.tolist()))),final_bundle=str(final),optimizer=memory.optimizer_hash(MODEL))
                RESULTS[ARM]=clean(result);save('ARM_RESULTS.json',RESULTS)
                np.savez_compressed(O/f'{ARM}_INITIAL_RANDOM_ACTIONS.npz',actions=np.asarray(cb.early_actions))
                if ARM=='B':
                    audit=json.loads((D/'PAIRED_INITIALIZATION_AUDIT.json').read_text());audit['B_random_action_sha256']=sha(O/'B_INITIAL_RANDOM_ACTIONS.npz');save('PAIRED_INITIALIZATION_AUDIT.json',audit)
                else:
                    with np.load(O/'B_INITIAL_RANDOM_ACTIONS.npz') as zz:np.testing.assert_array_equal(zz['actions'],np.asarray(cb.early_actions))
                    audit=json.loads((D/'PAIRED_INITIALIZATION_AUDIT.json').read_text());audit['first_5000_random_actions_identical']=True;save('PAIRED_INITIALIZATION_AUDIT.json',audit)
                table(f'{ARM}_LEARNING_CURVE.csv',cb.loss_rows);table(f'{ARM}_EPISODES.csv',cb.episode_rows)
                state('ARM_COMPLETE');print(json.dumps(dict(arm=ARM,status='ARM_50K_COMPLETE',steps=50000,updates=45000)),flush=True)
            except BaseException:
                # on_step interruption occurs before SB3 stores the current transition; mark exact sizes honestly.
                bundle(MODEL,f'paused_{MODEL.num_timesteps:07d}_{time.time_ns()}');raise
            finally:
                ENV.close();del cb;MODEL=None;ENV=None;gc.collect()
    except BaseException as ex:
        error=dict(reason=str(ex),traceback=traceback.format_exc());save('FORMAL_STOP_EXCEPTION.json',error);print(error['traceback'],flush=True)
    finally:
        WATCH_STOP.set();observer.join(timeout=35)
        save('PHASE_COVERAGE_COMPARISON.json',{k:v['online_phase'] for k,v in RESULTS.items()})
        save('DEMO_SAMPLING_STATISTICS.json',{k:v['sampling'] for k,v in RESULTS.items()})
        save('ALL_EVALUATIONS.json',EVALUATIONS);save('ALL_ACQUISITION_EVENTS.json',EVENTS)
        state('PAIRED_50K_COMPLETE_PENDING_REPORT' if len(RESULTS)==2 else 'PAUSED_PRESERVED',error=error,next='Run finish.py: verify preservation, audit sampling, select VALID only, write required comparison, individually stage compact artifacts, STOP. No new training.')
    return error is None
if __name__=='__main__':
    ok=run();sys.exit(0 if ok else 1)
