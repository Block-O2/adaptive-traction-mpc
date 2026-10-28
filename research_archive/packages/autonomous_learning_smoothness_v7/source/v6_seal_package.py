"""Final seal only after scientific review, raw replay, journal and owned cleanup."""
from pathlib import Path
import json,time,datetime,hashlib,os,sys,subprocess,traceback
P=Path(__file__).resolve().parents[1]
REQUIRED=['REPORT.md','EXPERIMENT_CONTRACT.md','SMOOTHNESS_BASELINE_COMPARISON.md',
 'WRENCH_FLUCTUATION_ANALYSIS.md','CRITIC_MODEL_AUDIT.md','CRITIC_STATE_AND_LABEL_AUDIT.md',
 'SHORT_HORIZON_VS_FULL_TAIL.md','CRITIC_DECISION_VALUE.md','SMOOTHNESS_CRITIC_COMBINED_RESULTS.md',
 'OPTIMIZATION_AND_SAMPLE_EFFICIENCY.md','MOTION_FORCE_MOMENT_TRADEOFF.md',
 'LEARNING_CONTROL_INTERFACE_GUIDE.md','RESEARCH_DECISIONS.jsonl',
 'RESOURCE_AND_ATTEMPT_ACCOUNTING.json','PACKAGE_VERIFICATION.json','NEXT_RESEARCH_DECISION.md','END.json']
CHECKS=['audit/HISTORY_PROTECTION_FINAL.json','audit/V5_MANIFEST_FINAL.json',
 'audit/EXECUTION_AND_CONTRACT_INTEGRITY.json','audit/OWNED_PROCESS_FINAL.json',
 'audit/JOURNAL_APPEND_ONLY_FINAL.json','audit/UNCHANGED_SCORER_REPLAY.json',
 'audit/FROZEN_TEST_ACTUAL_STATE_INDEPENDENCE.json','audit/CAUSAL_EVENT_AVAILABILITY_AND_TRUNCATION.json',
 'audit/BASELINE_RAW_RECOMPUTE.json','audit/V5_MATCHED_RAW_REPRODUCTION.json',
 'audit/COORDINATED_UPSTREAM_FULL_RAW_IDENTITY.json','audit/LIVE_WHOLE_HISTORY_FEATURE_REPLAY.json']
CHECKS += ['audit/NATIVE_STEP_LEDGER_REPLAY.json','audit/FREEZE_AND_CAUSAL_PREDICTION_CHRONOLOGY.json','audit/LEGACY_CONTINUATION_SOURCE_IDENTITY.json','audit/O3_V5_FULL_RAW_REPLAY_IDENTITY.json']
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(q):
 h=hashlib.sha256()
 with q.open('rb') as f:
  for b in iter(lambda:f.read(4*2**20),b''):h.update(b)
 return h.hexdigest()
