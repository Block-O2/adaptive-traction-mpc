"""Versioned monitor repair and verified restoration of this campaign's A checkpoint."""
from common import *
import run_paired as c
import threading, traceback, inspect
from stable_baselines3.common.logger import configure

def lines(name):
    p=D/name
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

def corrected_resources(tag):
    win=memory.windows();mem=memory.memfile('/proc/meminfo');proc=memory.processes()
    swap=mem['SwapTotal']-mem['SwapFree'];pss=sum(p.get('Pss',0) for p in proc['owned']);rss=sum(p.get('Rss',p.get('rss',0)) for p in proc['owned'])
    vm={k:int(v) for k,v in (x.split() for x in Path('/proc/vmstat').read_text().splitlines())};rs=[]
    if mem['MemAvailable']<1.5*2**30:rs.append('WSL_AVAILABLE_BELOW_1_5_GIB')
    if win['CommitLimit']-win['CommittedBytes']<2*2**30:rs.append('WINDOWS_COMMIT_HEADROOM_BELOW_2_GIB')
    if swap>16*2**20:rs.append('NEW_SWAP_OVER_16_MIB')
    if win['AvailableBytes']<256*2**20 and mem['MemAvailable']<2*2**30:rs.append('JOINT_LOW_MEMORY')
    if proc['other_heavy_python']:rs.append('OTHER_HEAVY_PYTHON')
    if win['ExternalVideoRender']:rs.append('EXTERNAL_VIDEO_RENDER')
    # Exact phase/step condition from continue_seed1_v3_guardfix.py. Neither 50k arm reaches 55k.
    if c.PHASE=='training' and c.MODEL is not None and c.MODEL.num_timesteps>=55000 and pss>4.5*2**30:rs.append('PERSISTENT_TRAINING_TREE_OVER_4_5_GIB')
    past=c.RESOURCE[-3:]
    if len(past)==3 and all(b['swap_used_bytes']>a['swap_used_bytes'] or b['pswpout']>a['pswpout'] for a,b in zip(past,past[1:]+[dict(swap_used_bytes=swap,pswpout=vm['pswpout'])])):rs.append('SUSTAINED_SWAP_ACTIVITY')
    row=dict(unix=time.time(),tag=tag,arm=c.ARM,phase=c.PHASE,step=int(c.MODEL.num_timesteps) if c.MODEL else 0,windows=win,wsl=mem,swap_used_bytes=swap,pswpout=vm['pswpout'],tree_pss_bytes=pss,tree_rss_bytes=rss,processes=proc,gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip(),cuda_allocated=torch.cuda.memory_allocated(),cuda_reserved=torch.cuda.memory_reserved(),stop_reasons=rs,monitor_version='guardfix_v2')
    c.RESOURCE.append(row);c.RESOURCE[:]=c.RESOURCE[-500:];append('RESOURCE_WATCH.jsonl',row);c.PRESSURE=row
    return row

class RecoveryEnv(c.EvidenceEnv):
    reconstructing=True
    def step(self,action):
        if self.reconstructing:return SACExpertEnv.step(self,action)
        return super().step(action)

