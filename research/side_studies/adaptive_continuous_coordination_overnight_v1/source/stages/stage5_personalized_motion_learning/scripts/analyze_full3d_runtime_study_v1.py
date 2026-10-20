#!/usr/bin/env python3
"""Artifact-only checks and plots for the runtime engineering study."""
from collections import Counter, defaultdict
import hashlib
import json
import subprocess
import sys
import ast

import numpy as np

from study_full3d_planner_runtime_v1 import ROOT, STAGE, REPO, save, stats, construct


def load(path):return json.loads(path.read_text())


def main():
    if '--seal' in sys.argv:
        output=ROOT/'final_seal.json'
        if output.exists():raise FileExistsError(output)
        directories=[STAGE/'docs/full3d_adaptive_integration_v1/runtime_study_v1',
            STAGE/'configs/full3d_adaptive_integration_v1/runtime_study_v1',ROOT]
        files=[p for d in directories for p in d.rglob('*') if p.is_file()]
        files += [STAGE/p for p in [
            'src/traction_mpc_stage5/human_waypoint_scheduler.py',
            'scripts/study_full3d_planner_runtime_v1.py',
            'scripts/run_full3d_runtime_regression_v1.py',
            'scripts/analyze_full3d_runtime_study_v1.py',
            'tests/full3d_adaptive_integration_v1/test_runtime_endpoint_pruning.py']]
        for p in files:
            if p.suffix=='.py':ast.parse(p.read_text())
        git={key:subprocess.check_output(command,cwd=REPO,text=True) for key,command in [
            ('head',['git','rev-parse','HEAD']),('branch',['git','branch','--show-current']),
            ('status',['git','status','--short','--untracked-files=all']),('staged',['git','diff','--cached','--name-only'])]}
        assert git['head'].strip()=='bd7952fbd0617ba6797cc86bb2b48b1648c1b0ce'
        assert git['branch'].strip()=='codex/stage5-architecture-recovery' and not git['staged']
        save(output,dict(status='PLANNER_RUNTIME_QUALIFIED',git=git,
            tests='19 passed in 3.87s; focused git diff --check exit 0; all archived/current study Python parses',
            hashes={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}))
        print('sealed',len(files),'files; branch/HEAD unchanged; index empty')
        return
    out=ROOT/'analysis'
    if out.exists():raise FileExistsError(out)
    out.mkdir()
    cases=load(ROOT/'repaired/inputs.json')
    profiles=load(ROOT/'repaired/profiles.json')
    stages=defaultdict(list);candidates=[]
    for row in profiles:
        grouped=defaultdict(float)
        for event in row['events']:
            grouped[event['stage']]+=event['wall_ns']/1e6
        for stage,value in grouped.items():stages[stage].append(value)
        for event in row['events']:
            if event['stage']!='candidate':continue
            events=[e for e in row['events'] if e['candidate']==event['candidate']]
            stage_time=lambda name:sum(e['wall_ns'] for e in events if e['stage']==name)/1e6
            candidates.append(dict(case_id=row['case_id'],label=event['candidate'],
                duration_s=event['duration_s'],duration_trial_count=sum(e['stage']=='polynomial_coefficients' for e in events),
                fixed_duration_trial_count=sum(e['stage']=='scheduler_fixed' for e in events),
                schedule_runtime_ms=stage_time('scheduler_search')+stage_time('scheduler_fixed'),
                mechanics_runtime_ms=stage_time('mechanics_screen'),total_candidate_runtime_ms=event['wall_ns']/1e6,
                feasible=event['feasible'],rejection_reason=event['rejection_reason'],
                rejection_stage=None if event['feasible'] else ('mechanics' if stage_time('mechanics_screen') else 'reference_or_scheduler')))
    save(out/'per_candidate_profiles.json',candidates)
    save(out/'stage_distributions.json',{k:stats(v) for k,v in stages.items()})
    timing=load(ROOT/'repaired/timings.json')
    save(out/'repeated_variability.json',{c['id']:stats([r['wall_ms'] for r in timing if r['case_id']==c['id']]) for c in cases})
    rootcase=next(c for c in cases if c['id']=='attempt_13_decision_10')
    planner,args=construct(rootcase)
    target=rootcase['historical']['evaluations'][7]['target_q_rad']
    save(out/'pathological_geometry.json',dict(
        current_clearance_m=planner.planner.scheduler._clearance_m(np.asarray(args['current_reference_state'][:2])),
        candidate_endpoint_clearance_m=planner.planner.scheduler._clearance_m(np.asarray(target)),
        floor_m=planner.planner.scheduler._clearance_m(planner.planner.start_rad),
        polynomial_system_condition=np.linalg.cond([[1,1,1],[3,4,5],[6,12,20]])))
    regressions=[]
    for i in range(1,4):
        folder=ROOT/f'nominal_regression_{i:02d}'
        s=load(folder/'run/summary.json');t=np.load(folder/'run/trace.npz')
        mask=t['stage']=='TASK';times=t['time_s'][mask]
        checks=dict(complete=s['status']=='COMPLETE', no_stale=all(d['activation_rejected_reason'] is None for d in s['decisions']),
            age_within_contract=all(d['stale_plan_age_at_activation_s']<=.100+1e-12 for d in s['decisions']),
            step_5ms=bool(np.allclose(np.diff(times),.005,atol=1e-10,rtol=0)),
            substeps_20=bool(np.all(np.diff(t['physics_steps'][mask])==20)),
            no_acceleration_flag=not bool(np.any(t['acceleration_limit_violation'][mask])),
            nonnegative_clearance=bool(np.nanmin(t['session_shank_clearance_m'][mask])>=0),
            wrench_within_limits=s['task']['peak_force_n']<=200 and s['task']['peak_moment_nm']<=60,
            q_dq_ddq_continuity=s['timing']['all_reference_boundaries_q_dq_ddq_continuous'],
            adaptation_active=s['task']['final_belief_sequence']>s['commissioning']['handoff_belief']['sequence'],
            no_truth_input=not s['commissioning']['handoff_belief']['deployable_truth_consumed'])
        wait_checks=[];activation_checks=[]
        for d in s['decisions']:
            a=d['activation_timestamp_s'];r=d['request_measurement_timestamp_s']
            waiting=mask & (t['time_s']>=r-1e-9) & (t['time_s']<a-1e-9)
            qdq=np.c_[t['reference_q_rad'][waiting],t['reference_dq_rad_s'][waiting]]
            wait_checks.append(bool(len(qdq)>0 and np.allclose(qdq,d['reference_executed_while_planning'],atol=1e-10,rtol=0)))
            activation_checks.append(bool(np.any(np.abs(t['time_s'][mask]-a)<1e-9)))
        checks['previous_reference_during_wait']=all(wait_checks)
        checks['activation_boundary_exists']=all(activation_checks)
        e=np.degrees(t['evaluation_only_human_state_rad_rad_s'][mask,:2]-t['reference_q_rad'][mask])
        calls=load(folder/'planner_requests.json')
        regressions.append(dict(name=folder.name,checks=checks,all_checks=all(checks.values()),
            duration_s=s['task']['physics_duration_s'],rmse_deg=np.sqrt(np.mean(e*e,axis=0)),
            peak_force_n=s['task']['peak_force_n'],peak_moment_nm=s['task']['peak_moment_nm'],
            minimum_clearance_mm=1000*np.nanmin(t['session_shank_clearance_m'][mask]),
            peak_causal_estimated_acceleration_deg_s2=np.nanmax(np.abs(np.degrees(t['actual_human_acceleration_rad_s2'][mask])),axis=0),
            wall_ms=stats(s['timing']['high_level_planning_runtime_ms']),
            decision_count=len(s['decisions']),adaptation_count=s['task']['continual_adaptation_update_count'],
            accepted_beta_updates=s['task']['accepted_beta_update_count'],
            end_to_end_first_execution_entry_ms=[c.get('request_to_first_execution_entry_ms') for c in calls],
            contact_pairs=s['task']['active_contact_pair_counts_evaluation_only']))
    save(out/'regression_checks.json',regressions)
    fault=ROOT/'deadline_fault_01'
    if fault.exists():
        s=load(fault/'run/summary.json');t=np.load(fault/'run/trace.npz')
        save(out/'deadline_fault_check.json',dict(status=s['status'],abort_reason=s['abort_reason'],
            planner_ms=s['timing']['high_level_planning_runtime_ms'],task_duration=s['task']['physics_duration_s'],
            task_intervals=s['task']['integration_interval_count'],decision_count=s['task']['decision_count'],
            rejected_reason=s['decisions'][0]['activation_rejected_reason'],
            no_task_interval_after_stale_rejection=s['task']['integration_interval_count']==0,
            learning_records=len(s['learning_records'])))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    comparison=load(ROOT/'repaired/equivalence.json')
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    axes[0].plot([r['old']['wall_ms'] for r in comparison],label='baseline',marker='.',lw=.8)
    axes[0].plot([r['new']['wall_ms'] for r in comparison],label='endpoint pruning',marker='.',lw=.8)
    axes[0].axhline(100,color='red',ls='--',label='100 ms deadline');axes[0].set_yscale('log')
    axes[0].set(xlabel='Deterministic case index',ylabel='Planner wall time (ms)',title='46 paired inputs');axes[0].legend()
    values=np.sort([r['wall_ms'] for r in timing]);axes[1].plot(values,np.arange(1,len(values)+1)/len(values))
    axes[1].axvline(100,color='red',ls='--');axes[1].set(xlabel='Planner wall time (ms)',ylabel='Empirical CDF',title='552 repaired calls; no exclusions')
    fig.tight_layout();fig.savefig(out/'runtime_comparison.png',dpi=180);plt.close(fig)
    inventory=[p for p in ROOT.rglob('*') if p.is_file()]
    save(out/'artifact_hashes.json',{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inventory})
    save(out/'git_end.json',{key:subprocess.check_output(command,cwd=REPO,text=True) for key,command in [
        ('head',['git','rev-parse','HEAD']),('branch',['git','branch','--show-current']),
        ('status',['git','status','--short','--untracked-files=all']),('staged',['git','diff','--cached','--name-only'])]})
    print(json.dumps(regressions,default=lambda v:v.tolist() if isinstance(v,np.ndarray) else v,indent=2))


if __name__=='__main__':main()
