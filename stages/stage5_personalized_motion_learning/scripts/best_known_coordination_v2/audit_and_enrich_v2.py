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
        e['Human_model_state'].update(task_start_deployable_beta=trace['task_beta'][task].tolist(),
            task_start_deployable_residual_weights_nm=trace['task_residual_weights_nm'][task].tolist(),
            task_start_belief_sequence=int(trace['belief_sequence'][task]),
            recorded_start_decision_context={k:first[k] for k in first if 'belief' in k or 'geometry' in k or 'state' in k},
            start_execution_screen_from_initial_state_trace=chosen.get('execution_screen'))
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
    if '--final' in sys.argv:enrich();verify_all_raw();convergence_detail()
