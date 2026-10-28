"""Final seal after completed evidence review; no simulation, Git or messaging."""
from pathlib import Path
import json,time,datetime,hashlib,collections
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
A=read('ACTIVATION.json');L=read('RESOURCE_AND_ATTEMPT_ACCOUNTING.json');ev=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in ev if r['event']=='START'];ends=[r for r in ev if r['event']=='END']
assert len(starts)==len(ends)==L['physical_START']==L['physical_END'] and L['all_starts_accounted']
assert len({r['id'] for r in starts})==len(starts) and collections.Counter(r['id'] for r in starts)==collections.Counter(r['id'] for r in ends)
assert all(r.get('returncode')==0 for r in ends),'NONZERO_PHYSICS_END_REQUIRES_EXPLICIT_REVIEW'
assert time.time()<A['hard_stop_unix'] and (P/'CLOSURE_START.json').exists()
checks={
 'audit/SOURCE_AND_PERMISSION_FINAL.json':'PASS','audit/ACTION_PERMISSION_ALL.json':'PASS',
 'audit/RAW_METRIC_COVERAGE_AND_DURATION.json':'PASS','audit/QUALIFICATION_AXES_FINAL.json':'PASS','audit/NEW_FAILURE_ANT_BLIND_IDENTITY.json':'PASS','audit/FROZEN_VALIDATION_AND_PROTOCOL_AUDIT.json':'PASS',
 'audit/ALL_RECEIPT_NATIVE_IDENTITY.json':'PASS','audit/HISTORY_FINAL_VERIFICATION.json':'PASS',
 'audit/CRITIC_FROZEN_PREDICTION_REPLAY.json':'PASS','audit/CRITIC_FEATURE_SENSITIVITY_RUN_IDENTITY.json':'PASS','audit/PPO_REWARD_BASELINE_AND_REPLAY.json':'PASS','audit/ROLLING_TAIL_POLICY_AND_TIME.json':'PASS',
 'audit/OWNED_PID_FINAL_AUDIT.json':'PASS','audit/FINAL_AUDIT_DEPENDENCY_NAME_CORRECTION.json':'PASS','audit/JOURNAL_FINAL_AUDIT.json':'PASS','audit/GIT_FINAL_AUDIT.json':'PASS',
 'audit/UNCHANGED_SCORER_REPLAY.json':'PASS','audit/NATIVE_WRENCH_LOGGING_PHYSICAL_IDENTITY.json':'PASS',
 'audit/NATIVE_WRENCH_UPDATE_CADENCE.json':'PASS_SOURCE_AND_DATA_REVIEW',
 'analysis/NEW_FAILURE_TAIL_RESCUE_RESULTS.json':'PASS_EVIDENCE_IDENTITY',
 'analysis/LOCKED_VALIDATION_PAIRED_SUMMARY.json':'FROZEN_VALIDATION_COMPLETE'}
freeze=read('audit/VALIDATION_CONTROL_SOURCE_FREEZE.json');executed={};conflicts=[]
for source_manifest in (P/'jobs').glob('*/SOURCE_MANIFEST.json'):
 binding=json.loads(source_manifest.read_text())
 for rel,expected in binding['files'].items():
  if rel in executed and executed[rel]!=expected:conflicts.append(rel)
  executed[rel]=expected
 cfg=P/'experiments'/(source_manifest.parent.name+'.json')
 assert sha(cfg)==binding['config_sha256'],'EXECUTED_CONFIG_CHANGED:'+cfg.name
conflicts.extend(rel for rel,expected in freeze['files'].items() if rel in executed and executed[rel]!=expected)
bad=[rel for rel,expected in {**executed,**freeze['files']}.items() if not (P/rel).is_file() or sha(P/rel)!=expected]
for model_file in (P/'models').glob('CRITIC_*_FROZEN.json'):
 model=json.loads(model_file.read_text());assert sha(P/'source/v5_cost_critic.py')==model['source_sha256'];assert sha(P/'experiments'/('CRITIC_'+model['id']+'.json'))==model['config_sha256']
 for binding in model['models'].values():assert sha(P/binding['path'])==binding['sha256']
