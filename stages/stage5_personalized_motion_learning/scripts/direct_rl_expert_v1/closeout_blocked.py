"""Close the user-defined safety stop with explicit unavailable results."""
from pathlib import Path
import sys,json,hashlib,subprocess,shutil,math,csv
from datetime import datetime,timezone
R=Path('/home/hank/coding/adaptive-traction-mpc-learning')
S=R/'stages/stage5_personalized_motion_learning'
D=S/'docs/direct_rl_expert_v1'
P=S/'scripts/direct_rl_expert_v1'
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/direct_rl_expert_work')
OUT=W/'output'

def load(p):return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def save(name,x):(D/name).write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')
def md(name,text):(D/name).write_text(text.rstrip()+'\n')
def git(*args):return subprocess.check_output(['git','-C',str(R),*args],text=True).strip()
assert git('branch','--show-current')=='codex/direct-rl-expert-v1'
probe=load(D/'SAFETY_ACTION_COMPATIBILITY_PROBE.json')
assert probe['probe_assertions_pass'] and len(probe['rows'])==8
frozen=load(D/'SOURCE_FINGERPRINTS.json')
changed=[p for p,h in frozen['protected_files'].items() if sha(R/p)!=h]
evidence_changed=[p for files in frozen['evidence_files'].values() for p,h in files.items() if sha(Path(p) if p.startswith('/') else R/p)!=h]
assert not changed and not evidence_changed
assert sha(D/'USER_REQUEST.txt')==frozen['user_request_sha256']
shutil.copy2(W/'closeout_blocked.py',P/'closeout_blocked.py')

gate={'A':'NOT_RUN: no Gym adapter replay','B':'NOT_RUN: no Gym expressivity validation','C':'NOT_RUN: no physical direct-action intervention','D':'NOT_RUN: zero/conservative action semantics only proposed','E':'NOT_RUN: no Gym complete-task validation','F':'NOT_RUN: failure ranking proposed but reward not tested','G':'NOT_RUN: terminated/truncated design only','H':'NOT_RUN: no actor observation implementation','I':'NOT_RUN: no Gym deterministic reset test'}
save('DIRECT_RL_ENV_VALIDATION.json',{'status':'BLOCKED','reason':'EXPANDED_PERIODIC_ACTION_INTERFACE_INCOMPATIBLE','gates':gate,'all_gates_pass':False,'gym_adapter_implemented':False,'main_training_permitted':False,'reference_compatibility_probe':'SAFETY_ACTION_COMPATIBILITY_PROBE.json','new_physical_rollouts':0,'scope':'reference arithmetic using frozen VALID source runs, not physical environment validation'})
table='|Task|Phase|Period ms|ddq jump rad/s²|Endpoint wait s|\n|---|---|---:|---:|---:|\n'+'\n'.join(f"|{x['condition_id']}|{x['phase']}|{x['policy_period_s']*1000:.0f}|{x['C2_acceleration_jump_rad_s2']:.9f}|{x['endpoint_deferred_effect_s']:.3f}|" for x in probe['rows'])
md('DIRECT_RL_ENV_VALIDATION.md',f'''# Direct RL environment validation — BLOCKED

No Gymnasium adapter has passed the A–I gates. Main SAC training is forbidden. No new physical rollout was performed.

Eight executable probes reconstructed the first OUTBOUND and RETURN schedules from two frozen VALID NATIVE baseline runs, using the authoritative quintic constructor and sampler. At each requested policy period, reissuing even the same endpoint preserves q/dq but resets reference acceleration to zero. The authoritative rolling splice rejects every such suffix because it joins at the ORIGINAL prefix endpoint. A control suffix starting at that endpoint is accepted, demonstrating that the exception is a boundary-semantic failure, not a general constructor failure.

{table}

Immediate arbitrary replacement: q/dq-only scheduler cannot preserve ddq. Delayed replacement: the certified old schedule remains active for 0.395–1.575 s in these first-segment probes, so the requested 20/50 ms action cannot take effect. These are reference-time deferrals, not host inference latency. Other segments were not exhaustively probed.

The live handoff validator explicitly requires new ddq = old ddq and also imposes zero new initial ddq. A general acceleration-aware C2 polynomial would fail the zero-initial-ddq predicate. Standard non-handoff activation does not compare the old ddq, so calling that path directly during a moving reference could conceal the discontinuity. Bypassing that check is not an allowed adapter repair.

Sources: human_waypoint_scheduler.py:180; full3d_adaptive_integration_v1/rolling_suffix_splice.py:21; activation_validation.py:144–149 and :212; runtime.py:3140–3152. See SOURCE_EVIDENCE.json for exact file hashes/line excerpts. This establishes a current integration incompatibility, not impossibility of safe direct RL or an observed learned-policy intervention fraction.

User section 18 explicitly requires stopping main training when existing safety is tied to the old action representation. Retaining the same physical/safety thresholds is mandatory. No safety thresholds, physical models, production code, historical evidence, or task endpoints were changed.
''')

