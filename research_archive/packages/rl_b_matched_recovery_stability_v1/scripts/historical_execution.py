from pathlib import Path
import json,sys,hashlib,collections
import numpy as np
r=Path(__file__).resolve().parents[1];c=r.parent/'rl_b_autonomous_replication_v1';sys.path.insert(0,str(r/'physical/runtime'))
from stream_json import array_items,object_value
from independent_physics_audit import audit
rows=[json.loads(s) for s in (c/'ALL_EVALUATION_LOG.jsonl').read_text().splitlines()];result=[];cache={}
for row in rows:
 if row['kind'] not in ['checkpoint050_first','checkpoint080_first']:continue
 p=c/row['run'];ep=p/'env/episode_0001';raw=ep/'runtime_artifacts.json';m=json.loads((ep/'episode_summary.json').read_text());s=json.loads((ep/'summary.json').read_text());truth=m['physical_evaluation_only'];a=audit(raw,truth['human_qpos_indices'],truth['human_dof_indices']);assert a['accounting_pass']
 receipts=[x for x in array_items(raw,'command_receipts') if x.get('applied') and x.get('native_steps',0)>0];trace=[x for x in array_items(raw,'trace') if x['stage']=='TASK'];decisions=[x for x in s['decisions'] if 'timing_request_id' in x];props=json.loads((ep/'native_rl_proposals.json').read_text());requests=json.loads((ep/'native_rl_requests.json').read_text());joined={x['request_id']:x for x in requests};hd=hashlib.sha256();prefix_n=0;t0=props[0]['source_sample_s']
 for n in array_items(raw,'native_states_evaluation_only'):
  if n['time_s']>t0+1e-10:break
  hd.update(np.asarray(n['qpos_evaluation_only']+n['qvel_evaluation_only']+n['command_torque_nm'],dtype=np.float64).tobytes());prefix_n+=1
 slim=[]
 for d in decisions:
  prop=next(x for x in props if x['request_id']==d['timing_request_id']);rr=joined[prop['request_id']]
  slim.append({'action_id':prop['action_id'],'task_s':prop['task_s'],'phase':prop['phase'],'policy_bounded_proposal':prop['action'],'request_id':d['timing_request_id'],'outcome':rr['outcome'],'reason':rr.get('reason'),'plan_activated':d.get('plan_activated'),'deadline_miss':d.get('deadline_miss'),'stale':d.get('stale'),'candidate_count':d.get('candidate_count'),'proposed_delta_q_rad':d.get('proposed_action_delta_q_rad'),'executed_delta_q_rad':d.get('executed_action_delta_q_rad'),'executed_label':d.get('executed_label'),'activation_physics_s':d.get('activation_timestamp_s'),'schedule_target_q_rad':next((x.get('schedule',{}).get('target_q_rad') for x in d.get('evaluations',[]) if x.get('feasible')),None),'fallback_physics_s':rr.get('fallback_physics_s')})
 data={'receipt_t':np.asarray([x['start_physics_s'] for x in receipts]),'receipt_torque':np.asarray([x['command_torque_nm'] for x in receipts]),'receipt_qref':np.asarray([x.get('q_ref_rad',[np.nan,np.nan]) for x in receipts]),'trace_t':np.asarray([x['time_s'] for x in trace]),'trace_qref':np.asarray([x['q_ref_rad'] for x in trace]),'trace_truth':np.asarray([x['truth_state'] for x in trace])}
 tag=f"seed{row['training_seed']}_{row['kind']}";np.savez_compressed(r/'stability'/f'{tag}_APPLIED_SERIES.npz',**data);cache[(row['training_seed'],row['kind'])]=data
 out={'seed':row['training_seed'],'kind':row['kind'],'run':row['run'],'status':row['status'],'task_s':row['task_s'],'abort_reason':row['abort_reason'],'original_summary_phases':s.get('task',{}).get('phase_transitions'),'config_snapshot_sha256':hashlib.sha256((ep/'config_snapshot.json').read_bytes()).hexdigest(),'numeric_native_prefix_sha256':hd.hexdigest(),'native_prefix_steps':prefix_n,'independent_ownership_audit':a,'force_summary_error':a['J_F_N_s']-row['JF'],'moment_summary_error':a['J_M_Nm_s']-row['JM'],'trace_safety_modes':dict(collections.Counter(x.get('safety_mode') for x in trace)),'receipt_supervisor_modes':dict(collections.Counter(x.get('supervisor_mode',x.get('mode')) for x in receipts)),'deadline_misses':sum(bool(x.get('deadline_miss')) for x in decisions),'stale_decisions':sum(bool(x.get('stale')) for x in decisions),'decisions':slim,'applied_series_file':f'stability/{tag}_APPLIED_SERIES.npz'};result.append(out);print(json.dumps({'seed':row['training_seed'],'kind':row['kind'],'raw_audit':a['accounting_pass'],'native_steps':a['native_steps_all']}),flush=True)
pairs=[]
for seed in sorted({x['seed'] for x in result}):
 a=cache[(seed,'checkpoint050_first')];b=cache[(seed,'checkpoint080_first')];d={'seed':seed}
 for key,timekey in [('receipt_torque','receipt_t'),('receipt_qref','receipt_t'),('trace_qref','trace_t'),('trace_truth','trace_t')]:
  n=min(len(a[key]),len(b[key]));same_t=np.abs(a[timekey][:n]-b[timekey][:n])<1e-9;delta=np.max(np.abs(a[key][:n]-b[key][:n]),axis=1);indices=np.flatnonzero((delta>1e-10)&same_t)
  if len(indices):
   i=int(indices[0]);d['first_'+key+'_divergence']={'physical_s':float(a[timekey][i]),'task_s':float(a[timekey][i]-10.05),'max_abs_difference':float(delta[i]),'checkpoint050':a[key][i].tolist(),'checkpoint080':b[key][i].tolist(),'same_time_grid_at_divergence':True}
  else:d['first_'+key+'_divergence']=None
 p=[x for x in result if x['seed']==seed];d['numeric_native_prefix_identical']=p[0]['numeric_native_prefix_sha256']==p[1]['numeric_native_prefix_sha256'];d['config_snapshot_identical']=p[0]['config_snapshot_sha256']==p[1]['config_snapshot_sha256'];pairs.append(d)
report={'category':'INDEPENDENT_SAVED_NATIVE_RECOMPUTATION_NO_NEW_PHYSICS','evaluations':result,'causal_pairs':pairs,'all_accounting_pass':all(x['independent_ownership_audit']['accounting_pass'] for x in result),'no_new_physics':True,'caveat':'The matched recorded deterministic traces link changed policy to changed admitted reference, applied torque and late RETURN rejection. No optimizer/reward ablation identifies a unique statistical learning cause.'}
(r/'stability/HISTORICAL_NATIVE_EXECUTION_AUDIT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');print(json.dumps(pairs,indent=2))
