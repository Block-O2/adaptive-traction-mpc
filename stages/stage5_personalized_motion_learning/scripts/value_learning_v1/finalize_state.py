"""Finish bounded analysis candidly; push equality is an unsatisfied requirement."""
import json,subprocess
from datetime import datetime,timezone
from research_campaign import R,D,RUNS,C,save

REQUIRED=['LEARNING_RESEARCH_V1_CONTRACT.md','LEARNING_RESEARCH_V1_CONTRACT.json','ACTION_EXPRESSIVITY_GATE.md','ACTION_EXPRESSIVITY_GATE.json','BEST_KNOWN_REFERENCE_SEARCH.md','BEST_KNOWN_REFERENCE_TABLE.json','REFERENCE_SEARCH_CONVERGENCE.csv','REFERENCE_SEARCH_CONVERGENCE.json','VALUE_DATASET_SCHEMA.md','VALUE_DATASET_SCHEMA.json','VALUE_DATASET_MANIFEST.json','OFFLINE_VALUE_MODEL_COMPARISON.md','OFFLINE_VALUE_MODEL_COMPARISON.json','SHORT_VS_FULL_VALUE_ABLATION.json','SCRATCH_VS_PRIOR_ANALYSIS.json','ONLINE_DECISION_LATENCY.md','ONLINE_DECISION_LATENCY.json','TRAINING_UPDATE_LATENCY.json','ONLINE_POLICY_IMPROVEMENT_PILOT.md','ONLINE_POLICY_IMPROVEMENT_PILOT.json','CONVERGENCE_ANALYSIS.md','CONVERGENCE_ANALYSIS.json','KNOWN_BENEFIT_CAPTURE.json','LEARNING_RESEARCH_V1_REPORT.md','RAW_DATA_MANIFEST.json','STATE.json','FINGERPRINTS.json']

def main():
 missing=[name for name in REQUIRED if not (D/name).exists()]
 if missing:raise RuntimeError('required evidence missing: '+str(missing))
 open_runs=[p.parent.name for p in RUNS.glob('*/rollout_result.json') if json.loads(p.read_text()).get('status')=='RUNNING']
 if open_runs:raise RuntimeError('scientific units still open: '+str(open_runs))
 state=json.loads((D/'STATE.json').read_text());now=datetime.now(timezone.utc)
 branch=subprocess.check_output(['git','-C',str(R),'branch','--show-current'],text=True).strip()
 head=subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()
 remote=subprocess.check_output(['git','-C',str(R),'ls-remote','origin','refs/heads/'+branch],text=True).strip()
 remote_sha=remote.split()[0] if remote else None
 audit=json.loads((D/'PILOT_EXECUTION_AUDIT.json').read_text())
 save(D/'STATE.json',{**state,'status':'VALUE_LEARNING_RESEARCH_V1_BLOCKED','phase':'FINAL_ANALYSIS_SAVED',
  'scientific_work_status':'COMPLETED_BOUNDED_STUDY_WITH_NATIVE_CONTINUITY_BLOCKER',
  'updated_utc':now.isoformat(),'campaign_elapsed_wall_s':(now-datetime.fromisoformat(C['campaign_start_utc'])).total_seconds(),
  'repair_cycles_used':6,'repair_budget_limit':6,'additional_controller_or_safety_revision_attempted':False,
  'pilot_attempted':sum(s['attempted'] for s in audit['sessions']),'pilot_valid':sum(s['valid'] for s in audit['sessions']),
  'continuous_pilot_demonstrated':False,'five_rep_convergence_demonstrated':False,
  'blocked_reasons':['native next-epoch reference bootstrap invalidates previously settled state before start guard; eight of sixteen starts rejected; no safety override or seventh pipeline repair',
   'git push auto-review rejected: destination/outbound research authorization requires user confirmation; final local/remote equality not achieved'],
  'remaining_deployment_gates':['full moving capture-to-activation host maximum47.410ms exceeds preliminary35ms opportunity; scientific algorithm profile is not realtime qualification',
   'held-out full-Q ranking transfer remains weak; native-conditioned critic not trained/evaluated'],
  'phase_outcomes':{'contract':'FROZEN','expressivity':'PASS_4_MATCHED_4_NATIVE','reference_search':'COMPLETE_FINITE_ALLOCATED_BUDGET','dataset':'PASS','offline_models':'COMPLETE_WITH_MIXED_TRANSFER','latency':'COMPLETE_SCIENTIFIC_ALGORITHM_PLAUSIBLE_HOST_BUDGET_UNDEMONSTRATED','pilot':'COMPLETE_ATTEMPT_BUDGET_NATIVE_START_GUARD_FAILURE','convergence':'ANALYZED_NO_CONTINUOUS_TRIGGER','analysis_report':'20_QUESTIONS_ANSWERED_WITH_UNAVAILABLE_REP8_MARKED','push':'BLOCKED_AUTO_APPROVAL'},
  'git':{'branch':branch,'head_before_final_evidence_checkpoint':head,'remote_branch_sha_observed':remote_sha,'equal':head==remote_sha,'remote_url':'https://github.com/Block-O2/adaptive-traction-mpc'},
  'next_action':'user review/authorize exact GitHub branch push; separately version continuity-consistent native template+ridge-Q development before larger learning study',
  'no_final_30rep_hardware_or_realtime_experiment':True})
 save(D/'REQUIRED_OUTPUT_CHECKLIST.json',{'status':'PASS_FILES_PRESENT','required_files':REQUIRED,'no_open_scientific_rollouts':True,'push_requirement_satisfied':head==remote_sha,'overall_status':'VALUE_LEARNING_RESEARCH_V1_BLOCKED'})

if __name__=='__main__':main()
