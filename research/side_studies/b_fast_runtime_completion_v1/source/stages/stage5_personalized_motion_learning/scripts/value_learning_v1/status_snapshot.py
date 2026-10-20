"""Compact read-only campaign status; no raw trace printing."""
import json
from research_campaign import D,RAW

def main():
 for name,keys in (
  ('STATE.json',['status','phase','search_evaluations','branch_attempts','repair_cycles_used']),
  ('VALUE_DATASET_MANIFEST.json',['status','dataset_path','rows','runs','features','branch_state_groups','split_row_counts']),
  ('OFFLINE_MODEL_PROMOTION_GATE.json',['status','chosen_model','ranking']),
  ('OFFLINE_VALUE_MODEL_COMPARISON.json',['ranking_gate','best_full_model']),
  ('ONLINE_LATENCY_PROMOTION_GATE.json',['status','pilot_configuration']),
  ('ONLINE_POLICY_IMPROVEMENT_PILOT.json',['status'])):
  path=D/name
  if not path.exists():continue
  record=json.loads(path.read_text());out={k:record[k] for k in keys if k in record}
  if 'ranking' in out:out['ranking']={k:v for k,v in out['ranking'].items() if k!='groups'}
  print(json.dumps({'file':name,**out}),flush=True)
 for name in ('BEST_KNOWN_REFERENCE_TABLE.json','NATIVE_BEST_KNOWN_REFERENCE_TABLE.json'):
  path=D/name
  if path.exists():
   record=json.loads(path.read_text());print(json.dumps({'file':name,'rows':[{k:r.get(k) for k in ('condition','best_known_J_F_n_s','improvement_over_previous_n_s','evaluations','level_evaluations')} for r in record['rows']]}),flush=True)
 path=D/'OFFLINE_VALUE_MODEL_COMPARISON.json'
 if path.exists():
  record=json.loads(path.read_text())
  print(json.dumps({'selected_offline_models':{k:{'validation_rank':{a:b for a,b in r['validation_full_action_ranking'].items() if a!='groups'},'test_rank':{a:b for a,b in r['test_full_action_ranking'].items() if a!='groups'},'test_MAE_n_s':r['test_target_prediction']['MAE_n_s'],'test_RMSE_n_s':r['test_target_prediction']['RMSE_n_s']} for k,r in record['selected_models'].items()}}),flush=True)
if __name__=='__main__':main()
