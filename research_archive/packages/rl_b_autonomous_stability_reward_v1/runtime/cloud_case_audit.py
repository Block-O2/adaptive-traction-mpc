"""Independent saved evidence audit for natural and TEST_ONLY supplementary cases."""
from common import put
from pathlib import Path
from audit_reward_physical import audit as reward_audit
from independent_physics_audit import audit as ownership_audit
from cloud_motion_audit import audit as motion_audit
from stream_json import array_items,object_value
import argparse,json,re

def audit(run,episode=1):
 run=Path(run);ep=run/f'env/episode_{episode:04d}';raw=ep/'runtime_artifacts.json';m=json.loads((ep/'episode_summary.json').read_text());s=json.loads((ep/'summary.json').read_text())
 reward=reward_audit(run,episode,episode-1);truth=m['physical_evaluation_only'];owner=ownership_audit(raw,truth['human_qpos_indices'],truth['human_dof_indices']);motion=motion_audit(run,episode)
 proposals=json.loads((ep/'native_rl_proposals.json').read_text());requests=[x for x in array_items(raw,'requests') if x['stage']=='TASK'];joined={x['request_id']:x for x in requests};vals=list(array_items(raw,'activation_validations'));bridges=list(array_items(raw,'future_handoff_bridges'));events=list(array_items(raw,'safe_fallback_events'));decisions={d['timing_request_id']:d for d in s['decisions'] if 'timing_request_id' in d}
 def validation_respected(v):
  if v['feasible']:
   return v['reference_continuity'] and v['request_phase']==v['activation_phase'] and v['request_model_sequence']==v['activation_model_sequence']
  label=v.get('current_model_mechanics',{}).get('candidate_label','');match=re.match(r'rl_(\d+)_',label)
  if not match:return False
  linked=[p for p in proposals if p['action_id']==int(match.group(1))]
  return len(linked)==1 and joined[linked[0]['request_id']]['outcome']=='REJECTED'
 checks={'reward_independent':reward['pass'],'single_native_owner_torque_and_source_age':not (owner['native_grid_errors'] or owner['unowned_native_steps'] or owner['torque_receipt_mismatches'] or owner['receipt_count_mismatches'] or owner['source_age_errors']),'raw_trace_integral_consistency':owner['accounting_pass'],'actual_human_motion_and_safety':motion['pass'],'no_truth_consumed_by_current_certificate':all(not v['truth_consumed'] and not v['current_model_mechanics']['deployable_truth_consumed'] for v in vals),'current_state_certificate_feasible':all(validation_respected(v) for v in vals),'100ms_original_immutable_age':all(0<=x['activation_simulation_version']['sim_time_s']-x['source_sample_time_s']<.1-1e-12 for x in requests if x['outcome']=='ACTIVATED'),'activation_same_episode_and_model':all(x['source_simulation_version']['episode_epoch']==x['activation_simulation_version']['episode_epoch'] and x['source_simulation_version']['human_model_version']==x['activation_simulation_version']['human_model_version'] for x in requests if x['outcome']=='ACTIVATED'),'40ms_bridges_original':all(abs(x['bridge_duration_s']-.04)<1e-12 and x['prevalidated'] and x['bridge_mechanics']['feasible'] for x in bridges),'one_native_proposal_per_request':len(proposals)==len(requests) and {p['request_id'] for p in proposals}==set(joined),'proposal_action_ids_unique':len({p['action_id'] for p in proposals})==len(proposals),'immutable_source_sample':all(abs(p['source_sample_s']-joined[p['request_id']]['source_sample_time_s'])<1e-12 for p in proposals),'decision_candidate_single_no_teacher_ranking':all((d['candidate_count']==1) if 'candidate_count' in d else (d.get('activation_outcome')=='FAILED' and not d.get('plan_activated') and bool(d.get('planning_exception'))) for d in decisions.values()),'executor_closed':object_value(raw,'executor_closed') is True}
 # A proposal is a certified waypoint intent; actual applied action remains torque in owned receipts.
 links=[]
 for p in proposals:
  req=joined[p['request_id']];d=decisions.get(p['request_id']);links.append({'action_id':p['action_id'],'request_id':p['request_id'],'proposed_rl_action':p['action'],'source_sample_s':p['source_sample_s'],'outcome':req['outcome'],'reason':req.get('reason'),'plan_activated':None if d is None else d.get('plan_activated'),'executed_label':None if d is None else d.get('executed_label'),'activation_physics_s':None if req.get('activation_simulation_version') is None else req['activation_simulation_version']['sim_time_s']})
 result={'category':'INDEPENDENT_SAVED_REAL_PHYSICS_EVIDENCE','run':str(run),'episode':episode,'pass':all(checks.values()),'checks':checks,'status':m['status'] if 'status' in m else s['status'],'reward':reward,'ownership':owner,'motion':motion,'native_actions':links,'activation_validations':len(vals),'bridges':len(bridges),'fallback_events':[{'event':x['event'],'physics_s':x['physics_s'],'request_id':x.get('request_id')} for x in events],'proposal_is_applied_action':False,'applied_action_definition':'actual command_torque_nm on each command receipt; every native step independently assigned to exactly one receipt','legacy_exact_19_03_regression':abs(m['task_s']-19.03)<.05 if m['success'] else 'NOT_APPLICABLE','scope':'observed native scientific execution only; no host realtime or all-action Human qualification'}
 put(ep/'CLOUD_CASE_AUDIT.json',result);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('run');p.add_argument('--episode',type=int,default=1);a=p.parse_args();x=audit(a.run,a.episode);print(json.dumps({'pass':x['pass'],'checks':x['checks'],'status':x['status'],'reward':x['reward']['sum_reward']}))