md('DIRECT_RL_OBSERVATION_ACTION_SPEC.md','''# Proposed observation/action spec — NOT IMPLEMENTED

Action: float32 Box[-1,1]^2, independent hip/knee target changes at 20 or 50 ms. A candidate design maps each coordinate to a bounded target increment using registered per-joint motion limits and maintains the executed target. Independent signs/magnitudes allow synchronous, hip-leading, knee-leading, pause, catch-up, and distinct phase coordination without H1–H4/lattice projection. Exact scale is NOT selected. This expressivity has not been validated physically.

Zero requests no target change; it is not a claim that the Human or CR12 stops immediately. A conservative completion policy must still demonstrate outbound arrival, real HOLD dwell and RETURN settling.

Proposed normalized causal actor groups: estimated Human q/dq; receipt-owned q/dq/ddq reference; measured cuff force/moment; robot joint state and command state needed to realize reference; phase; original start/goal; normalized estimated progress; sensor-supported remaining time; previous RAW and EXECUTED action; deployable estimated geometry/dynamics belief, confidence, validity and source age. Use immutable observation-ready snapshots and fixed physical scales or training-only running normalization frozen at evaluation. Feature dimensions/scales await implementation audit. No RNN or history stack selected.

Excluded: physical-case hidden parameters, evaluation-only Human state, future state/wrench, oracle geometry, reference-winner identity, rewards or evaluation labels as actor inputs. Historical case/checkpoint ids remain reproduction metadata only.

Constraints to retain: registered Human ROM, task q bounds, velocity/acceleration, CR12/interface feasibility, continuous nonpenetrating clearance, causal source ages, phase deadlines, completion boxes and real HOLD/RETURN. Same official evaluator. v9 reference velocity fraction 0.5 and acceleration fraction 0.25 are conservative execution/pacing choices, not fundamental plant limits; they remain frozen for this attempted workflow and are disclosed separately.

Old planner preferences: candidate lattice, normalized coordination directions, maximum waypoint fraction, monotonic-progress candidate rejection, waypoint ranking penalties, endpoint-only action activation, zero-initial-ddq schedule convention. Do not relabel those preferences physical laws. The action design should remove the lattice/pattern preference, but the authoritative activation/escape certificates currently depend on the old segment contract. No preference or safety check was removed in this run.

Required next interface work: versioned current-q/dq/ddq reference origin; explicit raw proposal -> full polynomial safety certificate -> accepted/rejected command; safe fallback on rejection; log both raw/executed actions and exact rejection reason; verify causal clearance, mechanics, terminal/time/fallback validity through the same CR12 CPU-MuJoCo pathway before any reward or training gate can pass.
''')

