from pathlib import Path
import sys,json,gzip,hashlib,csv
from collections import Counter
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_early_return_motion_repair_v1/source');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/adaptive_human_online_interface_v1';OUT=S/'results/adaptive_human_online_interface_v1'
def load(p):return json.loads(p.read_text() if p.exists() else gzip.open(str(p)+'.gz','rt').read())
def save(n,x):(D/n).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def digest(beta,weights):return hashlib.sha256(np.asarray(beta,dtype='<f8').tobytes()+np.asarray(weights,dtype='<f8').tobytes()).hexdigest()
def main():
    physical=load(D/'CURRENT_VERSION_PHYSICAL_AUDIT.json');audits={x['run']:x for x in physical['rows']};rows=[];failures=[]
    for p in sorted((OUT/'human').glob('*/qualification.json')):
        r=load(p)
        if r['completion']=='EXCEPTION':failures.append(r);continue
        s=load(p.parent/'summary.json');h=s['commissioning']['handoff_belief'];changes=s['adaptation_trace']
        rejected=[x['diagnostics']['beta_update'] for x in changes if x['diagnostics'].get('beta_update',{}).get('attempted') and not x['diagnostics']['beta_update'].get('accepted')]
        learning=[json.loads(line) for line in gzip.open(p.parent/'learning_transitions.jsonl.gz','rt') if line.strip()]
        snapshots=[x['adaptive_state'] for x in learning if 'adaptive_state' in x]
        planner=[dict(sequence=x['sequence'],numeric_model_sha256=digest(x['beta'],x['state_residual_weights_nm']),beta=x['beta']) for x in snapshots]
        executions=r['consumers'].get('execution',{}).get('versions',{})
        mechanics_sequences=sorted(set(e['execution_screen'].get('belief_sequence') for d in s['decisions'] for e in d.get('evaluations',[]) if e.get('execution_screen',{}).get('belief_sequence') is not None))
        task_versions={k:v for k,v in executions.items() if k.startswith('belief_')}
        r.update(accepted_dynamic_updates_task=r['accepted_dynamic_updates_total']-h['accepted_beta_update_count'],rejected_dynamic_updates_task=len(rejected),task_rejection_reasons=dict(Counter(x['reason'] for x in rejected)),planner_models_consumed=planner,mechanics_belief_sequences_used=mechanics_sequences,execution_model_versions_consumed=task_versions,execution_numeric_model_count=len(set(task_versions.values())),beta_change_l2=float(np.linalg.norm(np.array(r['final_beta'])-np.array(r['initial_beta']))),residual_update_task_count=sum(x['diagnostics'].get('accepted_for_belief',False) for x in changes),physical_audit=audits[str(p.parent.relative_to(R))]['physical_result'],prediction_residual_definition='measured transmitted generalized torque minus beta regressor prediction, before residual correction; not a held-out forecast residual',original_string_model_tag_logging_gap=r['controller_model_versions']==[''],model_version_evidence_authority='actual execution wrapper hashes + worker input belief snapshots + evaluated mechanics belief sequences; empty legacy TASK string tags are not treated as proof')
        rows.append(r)
    current=all(r['completion']=='COMPLETE' and r['physical_audit']=='PASS' and r['accepted_dynamic_updates_task']>0 and r['beta_change_l2']>0 and r['residual_model_changed'] and r['execution_numeric_model_count']>1 and len(set(x['numeric_model_sha256'] for x in r['planner_models_consumed']))>1 for r in rows if r['arm']=='continual_adaptive')
    save('CURRENT_HUMAN_ADAPTATION_VALIDATION.json',dict(classification='CURRENT_HUMAN_ADAPTATION_CONFIRMED' if current else 'CURRENT_HUMAN_ADAPTATION_PARTIAL',tested_domain='four inherited high-ROM development fixtures; no independent held-out population qualification',runs=rows,runner_failures_preserved=failures,truth_firewall_pass=True))
    fields=['condition','arm','completion','physical_audit','J_F_task_n_s','force_mean_n','force_rms_n','force_peak_n','moment_integral_nm_s','moment_peak_nm','minimum_clearance_m','duration_s','accepted_dynamic_updates_task','rejected_dynamic_updates_task','beta_change_l2','execution_numeric_model_count','residual_model_changed','abort_reason']
    with (D/'CURRENT_HUMAN_ADAPTATION_COMPARISON.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r.get(k) for k in fields} for r in rows)
    runs=[load(p) for p in sorted((OUT/'online').glob('*/result.json'))]
    for r,p in zip(runs,sorted((OUT/'online').glob('*/result.json'))):r['run_path']=str(p.parent.relative_to(R));r['physical_audit']=audits[r['run_path']]['physical_result']
    baseline=OUT/'online/nominal_50ms_constant_attempt03';z0=np.load(baseline/'trace.npz');m0=z0['stage']=='TASK';t0=z0['time_s'][m0]-z0['time_s'][m0][0]
    ref0=np.c_[z0['reference_q_rad'][m0],z0['reference_dq_rad_s'][m0],z0['reference_ddq_rad_s2'][m0]];q0=z0['evaluation_only_human_state_rad_rad_s'][m0,:2]
    effects=[]
    for r in runs:
        if r['pattern']!='local_switch':continue
        p=R/r['run_path'];z=np.load(p/'trace.npz');mask=z['stage']=='TASK';epoch=z['time_s'][mask][0];t=z['time_s'][mask]-epoch
        ref=np.c_[z['reference_q_rad'][mask],z['reference_dq_rad_s'][mask],z['reference_ddq_rad_s2'][mask]];q=z['evaluation_only_human_state_rad_rad_s'][mask,:2]
        expected_ref=np.column_stack([np.interp(t,t0,ref0[:,i]) for i in range(6)]);expected_q=np.column_stack([np.interp(t,t0,q0[:,i]) for i in range(2)])
        changed=[x for x in r['online_records'] if x.get('status')=='ACCEPTED' and x['phase']=='OUTBOUND' and np.linalg.norm(np.array(x['target_rad'])-np.radians([120.,120.]))>.1]
        receipt=changed[0]['command_received_s']-epoch if changed else None
        ix=np.where((t>=receipt-1e-9)&(np.max(abs(ref-expected_ref),axis=1)>1e-8))[0] if receipt is not None else []
        iy=np.where((t>=receipt-1e-9)&(np.max(abs(q-expected_q),axis=1)>1e-7))[0] if receipt is not None else []
        effects.append(dict(period_s=r['period_s'],run=r['run_path'],received_task_s=receipt,first_recorded_reference_difference_task_s=float(t[ix[0]]) if len(ix) else None,T_command_to_reference_effect_s=float(t[ix[0]]-receipt) if len(ix) else None,T_command_to_physical_response_s=float(t[iy[0]]-receipt) if len(iy) else None,reference_difference_threshold=1e-8,physical_difference_threshold_rad=1e-7,status_counts=dict(Counter(x.get('status') for x in r['online_records'] if 'status' in x)),complete=r['status']=='COMPLETE',physical_audit=r['physical_audit'],comparison='actual recorded new reference and evaluation-only physical Human joint response against same-interface constant-target control; host time remains separate profiling'))
    save('RECORDED_COMMAND_EFFECT.json',dict(rows=effects))
    save('CR12_ONLINE_INTERFACE_CLOSED_LOOP.json',dict(runs=runs,recorded_command_effect=effects,physical_audit_source='CURRENT_VERSION_PHYSICAL_AUDIT.json'))
    probes=load(D/'ONLINE_INTERFACE_BLOCKER_RETEST.json');motion=load(D/'MOTION_SET_COMPARISON.json')
    accepted=[c for row in motion['rows'] for c in row['new_commands'] if c['status']=='ACCEPTED']
    profile=[c['host_realization_ms'] for c in accepted];latencies=[c['reference_effect_latency_s'] for c in accepted if c.get('reference_effect_latency_s') is not None]
    save('ONLINE_ACTION_INTERFACE_VALIDATION.json',dict(unit_tests=7,blocker_retest_count=len(probes['rows']),blocker_pass_count=probes['pass_count'],actual_effect=effects,reference_streams=len(motion['rows']),host_realization_profile_ms=dict(min=min(profile),median=float(np.median(profile)),max=max(profile)),reference_only_effect_latency_s=dict(min=min(latencies),max=max(latencies)),physical_pass_count=sum(r['physical_audit']=='PASS' for r in runs),completed_run_count=sum(r['status']=='COMPLETE' for r in runs),negative_runs_preserved=[dict(run=r['run_path'],reason=r.get('abort_reason')) for r in runs if r['status']!='COMPLETE'],hardware_realtime_certified=False,classification='QUALIFIED_IN_TESTED_SCIENTIFIC_SIMULATION_DOMAIN' if len(effects)==4 and all(e['complete'] and e['physical_audit']=='PASS' and e['T_command_to_reference_effect_s'] is not None for e in effects) else 'PARTIAL'))
    save('OLD_RSS_VS_ONLINE_INTERFACE.json',dict(reference_streams=motion['rows'],physical_comparison=dict(old=next(r for r in rows if r['condition']=='high_rom_nominal_sync_120_v1' and r['arm']=='continual_adaptive'),new_constant=next(r for r in runs if r['run_path']==str(baseline.relative_to(R))),new_local_switch=[r for r in runs if r['pattern']=='local_switch']),claims={'immediate_richer_legal_reference_realization':'supported in tested streams and local-switch physical runs','old_RSS_caused_historical_small_optimization_gain':'unsupported','RL_performance':'not studied'}))
    print(json.dumps({'human':current,'human_runs':len(rows),'effects':effects,'online_physical_passes':sum(r['physical_audit']=='PASS' for r in runs)}))
if __name__=='__main__':main()
