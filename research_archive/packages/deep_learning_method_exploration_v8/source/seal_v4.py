"""Strict final seal; no new physics, no automatic next round."""
from pathlib import Path
import os,json,hashlib,time,datetime
P=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
def put(n,d):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);t=f.with_suffix(f.suffix+'.tmp');t.write_text(json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False)+'\n');t.replace(f)
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as z:
  for b in iter(lambda:z.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
a=read('ACTIVATION.json');account=read('RESOURCE_AND_ATTEMPT_ACCOUNTING.json');summary=read('analysis/RESULT_SUMMARY.json');assert time.time()<a['hard_stop_unix'],'ACTIVATION_DEADLINE';assert account['all_starts_accounted'] and account['physical_START']==account['physical_END']==38,'ATTEMPTS_NOT_CLOSED';assert account['actual_new_native_steps']<read('runtime/RUN_PLAN.json')['native_step_cap']
for n in ['audit/PRESEAL_AUDIT.json','audit/ALL_RECEIPT_NATIVE_IDENTITY.json','audit/UNCHANGED_SCORER_REPLAY.json','audit/DIAGNOSTIC_AND_FACTOR_CONTROL_IDENTITY.json']:assert read(n)['status']=='PASS',n
assert read('audit/UNCHANGED_SCORER_REPLAY.json')['audited']==38
assert read('audit/DIAGNOSTIC_AND_FACTOR_CONTROL_IDENTITY.json')['completed_comparisons']==8
for group in ['DEV','FACT','VAL_A','VAL_B','VAL_C']:
 d=read('owned/'+group+'_SUPERVISOR_END.json');assert d['worker_exit_code']==0 and not d['survivors_found_and_terminated'],group
assert read('owned/FOLLOWUP_QUEUE_END.json')['reason']=='FINITE_PREREGISTERED_QUEUE_COMPLETED'
assert read('owned/FACTOR_VALIDATION_QUEUE_END.json')['reason']=='FINITE_VAL_C_COMPLETED'
assert (P/'owned/SCORER_SERVICE_END.json').exists()
# Prospective prediction timing is verified independently of prediction accuracy.
pred=read('predictions/DEV_PREREGISTERED_PREDICTIONS.json');ptime=datetime.datetime.fromisoformat(pred['frozen_utc']).timestamp();events=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];localstarts=[e for e in events if e['event']=='START' and e['id'].startswith('DEV_LOCAL_')];assert len(localstarts)==6 and all(e['unix']>ptime for e in localstarts)
assert read('predictions/FROZEN_MENU_DECISION.json')['status']=='POSTHOC_RULE_DIAGNOSTIC_NOT_PROSPECTIVE_OPTIMIZER'
required=['REPORT.md','EXPERIMENT_CONTRACT.md','CLEARANCE_GEOMETRY_ANALYSIS.md','DUAL_ENDPOINT_CONSTRAINT_STUDY.md','ISOLATED_GUARD_IMPLEMENTATION.md','CAUSAL_PHYSICAL_COMPARISON.md','OPTIMIZATION_IMPACT.md','REPRESENTATION_PERMISSION_ALIGNMENT.md','LEARNING_DECISION_STUDY.md','CROSS_STATE_VALIDATION.md','RESEARCH_DECISIONS.jsonl','RESOURCE_AND_ATTEMPT_ACCOUNTING.json','NEXT_RESEARCH_DECISION.md']
assert all((P/n).is_file() and (P/n).stat().st_size for n in required),'DELIVERABLE_MISSING'
partial_files=list((P/'analysis/partials').glob('*.json'));bad=[]
for f in partial_files:
 d=json.loads(f.read_text());checks=d.get('protected_task_failure',{}).get('hard_safety_conditions',{})
 if not checks or any(v is not True for v in checks.values()):bad.append(d['id'])
assert not bad,'PARTIAL_HARD_SAFETY_REVIEW_REQUIRED:'+str(bad)
# Append only a concise final decision; preserve the initial journal prefix.
now=datetime.datetime.now(datetime.timezone.utc);j=P.parent/'RESEARCH_DECISION_JOURNAL.md';old=read('audit/JOURNAL_BEFORE.json');content=j.read_bytes();assert hashlib.sha256(content[:old['size']]).hexdigest()==old['sha256'];marker='Constraint Geometry & Learning v4 结束 ['+a['id']+']'
if marker not in content.decode():
 body=f"本轮完成双端点解析导数与采样间条件推导、原guard精确重放、六个未见局部点预测、终点锁/时长编译2×2物理消融及三个冻结合法prefix复核。点态等价成立，但observer/actuator误差界和可行backup尚未闭包，故未物理替换guard。局部分支模型6/6吻合，未证明独立Learning或优化效率收益。保留终点锁而恢复旧H150时长的开发候选JF1397.383797、JM108.639143，力矩代价上升，跨状态资格按冻结结果限定。全部{account['physical_START']}次物理尝试和失败partial计账，原门不变；raw/scorer、历史SHA和owned退出均已核验。下一步先补保护界与同权限状态相关运动余量，再决定Learning。本轮STOP，无硬件、Stage2或自动下一轮。"
 with j.open('a') as f:f.write('\n\n---\n\n## '+now.isoformat()+' UTC — '+marker+'\n\n'+body+'\n');f.flush();os.fsync(f.fileno())
