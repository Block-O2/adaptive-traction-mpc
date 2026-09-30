"""Freeze development anchor/probe plan before any counterfactual rollout."""
from datetime import datetime,timezone
from research_campaign import D,RAW,save,sha

def main():
 path=D/'COUNTERFACTUAL_AND_PROBE_PLAN.json'
 if not path.exists():save(path,{'timestamp_utc':datetime.now(timezone.utc).isoformat(),
  'status':'FROZEN_BEFORE_COUNTERFACTUAL_ROLLOUTS','study':'development, retrospective evidence, never influences an already executed action',
  'sessions':['SCRATCH','PRIOR'],'condition':'sync_120',
  'matched_baseline_and_reference_repetitions':list(range(1,9)),
  'native_baseline_and_reference_repetitions':[1,3,5,8],
  'targeted_alternative_repetitions':[1,3,5,8],
  'targeted_alternative_amplitude_deltas':[-.03,.03],'amplitude_clip':[-.2,.2],
  'source':'same verified end-of-previous-repetition checkpoint followed by original safe boundary; rep1 uses original immutable start',
  'all_initial_task_states_verified_equal_evaluation_only':True,'no_thresholds_fixed_before_pilot_distributions':True,
  'failed_probe_not_a_good_truncated_return':True,'new_better_learned_reference_requires_independent_confirmation':True})
 path=D/'PILOT_PROTOCOL_DEVIATIONS.json'
 if not path.exists():save(path,{'timestamp_utc':datetime.now(timezone.utc).isoformat(),
  'status':'PRESERVED_REQUIRES_NEW_COMPUTATION_GATE_BEFORE_RESUME',
  'deviations':[{'run_id':'pilot_scratch_v1_rep_01','physical_status':'VALID',
   'description':'first scratch repetition executed under subsequently superseded stationary continuation proxy gate; genuinely moving snapshot was not then benchmarked',
   'not_retroactively_classified_as_actual_moving_gate_pass':True,
   'old_publication_preserved_path':'latency_gate_v1/ONLINE_LATENCY_PROMOTION_GATE_STATIONARY_PROXY_SUPERSEDED.json',
   'old_publication_sha256':sha(RAW/'latency_gate_v1/ONLINE_LATENCY_PROMOTION_GATE_STATIONARY_PROXY_SUPERSEDED.json'),
   'rep1_and_source_checkpoint_preserved':True,
   'remediation':'new actual-moving v3 development profile with identical physical trace; original checkpoint resume only after current gate PASS; boundary amendment identifies later computation version'}]})

if __name__=='__main__':main()