assert not conflicts and not bad,(conflicts,bad)
put('audit/PRESEAL_CONTROL_AND_MODEL_IDENTITY.json',dict(status='PASS',utc=utc(),unique_executed_source_files=len(executed),pre_VAL_frozen_source_files=len(freeze['files']),model_configs_and_weights_rechecked=4,mismatches=bad,conflicting_historical_job_bindings=conflicts,new_physical_START=0))
checks['audit/PRESEAL_CONTROL_AND_MODEL_IDENTITY.json']='PASS'
for name,status in checks.items():assert read(name)['status']==status,(name,read(name).get('status'))
sc=read('audit/UNCHANGED_SCORER_REPLAY.json');assert sc['audited']==len(starts) and not sc['mismatches']
receipts=read('audit/ALL_RECEIPT_NATIVE_IDENTITY.json');assert len(receipts['rows'])==len(starts)
assert all(r['unowned_native_rows']==0 and r['multiply_owned_native_rows']==0 for r in receipts['rows'])
coverage=read('audit/RAW_METRIC_COVERAGE_AND_DURATION.json');candidates=list((P/'attempts').glob('*_RESULT.json'));assert len(coverage['rows'])==len(candidates)
pid=read('audit/OWNED_PID_FINAL_AUDIT.json');assert not pid['active_owned_processes'] and not pid['untracked_package_processes']
deps=read('queue/FINAL_AUDIT_DEPENDENCIES.json')['required_queue_end'];assert all((P/n).exists() for n in deps)
assert read('owned/FINAL_AUDIT_QUEUE_END.json')['reason']=='FINITE_POST_PHYSICS_AUDITS_COMPLETED'
for name in ['SCORER_SERVICE','ANALYSIS_SERVICE']:assert (P/'owned'/(name+'_END.json')).exists()
required=['REPORT.md','EXPERIMENT_CONTRACT.md','SMOOTHNESS_INTERVENTION_COMPARISON.md','WRENCH_FLUCTUATION_ANALYSIS.md','CLEARANCE_BRANCH_MECHANISM.md','ANTICIPATORY_COORDINATION.md','SHORT_HORIZON_VS_FULL_TAIL.md','CRITIC_STUDY.md','CRITIC_DECISION_VALUE.md','OPTIMIZATION_COMPARISON.md','MOTION_FORCE_MOMENT_TRADEOFF.md','LEARNING_CONTROL_INTERFACE_GUIDE.md','RESEARCH_DECISIONS.jsonl','RESOURCE_AND_ATTEMPT_ACCOUNTING.json','NEXT_RESEARCH_DECISION.md']
assert all((P/n).is_file() and (P/n).stat().st_size>100 for n in required)
assert '最终研究已完成' in (P/'REPORT.md').read_text() and '17.' in (P/'REPORT.md').read_text()
put('WORK_STATE.json',dict(state='STOP',utc=utc(),activation_id=A['id'],T0_unchanged=True,hard_deadline_unchanged=True,physical_START=len(starts),physical_END=len(ends),actual_new_native_steps=L['actual_new_native_steps'],all_owned_computation_ended=True,final_report='REPORT.md',no_automatic_next_round=True))
put('CLOSURE_TODO.json',dict(state='STOP',utc=utc(),activation_id=A['id'],remaining_research_actions=[],all_physical_queues_closed=True,all_owned_computation_ended=True,evidence_review_complete=True,authoritative_final_seal='END.json',no_automatic_next_round=True))
exclusions=['OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json','END.json'];files={}
for p in sorted(P.rglob('*')):
 if not p.is_file() or p.is_symlink() or '__pycache__' in p.parts or '.git' in p.parts:continue
 rel=str(p.relative_to(P))
 if rel in exclusions:continue
 files[rel]=dict(bytes=p.stat().st_size,sha256=sha(p))
put('OUTPUT_MANIFEST.json',dict(utc=utc(),activation_id=A['id'],files=files,excluded_self_referential_seal_files=exclusions,excluded_generated_directories=['__pycache__','.git'],scope='All regular package artifacts including source, raw, model, receipts, reports, logs and audits; verification and END seal the manifest without a hash cycle.'))
verification=dict(status='PASS',utc=utc(),activation_id=A['id'],manifest_sha256=sha(P/'OUTPUT_MANIFEST.json'),manifest_files=len(files),manifest_bytes=sum(r['bytes'] for r in files.values()),required_artifacts=required+['PACKAGE_VERIFICATION.json','END.json'],evidence_checks={n:dict(status=read(n)['status'],sha256=sha(P/n)) for n in checks},original_scorer_recomputed_START=sc['audited'],original_scorer_mismatches=0,receipt_native_all_rows_owned=True,protected_original_metadata_files=read('audit/HISTORY_FINAL_VERIFICATION.json')['metadata_files'],all_owned_processes_ended=True,independent_replay_scope='Same research agent; independent raw/source/scorer execution paths, not an external blind reviewer.',qualification_scope='Package evidence identity/completeness PASS does not mean every motion candidate passes, guard replacement is qualified, or host/hardware/clinical qualifications exist.',read_only_verifier='python -B VERIFY_PACKAGE.py')
put('PACKAGE_VERIFICATION.json',verification)
now=time.time();result=read('RESEARCH_CONCLUSIONS.json');put('END.json',dict(state='STOP',activation_id=A['id'],T0_UTC=A['T0_UTC'],T0_unix=A['t0_unix'],hard_stop_unix=A['hard_stop_unix'],deadline_UTC=A['deadline_UTC'],ended_unix=now,ended_UTC=datetime.datetime.fromtimestamp(now,datetime.timezone.utc).isoformat(),elapsed_seconds=now-A['t0_unix'],deadline_met=now<A['hard_stop_unix'],stop_reason='FINITE_INFORMATION_VALUE_QUEUE_AND_INDEPENDENT_EVIDENCE_AUDITS_COMPLETED',physical_START=len(starts),physical_END=len(ends),cold_parent_episodes=sum(r['kind']=='LEGAL_COLD_PARENT' for r in L['attempts']),candidate_full_task_evaluations=len(candidates),actual_new_native_steps=L['actual_new_native_steps'],actual_new_native_seconds=L['actual_new_native_steps']*.00025,new_MPC_requests=sum(r['new_MPC_requests'] for r in L['attempts']),new_PPO_training_episodes=0,new_PPO_optimizer_updates=0,true_physical_attempt_savings=0,active_owned_processes=0,no_automatic_next_round=True,output_manifest_sha256=sha(P/'OUTPUT_MANIFEST.json'),package_verification_sha256=sha(P/'PACKAGE_VERIFICATION.json'),journal_final_audit_sha256=sha(P/'audit/JOURNAL_FINAL_AUDIT.json'),conclusions='RESEARCH_CONCLUSIONS.json',qualified_scope=dict(scientific_physics_task_motion='PER_ATTEMPT_ORIGINAL_RESULTS_RETAINED',formal_guard_replacement='NOT_RUN_NOT_QUALIFIED',host_real_time='NOT_EVALUABLE',hardware='NOT_TESTED',clinical='NOT_TESTED'),remaining_branches_NOT_RUN=result['not_run']))
print('SEALED_STOP',len(starts),'START',L['actual_new_native_steps'],'new native',len(files),'manifest files','elapsed_h',(now-A['t0_unix'])/3600)
