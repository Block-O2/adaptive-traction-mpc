"""Actual decision/activation-aligned returns, with continuation provenance."""
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import argparse, hashlib, json, sys
import numpy as np
R=Path(__file__).resolve().parents[4];S=R/'stages/stage5_personalized_motion_learning'
for sub in ('stage5_personalized_motion_learning','stage4_adaptive_control','stage3_full3d'):sys.path.insert(0,str(R/'stages'/sub/'src'))
sys.path.insert(0,str(S/'scripts/high_rom_v1'))
from research_adapter import context_features, make_path, digest
from evidence_io import read_json,file_sha
D=S/'docs/value_learning_research_v1';RAW=S/'results/value_learning_research_v1'
OLD=S/'results/coordination_pacing_exploration_v1/runs';OD=S/'docs/coordination_pacing_exploration_v1'
C=json.loads((D/'LEARNING_RESEARCH_V1_CONTRACT.json').read_text())
M=json.loads((OD/'CONDITION_MATRIX.json').read_text())
conditions={c['id']:c for c in M['conditions']}

def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,indent=2,sort_keys=True,allow_nan=False)+'\n');tmp.replace(p)
def sha(p):return file_sha(p)
def split(condition):
 for name,ids in C['splits'].items():
  if isinstance(ids,list) and condition in ids:return name
 raise ValueError('condition missing split:'+condition)

