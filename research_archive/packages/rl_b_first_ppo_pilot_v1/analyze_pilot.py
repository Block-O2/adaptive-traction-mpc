"""Post-run independent accounting, force/phase integration, motion and policy comparison."""
from pathlib import Path
import json,gzip,math,hashlib,time,os
from collections import Counter
from common import ROOT,put,clean
from stream_json import array_items,object_value,read_evidence
import numpy as np

def read(p):
 with read_evidence(p,encoding='utf-8') as f:return json.load(f)
def lines(p):return [json.loads(s) for s in Path(p).read_text().splitlines()] if Path(p).exists() else []
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def force_and_tracking(run,native=False):
 ep=run/'env/episode_0001';m=read(ep/'episode_summary.json');s=read(ep/'summary.json');raw=ep/'runtime_artifacts.json';trace=[x for x in array_items(raw,'trace') if x['stage']=='TASK'];boundary=object_value(raw,'last_boundary');phase={};jf=jm=0.;track=np.zeros(2);vtrack=np.zeros(2);dur=0.;forcepeak=momentpeak=0.;errors=[];truthpos=[]
 for i,left in enumerate(trace):
  right=trace[i+1]['time_s'] if i+1<len(trace) else boundary['time_s'];dt=right-left['time_s']
  if dt<0:errors.append('negative_dt');continue
  f=float(np.linalg.norm(left['cuff_force_world_n']));moment=float(np.linalg.norm(left['cuff_moment_world_nm']));forcepeak=max(forcepeak,f);momentpeak=max(momentpeak,moment)
  p=phase.setdefault(left['task_phase'],{'duration_s':0.,'JF_N_s':0.,'JM_Nm_s':0.});p['duration_s']+=dt;p['JF_N_s']+=f*dt;p['JM_Nm_s']+=moment*dt;jf+=f*dt;jm+=moment*dt;dur+=dt
  if abs(left['interval_force_cost_n_s']-f*dt)>1e-7:errors.append('stored_interval_force_mismatch')
  truth=np.asarray(left['truth_state']);qref=np.asarray(left['q_ref_rad']);vref=np.asarray(left['dq_ref_rad_s']);track+=(truth[:2]-qref)**2*dt;vtrack+=(truth[2:]-vref)**2*dt;truthpos.append(truth[:2])
 ticks=lines(ep/'online_tick_evidence.jsonl');spec=read(ep/'public_reward_contract.json');start=np.array(spec['start_return_target_rad']);goal=np.array(spec['outbound_goal_target_rad']);max_phi=0.
 for row in ticks:
  q=np.array(row['online_estimated_state'][:2]);ph=row['phase']
  if ph=='OUTBOUND':phi=float(np.min(np.clip((q-start)/(goal-start),0,1)))
  elif ph=='HOLD':phi=1+min(1,row['hold_elapsed_s']/spec['hold_duration_s'])
  elif ph=='RETURN':phi=2+float(np.min(np.clip((goal-q)/(goal-start),0,1)))
  else:continue
  max_phi=max(max_phi,phi)
 check={'JF_vs_wrapper':abs(jf-m['force_integral_N_s'])<1e-7,'JM_vs_wrapper':abs(jm-m['moment_integral_Nm_s'])<1e-7,'JF_vs_runtime':abs(jf-s['task']['force_integral_n_s'])<1e-7,'JM_vs_runtime':abs(jm-s['qualification']['physical_interval_moment_integral_nm_s'])<1e-7,'phase_duration_closed':abs(sum(x['duration_s'] for x in phase.values())-m['task_s'])<1e-7,'stored_force_intervals':not errors}
 result={'run':str(run.relative_to(ROOT)),'status':m['status'],'success':m['success'],'task_s':m['task_s'],'complete_integral':m['success'],'JF_N_s':jf,'JM_Nm_s':jm,'phase_integrals':phase,'force_peak_N':forcepeak,'moment_peak_Nm':momentpeak,'tracking_rms_deg':np.degrees(np.sqrt(track/max(dur,1e-12))).tolist(),'velocity_tracking_rms_deg_s':np.degrees(np.sqrt(vtrack/max(dur,1e-12))).tolist(),'tracking_definition':'actual trace Human truth_state minus actually owned reference, left time-weighted at5ms boundaries, evaluation-only','max_sensor_task_potential':max_phi,'checks':check,'pass':all(check.values()),'abort_reason':m['abort_reason'],'actual_native_motion':None,'motion_noninferiority':'NOT_EVALUABLE_original_scorer_missing'}
 if native:
  qi=m['physical_evaluation_only']['human_qpos_indices'];vi=m['physical_evaluation_only']['human_dof_indices'];begin=trace[0]['time_s'];native_rows=[]
  for row in array_items(raw,'native_states_evaluation_only'):
   if begin+1e-10<row['time_s']<=boundary['time_s']+1e-9:native_rows.append([row['time_s'],*[row['qpos_evaluation_only'][k] for k in qi],*[row['qvel_evaluation_only'][k] for k in vi]])
  z=np.asarray(native_rows);ts=z[:,0];q=z[:,1:3];v=z[:,3:5];acc=np.diff(v,axis=0)/np.diff(ts)[:,None];jerk=np.diff(acc,axis=0)/np.diff(ts[1:])[:,None];n=20;a5=(v[n:]-v[:-n])/(ts[n:]-ts[:-n])[:,None];j5=(a5[n:]-a5[:-n])/(ts[2*n:]-ts[n:-n])[:,None]
  qdeg=np.degrees(q);outbound=qdeg[np.array(ts<=begin+phase.get('OUTBOUND',{}).get('duration_s',0)+1e-9)];return_mask=ts>=begin+phase.get('OUTBOUND',{}).get('duration_s',0)+phase.get('HOLD',{}).get('duration_s',0)-1e-9
  result['actual_native_motion']={'task_steps':len(z),'q_min_deg':qdeg.min(0).tolist(),'q_max_deg':qdeg.max(0).tolist(),'dq_abs_peak_deg_s':np.degrees(np.abs(v).max(0)).tolist(),'dq_rms_deg_s':np.degrees(np.sqrt((v*v).mean(0))).tolist(),'ddq_abs_peak_deg_s2':np.degrees(np.abs(acc).max(0)).tolist(),'jerk_native_abs_peak_deg_s3':np.degrees(np.abs(jerk).max(0)).tolist(),'jerk_native_rms_deg_s3':np.degrees(np.sqrt((jerk*jerk).mean(0))).tolist(),'jerk_5ms_abs_peak_deg_s3':np.degrees(np.abs(j5).max(0)).tolist(),'jerk_5ms_rms_deg_s3':np.degrees(np.sqrt((j5*j5).mean(0))).tolist(),'jerk_definition':'velocity backward differences atnative0.25ms; additional5ms lag acceleration then5ms lag derivative; diagnostic, no invented gate','terminal_q_deg':qdeg[-1].tolist(),'terminal_dq_deg_s':np.degrees(v[-1]).tolist(),'terminal_return_error_deg':(qdeg[-1]-np.degrees(start)).tolist(),'outbound_goal_overshoot_deg':np.maximum(0,outbound.max(0)-np.degrees(goal)).tolist() if len(outbound) else None,'return_target_undershoot_deg':np.maximum(0,np.degrees(start)-qdeg[return_mask].min(0)).tolist() if return_mask.any() else None}
 return result

