"""Independent saved-evidence analysis, isolated from all actor/training code."""
from pathlib import Path
import json,time,hashlib,math,gzip
from collections import Counter
from common import ROOT,put
from stream_json import array_items,object_value,read_evidence
import numpy as np

def read(p):
 with read_evidence(p,encoding='utf-8') as f:return json.load(f)
def lines(p):
 p=Path(p)
 if not p.exists() and not Path(str(p)+'.gz').exists():return []
 with read_evidence(p,encoding='utf-8') as f:return [json.loads(s) for s in f if s.strip()]
def scientific_metrics(run,native=False):
 ep=run/'env/episode_0001';m=read(ep/'episode_summary.json');s=read(ep/'summary.json');full=ep/'runtime_artifacts.json';compact=ep/'COMPACT_CAUSAL_RECEIPTS.json';raw=full if full.exists() or Path(str(full)+'.gz').exists() else compact
 trace=[x for x in array_items(raw,'trace') if x['stage']=='TASK'];end=m['native_steps_total']*.00025 if raw==compact else object_value(raw,'last_boundary')['time_s'];phase={};jf=jm=0.;tracking=np.zeros(2);vtracking=np.zeros(2);duration=0.;errors=[];peakf=peakm=0.
 for i,left in enumerate(trace):
  right=trace[i+1]['time_s'] if i+1<len(trace) else end;dt=right-left['time_s']
  if dt< -1e-9:errors.append('negative_duration');continue
  dt=max(0.,dt);f=float(np.linalg.norm(left['cuff_force_world_n']));moment=float(np.linalg.norm(left['cuff_moment_world_nm']));jf+=f*dt;jm+=moment*dt;duration+=dt;peakf=max(peakf,f);peakm=max(peakm,moment)
  row=phase.setdefault(left['task_phase'],{'duration_s':0.,'JF':0.,'JM':0.});row['duration_s']+=dt;row['JF']+=f*dt;row['JM']+=moment*dt
  if abs(left['interval_force_cost_n_s']-f*dt)>1e-6:errors.append('interval_force_mismatch')
  actual=np.asarray(left['truth_state']);tracking+=(actual[:2]-np.asarray(left['q_ref_rad']))**2*dt;vtracking+=(actual[2:]-np.asarray(left['dq_ref_rad_s']))**2*dt
 checks={'force_integral':abs(jf-m['force_integral_N_s'])<1e-6,'moment_integral':abs(jm-m['moment_integral_Nm_s'])<1e-6,'runtime_force_integral':abs(jf-s['task']['force_integral_n_s'])<1e-6,'runtime_moment_integral':abs(jm-s['qualification']['physical_interval_moment_integral_nm_s'])<1e-6,'phase_and_native_duration':abs(duration-m['task_s'])<1e-6,'trace_interval_costs':not errors}
 result={'run':str(run.relative_to(ROOT)),'success':m['success'],'status':m['status'],'abort_reason':m['abort_reason'],'phases':m['phases'],'task_s':m['task_s'],'integral_complete':m['success'],'JF':jf,'JM':jm,'force_peak_N':peakf,'moment_peak_Nm':peakm,'phase_integrals':phase,'tracking_rms_deg':np.degrees(np.sqrt(tracking/max(duration,1e-12))).tolist(),'velocity_tracking_rms_deg_s':np.degrees(np.sqrt(vtracking/max(duration,1e-12))).tolist(),'checks':checks,'pass':all(checks.values()),'full_native_raw_available':raw==full,'native_motion':None,'formal_motion_fairness':'NOT_READY_ORIGINAL_SCORER_MISSING'}
 if native:
  if raw!=full:raise ValueError('FULL_NATIVE_EVALUATION_RAW_REQUIRED')
  qi=m['physical_evaluation_only']['human_qpos_indices'];vi=m['physical_evaluation_only']['human_dof_indices'];begin=trace[0]['time_s'];z=[]
  for row in array_items(full,'native_states_evaluation_only'):
   if begin+1e-10<row['time_s']<=end+1e-9:z.append([row['time_s'],*[row['qpos_evaluation_only'][k] for k in qi],*[row['qvel_evaluation_only'][k] for k in vi]])
  z=np.asarray(z);ts=z[:,0];q=z[:,1:3];v=z[:,3:5];a=np.diff(v,axis=0)/np.diff(ts)[:,None];j=np.diff(a,axis=0)/np.diff(ts[1:])[:,None]
  def lagdiff(x,t,n):return (x[n:]-x[:-n])/(t[n:]-t[:-n])[:,None]
  a5=lagdiff(v,ts,20);a20=lagdiff(v,ts,80);j5=lagdiff(a5,ts[20:],20)
  rms=lambda x:np.degrees(np.sqrt(np.mean(x*x,axis=0))).tolist() if len(x) else [None,None];peak=lambda x:np.degrees(np.max(np.abs(x),axis=0)).tolist() if len(x) else [None,None]
  spec=read(ep/'public_reward_contract.json');start=np.asarray(spec['start_return_target_rad']);goal=np.asarray(spec['outbound_goal_target_rad']);out=q[ts<=begin+phase.get('OUTBOUND',{}).get('duration_s',0)+1e-9];back=q[ts>=begin+phase.get('OUTBOUND',{}).get('duration_s',0)+phase.get('HOLD',{}).get('duration_s',0)-1e-9]
  native_result={'task_steps':len(z),'q_min_deg':np.degrees(q.min(0)).tolist(),'q_max_deg':np.degrees(q.max(0)).tolist(),'excursion_deg':np.degrees(q.max(0)-q.min(0)).tolist(),'velocity_peak_deg_s':peak(v),'velocity_rms_deg_s':rms(v),'acceleration_native_peak_deg_s2':peak(a),'acceleration_5ms_peak_deg_s2':peak(a5),'acceleration_20ms_peak_deg_s2':peak(a20),'jerk_native_peak_deg_s3':peak(j),'jerk_native_rms_deg_s3':rms(j),'jerk_5ms_peak_deg_s3':peak(j5),'jerk_5ms_rms_deg_s3':rms(j5),'terminal_q_deg':np.degrees(q[-1]).tolist(),'terminal_velocity_deg_s':np.degrees(v[-1]).tolist(),'terminal_return_error_deg':np.degrees(q[-1]-start).tolist(),'outbound_goal_overshoot_deg':np.degrees(np.maximum(0,out.max(0)-goal)).tolist() if len(out) else None,'return_target_undershoot_deg':np.degrees(np.maximum(0,start-back.min(0))).tolist() if len(back) else None,'jerk_is_diagnostic_no_invented_threshold':True,'definition':'Actual native Human q/dq; backward native differences, 5ms-lag differences, no invented B-relative motion gate. Evaluation truth never enters actor.'}
  np.savez_compressed(run/'ACTUAL_HUMAN_NATIVE_MOTION.npz',time_s=ts,q_rad=q,dq_rad_s=v)
  result['native_motion']=native_result
 spec=read(ep/'public_reward_contract.json');start=np.asarray(spec['start_return_target_rad']);goal=np.asarray(spec['outbound_goal_target_rad']);maximum_potential=0.
 for row in lines(ep/'online_tick_evidence.jsonl'):
  q=np.asarray(row['online_estimated_state'][:2]);ph=row['phase']
  if ph=='OUTBOUND':potential=float(np.min(np.clip((q-start)/(goal-start),0.,1.)))
  elif ph=='HOLD':potential=1.+min(1.,row['hold_elapsed_s']/spec['hold_duration_s'])
  elif ph=='RETURN':potential=2.+float(np.min(np.clip((goal-q)/(goal-start),0.,1.)))
  else:continue
  maximum_potential=max(maximum_potential,potential)
 result['max_causal_phase_potential']=maximum_potential;result['analysis_schema_version']=3
 from qualification_status import classify
 independent=read(run/'INDEPENDENT_AUDIT.json');result['qualification']=classify(m,s,independent)
 boundary_path=run/'NATIVE_BOUNDARY_MOTION_AUDIT.json'
 if native and boundary_path.exists():
  boundary=read(boundary_path);result['native_boundary_motion_audit']=boundary
  mapping={'acceleration_native_peak_deg_s2':boundary['acceleration_peak_deg_s2']['native'],'acceleration_5ms_peak_deg_s2':boundary['acceleration_peak_deg_s2']['5ms'],'acceleration_20ms_peak_deg_s2':boundary['acceleration_peak_deg_s2']['20ms'],'jerk_native_peak_deg_s3':boundary['jerk_peak_deg_s3']['native'],'jerk_native_rms_deg_s3':boundary['jerk_rms_deg_s3']['native'],'jerk_5ms_peak_deg_s3':boundary['jerk_peak_deg_s3']['5ms'],'jerk_5ms_rms_deg_s3':boundary['jerk_rms_deg_s3']['5ms']}
  result['native_motion']['task_only_windows_without_anchors_diagnostic']={k:result['native_motion'][k] for k in mapping}
  result['native_motion'].update(mapping);result['native_motion']['complete_derivative_window_definition']=boundary['definition']
  result['checks']['complete_boundary_native_motion']=boundary['pass'];result['pass']=all(result['checks'].values())
 put(run/'FINAL_SCIENTIFIC_METRICS.json',result);return result

