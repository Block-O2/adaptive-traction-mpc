"""Descriptive paired analysis of safe counterfactual action/horizon rollouts."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,statistics
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull
from scipy.stats import pearsonr,spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

STAGE=Path(__file__).resolve().parents[2]
DOC=STAGE/'docs/safe_action_horizon_exploration_v1'
RUNS=STAGE/'results/safe_action_horizon_exploration_v1/runs'
BASE=STAGE/'results/zero_value_30rep_baseline_v3/formal_session_01'
SD=.6425003226154133
RANGE=1.9148941252947225


def write(name,value):
    (DOC/name).write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def stats(values):
    values=[float(x) for x in values if x is not None and math.isfinite(float(x))]
    if not values:return {'count':0}
    return {'count':len(values),'min':min(values),'q25':float(np.percentile(values,25)),'median':float(np.median(values)),'mean':float(np.mean(values)),'q75':float(np.percentile(values,75)),'max':max(values),'std_sample':float(np.std(values,ddof=1)) if len(values)>1 else None}

def correlation(x,y):
    a=np.asarray(x,dtype=float);b=np.asarray(y,dtype=float)
    if len(a)<3 or np.std(a)==0 or np.std(b)==0:return {'n':len(a),'pearson':None,'spearman':None}
    return {'n':len(a),'pearson':float(pearsonr(a,b).statistic),'spearman':float(spearmanr(a,b).statistic)}

def task_trace(path):
    with np.load(path) as trace:
        mask=trace['stage']=='TASK'
        return {key:np.asarray(trace[key][mask]) for key in ('time_s','reference_q_rad','reference_ddq_rad_s2','evaluation_only_human_state_rad_rad_s','physical_cuff_force_world_n')}

def align_divergence(path,baseline):
    current=task_trace(path)
    t0=baseline['time_s']-baseline['time_s'][0]
    t1=current['time_s']-current['time_s'][0]
    t=t0[t0<=min(t0[-1],t1[-1])+1e-10]
    def sample(field):
        b=np.asarray(baseline[field],dtype=float)
        c=np.asarray(current[field],dtype=float)
        if b.ndim==1:b=b[:,None];c=c[:,None]
        interp=np.stack([np.interp(t,t1,c[:,j]) for j in range(c.shape[1])],axis=1)
        return b[:len(t)],interp
    ref_b,ref_c=sample('reference_q_rad')
    human_b,human_c=sample('evaluation_only_human_state_rad_rad_s')
    force_b,force_c=sample('physical_cuff_force_world_n')
    jerk=np.diff(np.asarray(current['reference_ddq_rad_s2'],dtype=float),axis=0)/.005
    return {'reference_path_rms_distance_deg':float(np.degrees(np.sqrt(np.mean(np.sum((ref_c-ref_b)**2,axis=1))))),'human_q_rms_distance_deg':float(np.degrees(np.sqrt(np.mean(np.sum((human_c[:,:2]-human_b[:,:2])**2,axis=1))))),'human_dq_rms_distance_deg_s':float(np.degrees(np.sqrt(np.mean(np.sum((human_c[:,2:]-human_b[:,2:])**2,axis=1))))),'force_vector_rms_divergence_n':float(np.sqrt(np.mean(np.sum((force_c-force_b)**2,axis=1)))),'final_human_q_distance_deg':float(np.degrees(np.linalg.norm(current['evaluation_only_human_state_rad_rad_s'][-1,:2]-baseline['evaluation_only_human_state_rad_rad_s'][-1,:2]))),'reference_jerk_rms_rad_s3':float(np.sqrt(np.mean(np.sum(jerk**2,axis=1))))}

def first_action_metrics(result,baseline_decision):
    explored=next((a for a in result.get('exploration_executed_actions',[]) if a['label'] and a['label'].startswith('explore')),None)
    if explored is None:return {}
    base=np.asarray(baseline_decision['executed_action_delta_q_rad'],dtype=float)
    action=np.asarray(explored['delta_q_rad'],dtype=float)
    target=np.asarray(explored['target_q_rad'],dtype=float)
    candidates=np.asarray([e['target_q_rad'] for e in baseline_decision['evaluations'] if e['feasible']],dtype=float)
    nearest=float(np.degrees(np.min(np.linalg.norm(candidates-target,axis=1))))
    if len(candidates)>=3 and np.linalg.matrix_rank(candidates-candidates[0])==2:
        hull=ConvexHull(candidates)
        outside=bool(np.max(hull.equations[:,:2]@target+hull.equations[:,2])>1e-10)
    else:
        outside=nearest>1e-8
    return {'first_perturbed_phase':explored['phase'],'first_action_delta_q_deg':np.degrees(action).tolist(),'baseline_first_action_delta_q_deg':np.degrees(base).tolist(),'first_action_deviation_deg':float(np.degrees(np.linalg.norm(action-base))),'first_target_nearest_baseline_candidate_deg':nearest,'first_target_outside_baseline_candidate_hull':outside,'hip_knee_increment_ratio':float(abs(action[0])/(abs(action[1])+1e-12))}

def pairwise_order(rows,short_key):
    agree=disagree=0
    for cp in (1,5,15,25):
        group=[r for r in rows if r['checkpoint_rep']==cp and r.get(short_key) is not None and r.get('benefit_n_s') is not None]
        for i,a in enumerate(group):
            for b in group[i+1:]:
                x=a[short_key]-b[short_key];y=a['benefit_n_s']-b['benefit_n_s']
                if abs(x)<1e-6 or abs(y)<1e-6:continue
                if x*y>0:agree+=1
                else:disagree+=1
    return {'concordant_pairs':agree,'discordant_pairs':disagree,'agreement_fraction':agree/(agree+disagree) if agree+disagree else None}

def make_plots(valid):
    folder=DOC/'figures';folder.mkdir(exist_ok=True)
    plt.style.use('seaborn-v0_8-whitegrid')
    def save(name):plt.tight_layout();plt.savefig(folder/name,dpi=160);plt.close()
    benefit=np.asarray([r['benefit_n_s'] for r in valid])
    plt.figure(figsize=(7,4));plt.hist(benefit,bins=25,color='#246b8f');plt.axvline(0,color='black');plt.xlabel('Benefit (N s)');plt.ylabel('Valid rollouts');save('benefit_distribution.png')
    plt.figure(figsize=(7,4));
    for amplitude,color in zip(('very_small','small','fine_low','medium','fine_mid','fine_high','large'),plt.cm.viridis(np.linspace(0,1,7))):
        group=[r for r in valid if r['amplitude']==amplitude]
        if group:
            plt.scatter([r.get('first_action_deviation_deg',0) for r in group],[r['benefit_n_s'] for r in group],label=amplitude,color=color,alpha=.65)
    plt.axhline(0,color='black');plt.xlabel('First action deviation from baseline (deg)');plt.ylabel('Benefit (N s)');plt.legend();save('benefit_vs_action_amplitude.png')
    plt.figure(figsize=(7,4));plt.boxplot([[r['benefit_n_s'] for r in valid if r['horizon']==h] for h in ('H1','H2','H3','H4')],tick_labels=('H1','H2','H3','H4'));plt.axhline(0,color='black');plt.ylabel('Benefit (N s)');save('benefit_vs_horizon.png')
    plt.figure(figsize=(7,4));plt.boxplot([[r['benefit_n_s'] for r in valid if r['checkpoint_rep']==cp] for cp in (1,5,15,25)],tick_labels=('Rep2','Rep6','Rep16','Rep26'));plt.axhline(0,color='black');plt.ylabel('Benefit (N s)');save('checkpoint_vs_benefit.png')
    plt.figure(figsize=(6,5));plt.scatter([r['short_benefit_n_s'] for r in valid],[r['benefit_n_s'] for r in valid],alpha=.65);plt.axhline(0,color='black');plt.axvline(0,color='black');plt.xlabel('First 1.5 s Benefit (N s)');plt.ylabel('Full task Benefit (N s)');save('short_vs_full_benefit.png')
    plt.figure(figsize=(7,4));plt.scatter([r['reference_path_rms_distance_deg'] for r in valid],[r['benefit_n_s'] for r in valid],alpha=.65);plt.axhline(0,color='black');plt.xlabel('Reference path RMS divergence (deg)');plt.ylabel('Benefit (N s)');save('action_diversity_vs_benefit.png')

def main(final=False):
    matched={cp:json.loads((RUNS/f'matched_replay_rep{cp+1:02d}'/'rollout_result.json').read_text()) for cp in (1,5,15,25)}
    baseline_trace={cp:task_trace(RUNS/f'matched_replay_rep{cp+1:02d}'/f'rep_{cp+1:02d}'/'trace.npz') for cp in matched}
    baseline_decisions={cp:json.loads((BASE/f'rep_{cp+1:02d}'/'summary.json').read_text())['decisions'][0] for cp in matched}
    rows=[];raw_receipts={}
    for path in sorted(RUNS.glob('*/rollout_result.json')):
        result=json.loads(path.read_text());run_id=result['run_id']
        raw_receipts[run_id]={'rollout_result_sha256':digest(path),'source_checkpoint_sha256':result.get('source_checkpoint_sha256'),'raw_files_sha256':result.get('raw_files_sha256',{}),'status':result['status']}
        if not run_id.startswith(('coarse_','refine_','cross_')):continue
        pattern=result['action']['perturbation'];cp=result['source_checkpoint_repetition']
        row={'run_id':run_id,'campaign_stage':run_id.split('_')[0],'checkpoint_rep':cp,'target_rep':cp+1,**pattern,'status':result['status'],'failure_reason':result.get('failure_reason'),'physical_validity':result.get('physical_validity'),'scientific_validity':result.get('scientific_validity'),'matched_baseline_J_F_task_n_s':result['matched_baseline_J_F_task_n_s'],'J_F_task_n_s':result.get('J_F_task_n_s'),'J_F_session_n_s':result.get('J_F_session_n_s'),'benefit_n_s':result.get('benefit_n_s'),'force_peak_n':result.get('force_peak_n'),'moment_peak_nm':result.get('moment_peak_nm'),'moment_integral_nm_s':result.get('moment_integral_nm_s'),'minimum_deployable_clearance_m':result.get('minimum_deployable_clearance_m'),'completion_time_s':result.get('completion_time_s'),'horizons':result.get('horizons'),'source_checkpoint_sha256':result['source_checkpoint_sha256']}
        if row['status']=='VALID':
            h=row['horizons'];bh=matched[cp]['horizons']
            row.update(immediate_benefit_n_s=bh['immediate_0p5s_n_s']-h['immediate_0p5s_n_s'],short_benefit_n_s=bh['short_1p5s_n_s']-h['short_1p5s_n_s'],outbound_benefit_n_s=bh['outbound_n_s']-h['outbound_n_s'],benefit_percent=100*row['benefit_n_s']/row['matched_baseline_J_F_task_n_s'],benefit_baseline_std_units=row['benefit_n_s']/SD,benefit_baseline_range_units=row['benefit_n_s']/RANGE,peak_force_change_n=row['force_peak_n']-matched[cp]['force_peak_n'],clearance_change_m=row['minimum_deployable_clearance_m']-matched[cp]['minimum_deployable_clearance_m'])
            baseline_time=matched[cp]['completion_time_s']
            baseline_mean_force=matched[cp]['J_F_task_n_s']/baseline_time
            exploration_mean_force=row['J_F_task_n_s']/row['completion_time_s']
            row.update(baseline_completion_time_s=baseline_time,completion_time_change_s=row['completion_time_s']-baseline_time,baseline_mean_task_force_n=baseline_mean_force,mean_task_force_n=exploration_mean_force,mean_task_force_change_n=exploration_mean_force-baseline_mean_force,time_component_n_s=(baseline_time-row['completion_time_s'])*baseline_mean_force,mean_force_component_n_s=row['completion_time_s']*(baseline_mean_force-exploration_mean_force))
            row.update(first_action_metrics(result,baseline_decisions[cp]))
            row.update(align_divergence(path.parent/f'rep_{cp+1:02d}'/'trace.npz',baseline_trace[cp]))
        rows.append(row)
    valid=[r for r in rows if r['status']=='VALID']
    counts=dict(Counter(r['status'] for r in rows))
    write('ALL_EXPLORATORY_ROLLOUTS.json',rows)
    columns=['run_id','campaign_stage','checkpoint_rep','target_rep','direction','amplitude','horizon','status','failure_reason','physical_validity','scientific_validity','matched_baseline_J_F_task_n_s','J_F_task_n_s','J_F_session_n_s','benefit_n_s','benefit_percent','benefit_baseline_std_units','benefit_baseline_range_units','immediate_benefit_n_s','short_benefit_n_s','outbound_benefit_n_s','first_action_deviation_deg','first_target_outside_baseline_candidate_hull','reference_path_rms_distance_deg','human_q_rms_distance_deg','human_dq_rms_distance_deg_s','force_vector_rms_divergence_n','force_peak_n','moment_peak_nm','moment_integral_nm_s','minimum_deployable_clearance_m','completion_time_s','completion_time_change_s','mean_task_force_n','mean_task_force_change_n','time_component_n_s','mean_force_component_n_s']
    with (DOC/'ALL_EXPLORATORY_ROLLOUTS.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns,lineterminator='\n');writer.writeheader();writer.writerows({k:r.get(k) for k in columns} for r in rows)
    by=lambda key:{str(k):stats([r['benefit_n_s'] for r in valid if r[key]==k]) for k in sorted(set(r[key] for r in rows))}
    positive=[r for r in valid if r['benefit_n_s']>0]
    best=max(valid,key=lambda r:r['benefit_n_s']) if valid else None
    horizon={'schema':'horizon_headroom_summary_v1','counts':counts,'total_exploratory_attempts':len(rows),'valid_count':len(valid),'positive_count':len(positive),'benefit_n_s':stats([r['benefit_n_s'] for r in valid]),'positive_benefit_n_s':stats([r['benefit_n_s'] for r in positive]),'best':{k:best.get(k) for k in ('run_id','checkpoint_rep','direction','amplitude','horizon','benefit_n_s','benefit_percent','benefit_baseline_std_units','benefit_baseline_range_units')} if best else None,'by_checkpoint':by('checkpoint_rep'),'by_direction':by('direction'),'by_amplitude':by('amplitude'),'by_horizon':by('horizon'),'benefit_horizon_windows':{k:stats([r[k] for r in valid]) for k in ('immediate_benefit_n_s','short_benefit_n_s','outbound_benefit_n_s','benefit_n_s')},'duration_change_s':stats([r['completion_time_change_s'] for r in valid]),'mean_task_force_change_n':stats([r['mean_task_force_change_n'] for r in valid]),'benefit_vs_duration_reduction':correlation([-r['completion_time_change_s'] for r in valid],[r['benefit_n_s'] for r in valid]),'positive_benefit_time_component_n_s':stats([r['time_component_n_s'] for r in positive]),'positive_benefit_mean_force_component_n_s':stats([r['mean_force_component_n_s'] for r in positive]),'short_to_full_correlation':correlation([r['short_benefit_n_s'] for r in valid],[r['benefit_n_s'] for r in valid]),'immediate_to_full_correlation':correlation([r['immediate_benefit_n_s'] for r in valid],[r['benefit_n_s'] for r in valid]),'short_to_full_pairwise_rank':pairwise_order(valid,'short_benefit_n_s'),'short_positive_full_negative_count':sum(r['short_benefit_n_s']>0 and r['benefit_n_s']<0 for r in valid),'short_negative_full_positive_count':sum(r['short_benefit_n_s']<0 and r['benefit_n_s']>0 for r in valid),'baseline_variability_reference':{'std_n_s':SD,'range_n_s':RANGE,'descriptive_only':True}}
    write('HORIZON_HEADROOM_SUMMARY.json',horizon)
    diversity={'schema':'action_diversity_summary_v1','first_action_deviation_deg':stats([r.get('first_action_deviation_deg') for r in valid]),'first_target_nearest_baseline_candidate_deg':stats([r.get('first_target_nearest_baseline_candidate_deg') for r in valid]),'outside_baseline_first_candidate_hull_count':sum(r.get('first_target_outside_baseline_candidate_hull',False) for r in valid),'reference_path_rms_distance_deg':stats([r.get('reference_path_rms_distance_deg') for r in valid]),'human_q_rms_distance_deg':stats([r.get('human_q_rms_distance_deg') for r in valid]),'human_dq_rms_distance_deg_s':stats([r.get('human_dq_rms_distance_deg_s') for r in valid]),'force_vector_rms_divergence_n':stats([r.get('force_vector_rms_divergence_n') for r in valid]),'final_human_q_distance_deg':stats([r.get('final_human_q_distance_deg') for r in valid]),'reference_jerk_rms_rad_s3':stats([r.get('reference_jerk_rms_rad_s3') for r in valid]),'first_action_deviation_vs_benefit':correlation([r.get('first_action_deviation_deg',0) for r in valid],[r['benefit_n_s'] for r in valid]),'reference_path_divergence_vs_benefit':correlation([r['reference_path_rms_distance_deg'] for r in valid],[r['benefit_n_s'] for r in valid])}
    write('ACTION_DIVERSITY_SUMMARY.json',diversity)
    invalid=[r for r in rows if r['status']!='VALID']
    def category(r):
        reason=(r.get('failure_reason') or '').lower()
        if 'shank-table' in reason or 'clearance' in reason or 'geometry' in reason:return 'clearance_or_geometry'
        if 'mechanics' in reason or 'force' in reason or 'moment' in reason:return 'force_or_moment'
        if 'velocity' in reason or 'acceleration' in reason:return 'velocity_or_acceleration'
        if 'duration' in reason or 'window' in reason:return 'scheduling_time'
        return 'other_or_infrastructure'
    fail={'schema':'failure_infeasibility_summary_v1','counts':counts,'reason_categories':dict(Counter(category(r) for r in invalid)),'by_direction':{d:dict(Counter(r['status'] for r in rows if r['direction']==d)) for d in sorted(set(r['direction'] for r in rows))},'by_amplitude':{a:dict(Counter(r['status'] for r in rows if r['amplitude']==a)) for a in sorted(set(r['amplitude'] for r in rows))},'by_horizon':{h:dict(Counter(r['status'] for r in rows if r['horizon']==h)) for h in sorted(set(r['horizon'] for r in rows))},'invalid_samples':[{k:r.get(k) for k in ('run_id','checkpoint_rep','direction','amplitude','horizon','status','failure_reason')} for r in invalid]}
    write('FAILURE_INFEASIBILITY_SUMMARY.json',fail)
    baseline_fingerprint=json.loads((STAGE/'docs/zero_value_30rep_baseline_v3/PRODUCTION_FINGERPRINT_V3.json').read_text())
    source_checks={relative:{'baseline_sha256':expected,'current_sha256':digest(STAGE.parents[1]/relative),'match':digest(STAGE.parents[1]/relative)==expected} for relative,expected in baseline_fingerprint['source_config_contract_sha256'].items()}
    write('PRODUCTION_FINGERPRINT.json',{'schema':'safe_action_horizon_production_fingerprint_v1','source_checks':source_checks,'all_baseline_sources_unchanged':all(x['match'] for x in source_checks.values()),'exploration_code_sha256':{name:digest(Path(__file__).with_name(name)) for name in ('run_safe_action_horizon_rollout_v1.py','safe_action_horizon_adapter_v1.py','run_safe_action_horizon_coarse_v1.py','analyze_safe_action_horizon_v1.py')}})
    write('RAW_DATA_MANIFEST.json',{'schema':'safe_action_horizon_raw_manifest_v1','baseline_commit':'1f6308b820b64fc2cc7d8a01baa42e433835e68e','baseline_checkpoint_manifest_sha256':digest(STAGE/'docs/zero_value_30rep_baseline_v3/SESSION_CHECKPOINTS_MANIFEST_V3.json'),'rollouts':raw_receipts,'raw_trajectories_git_ignored':True})
    cross=[r for r in rows if r['campaign_stage']=='cross']
    write('CROSS_STATE_VALIDATION.json',{'schema':'cross_state_validation_v1','runs':cross,'by_pattern':{f"{d}/{a}/{h}":{str(cp):next((r['benefit_n_s'] for r in cross if r['direction']==d and r['amplitude']==a and r['horizon']==h and r['checkpoint_rep']==cp),None) for cp in (1,5,15,25)} for d,a,h in sorted(set((r['direction'],r['amplitude'],r['horizon']) for r in cross))}})
    if valid:make_plots(valid)
    if final:
        stage_counts=Counter(r['campaign_stage'] for r in rows)
        replay_pass={str(cp):bool(matched[cp].get('matched_replay_pass')) for cp in (1,5,15,25)}
        plan=json.loads((DOC/'CROSS_STATE_PLAN.json').read_text())
        pattern_valid={category:len(set(r['checkpoint_rep'] for r in cross if r['status']=='VALID' and any(e['run_id']==r['run_id'] and e['category']==category for e in plan['entries']))) for category in sorted(set(e['category'] for e in plan['entries']))}
        fingerprint=json.loads((DOC/'PRODUCTION_FINGERPRINT.json').read_text())
        gates={'matched_replays':all(replay_pass.values()),'coarse_120':stage_counts['coarse']==120,'refinement_64':stage_counts['refine']==64,'cross_state_20':stage_counts['cross']==20,'valid_at_least_60':len(valid)>=60,'cross_pattern_at_least_three_states':all(n>=3 for n in pattern_valid.values()),'production_fingerprint_unchanged':fingerprint['all_baseline_sources_unchanged']}
        if not all(gates.values()):
            raise RuntimeError('final completion gates not met: '+json.dumps(gates,sort_keys=True))
        write('STATE.json',{'schema':'safe_action_horizon_exploration_state_v1','status':'SAFE_ACTION_HORIZON_EXPLORATION_COMPLETE','total_exploratory_attempts':len(rows),'valid':len(valid),'infeasible':counts.get('INFEASIBLE',0),'invalid':counts.get('INVALID',0),'exception':counts.get('EXCEPTION',0),'baseline_replays_passed':replay_pass,'phase_counts':dict(stage_counts),'cross_pattern_valid_state_counts':pattern_valid,'completion_gates':gates,'repair_cycles_used':2,'learning_started':False,'scientific_variables_changed':[],'safety_thresholds_changed':False})
    print(json.dumps({'attempts':len(rows),'counts':counts,'positive':len(positive),'best':horizon['best'],'short_full':horizon['short_to_full_correlation']}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--final',action='store_true');args=parser.parse_args();main(final=args.final)
