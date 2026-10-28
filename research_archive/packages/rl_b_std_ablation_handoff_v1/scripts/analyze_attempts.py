"""Saved-only ablation statistics, applied receipts, pairing and physical divergence."""
from pathlib import Path
import json,sys,math,hashlib
from collections import Counter
from research_common import ROOT,RUNTIME,atomic,read,sha,now
sys.path.insert(0,str(RUNTIME))
from stream_json import array_items
from phase_dose import phase_dose
import numpy as np

def stats(values):
 a=np.asarray(values,float)
 return dict(count=len(a),minimum=a.min(0).tolist(),maximum=a.max(0).tolist(),mean=a.mean(0).tolist(),rms=np.sqrt(np.mean(a*a,0)).tolist()) if len(a) else None

def extend(row):
 run=Path(row['run']);dest=run/'ABLATION_EXECUTION_AUDIT_v2.json'
 if dest.exists():return read(dest)
 ep=run/'env/episode_0001';summary=read(ep/'summary.json');m=read(ep/'episode_summary.json');raw=ep/'runtime_artifacts.json';task_end=m['native_steps_total']*.00025;task_begin=task_end-m['task_s']
 receipts=list(array_items(raw,'command_receipts'));selected=[(i,r) for i,r in enumerate(receipts) if r.get('applied') and r.get('native_steps',0)>0 and r['end_physics_s']>task_begin+1e-9 and r['start_physics_s']<task_end-1e-9]
 host_ages=[(r['apply_ns']-r['source_capture_ns'])/1e6 for _,r in selected if r.get('apply_ns') is not None and r.get('source_capture_ns') is not None]
 requests=[x for x in array_items(raw,'requests') if x['stage']=='TASK']
 request_timing=[dict(request_id=x['request_id'],outcome=x['outcome'],source_sample_time_s=x['source_sample_time_s'],sensor_capture_ns=x.get('sensor_capture_ns'),activation_ns=x.get('activation_ns'),physics_activation_source_age_s=x['activation_simulation_version']['sim_time_s']-x['source_sample_time_s'] if x.get('activation_simulation_version') else None,host_activation_age_ms=(x['activation_ns']-x['sensor_capture_ns'])/1e6 if x.get('activation_ns') is not None else None,recorded_activation_age_ms=x.get('activation_age_ms'),disposition_age_ms=x.get('disposition_age_ms'),execution_mode=x.get('execution_mode')) for x in requests]
 torques=[r['command_torque_nm'] for _,r in selected];ages=[r['start_physics_s']-r['source_sample_time_s'] for _,r in selected]
 np.savez_compressed(run/'TASK_APPLIED_RECEIPTS_v2.npz',receipt_index=[i for i,r in selected],start_physics_s=[r['start_physics_s'] for i,r in selected],end_physics_s=[r['end_physics_s'] for i,r in selected],source_sample_time_s=[r['source_sample_time_s'] for i,r in selected],source_age_s=ages,native_steps=[r['native_steps'] for i,r in selected],command_torque_nm=torques,apply_ns=[r.get('apply_ns',-1) for _,r in selected],source_capture_ns=[r.get('source_capture_ns',-1) for _,r in selected],host_sensor_age_at_apply_ms_profile=[r.get('host_sensor_age_at_apply_ms_profile',-1) for _,r in selected])
 prefix=hashlib.sha256();count=0
 for n in array_items(raw,'native_states_evaluation_only'):
  if n['time_s']>task_begin+1e-9:break
  prefix.update(json.dumps([n['qpos_evaluation_only'],n['qvel_evaluation_only'],n['command_torque_nm']],separators=(',',':')).encode());count+=1
 transitions=read(run/'RESEARCH_TRANSITIONS.json');rs=np.asarray([t['raw_action'] for t in transitions]);cs=np.asarray([t['action'] for t in transitions]);phases={}
 for phase in ['OUTBOUND','HOLD','RETURN']:
  ds=[d for d in summary['decisions'] if d['phase']==phase]
  phases[phase]=dict(planner_decisions=len(ds),outcomes=dict(Counter(d['activation_outcome'] for d in ds)),proposed_delta_q_rad=[d.get('proposed_action_delta_q_rad') for d in ds],executed_delta_q_rad=[d.get('executed_action_delta_q_rad') for d in ds],reasons=[d.get('activation_rejected_reason') or d.get('planning_exception') for d in ds if d['activation_outcome']!='ACTIVATED'])
 cfg=read(run.parent/'EFFECTIVE_CONFIG.json');links=read(ep/'CLOUD_CASE_AUDIT.json')
 result=dict(time_utc=now(),job=row['job_id'],seed=row['seed'],arm=cfg['arm'],split=cfg['evaluation_split'],rng=cfg['evaluation_rng'],run=str(run),status=row['status'],success=row['success'],task_s=row['task_s'],JF=row['JF'],JM=row['JM'],integral_scope=row['integral_scope'],abort_reason=row['abort_reason'],native_steps=row['native_steps'],wall_s=read(ROOT/'jobs'/row['job_id']/'END.json')['wall_s'],motion=read(run/'COMMON_MOTION_METRICS.json'),phase_dose=phase_dose(run,row),task_phase_transitions=summary['task']['phase_transitions'],planner_by_phase=phases,raw_mean=stats([t['mean'] for t in transitions]),checkpoint_std=transitions[0]['std'],sampling_scale=None if cfg['arm']=='C' else transitions[0]['effective_std'],C_unused_effective_std_field='The inherited per-transition .2 field is unused by C; C directly chooses mean and never samples' if cfg['arm']=='C' else None,raw_sample=stats(rs),clipped_proposal=stats(cs),clipped_components=int((np.abs(rs)>1).sum()),total_components=int(rs.size),clip_fraction=float(np.mean(np.abs(rs)>1)),clip_by_dimension=np.mean(np.abs(rs)>1,0).tolist(),clip_mapping_error=float(np.max(np.abs(np.clip(rs,-1,1)-cs))),applied_receipts_TASK=len(selected),applied_torque_TASK=stats(torques),source_age_TASK_s=stats(ages),receipt_host_sensor_age_at_apply_ms_profile=stats(host_ages),request_timing=request_timing,request_host_activation_age_ms=stats([x['host_activation_age_ms'] for x in request_timing if x['host_activation_age_ms'] is not None]),request_physics_activation_age_s=stats([x['physics_activation_source_age_s'] for x in request_timing if x['physics_activation_source_age_s'] is not None]),host_vs_simulation_age_scope='Both are measured and saved separately; scientific simulation source age is not host realtime qualification',source_age_definition='receipt.start_physics_s minus immutable source_sample_time_s; only receipts overlapping executed TASK; no source refresh',receipt_archive=str(run/'TASK_APPLIED_RECEIPTS_v2.npz'),native_ownership=links['ownership'],native_actions=links['native_actions'],original_safety_checks=links['motion']['checks'],preTASK_physics_sha256=prefix.hexdigest(),preTASK_native_samples=count,source_sha256={str(ep/'episode_summary.json'):sha(ep/'episode_summary.json'),str(run/'RESEARCH_TRANSITIONS.json'):sha(run/'RESEARCH_TRANSITIONS.json'),str(raw)+'.gz':sha(str(raw)+'.gz')} if Path(str(raw)+'.gz').exists() else {str(raw):sha(raw)},independent_original_audits_pass=row['independent_audit_pass'])
 atomic(dest,result);return result

