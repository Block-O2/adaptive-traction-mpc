"""Independent saved-raw qualification; physics itself is not rerun here."""
from pathlib import Path
import json,math
from common import ROOT,SOURCE,put
from stream_json import array_items,object_value
from audit_reward_physical import audit as reward_audit
def audit(run,policy):
 run=Path(run);ep=run/'env/episode_0001';raw=ep/'runtime_artifacts.json'
 metrics=json.loads((ep/'episode_summary.json').read_text());summary=json.loads((ep/'summary.json').read_text());reward=reward_audit(run)
 requests=[r for r in array_items(raw,'requests') if r['stage']=='TASK'];proposals=json.loads((ep/'native_rl_proposals.json').read_text())
 joined={r['request_id']:r for r in requests};checks={}
 checks['reward_independent']=reward['pass']
 checks['one_proposal_per_request']=len(proposals)==len(requests) and {p['request_id'] for p in proposals}==set(joined)
 checks['causal_immutable_sources']=all(abs(p['source_sample_s']-joined[p['request_id']]['source_sample_time_s'])<1e-12 for p in proposals)
 checks['100ms_same_episode_admission']=all(0<=r['activation_simulation_version']['sim_time_s']-r['source_sample_time_s']<.1-1e-12 and r['source_simulation_version']['episode_epoch']==r['activation_simulation_version']['episode_epoch'] and r['source_simulation_version']['human_model_version']==r['activation_simulation_version']['human_model_version'] for r in requests if r['outcome']=='ACTIVATED')
 vals=list(array_items(raw,'activation_validations'));bridges=list(array_items(raw,'future_handoff_bridges'))
 checks['current_state_certificate']=all(r['feasible'] and r['reference_continuity'] and not r['truth_consumed'] and r['request_phase']==r['activation_phase'] and r['current_model_mechanics']['feasible'] and not r['current_model_mechanics']['deployable_truth_consumed'] for r in vals)
 checks['bridges_40ms']=all(abs(r['bridge_duration_s']-.04)<1e-12 and r['prevalidated'] and r['bridge_mechanics']['feasible'] for r in bridges)
 count=0;previous=0.;native_grid=True;rom=True;contacts=0
 for r in array_items(raw,'native_states_evaluation_only'):
  count+=1;native_grid &= abs(r['time_s']-previous-.00025)<1e-8;previous=r['time_s']
  q=r['qpos_evaluation_only'][:2];rom &= all(-1e-8<=v<=math.radians(125.)+1e-8 for v in q)
  contacts+=len(r['contact_pairs_evaluation_only'])
 checks['native_grid_count']=native_grid and count==metrics['native_steps_total']
 checks['native_ROM']=rom
 # Count all contacts diagnostically; only actual shank/bed task contacts are prohibited here.
 checks['no_task_bed_contact']=summary['task']['shank_bed_contact_sample_count_evaluation_only']==0
 applied=0;geometry=True;acceleration=True
 for r in array_items(raw,'execution_attempts'):
  if not r.get('applied'):continue
  applied+=1;geometry &= r.get('actual_loaded_target_geometry',{}).get('feasible',False)
  acceleration &= all(abs(x)<=math.radians(lim)+1e-8 for x,lim in zip(r.get('effective_reference_motion_check',{}).get('acceleration_rad_s2',[0,0]),[300,600]))
 receipts=list(array_items(raw,'command_receipts'))
 receipt_count=sum(bool(r.get('applied')) for r in receipts)
 checks['positive_applied_receipts']=receipt_count==metrics['applied_receipts'] and receipt_count>0 and applied>0 and geometry and acceleration
 checks['executor_closed']=object_value(raw,'executor_closed') is True
 source=(SOURCE/'stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_sac_expert_v1.py').read_text(encoding='utf-8')
 checks['governor_source_preserved']=all(x in source for x in ('reference_governor.select(','reference_governor.commit(','if online_command_period_s is not None:'))
 from independent_physics_audit import audit as physical_audit
 truth=metrics['physical_evaluation_only'];physical=physical_audit(raw,truth['human_qpos_indices'],truth['human_dof_indices'])
 checks['single_native_owner_torque_and_source_age']=physical['accounting_pass']
 if policy=='hold':
  checks['legal_zero_progress_fails_no_bonus']=not metrics['success'] and metrics['status']=='ABORTED' and metrics['reward_totals']['completion']==-10 and sum(metrics['reward_totals'].values())<=-10.+1e-8
 else:
  from ready_env import completion_evidence
  checks['full_original_task_complete']=metrics['success'] and completion_evidence(summary,metrics['phases']) and abs(metrics['task_s']-19.03)<.05
 if policy=='maximal':checks['bridge_and_admission_exercised']=len(bridges)>0 and len(vals)>0
 if policy=='maximal':
  events=[r['event'] for r in array_items(raw,'safe_fallback_events')]
  checks['rejected_proposal_legal_brake_hold_resume']=all(x in events for x in ('PRIMARY_REJECTED_ESCAPE_RETAINED','FALLBACK_COMMITTED','FALLBACK_STOPPED','FALLBACK_HOLD','FRESH_REPLAN_REQUESTED','RESUME_ACTIVATED'))
 result={'category':'INDEPENDENT_RAW_NATIVE_SCIENTIFIC_AUDIT','policy':policy,'pass':all(checks.values()),'checks':checks,'reward':reward,'physical_accounting':physical,'task_s':metrics['task_s'],'status':metrics['status'],'abort_reason':metrics['abort_reason'],'native_steps':count,'applied_execution_attempts':applied,'receipt_count':receipt_count,'requests':len(requests),'rejected_requests':sum(r['outcome']!='ACTIVATED' for r in requests),'bridges':len(bridges),'all_contact_pairs_diagnostic':contacts,'scope':'development nominal only; no host real-time or generalization claim'}
 put(run/'INDEPENDENT_AUDIT.json',result);return result
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--policy',required=True,choices=['hold','maximal','random']);a=p.parse_args();out=audit(a.run,a.policy);print(json.dumps(out));raise SystemExit(0 if out['pass'] else 1)
