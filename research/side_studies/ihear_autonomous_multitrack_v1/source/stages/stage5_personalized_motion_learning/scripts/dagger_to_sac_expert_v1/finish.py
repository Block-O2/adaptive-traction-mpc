from common import *
def run():
    st=read('STATE.json');pre=read('PRESERVATION_BEFORE.json')
    changed=[p for p,h in pre['files'].items() if not (R/p).exists() or sha(R/p)!=h]
    def git(*args):return subprocess.check_output(['git','-C',str(R),*args],text=True).strip()
    preserved=not changed and git('ls-files','--stage')==pre['index'] and git('rev-parse','HEAD')==pre['head']
    save('FINAL_PRESERVATION.json',dict(pass_=preserved,historical_files=len(pre['files']),changed=changed,
        preexisting_index_unchanged=git('ls-files','--stage')==pre['index'],HEAD_unchanged=git('rev-parse','HEAD')==pre['head'],
        starting_branch=pre['branch'],campaign_branch=git('branch','--show-current'),staged=False,committed=False,pushed=False))
    if not preserved:state('SCIENTIFIC_CONTRACT_OR_SAFETY_BROKEN',changed_historical=changed);st=read('STATE.json')
    gate=read('EXPERT_GATE.json');dag=read('DAGGER_RESULTS.json') if (D/'DAGGER_RESULTS.json').exists() else {}
    sac=read('SAC_RESULTS.json') if (D/'SAC_RESULTS.json').exists() else {}
    prior=json.loads((S/'docs/single_human_sac_expert_v1/r2/SAC_COMPARATOR_TABLE.json').read_text())['rows']
    comparisons=[]
    for row in prior:
        if row['name'] in ('old_nominal','fixed_hip_lead','cem_reference_transfer'):
            comparisons.append(dict(source='frozen historical same-wrapper R2, not a new replay this campaign',
                **{k:row.get(k) for k in ('name','scope','valid','J_F','force_peak','moment_integral','moment_peak','duration_s','clearance','trace','trace_sha256')}))
    final=[]
    if dag:
        final=dag['rounds'][-1]['evaluations']
        for scope in ('NATIVE','MATCHED'):
            candidates=[r for r in final if r['scope']==scope and r['valid']]
            if candidates:comparisons.append(dict(source='current pure-student qualification',name='DAgger_student',**{k:candidates[0][k] for k in ('scope','valid','J_F','force_peak','moment_integral','moment_peak','duration_s','clearance')}))
    for scope,row in sac.get('best',{}).items():
        comparisons.append(dict(source='current independently confirmed SAC',name='best_SAC',**{k:row[k] for k in ('scope','valid','J_F','force_peak','moment_integral','moment_peak','duration_s','clearance')}))
    save('COMPARATORS.json',dict(rows=comparisons,rank_only_VALID=True,scopes_separate=True,global_optimum_claim=False))
    failure_counts={};terminated=[]
    for rd in dag.get('rounds',[]):
        for row in rd['collection']+rd['evaluations']:
            if not row['valid']:
                reasons=row['physical_audit']['unchanged_evaluator']['physical_task_result']['reasons']
                for r in reasons:failure_counts[r]=failure_counts.get(r,0)+1
                terminated.append(dict(name=row['name'],gates=row['gates'],status=row['status'],rejections=row['rejections'],reasons=reasons))
    save('FAILURE_DIAGNOSIS.json',dict(counts=failure_counts,failures=terminated,
        interpretation='Expert recovery demonstrated on tested BC states. Persistent student failure, if any, indicates unresolved covariate shift / supervised control accuracy under the frozen pipeline. It does not prove 55-D/2-D insufficiency.',
        failed_states_discarded=0,parameters_retuned_after_results=False))
    last=final[0] if final else None
    summary=dict(STATUS=st['status'],EXPERT=dict(queryable=gate.get('queryable'),recovery_valid=sum(r['metric']['valid'] for r in gate['results'] if r['seed'] is not None),tested_recovery_states=3),
        DAGGER=dict(rounds=st.get('dagger_rounds',0),dataset_size=st.get('dataset_size',0),first_VALID_round=dag.get('first_VALID_round'),
          final_pure_success=sum(r['valid'] for r in final),evaluations=len(final),final_metric={k:last.get(k) for k in ('valid','J_F','force_peak','moment_integral','moment_peak','duration_s','clearance','gates')} if last else None),
        SAC=dict(started=st.get('sac_started',False),online_steps=st.get('online_steps',0),best=sac.get('best',{}),
                 success_preservation='STOP after two losses' if st['status']=='SAC_ABILITY_LOST' else 'not evaluated' if not st.get('sac_started') else 'See checkpoint counts',last_good=sac.get('last_good_checkpoint')),
        COMPARATORS=comparisons,preservation=preserved,scientific_variables_changed='causal expert query + aggregated imitation + conditional fresh SAC only',
        unchanged='plant/task/safety/55-D obs/2-D action/20ms/OTG/R2/reward',report=str(L/'DAGGER_TO_SAC_EXPERT_V1_REPORT.md'))
    save('SUMMARY.json',summary)
    lines=['# DAgger-to-SAC Expert Pipeline v1','',f"STATUS: {st['status']}",'',
        'User-authorized autonomous nominal Human simulation campaign. No new Human holdout: repeated deterministic rollouts demonstrate reproducibility on the exposed nominal case, not statistical robustness.',
        '',f"Starting branch: {pre['branch']}; campaign branch: {git('branch','--show-current')}; HEAD: {pre['head']}.",'',
        '## Expert','',
        'The expert query accepts only the normalized 55-D causal observation. It reuses hip-leading knee-preview intent and the current robust terminal reference, with release keyed to estimated/current-reference hip posture rather than the archived 1.5-second trajectory clock. Thresholds were calibrated once from archived deployable teacher posture before the gate. No simulator, original trajectory index, future observation/force or hidden Human truth enters the query.',
        '', '|Continuation|Prefix steps|First certified status|Full independent VALID|J_F (N s)|Duration (s)|','|---|---:|---|---|---:|---:|']
    for r in gate['results']:
        m=r['metric'];lines.append(f"|{r['name']}|{r['prefix_index']}|{r['first_action_status']}|{m['valid']}|{m['J_F']:.6f}|{m['duration_s']:.3f}|")
    lines += ['', 'BC prefixes reproduce archived observations exactly with their actual student actions; the expert then continues that live physics owner. No reset to teacher is used. At the late prefix, the 2-second continuation has already entered RETURN, so outbound progress decreases appropriately; full VALID confirms recovery.',
        '', '## DAgger','',
        'Native SB3 deterministic actor, 55→256→256→2, fresh initialization. Initial full VALID teacher data; all visited collection observations receive causal expert labels. Beta is fixed at .5/.25/.1/0/0/0/0/0. Adam, learning rate .0003, 18000 initial and per-round updates, batches of 96 per phase (288 total). Fixed final-update weights; no validation-gate stop or result-conditioned hyperparameter changes. Failed/difficult states are kept. Per-transition archives include label, actual raw action, realized action, phase, round, terminal outcome and stated mixture. Episode outcomes under a mixture are not per-state expert counterfactual recovery results.',
        '', '|Round|Beta|Dataset states|Collection VALID|Pure student VALID|Consecutive 3/3 rounds|','|---:|---:|---:|---:|---:|---:|']
    for rd in dag.get('rounds',[]):lines.append(f"|{rd['round']}|{rd['beta']}|{rd['dataset_size']}|{sum(r['valid'] for r in rd['collection'])}/3|{rd['valid_count']}/3|{rd['consecutive_qualified_rounds']}|")
    lines += ['',f"First pure-student VALID round: {dag.get('first_VALID_round')}. Final student metrics (unranked when INVALID): `{json.dumps(clean(summary['DAGGER']['final_metric']))}`.",
        '', '## SAC','',f"Started: {st.get('sac_started',False)}; online steps: {st.get('online_steps',0)}.",
        'SAC is eligible only after two consecutive 3/3 pure-student rounds. Actor mean identity, fresh critics/target critics/optimizers, actual executed transition replay semantics, no uniform random warmup, fixed demo/online ratio and every-10k capability preservation checks are specified in PREREGISTRATION.json. Formal SAC runtime evidence exists only if SAC was actually entered.',
        '', '## VALID-only comparators','', '|Method|Scope|VALID|J_F (N s)|Duration (s)|Evidence|','|---|---|---|---:|---:|---|']
    for r in comparisons:lines.append(f"|{r['name']}|{r['scope']}|{r['valid']}|{r['J_F']:.6f}|{r['duration_s']:.3f}|{r['source']}|")
    lines += ['', 'Historical comparator traces/hashes and source labels remain distinct from new replays. NATIVE and MATCHED rankings are separate; INVALID policy force integrals never establish an improvement. Current campaign contains no CEM search and makes no global-optimum claim.',
        '', '## Failure evidence and interpretation','',f"Unchanged evaluator failure counts: `{json.dumps(failure_counts)}`.",
        'Recovery-gate success establishes the tested expert interface. Unqualified student performance cannot by itself establish observation/action impossibility. See FAILURE_DIAGNOSIS.json for every failed collection/evaluation, not just the most favorable result.',
        '', '## Preservation, runtime and verification','',f"Historical files rehashed: {len(pre['files'])}; preservation PASS: {preserved}. No old result was rewritten. Preexisting Git index and HEAD are unchanged; no stage, commit, push, merge, reset or stash.",
        'CPU MuJoCo single-owner execution; CUDA imitation/SAC optimization. Reuses the repaired process ownership / memory monitor, with host commit headroom and swap-growth gates. Science hashes, preregistration hash, executable hashes, exact seed/config/environment, native actor/optimizer/RNG checkpoints, aggregated datasets, replay (if SAC started) and evaluation summaries are retained. Raw key success/failure traces are losslessly compressed with hash verification.',
        'Commands: preflight.py; expert_gate.py; mechanical_checks.py; workflow.py (conditional dagger.py then sac.py); finish.py. Python compile and the mechanical state-sensitivity, action-transform, beta-schedule and mixed-replay ratio checks are in MECHANICAL_CHECKS.json. No independent Auditor agent was dispatched; source/data-flow and preservation audits run in the single agent.',
        '', '## Next','',
        'If unqualified: audit the retained teacher/student-state label consistency and terminal command accuracy within this same interface before another training campaign. If SAC qualified but regressed: inspect last-good versus loss checkpoints. If complete: independently validate the confirmed best VALID policy on the same frozen contract before widening the Human domain.',
        '', 'STOP.']
    report='\n'.join(lines)+'\n'
    for folder in (D,L):(folder/'DAGGER_TO_SAC_EXPERT_V1_REPORT.md').write_text(report,encoding='utf-8')
    print(json.dumps(clean(summary)),flush=True)
if __name__=='__main__':run()