def summarize():
 cfg=read(ROOT/'PPO_TRAINING_CONFIG.json');train=lines(ROOT/'ALL_TRAINING_LOG.jsonl');ev=lines(ROOT/'ALL_EVALUATION_LOG.jsonl');metrics=[]
 for row in train+ev:
  path=ROOT/row['run']/'FINAL_SCIENTIFIC_METRICS.json'
  result=read(path) if path.exists() and read(path).get('analysis_schema_version')==3 else scientific_metrics(ROOT/row['run'],native=row['mode']=='evaluate')
  metrics.append(result)
 lookup={x['run']:x for x in metrics};seeds=[]
 stage1complete=read(ROOT/'STAGE1_COMPLETE.json') if (ROOT/'STAGE1_COMPLETE.json').exists() else None
 target=stage1complete['target'] if stage1complete else 50
 for seed in cfg['seeds']:
  rows=[x for x in train if x['training_seed']==seed and x['stage']=='stage1'];evaluation=[{**x,'scientific_metrics':lookup[x['run']]} for x in ev if x['training_seed']==seed and x['stage']=='stage1'];initial=[x for x in evaluation if x['kind']=='initial_deterministic'];final=[x for x in evaluation if x['kind'] in [f'checkpoint{target:03d}_first',f'checkpoint{target:03d}_repeat']]
  bins=[]
  for low in range(1,len(rows)+1,10):
   sub=[x for x in rows if low<=x['index']<low+10];bins.append({'first':low,'last':low+len(sub)-1,'successes':sum(x['success'] for x in sub),'episodes':len(sub),'mean_reward':float(np.mean([x['reward'] for x in sub])),'mean_entropy_nats':float(np.mean([x['entropy_mean'] for x in sub])),'mean_task_s':float(np.mean([x['task_s'] for x in sub]))})
  seeds.append({'seed':seed,'training_episodes':len(rows),'training_successes':sum(x['success'] for x in rows),'training_success_rate':sum(x['success'] for x in rows)/max(1,len(rows)),'training_runtime_complete_with_necessary19_030_timing':sum(x['success'] and abs(x['task_s']-19.03)<.05 for x in rows),'training_runtime_complete_outside_necessary19_030_timing':sum(x['success'] and abs(x['task_s']-19.03)>=.05 for x in rows),'RL_decisions':sum(x['decisions'] for x in rows),'native_physics_steps':sum(x['native_steps'] for x in rows),'task_native_steps':sum(x['task_native_steps'] for x in rows),'PPO_calls':len(rows),'PPO_epochs':sum(4 for x in rows),'Adam_updates':sum(len(x['gradient_steps']) for x in rows),'wall_s':sum(x['resource']['wall_s'] for x in rows),'accepted_actions':sum(x['accepted'] for x in rows),'rejected_actions':sum(x['rejections'] for x in rows),'fallback_events':sum(x['fallback_events'] for x in rows),'failure_reasons':dict(Counter(x['abort_reason'] for x in rows if not x['success'])),'failure_phases':dict(Counter(next((p for p in reversed(x['phases']) if p in ['OUTBOUND','HOLD','RETURN']),'NO_PHASE') for x in rows if not x['success'])),'all_episode_audits_pass':all(x['independent_audit_pass'] for x in rows),'training_curve_blocks':bins,'initial_evaluation_successes':sum(x['success'] for x in initial),'initial_evaluation_attempts':len(initial),'final_evaluation_successes':sum(x['success'] for x in final),'final_evaluation_attempts':len(final),'replicated_runtime_learning':len(initial)==1 and not initial[0]['success'] and len(final)==2 and all(x['success'] for x in final),'evaluations':evaluation,'final_checkpoint':read(ROOT/'seeds'/str(seed)/'stage1/PROGRESS.json')['checkpoint'] if (ROOT/'seeds'/str(seed)/'stage1/PROGRESS.json').exists() else None})
 result={'unix':time.time(),'study':cfg['study'],'category':'NOMINAL_DEVELOPMENT_REPLICATION','final_preregistered_target':target,'seeds':seeds,'three_seed_replication_pass':len(seeds)==3 and all(x['replicated_runtime_learning'] for x in seeds),'replicated_seed_count':sum(x['replicated_runtime_learning'] for x in seeds),'generalization':'NOT_TESTED; same deterministic nominal patient/initial-state generator','full_B_H150_qualification':'NOT_READY_ORIGINAL_SCORER_MISSING_AND_G4_STRICT_FAIL','reward_hyperparameters_or_seed_selected_on_frozen_evaluation':False,'training_length_extension_uses_preregistered_nominal_development_gate':target==80,'all_integral_tracking_recomputations_pass':all(x['pass'] for x in metrics)}
 result['exact50_episode_replication']=read(ROOT/'A2_FROZEN50_CHECKPOINT_RESULTS.json') if (ROOT/'A2_FROZEN50_CHECKPOINT_RESULTS.json').exists() else None
 result['extended_training_budget_episodes_per_seed']=target if target>50 else None
 put(ROOT/'MULTISEED_PPO_RESULTS.json',result);put(ROOT/'audit/ALL_SCIENTIFIC_METRICS.json',{'episodes':metrics,'all_pass':all(x['pass'] for x in metrics)})
 return result
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--run');a=p.parse_args()
 if a.run:print(json.dumps(scientific_metrics(ROOT/a.run,native=True)))
 else:
  result=summarize();print(json.dumps({'seeds':[{k:x[k] for k in ['seed','training_episodes','training_successes','Adam_updates','final_evaluation_successes','final_evaluation_attempts']} for x in result['seeds']],'three_seed_replication_pass':result['three_seed_replication_pass']}))