def extract_run(out,record,source_category, *, branch_entry=None):
 rep=next(out.glob('rep_*'));summary=read_json(rep/'summary.json')
 decisions=summary['decisions'];transitions=summary['learning_records'];trace=np.load(rep/'trace.npz')
 mask=trace['stage']=='TASK';times=trace['time_s'][mask]
 norms=np.linalg.norm(trace['physical_cuff_force_world_n'][mask],axis=1)
 if np.max(np.abs(np.diff(times)-.005))>1e-9:raise ValueError('task accounting grid invalid')
 interval_cost=norms[:-1]*.005;remaining=np.r_[np.cumsum(interval_cost[::-1])[::-1],0.]
 if abs(remaining[0]-record['J_F_task_n_s'])>1e-8:raise ValueError('trace/reported cost mismatch')
 condition=record['condition_id'];case=json.loads((R/conditions[condition]['case_path']).read_text())
 start=np.radians(case['task']['start_deg']);goal=np.radians(case['task']['goal_deg'])
 base=json.loads((OLD/conditions[condition]['baseline_run_id']/'rollout_result.json').read_text())['baseline_waypoints']
 p=record.get('pattern') or {}
 descriptor=p.get('descriptor')
 if descriptor is None:
  descriptor={'parameters':[p.get('lead',0)*p.get('amplitude',0),p.get('peak',.5)],'horizon':p.get('horizon','H4'),'return_reverse':p.get('return_reverse',False),'synchronous':p.get('synchronous',False)}
 factor=p.get('matched_duration_factor',1.3 if record['arm']=='MATCHED' else 1.)
 descriptor={**descriptor,'matched_duration_factor':factor}
 path=p.get('replay_targets') or make_path(base,start,goal,descriptor)
 policy_kind='frozen_declared_path_after_current_action' if record.get('pattern') else 'production_state_feedback_zero_value'
 continuation_id=digest({'descriptor':descriptor,'baseline':base,'rule':policy_kind})
 output=[];previous=np.zeros(2);phase_counts={};validation=[]
 for transition in transitions:
  k=transition['decision_index'];decision=decisions[k]
  if not transition.get('selected_plan_activated') or not decision.get('plan_activated'):continue
  chosen=transition['selected_plan'];phase=decision['phase'];index=phase_counts.get(phase,0);phase_counts[phase]=index+1
  actual_start=decision.get('activation_timestamp_s')
  if actual_start is None:raise ValueError('executed action missing actual activation timestamp')
  # First action has exactly one owning registered task node. Floating clock
  # error may select nearest only within the frozen 1e-9 s grid tolerance.
  idx=int(np.argmin(np.abs(times-float(actual_start))))
  if abs(times[idx]-float(actual_start))>1e-8:raise ValueError('action activation not at task sensor node')
  end=float(transition.get('end_time_s',times[-1]));end_idx=int(np.argmin(np.abs(times-end)))
  if abs(times[end_idx]-end)>1e-8:raise ValueError('transition end not on task grid')
  if end_idx<idx:raise ValueError('transition ends before actual activation')
  schedule=chosen['schedule'];target=np.asarray(chosen['target_q_rad'])
  rc=chosen.get('execution_screen',{}).get('research_context')
  if rc:
   x=np.asarray(rc['features']);names=rc['feature_names'];cid=rc['continuation_id'];desc=rc['continuation_descriptor'];policy=rc['continuation_rule']
  else:
   obj=SimpleNamespace(duration_s=schedule['duration_s'],candidate=SimpleNamespace(dq_waypoint_rad_s=np.asarray(schedule['target_dq_rad_s'])))
   x,names=context_features(state=transition['observation'],reference=decision['reference_state_rad_rad_s'],belief=transition['adaptive_state'],phase=phase,elapsed=decision['phase_elapsed_s'],remaining=decision['phase_remaining_s'],start=start,goal=goal,previous=previous,descriptor=descriptor,index=index,path=path,target=target,schedule=obj)
   cid=continuation_id;desc=descriptor;policy=policy_kind
  if transition['adaptive_state'].get('deployable_truth_consumed'):raise ValueError('truth-tainted belief')
  short_end=min(len(interval_cost),idx+300)
  segment=float(np.sum(interval_cost[idx:end_idx]));full=float(remaining[idx]);short=float(np.sum(interval_cost[idx:short_end]))
  next_q=transition.get('next_observation')
  branch_group=None
  if branch_entry:
   b=branch_entry['spec']['branch']
   if phase==b['phase'] and index==b['index']:branch_group=branch_entry['branch_group']
  row={'schema':'actual_decision_value_row_v1','condition_id':condition,'physical_condition_id':conditions[condition]['physical_condition_id'],
   'split':split(condition),'run_id':record['run_id'],'source_category':source_category,'decision_index':k,'phase_index':index,'phase':phase,
   'state':{'estimated_human_q_dq':transition['observation'],'reference_q_dq':decision['reference_state_rad_rad_s'],'phase_elapsed_s':decision['phase_elapsed_s'],'phase_remaining_s':decision['phase_remaining_s'],'deployable_belief':transition['adaptive_state'],'model_version':transition['belief_sequence_at_request'],'previous_executed_delta_q_rad':previous.tolist()},
   'action':{'target_q_rad':target.tolist(),'delta_q_rad':chosen['proposed_delta_q_rad'],'proposal_family':decision['selection_mode'],'legacy_score':chosen['total_cost'],'schedule':schedule},
   'transition':{'next_high_level_state':next_q,'next_deployable_belief':transition.get('next_adaptive_state'),'measured_actual_segment_cost_n_s':segment,'native_recorded_segment_cost_n_s':transition['measured_force_integral_n_s'],'request_time_s':transition.get('request_time_s'),'native_recorded_start_time_s':transition['start_time_s'],'actual_activation_time_s':float(actual_start),'end_time_s':end,'task_grid_activation_index':idx,'terminal':transition.get('completion')=='COMPLETE','completion':transition.get('completion'),'value_model_version_afterward':rc.get('active_value_version','ZERO') if rc else 'ZERO'},
   'return_full_n_s':full,'return_short_1p5_n_s':short,'remaining_cost_origin':'actual selected-action activation node through TASK termination; left endpoint measured force',
   'continuation_id':cid,'continuation_policy':policy,'continuation_descriptor':desc,'branch_group':branch_group,
   'feature_names':names,'features':x.tolist(),'actual_activation_verified':True,'safety_feasible':True,'task_scientific_valid':True,
   'source_summary_sha256':sha(rep/'summary.json'),'source_trace_sha256':sha(rep/'trace.npz')}
  # At branch comparisons, hash complete deployable source, reference and
  # continuation identity; exclude action identity and host timing fields.
  if branch_group:
   row['branch_state_sha256']=digest({'state':row['state'],'continuation_id':cid})
  output.append(row);previous=np.asarray(chosen['proposed_delta_q_rad'])
 return output

