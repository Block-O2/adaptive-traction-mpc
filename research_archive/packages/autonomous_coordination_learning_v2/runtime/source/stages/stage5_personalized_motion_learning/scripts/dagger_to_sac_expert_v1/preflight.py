from common import *
def run():
    assert not D.exists() and not O.exists() and not L.exists(),'NEW_CAMPAIGN_ALREADY_EXISTS'
    def git(*args):return subprocess.check_output(['git','-C',str(R),*args],text=True).strip()
    pre=dict(branch=git('branch','--show-current'),head=git('rev-parse','HEAD'),status=git('status','--short'),
             index=git('ls-files','--stage'),remote=git('remote','-v'))
    files={}
    # Include historical docs/scripts/configs/source; all large historical replay weights remain untouched.
    for group in ('src','configs','docs','scripts'):
        for p in (S/group).rglob('*'):
            if p.is_file() and '__pycache__' not in str(p):files[str(p.relative_to(R))]=sha(p)
    D.mkdir();L.mkdir();O.mkdir()
    save('PRESERVATION_BEFORE.json',dict(**pre,files=files))
    assert not git('branch','--list',BRANCH)
    subprocess.run(['git','-C',str(R),'switch','-c',BRANCH],check=True)
    assert git('ls-files','--stage')==pre['index']
    old=json.loads((S/'docs/bc_reproduction_gate_v1/SCIENTIFIC_LOCK.json').read_text())
    save('SCIENTIFIC_LOCK.json',old)
    shutil.copy2(P/'USER_REQUEST.txt',D/'USER_REQUEST.txt')
    z=np.load(DEMO)
    # Calibrate the existing 1.5s lead-release boundary using its causal posture,
    # then discard trajectory position/time from the executable expert.
    k=int(np.flatnonzero(z['task_s']>=1.5)[0]) if 'task_s' in z else 75
    raw=z['observations'][k]*SCALES
    spec=dict(question='Can unchanged 55-D/2-D imitation -> SAC reliably complete and improve task?',
        category='formal, previously exposed nominal Human; deterministic repeats are not robustness holdouts',
        development_split='Expert development uses archived causal teacher and three fixed BC-prefix states; no tuning after gate',
        heldout_split='Pure-student rollouts exclude teacher execution, dataset reads and expert queries; same exposed nominal case',
        truth_firewall='Expert accepts only observation(55), reference q/dq/ddq contained therein, phase and elapsed clocks; no plant/env/trajectory/index argument',
        expert=dict(kind='causal state/reference-gated hip-leading terminal controller',
            estimated_hip_release_rad=float(raw[0]),reference_hip_release_rad=float(raw[4]),
            knee_preview_rad=.02,calibration_source=str(DEMO),calibration_sha256=sha(DEMO),
            calibration='causal posture at existing fixed teacher release; no trajectory lookup during query',
            gate_prefixes=[dict(seed=20261004,index=75),dict(seed=20261005,index=150),dict(seed=20261006,index=300)],
            gate='All 3 exact archived BC prefixes: legal labels, first action certified, positive synchronized progress within next 2s unless already terminal, and complete independent VALID continuation. Nominal expert also VALID.'),
        task=dict(start_deg=[5,10],goal_deg=[120,120],phases=['OUTBOUND','HOLD','RETURN'],period_s=.02,Human='nominal',mode='commissioning_only',science_unchanged=True),
        seed=20261004,initial_condition_seed=20261003,
        dagger=dict(max_rounds=8,collection_rollouts=3,evaluation_rollouts=3,beta=[.5,.25,.1,0,0,0,0,0],
            qualification='Two consecutive rounds each >=3/3 pure deterministic independent VALID; no teacher execution/intervention',
            architecture=[55,256,256,2],initial_teacher_dataset=str(DEMO),optimizer='Adam',learning_rate=.0003,
            initial_updates=18000,round_updates=18000,batch_size=288,phase_sampling='96 samples each phase, with replacement; all difficult states retained',
            selection='fixed final-update checkpoint; no offline fit gate; never select using qualification results'),
        sac=dict(max_online_steps=100000,eval_interval=10000,eval_rollouts=3,initial_random_warmup_steps=0,
            replay='all executed DAgger transitions plus successful pure student evaluation transitions; actions are actually executed raw policy commands, never counterfactual expert labels',
            actor_init='qualified native actor weights; exact deterministic identity verified; fresh critics/targets/optimizers',
            demo_fraction_first_50k=.25,demo_fraction_after_50k_if_stable=.10,
            stable='Previous two NATIVE checkpoints each >=3/3 VALID; otherwise keep .25',
            success_loss='Two consecutive NATIVE checkpoints <=1/3 VALID: save last good, freeze actor, STOP',
            log_std_init=-4.,learning_rate=.0003,batch_size=256,buffer_size=100000,gamma=gamma_for(.02),tau=.005,
            ent_coef='auto',target_entropy='auto',train_freq=1,gradient_steps=1,extra_losses=[],
            timeout_bootstrap=False,comparator='qualified DAgger / fixed hip-leading / CEM / original controller, separate NATIVE and MATCHED; VALID only J_F rank; new best independently replayed at 1e-6 J_F tolerance'),
        exclusions='none; all failures and difficult states retained',budget=dict(target_wall_hours=[6,10],hard_wall_hours=12,physics_owners=1,physics='MuJoCo CPU',NN='CUDA'),
        stopping=['EXPERT_QUERY_INTERFACE_BLOCKED','SCIENTIFIC_CONTRACT_OR_SAFETY_BROKEN','DAGGER_8_ROUNDS_UNQUALIFIED','SAC_ABILITY_LOST','NAN_RESOURCE_EVIDENCE_CORRUPTION','HARD_WALL_CAP'])
    save('PREREGISTRATION.json',spec);save('PREREGISTRATION_SHA256.json',dict(sha256=sha(D/'PREREGISTRATION.json')))
    state('EXPERT_GATE_PENDING',branch=BRANCH,source_head=pre['head'],started_unix=time.time(),hard_cutoff_unix=time.time()+12*3600,
          dagger_rounds=0,sac_started=False,online_steps=0,next_action='Run fixed causal expert query/recovery gate on exact archived BC prefixes.')
    save('EXPERIMENT_SOURCE_LOCK.json',{p.name:sha(p) for p in P.glob('*.py')})
    resource('PREFLIGHT')
    save('ENVIRONMENT.json',dict(torch=torch.__version__,cuda=torch.cuda.is_available(),gpu=torch.cuda.get_device_name(0),
        python=sys.version,uname=subprocess.check_output(['uname','-a'],text=True),mujoco=__import__('mujoco').__version__,
        sb3=__import__('stable_baselines3').__version__,normalization=feature_spec()))
    assert torch.cuda.is_available()
    print(json.dumps(dict(phase='FROZEN',expert_thresholds=spec['expert'],historical_files=len(files))),flush=True)
if __name__=='__main__':run()
