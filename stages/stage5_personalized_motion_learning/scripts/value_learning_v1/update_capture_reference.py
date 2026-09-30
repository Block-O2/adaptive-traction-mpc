"""Update capture after independent probe confirmation; preserve original reference."""
import json
from research_campaign import D,RAW,save,sha
from pilot_counterfactuals import task_initial_state

def main():
 discovery=json.loads((D/'POST_PILOT_PROBE_REFERENCE_DISCOVERIES.json').read_text())['rows'][0]
 if not discovery['independent_confirmation_pass']:raise RuntimeError('new reference not confirmed')
 path=D/'KNOWN_BENEFIT_CAPTURE.json';data=json.loads(path.read_text())
 if data['status']!='COMPLETE':raise RuntimeError('initial capture units still running')
 original=RAW/'KNOWN_BENEFIT_CAPTURE_INITIAL_FROZEN_REFERENCE.json'
 if not original.exists():original.write_bytes(path.read_bytes())
 reference_state=task_initial_state(discovery['confirmation_run_id'])
 for row in data['rows']:
  if row['status']!='VALID':continue
  if row.get('updated_reference_independent_confirmation_run_id'):continue
  # Current valid attempts are separate fresh conditions. A carried checkpoint
  # would require a new state-specific reference rollout, not this transfer.
  fresh=('fresh' in row.get('starting_state_scope',''))
  equal=fresh and task_initial_state(row['learned_run_id'])==reference_state
  if not equal:
   row['updated_reference_unavailable_reason']='new reference source does not match this carried/adaptation starting state';continue
  for key in ('reference_J_F_n_s','reference_run_id','reference_regret_n_s','known_benefit_denominator_n_s','known_benefit_capture'):
   row['initial_frozen_'+key]=row.get(key)
  denominator=row['baseline_J_F_n_s']-discovery['J_F_task_n_s']
  row.update(reference_J_F_n_s=discovery['J_F_task_n_s'],reference_run_id=discovery['confirmation_run_id'],
   reference_policy_discovery_run_id=discovery['discovery_run_id'],
   reference_regret_n_s=row['learned_J_F_n_s']-discovery['J_F_task_n_s'],
   known_benefit_denominator_n_s=denominator,
   known_benefit_capture=None if denominator<=1e-6 else (row['baseline_J_F_n_s']-row['learned_J_F_n_s'])/denominator,
   updated_reference_independent_confirmation_run_id=discovery['confirmation_run_id'],
   updated_reference_same_initial_TASK_state_evaluation_verified=True,
   updated_reference_source_scope='same original immutable fresh scientific condition; different active critic affects only task action selection, not pre-task initialization; no continuous carryover claim')
 data.update(post_pilot_confirmed_best_known_reference_updated=True,
  initial_frozen_reference_evidence_path=str(original.relative_to(RAW)),initial_frozen_reference_sha256=sha(original))
 save(path,data)

if __name__=='__main__':main()
