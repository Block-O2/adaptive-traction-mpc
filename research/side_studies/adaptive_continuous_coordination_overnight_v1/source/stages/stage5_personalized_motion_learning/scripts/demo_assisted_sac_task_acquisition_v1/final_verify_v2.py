"""Lightweight final provenance and compact-output reconciliation; no training imports."""
from pathlib import Path
import json,hashlib,subprocess,csv,shutil,time
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_overnight_v1/source');S=R/'stages/stage5_personalized_motion_learning';NAME='demo_assisted_sac_task_acquisition_v1'
D=S/'docs'/NAME;O=S/'results'/NAME;P=S/'scripts'/NAME
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/NAME;L=W/'output'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def read(name):return json.loads((D/name).read_text())
def save(name,data):
    for root in (D,L):(root/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True).strip()
def run():
    required=['DEMO_DATA_AUDIT.md','DEMO_DATA_AUDIT.json','DEMO_SAMPLING_CONTRACT.md','DEMO_SAMPLING_CONTRACT.json','PAIRED_INITIALIZATION_AUDIT.json','A_SCRATCH_CONFIG.json','B_DEMO_CONFIG.json','A_LEARNING_CURVE.csv','B_LEARNING_CURVE.csv','A_EVALUATION.csv','B_EVALUATION.csv','PHASE_COVERAGE_COMPARISON.json','DEMO_SAMPLING_STATISTICS.json','SAC_HEALTH_COMPARISON.json','FIRST_SUCCESS_EVIDENCE.md','FIRST_SUCCESS_EVIDENCE.json','BEST_VALID_POLICY_ANALYSIS.md','BEST_VALID_POLICY_ANALYSIS.json','TASK_ACQUISITION_COMPARISON.md','STATE.json','RAW_DATA_MANIFEST.json']
    assert all((D/p).is_file() and (L/p).is_file() for p in required)
    state=read('STATE.json');assert state['status']=='PAIRED_50K_COMPLETE_STOP'
    res=read('ARM_RESULTS.json');evaluations=read('ALL_EVALUATIONS.json');sampling=read('DEMO_SAMPLING_STATISTICS.json')
    for a in ('A','B'):
        assert res[a]['steps']==50000 and res[a]['updates']==45000 and sampling[a]['batch_count']==45000
        assert len(evaluations[a])==12
        assert {(r['training_step'],r['scope'],r['tag']) for r in evaluations[a]}=={(n,s,t) for n,t in [(10000,'periodic'),(20000,'periodic'),(30000,'periodic'),(40000,'periodic'),(50000,'periodic'),(50000,'final')] for s in ('NATIVE','MATCHED')}
        b=json.loads((Path(res[a]['final_bundle'])/'BUNDLE.json').read_text());assert b['step']==b['online_size']==50000 and b['updates']==b['sampler_calls']==45000
        for name,h in b['files'].items():assert sha(Path(res[a]['final_bundle'])/name)==h
        with (O/f'{a}_BATCH_SAMPLING.csv').open() as f:rows=list(csv.DictReader(f))
        assert [int(r['batch']) for r in rows]==list(range(1,45001))
        assert [int(r['online_steps']) for r in rows]==list(range(5001,50001))
    assert read('EXACT_A_PHYSICS_RESTORATION.json')['status']=='PASS'
    assert read('PENDING_STANDARD_UPDATE_ACCOUNTING.json')['extra_updates']==0
    assert read('PAIRED_INITIALIZATION_AUDIT.json')['first_5000_random_actions_identical']
    pre=read('PRESERVATION_BEFORE.json');assert all(sha(R/p)==h for p,h in pre['files'].items())
    for name in ('EXPERIMENT_SOURCE_LOCK.json','RECOVERY_SOURCE_LOCK.json'):
        assert all(sha(p)==h for p,h in read(name)['files'].items())
    assert git('branch','--show-current')=='codex/demo-assisted-sac-task-acquisition-v1'
    assert git('rev-parse','HEAD')==git('rev-parse','codex/single-human-sac-expert-v1')==pre['head']
    old_index=dict(x.split('\t',1)[::-1] for x in pre['index'].splitlines());new_index=dict(x.split('\t',1)[::-1] for x in git('ls-files','--stage').splitlines())
    assert all(new_index.get(p)==v for p,v in old_index.items())
    assert time.time()<state['hard_cutoff_unix']
    settling=read('OUTBOUND_SETTLING_AUDIT.json');final={a:next(r for r in settling['rows'].values() if r['arm']==a and r['training_step']==50000 and r['scope']=='NATIVE' and r['tag']=='final') for a in ('A','B')}
    annotation=['','## Monitor repair and exact continuation','', 'At A10k, an unconditional process-tree PSS >4.5 GiB gate introduced in the orchestration caused a false pause during evaluation. The existing corrected monitor uses this gate only during training after55k steps; neither arm reaches that condition. The saved original source, stop exception and resource samples retain the defect transparently. See MONITOR_GUARDFIX_V2.md and EXACT_A_PHYSICS_RESTORATION.json.','', 'A resumed from its own10k checkpoint. All419 prior actor transitions in the open episode were reconstructed, with bitwise equality of observation, next observation, float32 reward and done flags. Optimizers, replay, sampler state and global RNG were restored. This reconstruction generated no new online samples or updates. The one pending ordinary update at step10000 was counted once; both arms finish with exactly45000 standard SAC updates. No cold episode reset confound, old300k inheritance, repeated B budget or scientific change. The original9h campaign cap includes the interruption and repair. Arm steps/s sum active process segments and exclude operator repair downtime.','', '## Saved-trace settling diagnostics','', 'Position progress alone did not establish settled arrival. The read-only goal-box audit is in OUTBOUND_SETTLING_AUDIT.md/json; its reference proxy never replaces the original state machine.']
    for a,r in final.items():annotation.append(f"\nFinal {a} NATIVE: position progress={r['max_synchronized_position_progress']:.6f}; goal-box samples={r['position_box_samples']}; position+velocity samples={r['position_and_velocity_samples']}; final q={r['final_q_deg']}deg; final dq={r['final_dq_deg_s']}deg/s; final reference q={r['final_reference_q_deg']}deg; HOLD={r['entered_HOLD']}; VALID={r['independent_VALID']}.")
    qa=read('OFFLINE_Q_PHASE_AUDIT.json');assert qa['status']=='READ_ONLY_PASS' and qa['new_online_steps']==qa['new_training_updates']==0
    annotation+=['','## Phase-specific Q and actor evidence','', 'OFFLINE_Q_PHASE_AUDIT.md/json and OFFLINE_Q_PHASE_CURVE.csv compare the final frozen checkpoints at identical causal Native teacher states. These read-only scores diagnose the learned value profile and actor discrepancy; they add no online steps or updates and do not establish physical counterfactual validity or a unique cause.']
    for a,v in qa['results'].items():
        for cohort in ('OUTBOUND_first64','HOLD','RETURN_last64'):
            x=v['cohorts'][cohort];annotation.append(f"\n{a} {cohort}: teacher Q={x['teacher_Q']['mean']:.4f}; online-action Q={x['online_action_counterfactual_Q']['mean']:.4f}; actor Q={x['actor_Q']['mean']:.4f}; teacher preferred rate={x['teacher_preferred_rate']:.4f}; actor-teacher raw-action MAE={x['actor_teacher_action_MAE']}.")
    rehydration=read('IMPORTANT_FAILURE_REHYDRATION_V2.json');assert rehydration['status']=='VALIDATED_ARCHIVAL_REHYDRATION' and rehydration['new_online_steps']==rehydration['new_updates']==0
    rehydrated_trace=str(Path(rehydration['restored_episode_dir'])/'trace.npz')
    assert sha(rehydrated_trace)==rehydration['original_trace_sha256']
    rehydration['verified_trace_checksum_matches_original']=True;save('IMPORTANT_FAILURE_REHYDRATION_V2.json',rehydration)
    ap=next(r for r in evaluations['A'] if r['training_step']==50000 and r['scope']=='NATIVE' and r['tag']=='periodic')
    af=next(r for r in evaluations['A'] if r['training_step']==50000 and r['scope']=='NATIVE' and r['tag']=='final')
    annotation+=['','## A50k positional discontinuity','', f"The periodic A50k checkpoint (44999 updates) reached {ap['max_synchronized_OUTBOUND_progress']:.6f} synchronized positional progress; the final checkpoint after the last ordinary update (45000 updates) reached {af['max_synchronized_OUTBOUND_progress']:.6f}. Neither entered HOLD or achieved VALID. This is positional sensitivity, not a prior successful task followed by regression. Both checkpoints, action sequences and original metrics remain preserved. The compact job pruned the periodic high-frequency trace before it was selected as important; IMPORTANT_FAILURE_REHYDRATION_V2.md/json records a separately labeled Native archival replay of its retained actor actions, verified against every saved transition and original force metrics. No extra training or new formal evaluation rows."]
    annotation+=['','The rehydrated trace.npz checksum equals the recorded original SHA-256. Runtime host-timing archives have separately recorded hashes and are not represented as byte-identical originals.']
    for root in (D,L):
        with (root/'TASK_ACQUISITION_COMPARISON.md').open('a') as f:f.write('\n'.join(annotation)+'\n')
    summary=read('TASK_ACQUISITION_COMPARISON.json');summary['monitor_repair']=read('EXACT_A_PHYSICS_RESTORATION.json');summary['settling_diagnostics_final_NATIVE']=final;summary['campaign_wall_s_including_repair']=time.time()-state['started_unix'];save('TASK_ACQUISITION_COMPARISON.json',summary);save('CHAT_SUMMARY.json',summary)
    command=dict(command='wsl -d Ubuntu -- bash /mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/demo_assisted_sac_task_acquisition_v1/launch_resume_v2.sh',launch_sha256=sha(W/'launch_resume_v2.sh'),repair_source_sha256=sha(W/'resume_a_guardfix_v2.py'),original_command_retained='ENVIRONMENT_AND_COMMAND.json',original_budget_unchanged=True)
    save('RESUME_COMMAND_AND_PROVENANCE.json',command)
    save('FINAL_VERIFICATION_V2.json',dict(status='PASS',required_outputs=required,each_arm_steps=50000,each_arm_updates=45000,each_arm_evaluations=12,all_batches_sequential_and_online_steps_exact=True,immutable_original_sources=True,protected_historical_files=len(pre['files']),preexisting_staged_entries_unchanged=len(old_index),old_branch_ref_and_HEAD_unchanged=True,within_original_9h=True,campaign_elapsed_s=time.time()-state['started_unix'],no_commit_push_merge=True,exact_physics_restoration=True,scientific_changes=[]))
    extras=[]
    for p in sorted(W.glob('*.sh')):
        shutil.copy2(p,P/p.name);extras.append(P/p.name)
    shutil.copy2(Path(__file__),P/Path(__file__).name);extras.append(P/Path(__file__).name)
    if not (D/'USER_REQUEST.txt').exists():shutil.copy2(W/'USER_REQUEST.txt',D/'USER_REQUEST.txt')
    extras+=[D/'USER_REQUEST.txt']
    for name in ('TASK_ACQUISITION_COMPARISON.md','TASK_ACQUISITION_COMPARISON.json','CHAT_SUMMARY.json','RESUME_COMMAND_AND_PROVENANCE.json','FINAL_VERIFICATION_V2.json'):extras.append(D/name)
    for name in ('OFFLINE_Q_PHASE_AUDIT.md','OFFLINE_Q_PHASE_AUDIT.json','OFFLINE_Q_PHASE_CURVE.csv'):extras.append(D/name)
    for name in ('IMPORTANT_FAILURE_REHYDRATION_V2.md','IMPORTANT_FAILURE_REHYDRATION_V2.json','RAW_DATA_MANIFEST.json'):extras.append(D/name)
    for name in ('recover_important_failure_v2.py','retain_sensitive_failure_v1.py','offline_q_phase_audit_v1.py'):
        shutil.copy2(W/name,P/name);extras.append(P/name)
    for p in extras:subprocess.run(['git','add','--',str(p.relative_to(R))],cwd=R,check=True)
    meta=read('FINAL_GIT_STATE.json');meta['individually_staged']=sorted(set(meta['individually_staged']+[str(p.relative_to(R)) for p in extras]));save('FINAL_GIT_STATE.json',meta)
    subprocess.run(['git','add','--',str((D/'FINAL_GIT_STATE.json').relative_to(R))],cwd=R,check=True)
    assert all(dict(x.split('\t',1)[::-1] for x in git('ls-files','--stage').splitlines()).get(p)==v for p,v in old_index.items())
    print(json.dumps(dict(status='FINAL_VERIFICATION_PASS_STOP',campaign_wall_h=(time.time()-state['started_unix'])/3600,staged_new_files=len(meta['individually_staged']),final_NATIVE={a:{k:r[k] for k in ('position_box_samples','position_and_velocity_samples','final_q_deg','final_dq_deg_s')} for a,r in final.items()})))
if __name__=='__main__':run()