attacks=['do nothing','abort early','stall before HOLD','skip RETURN','timeout','repeated safety rejection','shift load to moment']
save('DIRECT_RL_REWARD_AUDIT.json',{'status':'NOT_RUN_BLOCKED_BEFORE_REWARD_IMPLEMENTATION','reward_implemented':False,'reward_final_frozen':False,'cases':[{'case':x,'status':'NOT_RUN','return':None} for x in attacks],'proposed_terms':['negative measured cuff-force step integral','task potential difference','optional valid complete-task bonus','explicit failure penalty'],'forbidden_terms':['action magnitude reward','hip-leading preference','baseline deviation','CEM similarity'],'moment':'independent diagnostic and unchanged official safety acceptance; no arbitrary moment reward weight','ranking':'incomplete/unsafe episodes unranked, never compare early partial force integral as complete J_F','required_tests':'all seven attacks on real adapter; include discounted return and timeout bootstrap/terminal-potential semantics; numeric weights not chosen'})
md('DIRECT_RL_REWARD_AUDIT.md','''# Reward audit — NOT RUN

No reward was implemented or frozen. None of the seven required reward-hacking tests ran, so no no-hacking claim is made. Proposed reward terms and tests are recorded in JSON. Numeric shaping/completion/failure constants require real full-task return calibration. Every incomplete episode must remain excluded from scientific ranking. For shaped discounted reward, verify potential terminal handling and timeout bootstrap; a negative failure reward alone is not proof that early abort cannot win. Moment remains independent.
''')

comparison=load(S/'docs/best_known_coordination_search_v2/CONDITION_COMPARISON.json')
database=load(S/'docs/best_known_coordination_search_v2/BEST_KNOWN_REFERENCE_DATABASE.json')
comparators=[]
for entry in database['entries']:
    if entry['condition'] not in ('sync_120','low_ordinary_early'):continue
    cond,arm=entry['condition'],entry['matched_native_label']
    c=next(x for x in comparison['rows'] if x['condition']==cond and x['arm']==arm)
    root=S/'results/best_known_coordination_search_v2/runs'
    ids={'original_controller':f'A_{cond}_{arm}_baseline_0','preregistered_fixed_hip_leading':f'A_{cond}_{arm}_fixed_0','selected_universal_fixed':f'F_{cond}_{arm}_fixed'}
    selected=entry['result_path']
    # Exact run ids verified against campaign_v2.py's final FIXED entry.
    found={}
    for name in ('original_controller','preregistered_fixed_hip_leading','selected_universal_fixed'):
        p=root/ids[name]/'rollout_result.json'
        assert p.exists(), p
        found[name]=p
    for name,p in [*found.items(),('CEM_best_known',R/selected)]:
        v=load(p)
        comparators.append({'condition':cond,'arm':arm,'method':name,'source':'historical frozen evidence; not rerun this campaign','result_path':str(p.relative_to(R)),'result_sha256':sha(p),'status':v['status'],'J_F_n_s':v.get('J_F_task_n_s'),'mean_force_n':v.get('mean_force_n'),'rms_force_n':v.get('rms_force_n'),'peak_force_n':v.get('peak_force_n'),'moment_integral_nm_s':v.get('moment_integral_nm_s'),'moment_peak_nm':v.get('moment_peak_nm'),'duration_s':v.get('duration_s'),'minimum_clearance_m':v.get('minimum_clearance_m'),'comparability':'same historical condition and arm; direct RL not yet implemented/evaluated'})
    comparators.append({'condition':cond,'arm':arm,'method':'SAC','status':'NOT_TRAINED','J_F_n_s':None,'known_benefit_capture':None,'reason':'No validated direct RL policy; no direct-to-historical protocol comparability established'})
assert len(comparators)==20
save('CLOSEOUT_REPAIR_LOG.json',{'changes':[{'reason':'First draft comparison omitted selected universal fixed detailed metrics because its run id was incorrectly assumed. Exact F_<condition>_<arm>_fixed ids were checked against campaign_v2.py, then all four records were added. Narrative table values and blocked result did not change.','scientific_parameters_changed':False,'historical_evidence_changed':False}]})
save('SAC_VS_CONTROLLER_VS_CEM.json',{'status':'NO_SAC_COMPARISON_AVAILABLE','rows':comparators,'historical_source_commit':frozen['source_commit'],'interpretation':'Native timing may differ; matched has its frozen timing isolation criteria. CEM finite best-known, not global optimum. The selected universal fixed was neutral; retain preregistered beneficial sync comparator separately. No RL known-benefit capture is computable.'})
ctable='|Condition|Arm|Controller|Fixed hip-leading|Universal fixed|CEM best-known|SAC|\n|---|---|---:|---:|---:|---:|---|\n'
for x in comparison['rows']:
    if x['condition'] in ('sync_120','low_ordinary_early'):
        ctable+=f"|{x['condition']}|{x['arm']}|{x['baseline_J_F_n_s']:.6f}|{x['fixed_prior_J_F']:.6f}|{x['fixed_best_J_F']:.6f}|{x['best_known_J_F_n_s']:.6f}|not trained|\n"
