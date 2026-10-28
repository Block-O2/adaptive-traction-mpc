"""Detached bounded read-only finalization, reports, source/identity seal; no new jobs."""
from pathlib import Path
import os,sys,json,time,signal,subprocess,hashlib,traceback
R=Path(__file__).resolve().parents[1];os.environ['IHEAR_RESEARCH_ROOT']=str(R)
os.environ.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='')
sys.dont_write_bytecode=True;sys.path[:0]=[str(R/'scripts'),str(R/'analysis_tools')]
from research_common import atomic,read,sha,now,pid_identity,same_pid,HARD_STOP
signal.alarm(max(1,int(min(1200,HARD_STOP-time.time()-5))))
REQUIRED=['REPORT.md','AUTONOMOUS_RESEARCH_DECISIONS.jsonl','TRAINING_ADMISSION_AUDIT.md','STD_TRAINING_COMPARISON.md','STD_TRAINING_RESULTS.json','R1_R4_REWARD_COMPARISON.md','REWARD_VERSION_MANIFEST.json','PPO_TRAINING_RESULTS.json','CHECKPOINT_STABILITY_AUDIT.json','FROZEN_EVALUATION_RESULTS.json','HOLDOUT_EVALUATION_RESULTS.json','TASK_FORCE_MOMENT_MOTION.md','TRAINING_CURVES/training.csv','RESOURCE_USAGE.json','ATTEMPT_ACCOUNTING.json','FINAL_CAMPAIGN_READINESS.md','NEXT_RESEARCH_DECISION.md']

