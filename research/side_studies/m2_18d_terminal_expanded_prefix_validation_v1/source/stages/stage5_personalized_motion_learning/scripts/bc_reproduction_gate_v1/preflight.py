from common import *
import inspect, importlib.metadata

def run():
    assert not D.exists() and not O.exists(), 'REFUSE_OVERWRITE'
    for folder in (P,D,O,L): folder.mkdir(parents=True,exist_ok=True)
    def git(*args): return subprocess.check_output(['git',*args],cwd=R,text=True)
    tracked=git('ls-files','-z').split('\0'); others=git('ls-files','--others','--exclude-standard','-z').split('\0')
    protected={p:sha(R/p) for p in set(tracked+others) if p and (R/p).is_file()}
    for folder in (PREVIOUS,DEMO.parent,OLD):
        for path in folder.rglob('*'):
            if path.is_file(): protected[str(path.relative_to(R))]=sha(path)
    before=dict(branch=git('branch','--show-current').strip(),head=git('rev-parse','HEAD').strip(),
                status=git('status','--short'),index=git('ls-files','--stage'),files=protected,
                previous_branch_ref=git('rev-parse','refs/heads/codex/demo-assisted-sac-task-acquisition-v1').strip())
    save('PRESERVATION_BEFORE.json',before)
    assert before['branch']=='codex/demo-assisted-sac-task-acquisition-v1'
    subprocess.run(['git','switch','-c',BRANCH],cwd=R,check=True)
    assert git('ls-files','--stage')==before['index']
    for path in (W/NAME).glob('*.py'): shutil.copy2(path,P/path.name)
    shutil.copy2(W/NAME/'USER_REQUEST.txt',D/'USER_REQUEST.txt')
    lock=json.loads((PREVIOUS/'SCIENTIFIC_LOCK.json').read_text()); save('SCIENTIFIC_LOCK.json',lock)
    for path,h in lock['files'].items(): assert sha(R/path)==h,path
    z=np.load(DEMO); obs=z['observations']; nxt=z['next_observations']; actions=z['actions']
    assert obs.shape==nxt.shape==(593,55) and actions.shape==(593,2)
    assert obs.dtype==nxt.dtype==actions.dtype==np.float32
    assert np.isfinite(obs).all() and np.isfinite(nxt).all() and np.isfinite(actions).all()
    assert np.max(np.abs(actions))<=1
    np.testing.assert_array_equal(nxt[:-1],obs[1:])
    phases=np.array(['OUTBOUND','HOLD','RETURN'])[obs[:,41:44].argmax(1)]
    np.testing.assert_array_equal(phases,z['phase'])
    assert not z['terminated'][:-1].any() and z['terminated'][-1] and not z['truncated'].any()
    np.testing.assert_allclose(obs[:,44]*30,z['task_s'],atol=2e-6,rtol=0)
    norm=json.loads((OLD/'SAC_OBSERVATION_NORMALIZATION.json').read_text())
    audit=json.loads((PREVIOUS/'DEMO_DATA_AUDIT.json').read_text())
    assert audit['features']==feature_spec() and audit['source_sha256']==sha(DEMO)
    original=np.load(audit['source']); np.testing.assert_array_equal(actions,original['actions'])
    evidence=np.load(Path(audit['source']).parent/'SAC_ACTOR_ACTIONS.npz')
    np.testing.assert_array_equal(actions,evidence['raw_action'])
    np.testing.assert_allclose(actions,evidence['executed_action'],atol=2e-7,rtol=0)
    np.testing.assert_array_equal(nxt[:-1,49:51],actions[:-1])
    np.testing.assert_allclose(nxt[:-1,51:53],evidence['executed_action'][:-1],atol=2e-7,rtol=0)
    counts={p:int(np.sum(phases==p)) for p in ('OUTBOUND','HOLD','RETURN')}
    assert counts==dict(OUTBOUND=272,HOLD=35,RETURN=286)
    validation=np.concatenate([np.flatnonzero(phases==p)[4::5] for p in counts])
    train=np.setdiff1d(np.arange(593),validation)
    spec=dict(status='FROZEN_BEFORE_TRAINING_OR_CLOSED_LOOP',question='Can the unchanged deployable 55-D SAC actor representation autonomously reproduce the complete native teacher task?',
        seeds=[20261004,20261005,20261006],scope='NATIVE',initial_condition_seed=20261003,
        architecture='installed SB3 2.6.0 Actor: Flatten -> 256 ReLU -> 256 ReLU -> Gaussian mean 2 -> tanh; native log_std head frozen; no critic instantiated',
        observation='same fixed scale normalized 55-D float32; no new inputs, statistics or renormalization',
        action='raw Box[-1,1]^2; native deterministic squashed mean; identity unscale; absolute 0..125deg hip/knee targets',
        dataset=dict(path=str(DEMO),sha256=sha(DEMO),count=593,phase_counts=counts),
        split=dict(train_indices=train.tolist(),validation_indices=validation.tolist(),method='each fifth sample within phase, deterministic before training; correlated single trajectory interpolation validation, not independent robustness'),
        objective='mean((native_deterministic_action - teacher_raw_action)^2)',
        sampling=dict(method='phase-balanced replacement minibatches',per_phase_per_batch=96,batches_per_epoch=3,phase_weights=[1/3]*3,seed='initialization seed + 1000; local numpy generator'),
        optimizer=dict(name='Adam',learning_rate=.0003,weight_decay=0.,scheduler=None),
        budget=dict(max_epochs=5000,min_epochs=1000,evaluate_every_epochs=20,early_stopping_patience_epochs=600,balanced_validation_mse_min_delta=1e-7,training_total_wall_s=600),
        selection='lowest balanced validation action MSE per seed; all three seeds finish and offline gate frozen before any BC closed-loop result; no closed-loop tuning',
        offline_gate=dict(MAE_max=.005,RMSE_max=.01,per_phase_RMSE_max=.015,max_abs_error_max=.05,units='raw normalized action; respectively .3125/.625/.9375/3.125 degree',policy='all preregistered seeds must pass full teacher-dataset gate before closed-loop; otherwise BC_REPRESENTATION_FIT_FAILED and STOP'),
        primary_pass='at least one preregistered seed: unchanged settled OUTBOUND, continuous HOLD, RETURN COMPLETE and independent R2 physical/scientific VALID; independently replay best VALID checkpoint once',
        best_selection='VALID first, then lowest J_F; if none VALID, highest synchronized outbound progress then lowest seed; does not feed training',
        deviation=dict(time_aligned='nearest teacher task time; phase mismatch explicitly marked',nearest_comparable='same phase, current deployable observation Euclidean distance after removing constants by arithmetic cancellation; post-run only; no trajectory index input',first_significant='first 5 consecutive policy samples with time-aligned normalized observation L2 > .25; report whether phase-aligned',causal_coverage='clock/phase/history are existing 55-D inputs; elapsed time is permitted, extra trajectory index is forbidden'),
        data_retention='high-frequency teacher, best replay and one representative failure only; other evaluations policy-rate arrays + metrics; offline predictions/loss curves/checkpoints all seeds',
        exclusions='no failed seed excluded; source mismatch/resource/implementation exception is separately blocked/incomplete, never scientific success',
        firewall='teacher observations/actions used only offline training and post-run diagnostics; standalone BC evaluator never loads teacher data while physics runs; hidden truth evaluation only',
        prohibited=['SAC update','critic','reward optimization','inherited actor/critic/replay optimizer','DAgger','curriculum','HER','PPO','TQC','physical/scientific edits','hardware'],
        branch=BRANCH,source_head=before['head'],scientific_changes=[],human='commissioning_only frozen R2',policy_period_s=.02)
    save('PREREGISTRATION.json',spec); save('PREREGISTRATION_SHA256.json',dict(sha256=sha(D/'PREREGISTRATION.json')))
    save('OBSERVATION_NORMALIZATION.json',norm)
    save('DATA_AUDIT.json',dict(status='PASS',phase_counts=counts,teacher_sha256=sha(DEMO),features=feature_spec(),double_normalization=False,causal_features_unchanged=True,raw_executed_actions_verified=True,termination_verified=True))
    source={str(p.relative_to(R)):sha(p) for p in P.glob('*.py')}
    save('EXPERIMENT_SOURCE_LOCK.json',source)
    save('ENVIRONMENT.json',dict(python=sys.version,executable=sys.executable,packages={n:importlib.metadata.version(n) for n in ('torch','stable-baselines3','numpy','mujoco','gymnasium')},cuda_available=torch.cuda.is_available(),actor_source_sha256=sha(inspect.getfile(Actor)),command='wsl -d Ubuntu -- bash /mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/bc_reproduction_gate_v1/launch.sh',single_physics_owner=True))
    resource('PREFLIGHT'); state('PREREGISTERED_TEACHER_REPRODUCTION_NEXT',protected_files=len(protected),phase_counts=counts)

if __name__=='__main__': run()
