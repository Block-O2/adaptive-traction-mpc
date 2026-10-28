"""Declare fresh-segment comparisons before executing those counterfactuals."""
import json
from datetime import datetime,timezone
from research_campaign import D,save,sha

def main():
 path=D/'COUNTERFACTUAL_FRESH_SEGMENT_AMENDMENT.json'
 if path.exists():return
 pilot=D/'ONLINE_POLICY_IMPROVEMENT_PILOT.json'
 save(path,{'timestamp_utc':datetime.now(timezone.utc).isoformat(),
  'status':'FROZEN_BEFORE_FRESH_SEGMENT_COMPARISONS','original_plan_sha256':sha(D/'COUNTERFACTUAL_AND_PROBE_PLAN.json'),
  'development_pilot_snapshot_sha256':sha(pilot),
  'reason':'native settled-start rejects continuous attempts; original harness explicitly starts new development context only after its original boundary cannot legally return',
  'rules':['invalid learned repetitions receive no cost-return/capture/probe reward',
   'valid fresh segment may use original immutable fresh condition only when row records no carried native context',
   'baseline/reference/learned initial native TASK state must match exactly; otherwise comparison invalid',
   'verified prior valid checkpoint used for genuinely carried context; missing checkpoint means unavailable',
   'fresh segments excluded from consecutive-repetition convergence claims'],
  'actions_models_safety_thresholds_unchanged':True,'does_not_repair_or_override_start_guard':True,
  'never_present_as_continuous_eight_valid_repetitions':True})

if __name__=='__main__':main()