def main():
 train=lines(ROOT/'PPO_TRAINING_LOG.jsonl');evaluation=lines(ROOT/'FROZEN_EVALUATION_LOG.jsonl');allrows=train+evaluation
 independent=[]
 for row in allrows:
  x=force_and_tracking(ROOT/row['run'],native=row['mode']=='evaluate');independent.append(x);put(ROOT/row['run']/'FINAL_FORCE_TRACKING_RECOMPUTATION.json',x)
 put(ROOT/'audit/FINAL_INDEPENDENT_RECOMPUTATION.json',{'episodes':independent,'all_force_phase_pass':all(x['pass'] for x in independent)})
 # Recompute receipt ownership and actual Human native q/dq again for every new episode.
 from independent_physics_audit import audit as ownership
 owners={}
 for row in allrows:
  ep=ROOT/row['run']/'env/episode_0001';m=read(ep/'episode_summary.json');key=row['kind'] if row['mode']=='evaluate' else f"train_episode_{row['index']:03d}";owners[key]=ownership(ep/'runtime_artifacts.json',m['physical_evaluation_only']['human_qpos_indices'],m['physical_evaluation_only']['human_dof_indices'])
  print(json.dumps({'audit':'final_native_ownership','episode':key,'pass':owners[key]['accounting_pass']}),flush=True)
 put(ROOT/'audit/FINAL_NATIVE_OWNERSHIP_ALL.json',owners)
 put(ROOT/'audit/FINAL_EVALUATION_NATIVE_OWNERSHIP.json',{r['kind']:owners[r['kind']] for r in evaluation})
 import torch
 from stable_baselines3 import PPO
 from checkpoints import policy_hash
 torch.set_num_threads(1)
 ledger=read(ROOT/'LEDGER.json');initial=PPO.load(ROOT/'checkpoints/initial.zip',device='cpu');final=PPO.load(str(ROOT/ledger['checkpoint'])+'.zip',device='cpu');observations=[]
 for row in allrows:
  z=np.load(ROOT/row['run']/'transitions_0.npz');observations.extend(z['obs'])
 obs=np.asarray(observations,np.float32);before,_=initial.predict(obs,deterministic=True);after,_=final.predict(obs,deterministic=True);d=np.abs(after-before)
 first_observations={r['kind']:np.load(ROOT/r['run']/'transitions_0.npz')['obs'][0] for r in evaluation};baseline_first=first_observations['initial_deterministic'];first_differences={k:float(np.max(np.abs(v-baseline_first))) for k,v in first_observations.items()}
 put(ROOT/'audit/ACTION_CHANGE.json',{'evaluation_first_observation_max_abs_diff':first_differences,'all_evaluation_initial_causal_states_equal':all(v<1e-7 for v in first_differences.values()),'common_causal_observations':len(obs),'obs_sha256':hashlib.sha256(obs.tobytes()).hexdigest(),'initial_policy':policy_hash(initial),'final_policy':policy_hash(final),'mean_absolute_deterministic_action_change':d.mean(0).tolist(),'maximum_absolute_action_change':d.max(0).tolist(),'rms_action_change':np.sqrt(np.mean((after-before)**2,axis=0)).tolist(),'changed_fraction_above_1e_6':float(np.mean(np.any(d>1e-6,axis=1))),'initial_log_std':initial.policy.log_std.detach().numpy().tolist(),'final_log_std':final.policy.log_std.detach().numpy().tolist(),'actual_actions_initial':np.load(ROOT/evaluation[0]['run']/'transitions_0.npz')['actions'].tolist(),'actual_actions_final':np.load(ROOT/evaluation[-1]['run']/'transitions_0.npz')['actions'].tolist(),'pass':bool(policy_hash(initial)!=policy_hash(final) and d.max()>1e-6),'note':'same observation comparison separates policy changes from changed trajectories; actual actions remain proposals and native receipts independently prove execution'})
 # All actual optimizer generations and resume identities.
 cp=[]
 for p in sorted((ROOT/'checkpoints').glob('*.json')):
  m=read(p);base=p.with_suffix('');cp.append({'checkpoint':str(base.relative_to(ROOT)),'model_sha_match':sha(base.with_suffix('.zip'))==m['model_sha256'],'rng_sha_match':sha(base.with_suffix('.rng.pt'))==m['rng_sha256'],'policy_sha256':m['policy_sha256'],'decisions':m['decisions'],'epochs':m['updates'],'optimizer_step_calls':m.get('optimizer_step_calls',0),'source_contract':m['contract_sha256']})
 resumes=[read(p) for p in (ROOT/'runs').glob('*/RESUME_AUDIT.json')]
 put(ROOT/'PPO_CHECKPOINT_AUDIT.json',{'generations':cp,'resume_checks':resumes,'all_pass':all(x['model_sha_match'] and x['rng_sha_match'] for x in cp) and all(x['pass'] for x in resumes),'final':ledger['checkpoint'],'semantics':'full Adam/Python/NumPy/Torch RNG restore; fresh physical episode, no MuJoCo mid-episode resume','optimizer_steps':ledger['optimizer_steps'],'rollout_to_update':'all complete training transitions used; zero audit tail; raw Gaussian actions/logp/values/advantages/returns retained'})
 plot_curves(train,independent)
 print(json.dumps({'training':len(train),'evaluation':len(evaluation),'force_pass':all(x['pass'] for x in independent),'ownership_pass':all(x['accounting_pass'] for x in owners.values()),'action_change':float(d.max())}))

