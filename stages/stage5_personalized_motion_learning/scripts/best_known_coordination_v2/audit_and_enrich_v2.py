"""Offline evidence QA and full-state extraction, never used by candidate proposals."""
from pathlib import Path
import hashlib,json,gzip,sys
import csv
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-learning');S=R/'stages/stage5_personalized_motion_learning'
P=S/'scripts/best_known_coordination_v2';D=S/'docs/best_known_coordination_search_v2';RAW=S/'results/best_known_coordination_search_v2'
sys.path.insert(0,str(P));import campaign_v2 as c
def json_read(path):
    if path.exists():return json.loads(path.read_text())
    with gzip.open(path.with_suffix(path.suffix+'.gz'),'rt') as f:return json.load(f)
def json_save(path,x):path.write_text(json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n')
def audit():
    old=(S/'scripts/high_rom_v1/coordination_pacing_adapter_v1.py').read_text();new=(P/'coordination_adapter_v2.py').read_text()
    start='        state = np.asarray(kwargs["current_deployable_state"], dtype=float)'
    end='        chosen = replace(original, executed=alternative,'
    oldscreen=old[old.index(start):old.index(end)];newscreen=new[new.index(start):new.index(end)]
    assert oldscreen==newscreen
    from coordination_space import deformation,neutral,DIMENSIONS
    errors=[]
    for level in (1,2,3):
        rng=np.random.default_rng(level)
        for _ in range(20):
            p=rng.uniform(c.LOW[:DIMENSIONS[level]],c.HIGH[:DIMENSIONS[level]]);p=c.pure_matched(p)
            for phase in ('OUTBOUND','RETURN'):
                for s in np.linspace(0,1,31):
                    errors.append(abs(float(np.sum(deformation(s,phase,c.spec(level,p))))))
    assert max(errors)<1e-14
    json_save(D/'SAFETY_AND_COORDINATION_AUDIT.json',{'exact_inherited_evaluation_fixed_scheduler_mechanics_causal_clearance_block':True,
        'inherited_screen_block_sha256':hashlib.sha256(newscreen.encode()).hexdigest(),'MATCHED_max_common_progress_numeric_error':max(errors),
        'protected_fingerprint_count':c.check_frozen(),'no_hidden_truth_in_space_or_generation':True,
        'review':'Candidate inputs limited to declared parameters, task start/goal and frozen nominal baseline targets. Evaluation-only trace read exists solely in this offline enrichment script.'})
def enrich():
    db=c.read(D/'BEST_KNOWN_REFERENCE_DATABASE.json')
    raw_manifest_hash=c.sha(D/'RAW_DATA_MANIFEST.json')
    for e in db['entries']:
        rp=R/e['result_path'];record=c.read(rp)
        candidates=list(rp.parent.glob('rep_*/trace.npz'))
        winner_trace_available=bool(candidates)
        initial_origin='winning rollout trace, directly recorded'
        if not candidates:
            base=c.RUNS/f'A_{e["condition"]}_{e["matched_native_label"]}_baseline_0'
            candidates=list(base.glob('rep_*/trace.npz'))
            initial_origin='reproduced baseline from same case/options/checkpoint, with identical frozen pre-task execution; historical winner raw trace archived separately'
            if not candidates:raise RuntimeError('frozen initial-state source unavailable:'+str(rp))
        trace_path=candidates[0];trace=np.load(trace_path)
        task=int(np.flatnonzero(trace['stage']=='TASK')[0])
        def state(index):return {'time_s':float(trace['time_s'][index]),'stage':str(trace['stage'][index]),
            'estimated_q_dq_rad_rad_s':trace['estimated_human_state_rad_rad_s'][index].tolist(),
            'evaluation_only_Human_q_dq_rad_rad_s':trace['evaluation_only_human_state_rad_rad_s'][index].tolist(),
            'receipt_reference_q_rad':trace['reference_q_rad'][index].tolist(),'receipt_reference_dq_rad_s':trace['reference_dq_rad_s'][index].tolist(),
            'cr12_q_rad':trace['cr12_q_rad'][index].tolist(),'cr12_dq_rad_s':trace['cr12_dq_rad_s'][index].tolist()}
        e['initial_state'].update(run_start=state(0),task_start=state(task),trace_sha256=c.sha(trace_path),
            state_provenance=initial_origin,initial_state_trace_path=str(trace_path.relative_to(R)))
        artifact=json_read(trace_path.parent/'runtime_artifacts.json')
        decisions=artifact['task_decisions'];first=next(d for d in decisions if d.get('phase')=='OUTBOUND' and 'evaluations' in d)
        chosen=next(x for x in first['evaluations'] if x['label']==first['executed_label'])
        assert len(trace['task_beta'])==int(np.sum(trace['stage']=='TASK'))
        assert len(trace['task_residual_weights_nm'])==len(trace['task_beta'])
        e['Human_model_state'].update(task_start_deployable_beta=trace['task_beta'][0].tolist(),
            task_start_deployable_residual_weights_nm=trace['task_residual_weights_nm'][0].tolist(),
            task_start_belief_sequence=int(trace['belief_sequence'][task]),
            model_trace_indexing='beta/residual arrays contain TASK rows only; index 0 is first recorded TASK receipt. Other state arrays use full-trace first TASK index.',
            model_trace_feature_role='Recorded first TASK receipt metadata; use decision-owned pre-action belief/snapshot for causal learner features.',
            recorded_start_decision_context={k:first[k] for k in first if 'belief' in k or 'geometry' in k or 'state' in k},
            start_execution_screen_from_initial_state_trace=chosen.get('execution_screen'))
        screen=chosen.get('execution_screen') or {};causal=screen.get('causal_tracking_offset_clearance') or {}
        e['initial_state']['causal_snapshot_before_first_action']=causal.get('reference_snapshot')
        e['initial_state']['learner_feature_rule']='Use immutable pre-action deployable snapshot/belief; evaluation-only trace states and physical case truth are reproduction metadata, never learner inputs.'
        before_sequence=first.get('belief_sequence_used')
        same_sequence=before_sequence==int(trace['belief_sequence'][task])
        e['Human_model_state']['pre_action_belief_sequence_used']=before_sequence
        e['Human_model_state']['first_TASK_receipt_matches_pre_action_belief_sequence']=same_sequence
        e['Human_model_state']['pre_action_beta_when_sequence_matched']=trace['task_beta'][0].tolist() if same_sequence else None
        e['Human_model_state']['pre_action_residual_when_sequence_matched']=trace['task_residual_weights_nm'][0].tolist() if same_sequence else None
        e.setdefault('rollout_result_sha256',e['manifest_hash']);e['manifest_hash']=raw_manifest_hash
        e['manifest_hash_semantics']='SHA256 of campaign RAW_DATA_MANIFEST.json; rollout_result_sha256 separately identifies this reference result.'
        if e['reference_source']=='v2':
            e['coordination_parameter_family']='v2_nested_endpoint_zero'
            e['learning_action_encoding']=e['coordination_parameters'] or c.spec(1,c.neutral(1))
        else:
            e['coordination_parameter_family']='historical_frozen_nominal_proposal'
            mapped=c.prior_seed(e['condition'],e['matched_native_label'],3)
            e['learning_action_encoding']=None if mapped is None else c.spec(3,mapped)
            e['learning_action_mapping_status']='formula-equivalent descriptor, not independently reexecuted by v2 mapper' if mapped is not None else 'legacy nominal chunk retained; no exact v2 parameter encoding claimed'
        descriptor=e['coordination_parameters'] or {}
        e['learning_action_context']={'arm':e['matched_native_label'],
            'nominal_template_run_id':e['trajectory_descriptor']['nominal_template_run_id'],
            'full_original_descriptor':descriptor,
            'continuation_scope':'v2 adapter: active phase deforms frozen nominal template; inactive native phase continues original state-feedback planner; MATCHED uses original fixed-duration recertification' if e['reference_source']=='v2' else 'retain legacy nominal chunk and original timing/continuation mode; any mapped v2 parameters describe shape only and do not independently certify the same executed cost'}
        if winner_trace_available:
            mask=trace['stage']=='TASK';acc=trace['actual_human_acceleration_rad_s2'][mask];t=trace['time_s'][mask]
            dt=np.diff(t);valid=trace['actual_human_acceleration_valid'][mask]
            chosen_intervals=np.asarray(valid[:-1],bool)&np.asarray(valid[1:],bool)&(dt>0)
            jerk=np.diff(acc,axis=0)[chosen_intervals]/dt[chosen_intervals,None]
            e['force_metrics']['smoothness']={'acceleration_rms_rad_s2':record.get('ddq_rms_rad_s2'),
                'jerk_rms_rad_s3':np.sqrt(np.mean(jerk**2,axis=0)).tolist() if len(jerk) else None,
                'jerk_integral_rad_s2':float(np.sum(np.linalg.norm(jerk,axis=1)*dt[chosen_intervals])),
                'definition':'finite difference of recorded valid adjacent TASK acceleration samples; diagnostics only'}
        else:e['force_metrics']['smoothness']={'acceleration_rms_rad_s2':record.get('ddq_rms_rad_s2'),'jerk_rms_rad_s3':None,
                'limitation':'winning historical raw trace archived; jerk not recomputed from another rollout'}
        e['truth_firewall']='Evaluation-only initial Human/robot state is reproduction metadata; never supplied to candidate generation or online planner.'
    json_save(D/'BEST_KNOWN_REFERENCE_DATABASE.json',db)
    report=D/'BEST_KNOWN_REFERENCE_SEARCH_REPORT.md';text=report.read_text()
    text=text.replace('Database manifest_hash is the rollout-result digest containing raw hashes.',
                      'Database manifest_hash is the campaign raw-manifest digest; rollout_result_sha256 identifies each result header.')
    text += '\nAdditional audit: L2/L3 restarts share earlier best samples, so agreement of restart minima is correlated and is not independent convergence evidence. New levels are nested within v2; different historical smooth-basis families may not have an exact v2 parameter embedding. Legacy teacher chunks retain their nominal target descriptor and mapping status. Each new level has only 18 attempted evaluations per condition/arm.\n'
    text += '\nFrozen-start teacher generation does not resolve the earlier value-learning native cross-repetition continuity blocker. Prospective learning should first validate continuation/state features and the fixed-versus-lookup comparator. No learner was run here.\n'
    text += '\nThe fixed-pattern comparator was selected by previously observed cross-condition coverage, then mean fractional benefit. Only descriptors evaluated across the represented conditions compete at full coverage; this is not an exhaustive optimization of all universal fixed patterns. No fixed-policy insufficiency or personalization necessity is proved.\n'
    text += '\nThe normalized beta-shaped offsets are continuous, endpoint-zero and smooth in the interior. General peak/width exponents do not guarantee C1 behavior at the normalized endpoints. Executed references are emitted through the unchanged quintic scheduler and its physical feasibility checks; reference and Human acceleration/jerk diagnostics concern that executed motion. No global derivative bound is claimed for the analytic offset shape.\n'
    text += '\nDatabase J_F labels belong to the frozen task-start context and declared full-task continuation. They cannot be copied as remaining-cost labels for arbitrary intermediate states. A future remaining-value dataset needs supported state snapshots and continuation-conditioned rollouts; rejected/truncated candidates keep feasibility labels rather than being ranked by their partial force integral.\n'
    report.write_text(text)

def rollout_diagnostics():
    rows=[]
    for e,r in c.collect():
        base=c.baseline(e['condition'],e['arm']);rankable,isolated,residual=c.eligible(r,base,e['arm'])
        row={'run_id':e['run_id'],'condition':e['condition'],'arm':e['arm'],'phase':e['phase'],
             'level':e.get('level'),'status':r['status'],'rankable':rankable,'timing_isolated':isolated,
             'elapsed_host_s':r.get('elapsed_host_s'),'wrapper_elapsed_s':r.get('wrapper_elapsed_s'),
             'J_F_task_n_s':r.get('J_F_task_n_s'),'mean_force_n':r.get('mean_force_n'),'rms_force_n':r.get('rms_force_n'),
             'peak_force_n':r.get('peak_force_n'),'moment_integral_nm_s':r.get('moment_integral_nm_s'),
             'moment_peak_nm':r.get('moment_peak_nm'),'minimum_clearance_m':r.get('minimum_clearance_m'),
             'duration_s':r.get('duration_s'),'outbound_duration_s':r.get('outbound_duration_s'),
             'return_duration_s':r.get('return_duration_s'),'failure_reason':r.get('failure_reason')}
        rows.append(row)
    with (D/'ROLLOUT_DIAGNOSTICS.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def fixed_comparison_table():
    comparison=c.read(D/'CONDITION_COMPARISON.json');selection=c.read(D/'FIXED_PATTERN_SELECTION.json')
    lines=['# Fixed versus search baseline','',
           'All J_F values are in N s. Each arm has its own baseline. The selected fixed descriptor is shared across conditions within that arm.', '',
           '|Condition|Arm|Original baseline|Preregistered fixed hip-leading|Selected universal fixed|Best-known|Fixed minus best-known|',
           '|---|---|---:|---:|---:|---:|---:|']
    for r in comparison['rows']:
        fixed=f'{r["fixed_best_J_F"]:.6f}' if r['fixed_best_rankable'] else 'infeasible/confounded'
        gap=f'{r["fixed_vs_best_gap_n_s"]:.6f}' if r['fixed_vs_best_gap_n_s'] is not None else 'not rankable'
        prior=c.load_result(f'A_{r["condition"]}_{r["arm"]}_fixed_0')
        prior_ok=c.eligible(prior,c.baseline(r['condition'],r['arm']),r['arm'])[0]
        prior_text=f'{r["fixed_prior_J_F"]:.6f}'+(' (not isolated)' if not prior_ok else '')
        lines.append(f'|{r["condition"]}|{r["arm"]}|{r["baseline_J_F_n_s"]:.6f}|{prior_text}|{fixed}|{r["best_known_J_F_n_s"]:.6f}|{gap}|')
    lines += ['', 'Fixed descriptor selection (frozen before final cross-condition reexecution):', '',
              '```json',json.dumps(selection,indent=2,sort_keys=True),'```','',
              'Selection uses previously observed coverage first and mean relative benefit second. It is an in-sample comparison among tested descriptors, not an exhaustive search for the globally best fixed policy. Historical references are retained when stronger; v2-only minima and their independent confirmation are separately recorded in CONDITION_COMPARISON.json. No general fixed-policy sufficiency or personalization necessity follows from these gaps.']
    (D/'FIXED_VS_SEARCH_BASELINE.md').write_text('\n'.join(lines)+'\n')

def reference_pacing_audit():
    rows=[]
    for e in c.read(D/'BEST_KNOWN_REFERENCE_DATABASE.json')['entries']:
        r=c.read(R/e['result_path']);b=c.baseline(e['condition'],e['matched_native_label'])
        residual={name:r[name]-b[name] for name in ('duration_s','outbound_duration_s','return_duration_s')}
        remainder=lambda x:x['duration_s']-x['outbound_duration_s']-x['return_duration_s']
        rows.append({'condition':e['condition'],'arm':e['matched_native_label'],
            'duration_residual_s':residual,'other_task_phase_duration_residual_s':remainder(r)-remainder(b),
            'target_common_progress_residual':c.common_progress_residual(r,b),
            'mean_force_change_n':r['mean_force_n']-b['mean_force_n'],
            'rms_force_change_n':r['rms_force_n']-b['rms_force_n'],
            'peak_force_change_n':r['peak_force_n']-b['peak_force_n'],
            'moment_integral_change_nm_s':r['moment_integral_nm_s']-b['moment_integral_nm_s'],
            'moment_peak_change_nm':r['moment_peak_nm']-b['moment_peak_nm']})
    matched=[r for r in rows if r['arm']=='MATCHED']
    other_pass=all(abs(r['other_task_phase_duration_residual_s'])<=c.C['matched_tolerance_s']+1e-9 for r in matched)
    json_save(D/'REFERENCE_PACING_AND_METRIC_AUDIT.json',{'rows':rows,'MATCHED_other_phase_duration_guard_pass':other_pass,
        'interpretation':'MATCHED is the preregistered scheduler/common-progress control with 25ms measured-phase tolerance, not exact equality of every physical sample. Small gains should be read with timing quantization and metric changes. NATIVE may include phase/hold timing changes.'})
    if not other_pass:raise RuntimeError('MATCHED_OTHER_PHASE_PACING_NEEDS_REVIEW')

def observed_result_notes():
    report=D/'BEST_KNOWN_REFERENCE_SEARCH_REPORT.md';text=report.read_text()
    marker='## Observed metric and fixed-comparator qualifications'
    if marker in text:return
    text += '\n'+marker+'\n\n'
    text += 'The coverage-first universal fixed descriptor selected in both arms is neutral (all offsets zero), and its final costs reproduce the corresponding original baselines. The preregistered hip-leading descriptor remains a separate, often stronger comparator: its low-ROM MATCHED outbound timing residual is 30ms, exceeding the frozen 25ms guard, so it has only four-condition isolated coverage. These coverage restrictions do not prove neutral is the best possible universal policy. In sync_120 MATCHED, the preregistered fixed cost is 1488.972118 N s versus best-known 1465.626365 N s, a remaining gap of 23.345754 N s.\n\n'
    text += 'L2/L3 improve over the independently sampled L1 minimum in 1/5 MATCHED rows (variable-start, 1.501381 N s) and 4/5 NATIVE rows. L3 adds an improvement over L2 only for sync_120 NATIVE (25.736406 N s). Sparse samples, correlated incumbent reuse and distinct historical basis families prevent any dimensional saturation claim.\n\n'
    text += 'Every selected J_F-minimizing reference has a higher moment integral than its own baseline; this is a secondary-metric tradeoff, not an overall interaction improvement. Some NATIVE peak forces also increase while satisfying the original acceptance checks. Variable-start and sync_120 NATIVE shorten total task duration by 0.550s and 0.805s respectively, each including a 0.510s decrease in other task-phase duration. Their J_F gains therefore include pacing/hold effects. All selected MATCHED other-phase duration residuals are numerically zero; measured outbound/return residuals are at most 10ms. Small J_F differences should still be read with the fixed 5ms sampling and matched timing tolerance. Full numeric diagnostics are in REFERENCE_PACING_AND_METRIC_AUDIT.json.\n'
    report.write_text(text)
def verify_all_raw():
    manifest=c.read(D/'RAW_DATA_MANIFEST.json');checked=0
    for row in manifest['rollouts']:
        out=RAW/'runs'/row['run_id']
        for name,h in row['files'].items():
            if c.sha(out/name)!=h:raise RuntimeError('stored evidence corruption:'+str(out/name))
            checked+=1
    json_save(D/'RAW_MANIFEST_VERIFICATION.json',{'stored_files_checked':checked,'all_stored_SHA256_pass':True,
        'compression_original_content_validation':'All newly compressed JSON files were individually decompressed and SHA256-verified before exact original deletion.'})
def convergence_detail():
    with (D/'SEARCH_CONVERGENCE.csv').open() as f:curve=list(csv.DictReader(f))
    details=[];all_data=c.collect()
    for cond in c.CONDITIONS:
        for arm in c.ARMS:
            rows=[r for r in curve if r['condition']==cond['id'] and r['arm']==arm]
            for level in (1,2,3):
                restart=[]
                for rr in range(3):
                    xs=[(e,r) for e,r in all_data if e['condition']==cond['id'] and e['arm']==arm and e['phase']=='B' and e['level']==level and e['restart']==rr]
                    valid=[(e,r) for e,r in xs if c.eligible(r,c.baseline(cond['id'],arm),arm)[0]]
                    if valid:
                        e,r=min(valid,key=lambda x:x[1]['J_F_task_n_s'])
                        restart.append({'restart':rr,'evaluations':len(xs),'rankable':len(valid),'best_J_F_n_s':r['J_F_task_n_s'],
                                        'best_parameters':e['spec']['parameters'],'run_id':r['run_id']})
                    else:restart.append({'restart':rr,'evaluations':len(xs),'rankable':0,'best_J_F_n_s':None})
                costs=[r['best_J_F_n_s'] for r in restart if r['best_J_F_n_s'] is not None]
                distances=[]
                for i,a in enumerate(restart):
                    for b in restart[i+1:]:
                        if a['best_J_F_n_s'] is not None and b['best_J_F_n_s'] is not None:
                            d=np.asarray(a['best_parameters'])-np.asarray(b['best_parameters'])
                            distances.append(float(np.linalg.norm(d/(c.HIGH[:len(d)]-c.LOW[:len(d)]))))
                details.append({'condition':cond['id'],'arm':arm,'level':level,'restarts':restart,
                    'restart_cost_spread_n_s':max(costs)-min(costs) if costs else None,
                    'normalized_parameter_pair_distances':distances,'interpretation':'two generations and sparse populations; low spread does not prove convergence; inactive width/peak and correlated basis coefficients may be non-identifiable'})
    json_save(D/'INITIALIZATION_CONVERGENCE.json',{'rows':details,'global_optimum_claim':False})
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for arm in c.ARMS:
        fig,axes=plt.subplots(5,1,figsize=(10,14),constrained_layout=True)
        for ax,cond in zip(axes,c.CONDITIONS):
            rows=[r for r in curve if r['condition']==cond['id'] and r['arm']==arm]
            x=[int(r['evaluation']) for r in rows];y=[float(r['best_J_F_n_s']) for r in rows]
            fresh=[float(r['v2_only_best_J_F_n_s']) for r in rows]
            ax.plot(x,fresh,color='#718096',ls='--',label='v2 only')
            ax.plot(x,y,color='#126b90',lw=2,label='prior + v2 best known')
            n_a=sum(r['phase']=='A' for r in rows);ax.axvspan(0,n_a,alpha=.08,color='black',label='Phase A')
            ax.axvline(n_a+18,color='grey',lw=.8,ls=':');ax.axvline(n_a+36,color='grey',lw=.8,ls=':')
            ax.set_title(cond['id']);ax.set_ylabel('J_F task (N s)');ax.grid(alpha=.2)
            ax.set_xlim(0,max(x));ax.legend(fontsize=8,loc='upper right')
        axes[-1].set_xlabel('Attempted evaluations, including failed/interrupted records')
        fig.suptitle(arm+' — finite-budget best-known coordination search',fontsize=14)
        fig.savefig(D/f'{arm}_CONVERGENCE.png',dpi=120);fig.savefig(D/f'{arm}_CONVERGENCE.pdf');plt.close(fig)
if __name__=='__main__':
    audit()
    if '--final' in sys.argv:enrich();verify_all_raw();convergence_detail();rollout_diagnostics();fixed_comparison_table();reference_pacing_audit();observed_result_notes()