def extract_dataset(output_name='dataset_v1'):
 if json.loads((D/'ACTION_EXPRESSIVITY_GATE.json').read_text())['status']!='PASS':raise RuntimeError('expressivity gate not passed')
 rows=[];failures=[];sources=[]
 historical=json.loads((OD/'ALL_COORDINATION_ROLLOUTS.json').read_text())
 entries={x['run_id']:x for x in json.loads((D/'ONE_STEP_BRANCH_PLAN.json').read_text())['entries']} if (D/'ONE_STEP_BRANCH_PLAN.json').exists() else {}
 paths=[(OLD/x['run_id'],'historical') for x in historical]
 paths += [(p.parent,'research') for p in sorted((RAW/'runs').glob('*/rollout_result.json')) if not p.parent.name.startswith('pilot_')]
 seen=set()
 for out,category in paths:
  rp=out/'rollout_result.json';record=json.loads(rp.read_text())
  if record['run_id'] in seen:continue
  seen.add(record['run_id'])
  if record['status']!='VALID':
   failures.append({'run_id':record['run_id'],'status':record['status'],'reason':record.get('failure_reason'),'truncated_cost_excluded':True});continue
  if category=='historical' and record['arm']!='MATCHED':
   # Active study uses matched timing; native historical trajectories remain
   # separate to avoid pooling materially different scheduler continuations.
   continue
  branch_key=record['run_id'].split('_retry')[0]
  extracted=extract_run(out,record,category,branch_entry=entries.get(branch_key))
  rows+=extracted;sources.append({'run_id':record['run_id'],'result_sha256':sha(rp),'rows':len(extracted),'category':category,'split':split(record['condition_id'])})
  if len(sources)%30==0:print(json.dumps({'dataset_runs':len(sources),'rows':len(rows)}),flush=True)
 names=rows[0]['feature_names']
 if any(x['feature_names']!=names for x in rows):raise ValueError('feature schema inconsistency')
 checks=[];grouped={}
 for row in rows:
  if row['branch_group']:grouped.setdefault(row['branch_group'],[]).append(row)
 for key,g in grouped.items():
  ids={x['branch_state_sha256'] for x in g}
  checks.append({'group':key,'rows':len(g),'identical_checkpoint_prefix_state':len(ids)==1,'state_hashes':sorted(ids),'continuation_ids':sorted({x['continuation_id'] for x in g}),'valid_target_count':len({tuple(x['action']['target_q_rad']) for x in g}),'return_range_n_s':max(x['return_full_n_s'] for x in g)-min(x['return_full_n_s'] for x in g)})
 if any(not x['identical_checkpoint_prefix_state'] for x in checks):raise ValueError('branch source states mismatch')
 folder=RAW/output_name;folder.mkdir(parents=True,exist_ok=False)
 with (folder/'rows.jsonl').open('w') as f:
  for row in rows:f.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n')
 X=np.array([x['features'] for x in rows]);y=np.array([x['return_full_n_s'] for x in rows]);short=np.array([x['return_short_1p5_n_s'] for x in rows])
 np.savez_compressed(folder/'data.npz',X=X,y_full=y,y_short=short,split=np.array([x['split'] for x in rows]),condition=np.array([x['condition_id'] for x in rows]),group=np.array([x['branch_group'] or '' for x in rows]),legacy=np.array([x['action']['legacy_score'] for x in rows]))
 schema={'schema':'value_dataset_schema_v1','decision':'Only actually activated high-level target actions from completed VALID tasks; no whole-pattern benefit assigned to first waypoint','state':rows[0]['state'],'action_fields':list(rows[0]['action']),'transition_fields':list(rows[0]['transition']),'return':'Measured cuff-force cumulative sum from actual activation to terminal; separately next 1.5s cost','continuation':'Actual source policy family, declared parameters/schedules, continuation id and active model version; path context used as input, not omitted','feature_names':names,'feature_dimension':len(names),'truth_firewall':'Only estimated state, deployable belief, receipt/reference, task specification and declared controller memory in X; native q and future force only evaluation labels','split':C['splits'],'failure_rule':'Rejected/truncated/INVALID/EXCEPTION rows recorded separately, never attractive regression targets','native_schedule_exclusion':'Historical native-time arm excluded from current matched-scheduler cost fit; preserved historical evidence remains untouched'}
 save(D/'VALUE_DATASET_SCHEMA.json',schema)
 (D/'VALUE_DATASET_SCHEMA.md').write_text('# Per-decision cost-to-go dataset schema\n\n'+json.dumps(schema,indent=2)+'\n')
 save(D/'ONE_STEP_BRANCH_STATE_VALIDATION.json',{'status':'PASS','groups':checks,'method':'Bitwise canonical equality of estimated state/reference/complete deployable belief/previous action and continuation identity after deterministic checkpoint-prefix replay; no native state used for action selection'})
 save(folder/'failures.json',failures)
 manifest={'schema':'value_dataset_manifest_v1','status':'PASS','dataset_path':str(folder.relative_to(R)),'rows':len(rows),'runs':len(sources),'features':len(names),'sources':sources,'files_sha256':{p.name:sha(p) for p in folder.iterdir()},'split_row_counts':{k:sum(x['split']==k for x in rows) for k in ('train','validation','test')},'branch_state_groups':len(checks),'failure_rows_separately_recorded':len(failures),'source_gate':'PASS','all_actual_activations_verified':True,'all_return_targets_trace_verified':True,'no_random_neighbor_split':True}
 save(D/'VALUE_DATASET_MANIFEST.json',manifest);print(json.dumps({k:manifest[k] for k in ('status','rows','runs','features','split_row_counts','branch_state_groups')}),flush=True)
 return rows

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output-name',default='dataset_v1');args=p.parse_args();extract_dataset(args.output_name)