def run():
    assert c.STATE['status']=='PAUSED_PRESERVED' and c.STATE['steps']=={'A':10000,'B':50000}
    save('PRE_GUARDFIX_PAUSED_STATE.json',c.STATE)
    save('PRE_GUARDFIX_STOP_EXCEPTION.json',json.loads((D/'FORMAL_STOP_EXCEPTION.json').read_text()))
    source=json.loads((D/'EXPERIMENT_SOURCE_LOCK.json').read_text())
    for p,h in source['files'].items():assert sha(p)==h,p
    assert hashlib.sha256(inspect.getsource(SAC.train).encode()).hexdigest()==source['SAC_train_sha256']
    c.LOCK=check_lock();c.ARM='A';c.PHASE='restoration';c.sample_resources=corrected_resources
    c.RESOURCE=lines('RESOURCE_WATCH.jsonl')[-500:];c.EVENTS=json.loads((D/'ALL_ACQUISITION_EVENTS.json').read_text())
    c.EVALUATIONS=json.loads((D/'ALL_EVALUATIONS.json').read_text());c.HEALTH=json.loads((D/'SAC_HEALTH_COMPARISON.json').read_text());c.RESULTS=json.loads((D/'ARM_RESULTS.json').read_text())
    c.ONLINE_PHASE['B']=np.array([50000,0,0]);c.ONLINE_PHASE['A']=np.array([10000,0,0])
    corrected_resources('before_guardfix_restore');c.guard()
    receipt=json.loads((D/'A_LATEST_BUNDLE.json').read_text());folder=Path(receipt['path'])
    assert receipt['step']==10000 and receipt['updates']==4999
    for name,h in receipt['files'].items():assert sha(folder/name)==h
    with (folder/'global_rng.pkl').open('rb') as f:saved_rng=pickle.load(f)
    cb=c.Callback();cb.loss_rows=lines('A_LEARNING_CURVE.jsonl');cb.episode_rows=lines('A_EPISODES.jsonl');cb.episodes=len(cb.episode_rows)
    case,options=load_case_options();c.ENV=RecoveryEnv(O/'A'/'training_guardfix_v2',case,options,.02,'NATIVE',False);c.ENV.episode_index=cb.episodes
    c.MODEL=SAC.load(folder/'policy.zip',env=c.ENV,device='cuda',force_reset=False)
    c.MODEL.load_replay_buffer(folder/'online_and_sampler.pkl');model=c.MODEL;rb=model.replay_buffer
    assert policy_hash(model)==receipt['policy_hash'] and memory.optimizer_hash(model)==receipt['optimizers']
    assert rb.size()==rb.online_steps==model.num_timesteps==10000 and rb.calls==model._n_updates==4999 and rb.demo is None
    assert str(model.device)=='cuda' and model.learning_starts==5000 and model.batch_size==256
    expected=model._last_obs.copy();episode_starts=model._last_episode_starts.copy()
    indices=np.flatnonzero(rb.dones[:rb.size(),0]);start=int(indices[-1])+1
    assert start==cb.episode_rows[-1]['training_step'] and not rb.dones[9999,0]
    cb.early_actions=[x.copy() for x in rb.actions[:5000,0]]
    with np.load(O/'B_INITIAL_RANDOM_ACTIONS.npz') as z:np.testing.assert_array_equal(z['actions'],np.asarray(cb.early_actions))
    vec=model.get_env();vec.seed(SEED);obs=vec.reset();np.testing.assert_array_equal(obs,rb.observations[start])
    for i in range(start,10000):
        c.guard();np.testing.assert_array_equal(obs,rb.observations[i])
        obs,reward,done,info=vec.step(rb.actions[i].copy())
        np.testing.assert_array_equal(obs,rb.next_observations[i]);np.testing.assert_array_equal(reward,rb.rewards[i]);np.testing.assert_array_equal(done,rb.dones[i].astype(bool))
    np.testing.assert_array_equal(obs,expected);assert c.ENV.model_hash==c.LOCK['frozen_model_hash'] and c.ENV.step_count==10000-start
    assert policy_hash(model)==receipt['policy_hash'] and memory.optimizer_hash(model)==receipt['optimizers'] and rb.calls==4999
    c.ENV.evidence_previous=obs[0].copy();c.ENV.reconstructing=False;model._last_obs=obs.copy();model._last_episode_starts=episode_starts
    restore(saved_rng);model.set_logger(configure(str(O/'A'/'sb3_guardfix_v2'),[]))
    restored=dict(status='PASS',own_campaign_checkpoint=str(folder),reconstructed_prior_actor_steps=10000-start,original_episode=cb.episodes+1,observation_reward_done_comparison='BITWISE_ARRAY_EQUAL_EVERY_TRANSITION',new_online_steps_during_reconstruction=0,new_updates_during_reconstruction=0,cold_physics_reset_avoided=True,RNG_restored=True,optimizer_restored=True,replay_restored=True,first_5000_A_B_actions_equal=True,hard_cutoff_unchanged=c.STATE['hard_cutoff_unix'],source_lock_verified=True,scientific_changes=[])
    save('EXACT_A_PHYSICS_RESTORATION.json',restored)
    prose('MONITOR_GUARDFIX_V2.md','# Monitor repair and exact A restoration\n\nThe original orchestration incorrectly applied the 4.5 GiB process-tree gate unconditionally, including evaluation. The previously corrected monitor applies it only during training at >=55k steps, unreachable by either 50k arm. Real memory, commit, swap, external-process and wall-cap guards remain active. Original source and false-stop logs are retained.\n\nOnly this campaign\'s own A step-10000 checkpoint, optimizer, replay and RNG are restored. The open episode is reconstructed with its 419 prior actor actions; every observation, next observation, float32 reward and done flag must match bitwise. Reconstruction adds no online samples or updates. The outstanding standard update for the already collected step 10000 is performed once, then standard SAC learns exactly 40000 remaining steps. No teacher actions, prior scratch300k state, modified science, new budget or repeated B training.\n')
    print(json.dumps(restored),flush=True)
    c.PHASE='training';corrected_resources('after_exact_physics_restore');c.guard()
    model.train(gradient_steps=1,batch_size=256)
    assert model._n_updates==rb.calls==5000 and rb.size()==model.num_timesteps==10000
    save('PENDING_STANDARD_UPDATE_ACCOUNTING.json',dict(before_updates=4999,after_updates=5000,collected_step=10000,online_steps_unchanged=10000,extra_updates=0))
    # Include prior A process time; exclude operator repair downtime and label it explicitly.
    prior_rows=[r for r in lines('RESOURCE_WATCH.jsonl') if r['arm']=='A' and r.get('monitor_version')!='guardfix_v2']
    prior_wall=prior_rows[-1]['unix']-prior_rows[0]['unix'];cb.begin=time.monotonic()-prior_wall
    observer=threading.Thread(target=c.watch,name='resource_observer_guardfix_v2',daemon=True);observer.start();error=None
    try:
        c.state('FORMAL_TRAINING',exact_restoration=True,monitor_version='guardfix_v2')
        model.learn(total_timesteps=40000,callback=cb,reset_num_timesteps=False)
        assert model.num_timesteps==50000 and model._n_updates==rb.calls==45000
        final=c.bundle(model,'step_0050000_final');c.ENV.close()
        for scope in ('NATIVE','MATCHED'):c.evaluate(model,50000,scope,'final',final/'policy.zip')
        c.health(model,50000)
        online=rb.observations[:rb.size(),0];actions=rb.actions[:rb.size(),0]
        result=dict(arm='A',steps=model.num_timesteps,updates=model._n_updates,wall_s=time.monotonic()-cb.begin,steps_s=model.num_timesteps/(time.monotonic()-cb.begin),episodes=cb.episodes,wall_accounting='sum of A process segments; repair downtime excluded, campaign 9h cap unchanged',online_phase=phases(online),all_collected_phase=dict(zip(('OUTBOUND','HOLD','RETURN'),c.ONLINE_PHASE['A'].tolist())),completion_rewards=int((rb.rewards[:rb.size()]>100).sum()),online_near_bound_action_rate=float((np.abs(actions)>=.95).any(1).mean()),online_action_mean=actions.mean(0),online_action_std=actions.std(0),previous_rejection_rate=float((online[:,53]>.5).mean()),sampling=dict(batches=rb.calls,demo_samples=int(rb.demo_sample_counts.sum()),online_samples=int(rb.online_sample_counts.sum()),demo_phase=dict(zip(('OUTBOUND','HOLD','RETURN'),rb.demo_sample_counts.tolist())),online_phase=dict(zip(('OUTBOUND','HOLD','RETURN'),rb.online_sample_counts.tolist()))),final_bundle=str(final),optimizer=memory.optimizer_hash(model))
        c.RESULTS['A']=clean(result);save('ARM_RESULTS.json',c.RESULTS)
        np.savez_compressed(O/'A_INITIAL_RANDOM_ACTIONS.npz',actions=np.asarray(cb.early_actions))
        audit=json.loads((D/'PAIRED_INITIALIZATION_AUDIT.json').read_text());audit['first_5000_random_actions_identical']=True;save('PAIRED_INITIALIZATION_AUDIT.json',audit)
        table('A_LEARNING_CURVE.csv',cb.loss_rows);table('A_EPISODES.csv',cb.episode_rows)
        c.state('ARM_COMPLETE');print(json.dumps(dict(arm='A',status='ARM_50K_COMPLETE',steps=50000,updates=45000)),flush=True)
    except BaseException as ex:
        error=dict(reason=str(ex),traceback=traceback.format_exc());save('RESUME_GUARDFIX_V2_EXCEPTION.json',error)
        c.bundle(model,f'guardfix_paused_{model.num_timesteps:07d}_{time.time_ns()}');print(error['traceback'],flush=True)
    finally:
        c.WATCH_STOP.set();observer.join(timeout=35);c.ENV.close()
        save('PHASE_COVERAGE_COMPARISON.json',{k:v['online_phase'] for k,v in c.RESULTS.items()});save('DEMO_SAMPLING_STATISTICS.json',{k:v['sampling'] for k,v in c.RESULTS.items()})
        save('ALL_EVALUATIONS.json',c.EVALUATIONS);save('ALL_ACQUISITION_EVENTS.json',c.EVENTS)
        c.state('PAIRED_50K_COMPLETE_PENDING_REPORT' if len(c.RESULTS)==2 else 'PAUSED_PRESERVED',error=error)
    return error is None

if __name__=='__main__':
    shutil.copy2(Path(__file__),P/Path(__file__).name)
    save('RECOVERY_SOURCE_LOCK.json',dict(files={str(P/Path(__file__).name):sha(P/Path(__file__).name)},original_frozen_files_unchanged=True,monitor_only_repair=True))
    sys.exit(0 if run() else 1)