md('SAC_VS_CONTROLLER_VS_CEM.md',f'''# Reference inventory — no SAC comparison

Historical measured J_F in N·s; these are frozen references, not new replays. Full force/moment/duration/clearance records with hashes are in JSON. The universal fixed comparator selected by cross-condition coverage is neutral; the preregistered hip-leading fixed comparator is beneficial on sync_120, adverse on ordinary low-ROM. Its ordinary MATCHED result was not timing-isolated. Both are preserved instead of calling the neutral fixed comparator universally strongest.

{ctable}
No direct RL policy exists. No known-benefit capture, superiority, global optimality, coordination/timing separation or seed reliability is claimed. Future direct comparisons require genuine condition/start/task and timing protocol equivalence; cross-arm minima must not be compared as isolated coordination gains.
''')

horizon=[]
for x in comparators:
    if x['method']!='original_controller':continue
    for period in (.02,.05):
        n=math.ceil(x['duration_s']/period-1e-8)
        for gamma in (.99,.999,.9995,1.):
            horizon.append({'condition':x['condition'],'arm':x['arm'],'historical_full_task_duration_s':x['duration_s'],'period_s':period,'estimated_decisions':n,'gamma_candidate':gamma,'effective_horizon_decisions':None if gamma==1. else 1/(1-gamma),'effective_horizon_seconds':None if gamma==1. else period/(1-gamma),'gamma_to_full_episode':gamma**n,'source':'historical task duration estimate only; actual direct episode unknown','gamma_one_note':'undiscounted candidate requires absorbing terminal and failure/timeout validation; not automatically selected' if gamma==1. else None})