def plot_curves(rows,independent):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 x=np.array([r['index'] for r in rows]);success=np.array([r['success'] for r in rows],float);reward=np.array([r['reward'] for r in rows]);duration=np.array([r['task_s'] for r in rows]);lookup={r['run']:r for r in independent};potential=[lookup[r['run']]['max_sensor_task_potential'] for r in rows]
 fig,axes=plt.subplots(2,2,figsize=(12,7),constrained_layout=True)
 axes[0,0].plot(x,reward,'o-',ms=3);axes[0,0].set_ylabel('Episode return');axes[0,0].set_title('Frozen pilot reward v3')
 axes[0,1].plot(x,np.cumsum(success)/np.arange(1,len(x)+1),'o-',ms=3);axes[0,1].set_ylim(-.05,1.05);axes[0,1].set_ylabel('Cumulative runtime success rate')
 axes[1,0].plot(x,duration,'o-',ms=3,label='TASK elapsed');axes[1,0].scatter(x[success==1],duration[success==1],s=30,color='green',label='COMPLETE');axes[1,0].axhline(19.03,color='gray',ls='--',label='19.030s necessary matched timing');axes[1,0].set_ylabel('Actual task time (s)');axes[1,0].legend(fontsize=8)
 axes[1,1].plot(x,potential,'o-',ms=3);axes[1,1].set_ylabel('Maximum causal phase potential');axes[1,1].set_ylim(0,3.1)
 for ax in axes.ravel():
  ax.set_xlabel('Training episode');ax.grid(alpha=.25)
  for gate in (5,20):ax.axvline(gate,color='gray',alpha=.25)
 fig.suptitle('RL-B first CPU PPO pilot: 1 seed, nominal development episodes; no generalization claim');fig.savefig(ROOT/'PPO_LEARNING_CURVE.png',dpi=160);fig.savefig(ROOT/'PPO_LEARNING_CURVE.pdf');plt.close(fig)
 table=['|Episode|Runtime|TASK s|Max progress|Return|JF (partial unless COMPLETE)|Decisions|Adam steps|','|---:|---|---:|---:|---:|---:|---:|---:|']
 for r,p in zip(rows,potential):table.append(f"|{r['index']}|{r['status']}|{r['task_s']:.3f}|{p:.4f}|{r['reward']:.6f}|{r['JF']:.3f}|{r['decisions']}|{len(r['gradient_steps'])}|")
 groups=[]
 for lo,hi in [(1,5),(6,20),(21,50)]:
  sub=[r for r in rows if lo<=r['index']<=hi]
  if sub:groups.append({'episodes':[lo,min(hi,len(rows))],'count':len(sub),'successes':sum(r['success'] for r in sub),'mean_return':float(np.mean([r['reward'] for r in sub])),'mean_task_s':float(np.mean([r['task_s'] for r in sub])),'mean_entropy':float(np.mean([r['entropy_mean'] for r in sub])),'failure_reasons':dict(Counter(r['abort_reason'] for r in sub if not r['success']))})
 put(ROOT/'audit/LEARNING_PHASE_SUMMARY.json',groups)
 (ROOT/'PPO_LEARNING_CURVE.md').write_text('# PPO学习曲线\n\n![学习曲线](PPO_LEARNING_CURVE.png)\n\n单seed nominal开发训练；失败总回报成本下限固定，不以少积JF换取回报。partial JF不作完整收益；采样训练成功不替代冻结checkpoint。每episode一次完整PPO rollout。阶段5/20/50门、entropy/losses/所有失败见原JSONL。entropy为Box clipping前二维Gaussian分布的总微分熵（nats），并非实际已执行扭矩的熵。\n\n'+'\n'.join(table)+'\n')
if __name__=='__main__':main()
