"""Independent confirmation of a better post-pilot alternate, not learner credit."""
import json
from research_campaign import D,RAW,RUNS,launch,save,sha
from pilot_counterfactuals import task_initial_state

def main():
 discovery='alternate_probe_scratch_v1_rep05_P1'
 source=json.loads((RUNS/discovery/'rollout_result.json').read_text())
 specification=RAW/'specs'/(discovery+'.json')
 spec=json.loads(specification.read_text())
 if spec.get('mode')!='PATH' or 'parameters' not in spec.get('descriptor',{}):raise ValueError('expected exact original probe descriptor')
 initial=D/'POST_PILOT_PROBE_REFERENCE_DISCOVERIES.json'
 if initial.exists() and not (RAW/'POST_PILOT_PROBE_INITIAL_CONFIRMATION_FAILURE.json').exists():
  (RAW/'POST_PILOT_PROBE_INITIAL_CONFIRMATION_FAILURE.json').write_bytes(initial.read_bytes())
 result=launch({'condition':'sync_120','run_id':'confirm_post_pilot_probe_sync_exact_spec_v2','spec':spec})
 equal=result['status']=='VALID' and task_initial_state(discovery)==task_initial_state(result['run_id'])
 diff=None if result['status']!='VALID' else abs(source['J_F_task_n_s']-result['J_F_task_n_s'])
 row={'condition':'sync_120','scope':'MATCHED_CONDITIONAL','source':'post-pilot alternate probe; not chosen by online learner',
  'discovery_run_id':discovery,'confirmation_run_id':result['run_id'],'descriptor':spec['descriptor'],'exact_original_spec_sha256':sha(specification),
  'J_F_task_n_s':result.get('J_F_task_n_s'),'J_F_abs_difference_n_s':diff,'same_initial_TASK_state_verified':equal,
  'independent_confirmation_pass':equal and diff is not None and diff<=1e-6}
 save(D/'POST_PILOT_PROBE_REFERENCE_DISCOVERIES.json',{'status':'PASS' if row['independent_confirmation_pass'] else 'FAIL','rows':[row]})

if __name__=='__main__':main()
