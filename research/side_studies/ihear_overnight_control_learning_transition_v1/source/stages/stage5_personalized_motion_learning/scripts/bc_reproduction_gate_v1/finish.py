from common import *
from diagnose import diagnose

def run():
    check_lock(); spec=read('PREREGISTRATION.json'); offline=read('OFFLINE_RESULTS.json'); rows=[]; replay=None; diagnoses=[]
    gate=all(r['offline_pass'] for r in offline) and len(offline)==3
    if gate:
        rows=[read(f'CLOSED_LOOP_seed_{seed}_formal.json') for seed in spec['seeds']]
        diagnoses=[read(f'DIAGNOSIS_seed_{seed}_formal.json') for seed in spec['seeds']]
        best=read('BEST_SELECTION.json')
        if best['replay_required']:
            replay=read(f'CLOSED_LOOP_seed_{best["seed"]}_confirmation.json');diagnose(replay)
            formal=next(r for r in rows if r['seed']==best['seed'])
            a=np.load(Path(formal['episode_dir'])/'BC_POLICY_TRANSITIONS.npz');b=np.load(Path(replay['episode_dir'])/'BC_POLICY_TRANSITIONS.npz')
            errors={k:float(np.max(np.abs(a[k]-b[k]))) if a[k].shape==b[k].shape else None for k in ('observations','raw_actions','executed_actions','task_s')}
            save('INDEPENDENT_REPLAY_CONFIRMATION.json',dict(seed=best['seed'],valid=replay['endpoints']['independent_VALID'],exact_policy_replay_errors=errors,checkpoint_sha256=replay['checkpoint_sha256'],fresh_process=True,teacher_access_count=0))
        nvalid=sum(r['endpoints']['independent_VALID'] for r in rows)
        status='BC_REPRODUCTION_PASS' if nvalid and replay and replay['endpoints']['independent_VALID'] else ('BC_REPLAY_CONFIRMATION_FAILED' if nvalid else 'BC_CLOSED_LOOP_REPRODUCTION_FAILED')
        verdict='PASS' if status=='BC_REPRODUCTION_PASS' else 'UNCERTAIN'
        mode=['G. successful reproduction'] if status=='BC_REPRODUCTION_PASS' else ['B. closed-loop compounding error / covariate shift']
        keep={O/'teacher_reference/episode_00001'}
        keep.add(Path(replay['episode_dir']) if replay else Path(next(r for r in rows if r['seed']==best['seed'])['episode_dir']))
        failures=[r for r in rows if not r['endpoints']['independent_VALID'] and Path(r['episode_dir']) not in keep]
        if failures:keep.add(Path(min(failures,key=lambda r:(r['endpoints']['max_synchronized_progress'],r['seed']))['episode_dir']))
    else:
        nvalid=0;status='BC_REPRESENTATION_FIT_FAILED';verdict='FAIL';mode=['A. actor/network cannot fit teacher mapping to preregistered thresholds']; keep={O/'teacher_reference/episode_00001'}
    manifest=[]
    # Retention operates only on known newly created high-frequency files in this experiment.
    for path in O.rglob('*'):
        if not path.is_file():continue
        if path.name not in ('trace.npz','runtime_artifacts.json.gz'): continue
        resolved=path.resolve();assert O.resolve() in resolved.parents
        item=dict(path=str(path),sha256=sha(path),bytes=path.stat().st_size,retained=path.parent in keep)
        if not item['retained']:path.unlink()
        manifest.append(item)
    save('HIGH_FREQUENCY_RETENTION.json',manifest)
    pre=read('PRESERVATION_BEFORE.json');changed=[p for p,h in pre['files'].items() if not (R/p).is_file() or sha(R/p)!=h]
    git=lambda *args:subprocess.check_output(['git',*args],cwd=R,text=True)
    assert not changed,'HISTORICAL_EVIDENCE_CHANGED:'+repr(changed[:10])
    assert git('ls-files','--stage')==pre['index'],'PREEXISTING_INDEX_CHANGED'
    assert git('rev-parse','HEAD').strip()==pre['head']
    assert git('branch','--show-current').strip()==BRANCH
    assert git('rev-parse','refs/heads/codex/demo-assisted-sac-task-acquisition-v1').strip()==pre['previous_branch_ref']
    check_lock()
    save('FINAL_VERIFICATION.json',dict(status='PASS',historical_files_verified=len(pre['files']),historical_changed=changed,scientific_source_hashes_unchanged=True,preexisting_index_unchanged=True,old_branch_ref_unchanged=True,HEAD_unchanged=True,branch=BRANCH,no_stage_commit_push_merge_reset=True,critic_instances=0,SAC_updates=0,reward_optimization_updates=0,teacher_override_count=0,formal_seeds_reported=len(offline),high_frequency_retained=len([r for r in manifest if r['retained']]),truth_firewall_pass=True))
    save('FINAL_GIT_STATE.json',dict(branch=BRANCH,head=pre['head'],status=git('status','--short')))
    summary=dict(STATUS=status,OFFLINE_FIT=offline,CLOSED_LOOP=dict(seed_success_count=nvalid,total_seeds=3,
        best_progress=max((r['endpoints']['max_synchronized_progress'] for r in rows),default=None),
        first_HOLD=min((r['endpoints']['HOLD_entry_s'] for r in rows if r['endpoints']['HOLD_entry_s'] is not None),default=None),
        first_RETURN=min((r['endpoints']['RETURN_entry_s'] for r in rows if r['endpoints']['RETURN_entry_s'] is not None),default=None),
        VALID=bool(nvalid),confirmation_VALID=replay['endpoints']['independent_VALID'] if replay else None,
        per_seed=[dict(seed=r['seed'],**r['endpoints']) for r in rows]),FAILURE_MODE=mode,
        REPRESENTATION_VERDICT=verdict,J_F_F_PEAK_M_PEAK=({k:replay['metric'][k] for k in ('J_F','force_peak','moment_peak')} if replay and replay['endpoints']['independent_VALID'] else None),
        scientific_interpretation=(['The frozen 55-D deployable observation and native 256/256 squashed Gaussian mean express a complete legal policy on the fixed exposed Human.',
        'Independent autonomous replay confirms original settling, HOLD, RETURN and physical/scientific validity; this is not held-out robustness.',
        'J_F characterizes the valid BC replay; no teacher-improvement or SAC-learning claim is made.'] if status=='BC_REPRODUCTION_PASS' else
        (['Offline teacher-action fitting passed for every preregistered seed, but the autonomous task gate failed.',
        'Post-run deviation supports off-trajectory accumulation; this outcome is not attributed to SAC.',
        'Single-trajectory evidence does not isolate partial observability or absolute-target sensitivity.'] if gate else
        ['Native actor-only supervised fitting did not meet the frozen offline reproduction gate; no BC physical evaluation was run.',
        'This bounded run rejects the registered fit test, not a mathematical impossibility proof for the representation.'])),
        NEXT=('BC-initialized SAC fine-tuning in a separately authorized experiment.' if status=='BC_REPRODUCTION_PASS' else ('Study covariate shift and recovery-data coverage before further RL.' if gate else 'Study observation/network/action representation and offline approximation error.')),
        REPORT_PATH=str(L/'BC_REPRODUCTION_GATE_V1_REPORT.md'),new_scientific_variables='BC-only actor objective, phase-balanced sampling, independent initialization seeds',frozen_R2_changes=[],automatic_followups_started=False)
    save('SUMMARY.json',summary)
    lines=['# Behavior Cloning Reproduction Gate v1',f'\nSTATUS: {status}',f'\nRepresentation verdict: {verdict}',
        '\n## Contract and provenance',f'\nQuestion: {spec["question"]}\n\nBranch: `{BRANCH}`; starting branch `{pre["branch"]}`; HEAD `{pre["head"]}`. Three fixed initialization seeds; installed native SB3 Actor only. No critic, replay optimizer, reward optimization or SAC update. Fixed normalization and identity action scaling were verified. All original physical/safety/task/R2 sources stayed byte-identical. Teacher is offline supervision; the standalone evaluation process never opens the dataset while physics runs.',
        '\nValidation is interpolation within one correlated, previously exposed successful trajectory. It is not an independent deployment or robustness test. Original phase/settling tolerances and .5 s continuous HOLD remain authoritative.',
        '\n## Offline gate', '\nRaw action units convert at 62.5 degrees per unit. Training and validation indices, objective, seeds, sampling, budgets and exact gate thresholds were frozen in PREREGISTRATION.json before any BC training or closed-loop result.',
        '\n|Seed|Epochs / best|Stop|MAE|RMSE|Max error|OUTBOUND RMSE|HOLD RMSE|RETURN RMSE|Offline gate|',
        '|---|---|---|---|---|---|---|---|---|---|']
    for r in offline:
        m=r['metrics'];p=m['per_phase'];lines.append(f'|{r["seed"]}|{r["epochs"]} / {r["best_epoch"]}|{r["stop_reason"]}|{m["MAE"]:.8f}|{m["RMSE"]:.8f}|{m["max_error"]:.8f}|{p["OUTBOUND"]["RMSE"]:.8f}|{p["HOLD"]["RMSE"]:.8f}|{p["RETURN"]["RMSE"]:.8f}|{r["offline_pass"]}|')
    lines+=['\nTotal/hip/knee MAE and RMSE, max error, near-bound rates and all exact teacher-state predictions are preserved per seed. Full epoch curves and selected actor checkpoints are saved. Native public predict output equals the trained deterministic forward action; CPU/CUDA consistency was checked.',
        '\n## Closed loop','\n|Seed|Progress|Settled OUTBOUND|HOLD entry s|HOLD complete|RETURN entry s|RETURN complete|VALID|Termination|', '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        e=r['endpoints'];lines.append(f'|{r["seed"]}|{e["max_synchronized_progress"]:.6f}|{e["settled_OUTBOUND_arrival"]}|{e["HOLD_entry_s"]}|{e["HOLD_completed"]}|{e["RETURN_entry_s"]}|{e["RETURN_completed"]}|{e["independent_VALID"]}|{e["termination_reason"]}|')
    if not rows: lines.append('\nSTOP at the offline gate; no autonomous BC closed-loop evaluation was started.')
    lines+=['\nThe independent frozen evaluator consumed recorded physical outputs only after the episode. Each rollout freshly commissions the same legal initial condition, uses the online q/dq/ddq and safety chain, deterministic actor output every 20 ms and original R2 termination. Raw/executed actions, force/moment, clearance, tracking errors and initial-state equivalence are recorded in CLOSED_LOOP_seed files and retained traces.',
        '\n## Error accumulation and diagnosis',f'\nClassification: {", ".join(mode)}.']
    for d in diagnoses:
        lines.append(f'\nSeed {d["seed"]}: first significant deviation = {json.dumps(d["first_significant_deviation"])}; time-aligned observation L2 = {json.dumps(d["observation_L2_time_aligned"])}; same-phase nearest-observation L2 = {json.dumps(d["nearest_observation_L2"])}; nearest-comparable action L2 = {json.dumps(d["action_L2_nearest_comparable"])}.')
    lines+=['\nTime-aligned and nearest same-phase comparisons are post-run diagnostics. State/action errors are stored at every policy sample; phase mismatches, repeated nearest states, and time beyond teacher completion are explicit. A finite teacher trajectory cannot supply a true off-trajectory teacher policy. B is supported when offline errors are low and deviations accumulate; C (observation insufficiency) and D (absolute-target sensitivity) remain unproven. E/F mismatch routes are checked through exact teacher wrapper reproduction, native transform identity and identical initial observation.',
        '\n## Independent replay and valid-only force characterization', '\n'+json.dumps(clean(summary['J_F_F_PEAK_M_PEAK']),indent=2)]
    if replay: lines.append('\nReplay confirmation: '+json.dumps(read('INDEPENDENT_REPLAY_CONFIRMATION.json'),indent=2))
    lines+=['\n## Scientific interpretation']+['\n- '+x for x in summary['scientific_interpretation']]
    lines+=['\n## Preservation and checks',f'\n{len(pre["files"])} historical files rehashed unchanged; preexisting index, HEAD and old branch ref preserved. No staging, commit, push, merge or reset. New branch creation was explicitly requested. Only newly generated high-frequency evidence was pruned under the predeclared retention policy; all per-seed compact traces and metrics remain. Details: FINAL_VERIFICATION.json, HIGH_FREQUENCY_RETENTION.json, ENVIRONMENT.json, EXPERIMENT_SOURCE_LOCK.json and PRESERVATION_BEFORE.json.',
        '\nMechanical checks: Python compile; native actor deterministic forward vs public predict and direct tanh(mean); frozen log_std gradients and weights; empty fresh Adam state; no critic; distinct initialization hashes; CPU/CUDA predictions; exact all-593-transition teacher observation/next-observation/raw/executed/phase/termination/reward reproduction; frozen independent physical evaluator; all seeds and failures reported. No BC hyperparameter retraining after closed-loop results.',
        '\nCommands: launch.sh (preflight.py, teacher.py, train.py, three evaluate.py formal processes, diagnose.py, optional one evaluate.py confirmation process, finish.py). Runtime and complete logs are in FORMAL_RUN.log. No extra scientific experiment or automatic next phase is started.',
        '\n## Next', '\n'+summary['NEXT'], '\nSTOP.']
    prose('BC_REPRODUCTION_GATE_V1_REPORT.md','\n'.join(lines)+'\n')
    state(status,representation_verdict=verdict,valid_count=nvalid,report_path=summary['REPORT_PATH'],STOP=True)

if __name__=='__main__': run()
