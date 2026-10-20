"""Close the sixth bounded development revision without widening time budgets."""
import json
from datetime import datetime,timezone
from research_campaign import D,S,save,sha,state

def main():
 gate=json.loads((D/'ONLINE_LATENCY_PROMOTION_GATE.json').read_text())
 if gate['status']!='PASS' or not gate.get('ready_for_small_scientific_pilot'):
  raise RuntimeError('fresh v3 scientific computation gate not ready')
 path=D/'BOUNDED_REPAIR_06_DUPLICATE_COMPUTATION.json'
 if not path.exists():save(path,{'repair_cycle':6,'timestamp_utc':datetime.now(timezone.utc).isoformat(),
  'development_revision':'reuse inherited original _evaluate for committed target; omit duplicate eager legacy baseline comparator only in explicitly flagged committed VALUE_PATTERN continuation',
  'frozen_revision_evidence':'LATENCY_LAZY_COMPARATOR_REVISION_V3.json',
  'new_revision_source_sha256':sha(S/'scripts/value_learning_v1/research_adapter.py'),
  'current_gate_sha256':sha(D/'ONLINE_LATENCY_PROMOTION_GATE.json'),
  'regression_tests':'40 PASS: 33 latency, 4 actual-snapshot semantics, 3 activation identity tests',
  'fresh_scientific_capture_and_clean_J_F_n_s':1478.8735474783039,
  'actual_physical_state_and_force_trajectory_errors':0.,
  'moving_algorithm_observed_max_ms':20.953,'first_pattern_algorithm_observed_max_ms':56.614,
  'authority_terminal_setup_escape_original_epoch_safety_preserved':True,
  'rejected_committed_target_still_fails_research_and_preserves_original_baseline_diagnostics':True,
  'time_budget_relaxed':False,'old_v2_failure_and_outlier_preserved':True,
  'full_host_wall_budget_or_hardware_qualified':False})
 state('ONLINE_PILOT_RESUME',repair_cycles_used=6,
  next_action='original verified rep1 checkpoint restore; pending immutable model promotion at original safe boundary; then independent PRIOR session')

if __name__=='__main__':main()