def main():
 rows=[json.loads(x) for x in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()] if (ROOT/'ALL_ATTEMPTS.jsonl').exists() else [];cases=[extend(x) for x in rows if read(ROOT/'jobs'/x['job_id']/'END.json',{}).get('success') and (Path(x['run'])/'COMMON_MOTION_METRICS.json').exists()];pairs=[];summaries=[]
 for case in cases:
  entropy=lambda std:.5*sum(math.log(2*math.pi*math.e*x*x) for x in std)
  case['checkpoint_reference_preclip_entropy']=entropy(case['checkpoint_std'])
  case['evaluation_preclip_gaussian_entropy']=entropy(case['sampling_scale']) if case['sampling_scale'] is not None else None
  case['inherited_entropy_field_semantics']='Raw entropy/entropy_mean fields describe the unchanged checkpoint Gaussian, not B override or C deterministic deployment; clipped proposal is a mixed distribution'
  for phase in case['planner_by_phase'].values():
   phase['rejection_classes']=dict(Counter('GEOMETRY' if 'geometry' in str(q).lower() else 'REFERENCE_REGRESSION' if 'regress the emitted reference' in str(q).lower() else 'OTHER' for q in phase['reasons']))
 for seed in [1495656323,1630784693]:
  for rng in range(202610213101,202610213107):
   a=next((x for x in cases if x['seed']==seed and x['arm']=='A' and x['rng']==rng),None);b=next((x for x in cases if x['seed']==seed and x['arm']=='B' and x['rng']==rng),None)
   if not a or not b:continue
   ta=read(Path(a['run'])/'RESEARCH_TRANSITIONS.json');tb=read(Path(b['run'])/'RESEARCH_TRANSITIONS.json');nn=min(len(ta),len(tb));noise_equal=all(x['noise_index']==y['noise_index'] and np.array_equal(x['noise'],y['noise']) for x,y in zip(ta,tb))
   assert noise_equal and a['preTASK_physics_sha256']==b['preTASK_physics_sha256'] and a['preTASK_native_samples']==b['preTASK_native_samples']
   obs_delta=np.asarray([np.asarray(x['obs'])-np.asarray(y['obs']) for x,y in zip(ta,tb)]);mean_delta=np.asarray([np.asarray(x['mean'])-np.asarray(y['mean']) for x,y in zip(ta,tb)])
   aa=np.load(Path(a['run'])/'ACTUAL_HUMAN_TASK_SERIES.npz');bb=np.load(Path(b['run'])/'ACTUAL_HUMAN_TASK_SERIES.npz');common=min(len(aa['time_s']),len(bb['time_s']));assert np.max(np.abs(aa['time_s'][:common]-bb['time_s'][:common]))<1e-8
   divergence=dict(paired_indices=nn,noise_equal=True,initial_obs_exact=np.array_equal(ta[0]['obs'],tb[0]['obs']),same_preTASK_physics=True,observation_l2_by_decision=np.linalg.norm(obs_delta,axis=1).tolist(),actor_mean_abs_difference_by_decision=np.abs(mean_delta).tolist(),common_physical_TASK_s=common*.00025,actual_Human_q_difference_RMS_deg=np.degrees(np.sqrt(np.mean((aa['q_rad'][:common]-bb['q_rad'][:common])**2,0))).tolist(),actual_Human_dq_difference_RMS_deg_s=np.degrees(np.sqrt(np.mean((aa['dq_rad_s'][:common]-bb['dq_rad_s'][:common])**2,0))).tolist(),warning='Noise index pairs RL decisions, not equal state, equal phase, or equal physical time; q/dq divergence is separately aligned on overlapping native time')
   comparable=a['success'] and b['success'] and abs(a['task_s']-b['task_s'])<1e-7
   pairs.append(dict(seed=seed,rng=rng,A_success=a['success'],B_success=b['success'],A_task_s=a['task_s'],B_task_s=b['task_s'],complete_equal_duration=comparable,JF_difference_B_minus_A=b['JF']-a['JF'] if comparable else None,JM_difference_B_minus_A=b['JM']-a['JM'] if comparable else None,divergence=divergence))
  per={}
  for arm in ['A','B']:
   xs=[x for x in cases if x['seed']==seed and x['arm']==arm and x['split']=='preregistered'];completed=[x for x in xs if x['success']]
   per[arm]=dict(attempts=len(xs),complete=len(completed),failed=len(xs)-len(completed),rejected_decisions_by_phase={p:sum(sum(n for k,n in x['planner_by_phase'][p]['outcomes'].items() if k!='ACTIVATED') for x in xs) for p in ['OUTBOUND','HOLD','RETURN']},geometry_rejections_by_phase={p:sum(x['planner_by_phase'][p]['rejection_classes'].get('GEOMETRY',0) for x in xs) for p in ['OUTBOUND','HOLD','RETURN']},reference_regression_rejections_by_phase={p:sum(x['planner_by_phase'][p]['rejection_classes'].get('REFERENCE_REGRESSION',0) for x in xs) for p in ['OUTBOUND','HOLD','RETURN']},other_rejections_by_phase={p:sum(x['planner_by_phase'][p]['rejection_classes'].get('OTHER',0) for x in xs) for p in ['OUTBOUND','HOLD','RETURN']},task_durations_s=[x['task_s'] for x in xs],complete_task_JF=[x['JF'] for x in completed],complete_task_JM=[x['JM'] for x in completed],failed_partials=[dict(rng=x['rng'],task_s=x['task_s'],JF=x['JF'],JM=x['JM'],reason=x['abort_reason']) for x in xs if not x['success']],clipped_components=sum(x['clipped_components'] for x in xs),total_components=sum(x['total_components'] for x in xs),clip_fraction=(sum(x['clipped_components'] for x in xs)/sum(x['total_components'] for x in xs)) if xs else None)
  ps=[p for p in pairs if p['seed']==seed];per['paired_outcomes']=dict(both_complete=sum(p['A_success'] and p['B_success'] for p in ps),A_only=sum(p['A_success'] and not p['B_success'] for p in ps),B_only=sum(not p['A_success'] and p['B_success'] for p in ps),neither=sum(not p['A_success'] and not p['B_success'] for p in ps))
  n=per['paired_outcomes']['A_only']+per['paired_outcomes']['B_only'];k=min(per['paired_outcomes']['A_only'],per['paired_outcomes']['B_only']);per['exploratory_paired_exact_two_sided_p']=min(1.,2*sum(math.comb(n,i) for i in range(k+1))/2**n) if n else 1.
  summaries.append(dict(seed=seed,arms=per))
 result=dict(time_utc=now(),status='COMPLETE' if len(cases)==28 and len(pairs)==12 else 'IN_PROGRESS',cases=cases,pairs=pairs,per_parent=summaries,planned_attempts=28,actual_closed_attempts=len(cases),actual_new_physics_attempts=len(read(ROOT/'LEDGER.json',{}).get('attempts',[])),gradient_updates=0,primary_population='Per parent 6 new paired action streams; pilot and C excluded from rates',scope='Nominal action-stream development evidence; no training-STD, patient-generalization, G4, live matched or Stage2 qualification')
 atomic(ROOT/'STD_ABLATION_RESULTS.json',result);print(json.dumps(dict(status=result['status'],closed=len(cases),pairs=len(pairs),per_parent=summaries),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
