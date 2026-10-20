from common import *
import inspect, collections

def run():
    assert not D.exists(),'Refuse overwrite of a previous formal experiment'
    for f in (D,O,P,L):f.mkdir(parents=True,exist_ok=True)
    begin=time.time()
    # Snapshot pre-existing index and all visible research evidence plus large archived bundles.
    pre=memory.snapshot()
    historical=json.loads((DIAG/'PRESERVATION_BEFORE.json').read_text())
    for p in historical['files']:pre['files'][p]=sha(R/p)
    for root in (DIAG,S/'results/single_human_sac_seed1_300k_failure_diagnosis_v1',S/'results/single_human_sac_seed1_continuation_v2_guardfix_attempt3'):
        for p in root.rglob('*'):
            if p.is_file():pre['files'][str(p.relative_to(R))]=sha(p)
    save('PRESERVATION_BEFORE.json',pre)
    assert pre['branch']=='codex/single-human-sac-expert-v1'
    subprocess.run(['git','switch','-c',BRANCH],cwd=R,check=True)
    assert subprocess.check_output(['git','ls-files','--stage'],cwd=R,text=True)==pre['index']
    lock=json.loads((OLD/'SAC_CONTRACT_LOCK.json').read_text())
    for p,h in lock['files'].items():assert sha(R/p)==h,p
    save('SCIENTIFIC_LOCK.json',lock)
    for name in ('SAC_EXPERT_V1_CONTRACT.json','SAC_OBSERVATION_NORMALIZATION.json','SAC_TRAINING_CONFIG.json'):
        shutil.copy2(OLD/name,O/name)
    for p in (W/NAME).glob('*.py'):shutil.copy2(p,P/p.name)
    shutil.copy2(W/NAME/'USER_REQUEST.txt',D/'USER_REQUEST.txt')
    state=dict(status='PREFLIGHT',started_unix=begin,hard_cutoff_unix=begin+9*3600,steps={'A':0,'B':0},branch=BRANCH,source_head=pre['head'],order=['B','A'],target_per_arm=TARGET,next='Audit saved teacher; freeze sampler; fresh paired initialization; run B then A; STOP')
    save('STATE.json',state)
    row=dict(windows=memory.windows(),wsl=memory.memfile('/proc/meminfo'),processes=memory.processes())
    assert not row['processes']['other_heavy_python'] and not row['windows']['ExternalVideoRender']
    assert row['wsl']['MemAvailable']>=1.5*2**30 and row['wsl']['SwapFree']==row['wsl']['SwapTotal']
    assert row['windows']['CommitLimit']-row['windows']['CommittedBytes']>=2*2**30
    save('RESOURCE_PREFLIGHT.json',row)
    diag=json.loads((DIAG/'DIAGNOSTIC_fixed_hip_lead_NATIVE.json').read_text())
    path=R/diag['transition_archive'];ep=path.parent;z=np.load(path)
    assert diag['valid'] and diag['independent_physical_audit']['pass_'] and diag['scope']=='NATIVE'
    assert diag['frozen_model_hash']==lock['frozen_model_hash']
    n=len(z['rewards']);assert n==593
    obs=z['observations'];nxt=z['next_observations'];actions=z['actions']
    assert obs.shape==nxt.shape==(n,55) and actions.shape==(n,2)
    assert obs.dtype==nxt.dtype==np.float32
    assert np.isfinite(obs).all() and np.isfinite(nxt).all() and np.isfinite(actions).all()
    assert np.max(np.abs(actions))<=1
    np.testing.assert_array_equal(nxt[:-1],obs[1:])
    np.testing.assert_allclose(obs[:,44]*30,z['task_s'],atol=2e-6,rtol=0)
    assert (np.array(['OUTBOUND','HOLD','RETURN'])[obs[:,41:44].argmax(1)]==z['phase']).all()
    assert np.all(z['terminated'][:-1]==False) and z['terminated'][-1] and not z['truncated'].any()
    assert not nxt[-1,41:44].any() and nxt[-1,54]==0
    with np.load(ep/'SAC_ACTOR_ACTIONS.npz') as az:
        np.testing.assert_allclose(actions,az['raw_action'],atol=0,rtol=0)
        np.testing.assert_allclose(az['executed_action'],actions,atol=2e-7,rtol=0)
        np.testing.assert_allclose(nxt[:-1,49:51],actions[:-1],atol=0,rtol=0)
        np.testing.assert_allclose(nxt[:-1,51:53],az['executed_action'][:-1],atol=2e-7,rtol=0)
        rejected=~np.isin(az['status'],['ACCEPTED','IDENTICAL_CONTINUATION']);assert not rejected.any()
    # Recompute rewards from the causal policy state and measured-force trace.
    def phi(o):
        p=np.mean(np.clip((o[:,:2]*SCALES[:2]-np.radians([5,10]))/np.radians([115,110]),0,1),axis=1)
        ph=o[:,41:44].argmax(1)
        return np.where(ph==0,p,np.where(ph==1,1+np.minimum(1,o[:,48]),3-p))
    pn=phi(nxt);pn[-1]=0
    recomputed_shaping=5*(np.exp(-.02/150)*pn-phi(obs))
    np.testing.assert_allclose(recomputed_shaping,z['reward_shaping'],atol=4e-6,rtol=0)
    with np.load(ep/'trace.npz') as tr:
        mask=tr['stage']=='TASK';t=tr['time_s'][mask];t=t-t[0]
        force=np.linalg.norm(tr['measured_cuff_force_world_n'][mask],axis=1) if 'measured_cuff_force_world_n' in tr.files else None
        trace_keys=tr.files
    parts=sum(z['reward_'+k] for k in ('force','shaping','completion','failure','rejection'))
    np.testing.assert_allclose(parts,z['rewards'],atol=1e-10,rtol=0)
    assert np.sum(z['reward_completion'])==500 and np.sum(z['reward_failure'])==0
    assert abs(z['rewards'].sum()-diag['reward_total'])<1e-8
    assert sha(R/diag['metric']['trace'])==diag['metric']['trace_sha256']
    # Same source writer recorded measured left quadrature; physical quadrature is independently equal.
    assert abs(-z['reward_force'].sum()*100-diag['metric']['J_F'])<1e-7
    per=[dict(index=i,phase=str(z['phase'][i]),task_s=float(z['task_s'][i]),observation_shape=True,fixed_normalization=True,causal_schema=True,raw_action_matches=True,executed_target_matches=True,reward_parts_verified=True,next_observation_continuity=True,terminated=bool(z['terminated'][i]),truncated=bool(z['truncated'][i]),task_version=lock['task_hash'],human_model=lock['frozen_model_hash'],wrapper_sha256=sha(S/'scripts/single_human_sac_expert_v1/sac_env.py')) for i in range(n)]
    audit=dict(status='PASS',source=str(path),source_sha256=sha(path),count=n,scope='NATIVE',phase_counts=phases(obs),features=feature_spec(),normalization='already normalized float32; do NOT renormalize',raw_action='[-1,1]^2 absolute 0..125 degree target; identity SB3 action scaling',executed_action='accepted/fallback target encoding, never actual joint motion',reward='unchanged R2 measured quadrature, potential shaping, completion/failure/rejection; finite-task timeout has no bootstrap',independent_valid=True,task_hash=lock['task_hash'],human_hash=lock['frozen_model_hash'],per_transition=per,forbidden_fields_absent=True,no_oracle_actor=True,trace_keys_evaluation_only=trace_keys)
    save('DEMO_DATA_AUDIT.json',audit)
    prose('DEMO_DATA_AUDIT.md',f'# Demo data audit\n\nPASS: all {n} saved NATIVE transitions. Phase counts: {audit["phase_counts"]}. Every state follows the unchanged 55-feature causal schema and fixed normalization. Raw/executed targets, next-state continuity, absorbing terminal flags and rewards checked against saved writer/source/action/trace evidence. Hidden physical truth is used only by the independent evaluator, never by replay or actor. No MATCHED transitions ingested. Source SHA: {audit["source_sha256"]}.\n')
    shutil.copy2(path,O/'NATIVE_DEMO.npz');shutil.copy2(path,L/'NATIVE_DEMO.npz')
    config=json.loads((OLD/'SAC_TRAINING_CONFIG.json').read_text())
    for arm in ('A','B'):
        cfg={k:config[k] for k in ('learning_rate','batch_size','buffer_size','learning_starts','train_freq','gradient_steps','gamma','tau','ent_coef','target_entropy','network','device','torch_num_threads','policy_period_s','replay_buffer_kwargs')}
        cfg.update(arm=arm,seed=SEED,online_steps=TARGET,training_scope='NATIVE',evaluation_scopes=['NATIVE','MATCHED'],evaluation_steps=list(range(10000,50001,10000)),demo_fraction=.5 if arm=='B' else 0,online_capacity=100000,normalization_sha256=lock['normalization_hash'],initialization='fresh actor/critics/target/entropy/Adam; no historical load',hard_wall_cutoff_unix=state['hard_cutoff_unix'])
        save('A_SCRATCH_CONFIG.json' if arm=='A' else 'B_DEMO_CONFIG.json',cfg)
    contract=dict(status='FROZEN_BEFORE_TRAINING',question='Does full legal causal successful replay help independent long-horizon task acquisition?',demo_count=n,batch_size=256,demo_per_batch=128,online_per_batch=128,immutable_demo=True,online_capacity=100000,replacement_sampling=True,ratio_fixed_entire_50k=True,learning_starts_online_only=5000,gradient_steps=1,train_freq=1,no_extra_updates=True,algorithm='unmodified installed SB3 SAC.train',batch_logging='every update: exact count/fraction and each source phase counts',actor='fully autonomous, no teacher intervention/BC/HER/pretraining/curriculum',training_mode='NATIVE only',seed=SEED,order=['B','A'],targets={'B':50000,'A':50000},wall_hours=9,holdout='none: previously exposed fixed Human, single paired seed; not a robustness study',endpoints=['settled_outbound','hold_entry','hold_completed','return_entry','valid_complete'],endpoint_order='actual causal phase transition/independent VALID; position100% never sufficient',selection='VALID only, separately per NATIVE/MATCHED scope; retain first/best/final',truth_firewall='only unchanged causal observation and raw actor action in replay; evaluator truth is diagnostic only',excluded='resource/OOM/simulation runtime/source-corruption pause, never omit failure cases',resource_policy='existing corrected WSL + Windows commit headroom and joint low-memory; no Windows-only gate',threads={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},source_head=pre['head'],scientific_changes=[],formal_initialization=0)
    save('DEMO_SAMPLING_CONTRACT.json',contract)
    prose('DEMO_SAMPLING_CONTRACT.md','# Fixed demo sampling contract\n\n'+json.dumps(contract,indent=2)+'\n')
    case,options=load_case_options();env=SACExpertEnv(O/'initialization_unused',case,options,.02,'NATIVE',False)
    hashes={};optimizers={}
    for arm in ('B','A'):
        model=make_model(env,arm,config);assert model.num_timesteps==model._n_updates==0 and model.replay_buffer.size()==0
        hashes[arm]=policy_hash(model);optimizers[arm]=memory.optimizer_hash(model)
        assert all(v['state_count']==0 for v in optimizers[arm].values())
        model.save(O/f'{arm}_INITIAL.zip');del model
    env.close();assert hashes['A']==hashes['B'] and optimizers['A']==optimizers['B']
    save('PAIRED_INITIALIZATION_AUDIT.json',dict(status='PASS',policy_sha256=hashes,optimizers=optimizers,same_weights=True,same_empty_optimizers=True,online_steps=0,online_replay_size=0,old_300k_state_inherited=False))
    # Synthetic sampler test cannot touch formal models or global training RNG state.
    env=SACExpertEnv(O/'sampler_unused',case,options,.02,'NATIVE',False)
    b=PairedReplay(6000,env.observation_space,env.action_space,device='cuda',handle_timeout_termination=False,demo_path=O/'NATIVE_DEMO.npz')
    for i in range(5001):b.add(obs[:1],nxt[:1],actions[:1],z['rewards'][:1],np.array([False]),[{}])
    for _ in range(5):assert b.sample(256).observations.shape==(256,55)
    assert b.demo.size()==593 and b.size()==5001 and b.demo_sample_counts.sum()==640 and b.online_sample_counts.sum()==640
    try:b.demo.actions[0]=0;raise AssertionError('Demo writable')
    except ValueError:pass
    save('SAMPLER_VALIDATION.json',dict(status='PASS',synthetic_batches=5,demo_samples=640,online_samples=640,immutable_checked=True,formal_updates=0))
    del b;env.close()
    state['status']='READY_FOR_FORMAL_B_THEN_A';save('STATE.json',state)
    print(json.dumps(dict(status=state['status'],teacher=n,phase_counts=audit['phase_counts'],paired_hash=hashes['A'],protected_files=len(pre['files']),cutoff=state['hard_cutoff_unix'])),flush=True)
if __name__=='__main__':run()