def main():
 started=time.time();atomic(R/'FINALIZATION_START.json',dict(time_utc=now(),identity=pid_identity(os.getpid()),source_sha256=sha(Path(__file__)),hard_stop_utc=read(R/'START.json')['hard_stop_utc']))
 services=read(R/'LAUNCHED_SERVICES.json',{}).get('services',[])
 for _ in range(60):
  if not any(same_pid(x) for x in services):break
  time.sleep(1)
 assert not any(same_pid(x) for x in services),'SERVICES_NOT_CLOSED'
 stage=read(R/'owned/PROGRESS_STAGE_REPORTER.json')
 if stage and not same_pid(stage.get('worker')) and not (R/'STAGE_REPORTER_END.json').exists():
  terminal=dict(time_utc=now(),worker=stage['worker'],owner_joined=True,closure='External confirmation after package closer TERM/KILL; no physics or optimizer owned')
  atomic(R/'STAGE_REPORTER_END.json',terminal);stage['ended']=terminal;atomic(R/'owned/PROGRESS_STAGE_REPORTER.json',stage)
 # Register and join every final analysis child. Child carries its own independent alarm too.
 with (R/'independent_full.stdout.log').open('w') as out,(R/'independent_full.stderr.log').open('w') as err:
  child=subprocess.Popen([sys.executable,str(R/'analysis_tools/independent_audit.py')],cwd=R,env=os.environ,stdout=out,stderr=err,start_new_session=True)
  identity=dict(time_utc=now(),worker=pid_identity(child.pid),supervisor=pid_identity(os.getpid()),pgid=child.pid,kind='readonly_saved_data_audit',deadline_unix=min(time.time()+1000,HARD_STOP-15))
  atomic(R/'FINAL_ANALYSIS_OWNER.json',identity)
  try:rc=child.wait(timeout=max(1,min(1010,HARD_STOP-time.time()-10)))
  except BaseException:
   if child.poll() is None:
    try:os.killpg(child.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    child.wait(timeout=5)
   raise
  finally:
   identity['ended']=dict(time_utc=now(),returncode=child.poll(),joined=child.poll() is not None);atomic(R/'FINAL_ANALYSIS_OWNER.json',identity)
 audit=read(R/'audit/INDEPENDENT_FULL_AUDIT.json',{})
 # Preserve incomplete/failing scientific evidence and still deliver every requested report.
 import paired_reward_audit
 paired_reward_audit.build()
 import diagnostics
 diagnostics.build()
 import phase_comparison
 phase_comparison.build()
 import analyze
 summary=analyze.build(live=False)
 source=read(R/'ACTIVATION.json')['script_sha256'];source_mismatch=[name for name,h in source.items() if sha(R/'scripts'/name)!=h]
 missing=[name for name in REQUIRED if not (R/name).exists()]
 ledger=read(R/'LEDGER.json',{});owned=[read(p) for p in (R/'owned').glob('*.json') if not p.name.endswith('_WATCHDOG_STOP.json')]
 owners_alive=[x for x in owned if same_pid(x.get('worker'))]
 verification=dict(time_utc=now(),required_missing=missing,independent_full_audit_pass=audit.get('pass_',False),independent_review_process_returncode=rc,source_scripts_unchanged=not source_mismatch,source_mismatches=source_mismatch,runtime_contract_unchanged=audit.get('checks',{}).get('contract_unchanged',False),parents_unchanged=not audit.get('parent_mismatches',[]),historical_handoff_2300_unchanged=not audit.get('origin_mismatches',[]),all_experiment_workers_and_services_exited=not owners_alive and not any(same_pid(x) for x in services),all_START_END_closed=audit.get('checks',{}).get('all_job_START_END',False),all_attempts_settled=all(a['settled'] for a in ledger.get('attempts',[])),finalizer_exit_pending=True,hard_deadline_met=time.time()<HARD_STOP,final_campaign_started=False,Stage2_started=False,git_mutations=False,scope='Bounded nominal development only',final_state='STOP' if not missing and not owners_alive and audit.get('pass_',False) and not source_mismatch else 'STOP_WITH_AUDIT_GAPS')
 previous_state=read(R/'RESEARCH_STATE.json',{})
 atomic(R/'RESEARCH_STATE.json',dict(status='STOP',time_utc=now(),previous_queue_state=previous_state,independent_full_audit_pass=audit.get('pass_',False),all_owned_experiment_processes_exited=not owners_alive,Stage2_started=False,final_campaign_started=False))
 handoff=R/'AUTONOMOUS_HANDOFF.md'
 if handoff.exists() and not (R/'audit/ACTIVE_SESSION_HANDOFF.md').exists():
  (R/'audit/ACTIVE_SESSION_HANDOFF.md').write_bytes(handoff.read_bytes())
 handoff.write_text('# 最终研究交接：STOP\n\n本轮有界开发研究已结束。请从REPORT.md、ANALYSIS_SUMMARY.json、PACKAGE_VERIFICATION.json读取实际结果与证据范围；旧运行中交接保存在audit/ACTIVE_SESSION_HANDOFF.md。\n\n原ACTIVATION和硬截止未重置。全部owned实验/监督服务已关闭，独立保存数据审计与归档状态以PACKAGE_VERIFICATION.json为准。所有原始失败、partial、checkpoint与源码身份均保留。\n\nG4_STRICT_PASS=FAIL；NEW_LIVE_MATCHED_READY、STAGE2_READY、FINAL_CAMPAIGN_READY=NOT_READY。禁止自动重启本包、启动下一研究包、Stage2、最终大规模Campaign或Git写入。唯一后续建议见NEXT_RESEARCH_DECISION.md，须另获授权。\n')
 finish=now();activation=read(R/'ACTIVATION.json')
 from datetime import datetime
 elapsed_total=(datetime.fromisoformat(finish)-datetime.fromisoformat(activation['activation_utc'])).total_seconds()/3600
 resource=read(R/'RESOURCE_USAGE.json');resource.update(autonomous_total_hours_through_final_analysis=elapsed_total,final_analysis_end_utc=finish);atomic(R/'RESOURCE_USAGE.json',resource)
 report=(R/'REPORT.md').read_text();report=report.replace('## 本轮结果',f'截至最终分析结束，实际自主运行 **{elapsed_total:.4f} 小时**（{finish} UTC）；物理队列与分析归档时长分别保留。\n\n## 本轮结果',1);(R/'REPORT.md').write_text(report)
 atomic(R/'FINALIZATION_END.json',dict(time_utc=finish,identity=pid_identity(os.getpid()),wall_s=time.time()-started,autonomous_total_hours=elapsed_total,analysis_summary=summary,final_state=verification['final_state'],owned_physics_processes_exited=not owners_alive,hard_deadline_met=time.time()<HARD_STOP))
 # These two files are mutually self-referential and intentionally excluded from payload coverage.
 excluded={'OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json'}
 print(json.dumps(dict(final_state=verification['final_state'],reports_missing=missing,audit_pass=audit.get('pass_'),elapsed_finalization_s=time.time()-started)),flush=True)
 files=[]
 for p in sorted(R.rglob('*')):
  if p.is_file() and str(p.relative_to(R)) not in excluded:
   files.append(dict(path=str(p.relative_to(R)),bytes=p.stat().st_size,sha256=sha(p)))
 atomic(R/'OUTPUT_MANIFEST.json',dict(time_utc=now(),files=files,excluded_self_referential_files=sorted(excluded),source_identity=read(R/'ACTIVATION.json'),scope='Exact payload coverage after services exit; transient finalizer exit checked by root'))
 verification.update(manifest_entries=len(files),manifest_sha256=sha(R/'OUTPUT_MANIFEST.json'),manifest_exact_payload_coverage=True)
 atomic(R/'PACKAGE_VERIFICATION.json',verification)
if __name__=='__main__':
 try:main()
 except BaseException as exc:
  atomic(R/'FINALIZATION_FAILURE.json',dict(time_utc=now(),error=repr(exc),traceback=traceback.format_exc(),new_physics=0))
  raise