save('DISCOUNT_HORIZON_CALIBRATION.json',{'status':'CANDIDATE_CALCULATION_ONLY','rows':horizon,'selected_gamma':None,'selected_period_s':None})
save('SAC_TRAINING_CONFIG.json',{'status':'PROPOSED_NOT_RUN','algorithm':'Stable-Baselines3 SAC','policy':'MlpPolicy','device':'cuda','network_architecture':[256,256],'learning_rate':.0003,'batch_size':256,'buffer_size':200000,'learning_starts':10000,'train_freq':1,'gradient_steps':1,'tau':.005,'ent_coef':'auto','target_entropy':'auto','gamma':None,'gamma_candidates':[.99,.999,.9995,1.],'policy_period_s':None,'seeds':[20261002,20261003],'observation_normalization':'not implemented; must freeze eval statistics','action_scale':None,'reward_configuration':None,'n_envs':1,'main_training_permitted':False,'source':'SB3 official SAC defaults; proposed bounded replay/warmup changes; not a frozen run config','url':'https://stable-baselines3.readthedocs.io/en/master/modules/sac.html'})
blocked_bench={'status':'NOT_RUN_SAFETY_GATE_BLOCKED','environment_steps_per_s':None,'simulation_seconds_per_s':None,'SAC_steps_per_s':None,'CPU_utilization':None,'GPU_utilization_during_training':None,'GPU_VRAM_during_training':None,'training_peak_RSS':None,'disk_write_rate':None,'workers_tested':0,'two_environments_tested':False,'diagnostic_probe_peak_RSS_KiB':probe['diagnostic_peak_RSS_KiB'],'diagnostic_RSS_is_not_training_RSS':True,'estimates_hours':{str(n):None for n in (100000,300000,1000000,2000000)},'reason':'No validated env; arithmetic probe speed or historical CEM rollout speed is not Direct RL throughput.'}
save('DIRECT_RL_THROUGHPUT_BENCHMARK.json',blocked_bench)
md('DIRECT_RL_THROUGHPUT_BENCHMARK.md','''# Throughput benchmark — NOT RUN

Environment-only, SAC CUDA learning and evaluation benchmarks did not run because expanded-action safety compatibility failed. No valid steps/s, simulation seconds/s, CPU/GPU training utilization, VRAM, disk write rate, training RSS or 100k/300k/1M/2M wall-time estimate exists. Two environments were not attempted. The ~648 MiB peak RSS of this JSON-reading/reference probe is not environment/training-worker RSS. Historical CEM throughput does not justify a Direct RL estimate.
''')
save('DIRECT_RL_RUNTIME_PROFILE.json',{'status':'NOT_RUN','actor_CPU_latency_ms':None,'actor_GPU_latency_ms':None,'full_action_latency_ms':None,'reason':'No trained actor or safe action-realization interface; endpoint deferral is reference time, not measured computation latency'})
md('DIRECT_RL_RUNTIME_PROFILE.md','''# Runtime profile — NOT RUN

No actor CPU/GPU latency or full observation-ready -> actor -> safety/action realization -> command-ready latency was measured. There is no evaluated actor. The probe's endpoint deferral is not inference or realtime timing qualification.
''')
for stem,columns in [('SAC_LEARNING_CURVE',['seed','condition','agent_steps','wall_time_s','success_rate','J_F_n_s','training_return']),('SAC_CHECKPOINT_EVALUATION',['seed','condition','checkpoint','agent_steps','status','J_F_n_s','moment_integral_nm_s','duration_s','clearance_m'])]:
    save(stem+'.json',{'status':'NOT_RUN','rows':[],'training_steps':0,'reason':'Safety/action compatibility gate failed; empty data is deliberate, no fabricated curve or checkpoint'})
    with (D/(stem+'.csv')).open('w',newline='') as f:csv.writer(f).writerow(columns)
save('SAC_BEST_POLICY_ANALYSIS.json',{'status':'NO_TRAINED_POLICY','best_valid_J_F':None,'checkpoints':0,'training_steps':0,'path_analysis':None,'safety_intervention_rate':None,'moment_outcome':None,'learning_trend':None,'seed_reliability':None})
md('SAC_BEST_POLICY_ANALYSIS.md','''# Best policy analysis — unavailable

No SAC model was trained or evaluated. No best policy, actual hip/knee trajectory, lead/lag, force/moment timeline, safety timeline, discovered coordination, intervention frequency, seed reliability or end-of-training trend is available. Reference compatibility probes are not learned-policy rejection statistics.
''')

facts=[('Quintic origin is q/dq only, initial ddq is zero','human_waypoint_scheduler.py','def _quintic_coefficients',29),('Rolling splice uses original segment endpoint','full3d_adaptive_integration_v1/rolling_suffix_splice.py','    def __post_init__',13),('Activation includes zero-initial-ddq convention','full3d_adaptive_integration_v1/activation_validation.py','def validate_activation',11),('Live handoff compares reference acceleration','full3d_adaptive_integration_v1/activation_validation.py','        live_c2',1),('Runtime task requests occur at endpoints','full3d_adaptive_integration_v1/runtime.py','        if online_timing and async_pending is None and (',13),('No-regression rule is old planner preference','human_waypoint_feedback_mpc.py','        if np.any(reference_remaining *',15)]
excerpts=[]
for label,rel,needle,count in facts:
    path=S/'src/traction_mpc_stage5'/rel
    lines=path.read_text().splitlines()
    i=next(i for i,t in enumerate(lines) if needle in t)
    excerpts.append({'claim':label,'file':str(path.relative_to(R)),'sha256':sha(path),'start_line':i+1,'end_line':i+count,'excerpt':'\n'.join(lines[i:i+count])})