def utc(t):return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat()
def skip(rel):return str(rel) in {'OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json','END.json'} or any(s in {'.venv','__pycache__'} for s in rel.parts) or rel.parts[:2]==('runtime','tmp')
def main():
 assert '--finalize' in sys.argv,'EXPLICIT_LOCAL_FINALIZATION_REQUIRED'
 assert (P/'CLOSURE_START.json').exists()
 for n in CHECKS:assert read(n)['status']=='PASS',n
 second=read('analysis/SECOND_LOCAL_BOUNDARY_RESULT.json');assert second['status'] in ['COMPLETED_FROZEN_LOCAL_CHALLENGE','NOT_RUN']
 expected_legacy=3 if second['status']=='COMPLETED_FROZEN_LOCAL_CHALLENGE' else 2
 ia=read('audit/FROZEN_TEST_ACTUAL_STATE_INDEPENDENCE.json')
 assert len(ia['extra_frozen_risk_states'])==2,'RISK_STATE_INDEPENDENCE_INCOMPLETE'
 assert len(ia.get('reclassified_training_parent_replays',[]))==(expected_legacy-2),'REPLAY_RECLASSIFICATION_INCOMPLETE'
 a=read('RESOURCE_AND_ATTEMPT_ACCOUNTING.json');e=read('analysis/COMBINED_FROZEN_RESULTS.json')
 assert a['status']=='ALL_STARTED_ATTEMPTS_ACCOUNTED' and not a['unexpected_incomplete_ids']
 assert e['primary_states']==4,'CORE_FROZEN_STATES_INCOMPLETE'
 assert len(e['legacy_rows'])==expected_legacy,'LEGACY_REPAIR_AND_BOUNDARY_STATES_INCOMPLETE'
 assert len([r for r in read('analysis/BLEND_FIXED_CONFIRMATION_RESULTS.json') if r['role'].startswith('independent')])==2
 assert len(read('analysis/PROSPECTIVE_SAMPLE_EFFICIENCY.json')['rows'])==4,'SCREEN_WORKFLOW_INCOMPLETE'
 assert read('audit/UNCHANGED_SCORER_REPLAY.json')['audited']==a['physical_START']
 assert read('audit/NATIVE_STEP_LEDGER_REPLAY.json')['independently_counted_new_native_steps']==a['actual_new_native_steps'],'NATIVE_REPLAY_SUM'
 assert read('analysis/CRITIC_PHYSICAL_REPRODUCTION.json')['status'] in ['PASS','NOT_RUN']
 rule=read('analysis/ADAPTIVE_FIXED_RULE_RESULTS.json');assert rule['status'] in ['COMPLETED_FROZEN_CONFIRMATIONS','STOPPED_AT_REGISTERED_DEVELOPMENT_GATE','NOT_RUN']
 phase=read('analysis/FIXED_PHASE_RULE_RESULTS.json');assert phase['status'] in ['COMPLETED_TWO_PAIRED_CONFIRMATIONS','NOT_RUN']
 for n in ['jobs/CAMPAIGN_ERROR.json','jobs/ADAPTIVE_RULE_V3_ERROR.json','jobs/SECOND_BOUNDARY_ERROR.json']:assert not (P/n).exists(),'UNRESOLVED:'+n
 act=read('ACTIVATION.json');now=time.time();assert now<act['hard_stop_unix']
 branches=dict(primary_frozen_cost_critic='COMPLETED_NO_RETRAINING_AFTER_TEST',legacy_B_repair='COMPLETED_SEPARATE_POLICY',
  BLEND='COMPLETED_TWO_FROZEN_CONFIRMATIONS',prestate_traditional_screen='COMPLETED_DEVELOPMENT_AND_FROZEN_AUDIT',
  actual_frozen_choice_reproduction=read('analysis/CRITIC_PHYSICAL_REPRODUCTION.json')['status'],
  single_fixed_rule=rule['status'],fixed_phase_followup=phase['status'],second_local_boundary=second['status'],BO='NOT_RUN',ILC='NOT_RUN',PPO='NOT_RUN',new_Q_network='NOT_RUN',
  commissioned_other_Human='NOT_RUN',patient_hardware='NOT_RUN',Stage2_final_campaign='NOT_RUN')
 put('BRANCH_STATUS.json',dict(branches=branches,not_run_reason='No independent cost-Critic increment requiring larger learning; targeted traditional refinements and strong phase controls addressed observed decision problem. No broad search or new hardware/clinical authorization.',registered_but_incomplete_required_branches=[]))
 put('END.json',dict(state='STOP',activation_id=act['activation_id'],T0_UTC=act['T0_UTC'],T0_unix=act['T0_unix'],
  deadline_UTC=act['deadline_UTC'],hard_stop_unix=act['hard_stop_unix'],ended_UTC=utc(now),ended_unix=now,
  elapsed_seconds=now-act['T0_unix'],physical_START=a['physical_START'],physical_END=a['physical_END'],
  actual_new_native_steps=a['actual_new_native_steps'],owned_active=0,branch_status=branches,
  research_and_closeout_completed=True,automatic_next_research=False,
  cost_critic_increment_vs_strong_fixed_phase='NOT_ESTABLISHED',independent_outbound_failure_repair='NOT_TESTED',
  independently_validated_main_states=4,independent_legacy_new_states=2,quarantined_training_parent_replays=['LEGACY_BOUNDARY_O3'],
  timing_semantics='elapsed_seconds ends after scientific closeout and before final seal hashing. actual_total_wall_seconds additionally includes manifest/independent verification.',
  manifest_sha256=None,verification_sha256=None))
 # Timing/report metrics become final; all model/data/source freezes remain unchanged.
 env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
 for script in ['v6_summarize.py','v6_reports.py','v6_final_report_supplement.py']:
  r=subprocess.run([sys.executable,'-B',str(P/'source'/script)],env=env,check=False)
  assert r.returncode==0,script
 for n in REQUIRED:
  if n not in ['PACKAGE_VERIFICATION.json']:assert (P/n).is_file(),'MISSING:'+n
 files={}
 for f in sorted(P.rglob('*')):
  if not f.is_file() or skip(f.relative_to(P)):continue
  files[str(f.relative_to(P))]=dict(bytes=f.stat().st_size,sha256=sha(f))
 put('OUTPUT_MANIFEST.json',dict(activation_id=act['activation_id'],created_UTC=utc(time.time()),files=files,
  excluded_self_referential_seal_files=['OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json','END.json'],
  excluded_generated_directories=['.venv','__pycache__','runtime/tmp'],
  raw_results_sources_models_reports_audits_included=True))
 v=dict(status='PASS',created_UTC=utc(time.time()),required_artifacts=REQUIRED,
  required_artifacts_present=True,manifest_files=len(files),manifest_sha256=sha(P/'OUTPUT_MANIFEST.json'),
  checks={n:read(n)['status'] for n in CHECKS},all_attempts_accounted=True,owned_active=0,
  independent_model_evaluation_states=6,model_evaluation_training_parent_replays=1,
  sealed_identity_finding='O3 exact old training parent; original FAIL audit retained, branch excluded from independent claims, no weights retuned.',
  original_guard_task_motion_scoring_unchanged=True,v5_history_protection='PASS',journal_append_only='PASS',
  independent_verifier='VERIFY_PACKAGE.py',seal_file_self_reference_exclusion=True,
  limitations=['Only same nominal Human legal-prefix generalization; no patients/hardware.',
              'Observed risk remains incomplete; no calibrated full native qualification certificate.',
              'Frozen full-menu Critic audit saves zero physics attempts; traditional omissions are not net amortized campaign savings.'])
 put('PACKAGE_VERIFICATION.json',v)
 end=read('END.json');end.update(manifest_sha256=sha(P/'OUTPUT_MANIFEST.json'),verification_sha256=sha(P/'PACKAGE_VERIFICATION.json'));put('END.json',end)
 r=subprocess.run([sys.executable,'-B',str(P/'VERIFY_PACKAGE.py')],env=env,check=False)
 assert r.returncode==0,'READ_ONLY_INDEPENDENT_VERIFICATION_FAILED'
 finished=time.time();assert finished<act['hard_stop_unix'],'SEAL_EXCEEDED_HARD_DEADLINE'
 end=read('END.json');end.update(finalized_UTC=utc(finished),finalized_unix=finished,
  actual_total_wall_seconds=finished-act['T0_unix'],seal_and_independent_verification_wall_seconds=finished-now,
  independent_verification='PASS');put('END.json',end)
 print('FINAL_STOP',a['physical_START'],'attempts','total_hours',(finished-act['T0_unix'])/3600,flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as error:
  if (P/'END.json').exists():
   d=read('END.json');d.update(state='SEAL_FAILED',seal_error=str(error));put('END.json',d)
  raise
