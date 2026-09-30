"""Independently verify Q-selected discovery before expanding best-known set."""
import json
from research_campaign import D,RUNS,launch,save
from evidence_io import read_json

if __name__=='__main__':
 source='latency_real_capture_v1';record=read_json(RUNS/source/'rollout_result.json')
 summary=read_json(next((RUNS/source).glob('rep_*'))/'summary.json')
 first=next(d for d in summary['decisions'] if d['phase']=='OUTBOUND' and 'evaluations' in d)
 chosen=next(e for e in first['evaluations'] if e['label']==first['executed_label'])
 descriptor=chosen['execution_screen']['research_context']['continuation_descriptor']
 result=launch({'condition':record['condition_id'],'run_id':'confirm_offline_value_selected_reference_v1',
  'spec':{'mode':'PATH','descriptor':descriptor,'matched_duration_factor':1.3}})
 error=None if result['status']!='VALID' else abs(result['J_F_task_n_s']-record['J_F_task_n_s'])
 row={'condition':record['condition_id'],'discovery_run_id':source,'confirmation_run_id':result['run_id'],
  'descriptor':descriptor,'J_F_task_n_s':record['J_F_task_n_s'],'J_F_abs_difference_n_s':error,
  'independent_confirmation_pass':error is not None and error<=1e-6,
  'source':'offline-trained Q selection during opt-in latency capture; not online-personalization discovery',
  'capture_io_affects_host_profile_not_frozen_scientific_physics':True,
  'scope':'MATCHED_CONDITIONAL','physical_start':'same immutable scientific condition starting state',
  'timing_isolated_claim_requires_phase_and_count_comparison':True}
 save(D/'VALUE_SELECTED_REFERENCE_DISCOVERIES.json',{'status':'PASS' if row['independent_confirmation_pass'] else 'FAIL','rows':[row]})