save('SOURCE_EVIDENCE.json',{'excerpts':excerpts})
answers=[
('Is the new environment physically equivalent enough?','Not established. No Gym environment passed validation. Underlying protected physical/controller/config sources and historical evidence stayed hash-identical.'),
('Does the action interface express more coordination freedom?','Proposed independent continuous 2-D target changes would; no implemented safe interface demonstrates that freedom. Existing endpoint activation blocks immediate periodic commands.'),
('Can SAC reliably complete the full task?','Unknown; zero training/evaluation episodes.'),
('Best VALID SAC J_F?','Unavailable; no trained checkpoint.'),
('Comparison with controller/fixed/CEM?','Only historical frozen reference inventory is available. No SAC comparison or benefit capture.'),
('Different hip/knee coordination path?','Unknown; no learned path.'),
('Gain from coordination or timing?','Unknown; no gain measured. Native historical references may include timing.'),
('Moment outcome?','Historical comparator moment metrics retained; no SAC moment outcome.'),
('How often does safety modify/reject SAC?','Unmeasured. Eight reference splice failures are diagnostic probes, not learned-policy intervention frequency.'),
('Does safety suppress much RL behavior?','Current interface demonstrably cannot immediately realize these periodic reference replacements. Closed-loop suppression fraction is unmeasured; no global safety-layer verdict.'),
('Learning curve still improving?','No learning curve.'),
('More training justified?','Training cannot be judged before environment/safety compatibility. More steps on current interface are not authorized.'),
('Environment/training throughput?','Unmeasured; no valid adapter. Probe throughput is not training throughput.'),
('GPU utilized?','GPU visible (RTX 4060 Laptop, 8188 MiB), no training utilization. Scientific Python has no torch; capstone Python has torch 2.14.0+cpu, CUDA runtime None, availability False. No CPU main training.'),
('CPU bottleneck?','Not measured. Source inspection shows CPU physics, mechanics/clearance certificates and reference control; do not assign dominance without profiling.'),
('1M/2M wall time?','Unavailable because Direct RL steps/s was not measured.'),
('Inference/full action latency?','Unmeasured; no evaluated actor/safe action pipeline.'),
('Next campaign priority?','Environment/safety action-realization redesign and revalidation first, CUDA package repair second, then the originally requested SAC pilot. No TQC/PPO/hardware or multi-day campaign launched.')]
save('DIRECT_RL_V1_REPORT.json',{'state':'DIRECT_RL_SAC_V1_BLOCKED','answers':[{'number':i+1,'question':q,'answer':a} for i,(q,a) in enumerate(answers)],'main_training_steps':0,'stop_source':'User request section 18','blocker':'EXPANDED_PERIODIC_ACTION_INTERFACE_INCOMPATIBLE'})
md('DIRECT_RL_V1_REPORT.md',f'''# Direct RL Expert Search v1

**DIRECT_RL_SAC_V1_BLOCKED** — stopped at the user-defined expanded-action safety gate, before Gym validation or SAC training.

Branch `codex/direct-rl-expert-v1` was created from clean `7bfe141308cacb2d23cf544aa5942e0337bccaed`. Frozen 365 physical/controller/config source files and 170 historical/audit evidence files remained identical at closeout. Original zero-value, coordination and value-learning HEADs match reachable origin branches. The latest best-known v2 branch is local-only; its HEAD and database/evidence hashes are pinned. No merge/force push or history rewrite occurred.

Resource preflight: host RAM 16,890,322,944 bytes; WSL 7.6 GiB total, ~7 GiB available, 2 GiB unused swap; C: ~85 GiB free, WSL ~878 GiB free, Linux process count 77 initially. GPU NVIDIA RTX 4060 Laptop, driver 560.94, 8188 MiB VRAM; WSL GPU query ~7957 MiB free. CPU/RAM/swap/disk/process/GPU records are in RESOURCE_PREFLIGHT.json. One environment maximum was planned; no environment worker was started, and two environments were not attempted.

The primary blocker is the authoritative action/safety representation. At 20 and 50 ms in both conditions/phases, reissuing the same target via the existing q/dq-only quintic creates a ddq discontinuity (0.076–2.070 rad/s² in first-segment probes). Existing rolling suffix rejects it; accepted endpoint suffixes defer effects 0.395–1.575 s. Live activation requires zero initial ddq while C2 requires matching nonzero moving-reference ddq. A naive standard-activation call would fail to compare the old ddq. Removing continuity checks, declaring this immediate direct control, or restricting all actor commands to old endpoints would not satisfy the request. Probe assertions passed; environment A–I gates did not run or pass.

User section 18: “If current safety layer is demonstrably tied to the old action representation and cannot correctly screen the expanded RL action: STOP main training and report the exact incompatibility.” This is the stop applied here. It does not establish that safe direct RL is impossible or that SAC failed to learn.

Secondary preflight issue: scientific Python lacks PyTorch/Gymnasium/SB3; existing capstone environment has CPU-only torch 2.14.0+cpu, despite visible WSL GPU. CUDA package setup remains unresolved. No packages were installed because the earlier safety stop blocks the main campaign. A supported CUDA wheel needs installation and verification in the scientific environment before a resumed training campaign. This is not an unavailable-GPU claim. CPU MuJoCo path is unchanged.

No Gym environment, reward audit, 100k pilot, checkpoint evaluation, second seed, action/path analysis, throughput benchmark or inference/full action timing was completed. Required downstream output files explicitly say NOT_RUN and contain null/empty values. Hyperparameters/action/observation/reward files are proposed designs, not validated/frozen training results. No 1M/2M estimate is invented from historical CEM or arithmetic probes.

## Final questions

'''+ '\n\n'.join(f'{i+1}. **{q}** {a}' for i,(q,a) in enumerate(answers))+'''

## Required next work

Version an acceleration-aware reference realization interface carrying current receipt-owned q/dq/ddq through full continuous clearance/mechanics, midsegment activation and prevalidated fallback. Preserve all ROM, velocity/acceleration, clearance, deadline, task endpoint/HOLD/RETURN and physical interaction gates. Validate baseline equivalence and continuous action effects before reward-hacking/rate/throughput/SAC gates. Keep lattice/monotonic-progress preferences separate from physical constraints. This redesign was not silently performed in this workflow.

Official method sources consulted: [SB3 SAC](https://stable-baselines3.readthedocs.io/en/master/modules/sac.html), [Gymnasium Env](https://gymnasium.farama.org/api/env/), [PyTorch CUDA wheels](https://pytorch.org/get-started/previous-versions/). They informed proposed integration/package diagnostics, not a claim of completed training.

Git closeout: new campaign files may be staged individually under the user's stage instruction; commit and push were not explicitly authorized in this chat, and repository AGENTS.md requires separate exact authorization. No commit/push/merge was performed. Training and physical processes are absent. Compact evidence only; no raw training/replay buffer/checkpoint artifacts or destructive cleanup. See RAW_DATA_MANIFEST.json.
''')
save('FINAL_FINGERPRINT_VERIFICATION.json',{'status':'PASS','protected_count':len(frozen['protected_files']),'historical_evidence_count':sum(map(len,frozen['evidence_files'].values())),'protected_changes':changed,'historical_evidence_changes':evidence_changed,'contract_sha256':sha(D/'DIRECT_RL_V1_CONTRACT.json'),'user_request_sha256':sha(D/'USER_REQUEST.txt')})
save('STATE.json',{'status':'DIRECT_RL_SAC_V1_BLOCKED','phase':'CLOSEOUT','closed_utc':datetime.now(timezone.utc).isoformat(),'blocker':'EXPANDED_PERIODIC_ACTION_INTERFACE_INCOMPATIBLE','stop_rule':'User section 18','source_commit':frozen['source_commit'],'branch':git('branch','--show-current'),'main_training_started':False,'training_steps':0,'environment_validation_pass':False,'next_action':'New explicitly scoped acceleration-aware safety/action interface workflow, then original A-I/reward/rate/CUDA/throughput gates; do not automatically resume training','push_authorized':False,'committed':False,'pushed':False,'merged':False})
required=['DIRECT_RL_V1_CONTRACT.md','DIRECT_RL_V1_CONTRACT.json','DIRECT_RL_ENV_VALIDATION.md','DIRECT_RL_ENV_VALIDATION.json','DIRECT_RL_OBSERVATION_ACTION_SPEC.md','DIRECT_RL_REWARD_AUDIT.md','DIRECT_RL_REWARD_AUDIT.json','DIRECT_RL_THROUGHPUT_BENCHMARK.md','DIRECT_RL_THROUGHPUT_BENCHMARK.json','SAC_TRAINING_CONFIG.json','SAC_LEARNING_CURVE.csv','SAC_LEARNING_CURVE.json','SAC_CHECKPOINT_EVALUATION.csv','SAC_CHECKPOINT_EVALUATION.json','SAC_BEST_POLICY_ANALYSIS.md','SAC_BEST_POLICY_ANALYSIS.json','SAC_VS_CONTROLLER_VS_CEM.md','SAC_VS_CONTROLLER_VS_CEM.json','DIRECT_RL_RUNTIME_PROFILE.md','DIRECT_RL_RUNTIME_PROFILE.json','DIRECT_RL_V1_REPORT.md','STATE.json']
assert all((D/x).is_file() for x in required)
assert load(D/'STATE.json')['training_steps']==0
assert not load(D/'DIRECT_RL_ENV_VALIDATION.json')['all_gates_pass']
assert len(load(D/'SAC_LEARNING_CURVE.json')['rows'])==0
assert len(load(D/'SAC_CHECKPOINT_EVALUATION.json')['rows'])==0
assert all(x['J_F_n_s'] is None for x in comparators if x['method']=='SAC')
for x in comparators:
    if x['method']=='SAC':continue
    assert x['status']=='VALID'
    assert all(x[k] is not None for k in ('mean_force_n','rms_force_n','peak_force_n','moment_integral_nm_s','moment_peak_nm','duration_s','minimum_clearance_m'))