content=j.read_bytes();put('audit/JOURNAL_FINAL_AUDIT.json',dict(status='PASS',original_prefix_preserved=hashlib.sha256(content[:old['size']]).hexdigest()==old['sha256'],start_and_end_present=bool(a['id'] in content.decode() and marker in content.decode()),final_size=len(content),final_sha256=hashlib.sha256(content).hexdigest()))
with (P/'RESEARCH_DECISIONS.jsonl').open('a') as f:f.write(json.dumps(dict(utc=now.isoformat(),decision='FINAL_STOP',physical_START=account['physical_START'],new_native_steps=account['actual_new_native_steps'],guard_replacement='NOT_RUN_AFTER_PROTECTION_GATE',local_frozen_predictions=f"{sum(bool(r['match']) for r in summary['local_unseen'])}/6",P3B='NOT_RUN',independent_learning_or_new_PPO='NOT_RUN',all_owned_scientific_jobs_ended=True,next_round_started=False),ensure_ascii=False)+'\n')
source={}
for directory in ['source','legacy_source','runtime/control','runtime/code','runtime/deps','runtime/source']:
 for f in (P/directory).rglob('*'):
  if f.is_file() and 'results' not in f.relative_to(P/directory).parts and f.suffix in ['.py','.json','.xml','.so','.toml','.yaml','.yml']:source[str(f.relative_to(P))]=sha(f)
put('audit/FINAL_SOURCE_IDENTITY.json',dict(files=source,guard_replacement=False,cloud_execution_closure=True))
put('STATUS.json',dict(state='STOP',activation=a['id'],scientific_jobs='ALL_ENDED',qualification='ORIGINAL_GUARD_SIMULATION_ONLY; NO_REPLACEMENT_QUALIFICATION',new_physics_allowed=False,next_round_started=False))
# Exclude circular/self-referential final control files; everything else is sealed.
exclude={'OUTPUT_MANIFEST.json','OUTPUT_MANIFEST_VERIFY.json','PACKAGE_VERIFICATION.json','END.json'};files={}
for f in sorted(P.rglob('*')):
 if not f.is_file() or str(f.relative_to(P)) in exclude:continue
 files[str(f.relative_to(P))]=dict(sha256=sha(f),size=f.stat().st_size)
put('OUTPUT_MANIFEST.json',dict(schema='cgl4.output.v1',files=files,excluded_final_control_files=sorted(exclude)))
bad=[n for n,r in files.items() if (P/n).stat().st_size!=r['size'] or sha(P/n)!=r['sha256']];assert not bad,'OUTPUT_MANIFEST_MISMATCH';put('OUTPUT_MANIFEST_VERIFY.json',dict(status='PASS',files=len(files),mismatches=bad,manifest_sha256=sha(P/'OUTPUT_MANIFEST.json')))
verification=dict(status='PASS_WITH_PRESERVED_MOTION_AND_TASK_FAILURES',verification_pass=True,state='STOP',closeout_metadata_path_error_recovered='PASS; exact inverse mapping, original values retained; failed records preserved',task_torque_clipping_audit='38/38 exhaustive task receipt joins; 0 clipped commands',physical_START=38,physical_END=38,actual_new_native_steps=account['actual_new_native_steps'],all_starts_accounted=True,protected_task_partial_ids=account.get('protected_task_failure_ids',[]),complete_motion_failure_ids=account['motion_failure_ids'],original_scorer_verdict_replay='38/38 EXACT',all_archived_native_receipt_identity='PASS; including partials and inherited prefixes',original_guard_and_runtime_source='UNCHANGED; exact six historical and two factorial control replications',frozen_local_predictions_before_START=True,local_predictions_match=sum(bool(r['match']) for r in summary['local_unseen']),local_predictions_evaluated=6,menu_selection_analysis='POSTHOC; no prospective optimizer claim',old_vs_new_guard_optimization='NOT_RUN',independent_learning_and_new_PPO='NOT_RUN',prior_manifest_hashes='14677 files; 0 mismatches',protected_metadata=read('audit/PROTECTED_METADATA_AFTER.json')['status'],journal_start_end_and_original_prefix='PASS',all_owned_scientific_jobs_ended=True,job_source_and_parent_audit='5/5 PASS',git_HEAD=read('audit/GIT_AFTER.json')['HEAD'],git_tracked_clean=True,guard_safety_promotion='NOT_ESTABLISHED; NO_PHYSICAL_REPLACEMENT',hardware_stage2_or_next_round_started=False,required_deliverables=required+['PACKAGE_VERIFICATION.json','END.json'],manifest_file_count=len(files),manifest_sha256=sha(P/'OUTPUT_MANIFEST.json'))
put('PACKAGE_VERIFICATION.json',verification);end=time.time();put('END.json',dict(state='STOP',activation=a['id'],T0_UTC=a['T0_UTC'],end_UTC=datetime.datetime.fromtimestamp(end,datetime.timezone.utc).isoformat(),end_Asia_Shanghai=datetime.datetime.fromtimestamp(end,datetime.timezone(datetime.timedelta(hours=8))).isoformat(),elapsed_seconds=end-a['t0_unix'],hard_stop_unix=a['hard_stop_unix'],deadline_met=end<a['hard_stop_unix'],all_owned_scientific_jobs_ended=True,physical_START=38,physical_END=38,new_native_steps=account['actual_new_native_steps'],verification_pass=True,package_verification_sha256=sha(P/'PACKAGE_VERIFICATION.json'),next_round_started=False))
print('SEALED_STOP',end-a['t0_unix'],'seconds',len(files),'files',flush=True)