save('CLOSEOUT_VALIDATION.json',{'status':'PASS','required_output_presence_only':True,'required_outputs':required+['RAW_DATA_MANIFEST.json'],'required_output_count':len(required)+1,'outputs_do_not_imply_completed_stages':True,'all_json_parseable':True,'comparison_rows':len(comparators),'missing_historical_metrics':0,'SAC_metric_values_all_null':True,'empty_curve_and_checkpoint_data':True,'source_fingerprint_check':'PASS','training_permitted':False,'actual_stage_status':'BLOCKED_BEFORE_GYM_IMPLEMENTATION'})
files=[p for root in (D,P) for p in root.iterdir() if p.is_file() and p.name!='RAW_DATA_MANIFEST.json']
save('RAW_DATA_MANIFEST.json',{'schema':'direct_rl_v1_retention','status':'BLOCKED_COMPACT_CLOSEOUT','files':[{'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p),'retention_class':'KEEP','purpose':'reproducible preflight/source contract/safety diagnosis and unavailable-result closeout'} for p in sorted(files)],'training_raw_bytes':0,'replay_buffer_saved':False,'model_checkpoints':0,'new_high_frequency_physics_traces':0,'bulk_cleanup_performed':False,'self_hash_note':'Manifest excluded from its own inventory','historical_raw':'untouched; reference artifacts pinned by source hashes','large_artifacts':[]})
for p in D.glob('*.json'):load(p)
for x in load(D/'RAW_DATA_MANIFEST.json')['files']:
    assert sha(R/x['path'])==x['sha256']
OUT.mkdir(exist_ok=True)
for p in D.iterdir():
    if p.is_file():shutil.copy2(p,OUT/p.name)
print(json.dumps({'status':'DIRECT_RL_SAC_V1_BLOCKED','probe_rows':len(probe['rows']),'protected_verified':len(frozen['protected_files']),'historical_verified':sum(map(len,frozen['evidence_files'].values())),'docs':str(D),'local_output':str(OUT),'bytes':sum(x.stat().st_size for x in D.iterdir() if x.is_file()),'training_steps':0,'comparison_rows':len(comparators)}))
