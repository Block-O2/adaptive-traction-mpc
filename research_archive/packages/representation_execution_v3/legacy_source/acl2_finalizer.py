"""Independent bounded closer; survives agent/SSH loss and appends journal once."""
from pathlib import Path
import os,sys,time,signal,json,hashlib,subprocess,fcntl,traceback
from acl2_shared import P,R,put,read,sha,utc,records,native_used
os.environ['GIT_OPTIONAL_LOCKS']='0'
A=read('ACTIVATION.json');deadline=A['hard_stop_unix'];pid=os.getpid()
def owned():
 out=[]
 for f in Path('/proc').glob('[0-9]*/environ'):
  try:
   if ('ACL2_OWNER='+A['identity']).encode()+b'\0' in f.read_bytes():out.append(int(f.parent.name))
  except OSError:pass
 return out
def signal_owned(sig,exclude=[]):
 for n in owned():
  if n in [pid]+exclude:continue
  try:os.kill(n,sig)
  except ProcessLookupError:pass
def close():
 lock=(P/'CLOSURE.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 put('CLOSURE_START.json',dict(utc=utc(),pid=pid,original_T0=A['T0_utc'],hard_deadline=A['hard_stop_utc']));put('STOP_REQUESTED',dict(reason='FINAL_CLOSURE_NO_NEW_COMPUTE',utc=utc()))
 watchdog=read('owned/WATCHDOG_START.json')['pid'];before=[]
 for n in owned():
  if n in [pid,watchdog]:continue
  try:
   stat=Path('/proc',str(n),'stat').read_text();tail=stat[stat.rfind(')')+2:].split();before.append(dict(pid=n,ppid=int(tail[1]),start_ticks=int(tail[19]),command=Path('/proc',str(n),'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')))
  except OSError:pass
 signal_owned(signal.SIGINT,[watchdog]);time.sleep(8);signal_owned(signal.SIGTERM,[watchdog]);time.sleep(3);signal_owned(signal.SIGKILL,[watchdog]);time.sleep(.2)
 put('audit/OWNED_PROCESS_CLOSURE.json',dict(utc=utc(),identity=A['identity'],before=before,remaining_non_closer_watchdog=[n for n in owned() if n not in [pid,watchdog]],method='Exact initial environment identity; staged SIGINT/SIGTERM/SIGKILL; unrelated processes excluded. Finalizer exits after END and watchdog exits on END.'))
 # Complete missing independent raw checks; cached checks bind raw input hashes.
 import legacy_independent_audit as ia
 starts=[r for r in records() if r['event']=='START'];audits=[]
 for r in starts:
  f=P/'audit/independent'/(r['id']+'.json')
  if f.exists():
   cached=json.loads(f.read_text())
   if cached.get('status') not in ['FAIL','INDEPENDENT_AUDIT_ERROR','NOT_AUDITED_DEADLINE']:
    audits.append(cached);continue
   put('audit/independent_revisions/'+r['id']+'_BEFORE_CLOSURE_RETRY.json',cached)
  if time.time()>deadline-300:audits.append(dict(id=r['id'],status='NOT_AUDITED_DEADLINE'));continue
  try:x=ia.audit(r['id'])
  except BaseException as e:x=dict(id=r['id'],status='INDEPENDENT_AUDIT_ERROR',error=str(e),traceback=traceback.format_exc())
  put('audit/independent/'+r['id']+'.json',x);audits.append(x)
 put('audit/INDEPENDENT_RAW_AUDIT.json',dict(status='PASS' if all(r['status']=='PASS' for r in audits) else 'REVIEW_REQUIRED_WITH_FAILURES_PRESERVED',attempt_denominator=len(starts),audited=len(audits),rows=audits,utc=utc(),method='separate complete JSON decoding, integral and native receipt/torque/motion recomputation; same agent, not independent investigator'))
 # Original scorer cache-bypassing replay and real PPO numerical ownership replay.
 import acl2_scorer_replay
 original_scorer=acl2_scorer_replay.finish_missing()
 import acl2_ppo_audit
 ppo_replay=acl2_ppo_audit.audit();put('audit/PPO_ON_POLICY_REPLAY.json',ppo_replay)
 import acl2_post_analysis
 acl2_post_analysis.main()
 import acl2_evidence_integrity
 evidence_integrity=acl2_evidence_integrity.audit(final=True)
 gp_decision_replay=read('GP_DECISION_LAYER_REPLAY.json')
 # Verify every protected historical metadata/content record and Git identity.
 changes=[];hstart=read('audit/HISTORY_START.json')
 for name,row in hstart.items():
  f=Path(name)
  if not f.exists():changes.append(dict(path=name,reason='MISSING'));continue
  st=f.stat()
  if st.st_size!=row['size'] or st.st_mtime_ns!=row['mtime_ns']:changes.append(dict(path=name,reason='METADATA_CHANGED'))
  if row.get('sha256') and sha(f)!=row['sha256']:changes.append(dict(path=name,reason='CONTENT_CHANGED'))
 G=P.parent/'rl_b_matched_recovery_stability_v1/github';git=dict(head=subprocess.check_output(['git','-C',str(G),'rev-parse','HEAD'],text=True).strip(),branch=subprocess.check_output(['git','-C',str(G),'branch','--show-current'],text=True),status=subprocess.check_output(['git','-C',str(G),'status','--porcelain=v1','--untracked-files=all'],text=True),index_sha256=sha(G/'.git/index'))
 put('audit/HISTORY_END.json',dict(utc=utc(),protected_files=len(hstart),changes=changes,Git_end=git,Git_unchanged=git==read('audit/GIT_START.json')))
 import importlib,acl2_report
 report=importlib.reload(acl2_report);report.main('STOP')
 summary=read('REPORT_SUMMARY.json');b=summary.get('best_new_modal');result='未取得可列入正式收益的新modal方案' if b is None else '最佳新增modal完整合格JF=%.6f N·s、JM=%.6f Nm·s，动作身份%s'%(b['JF'],b['JM'],b['id'])
 if not (P/'audit/JOURNAL_END_RECORDING.json').exists():
  journal=P.parent/'RESEARCH_DECISION_JOURNAL.md';before=sha(journal)
  methods=summary.get('methods',{});main_best={k:(v.get('best') or {}).get('JF') for k,v in methods.items()};ppo_mean=(summary.get('PPO_exploration') or {}).get('best_evaluated_mean_JF');response=summary.get('reference_response',{})
  text='\n\n---\n\n## %s UTC — Autonomous Coordination & Learning v2 结束\n\n状态：STOP；研究包：`%s`。本轮累计%.3f小时、物理START=%d。完成同运动族坐标核验、八方向实签参考核验与等预算A/B/C优化；PPO及冻结合法prefix只按实际结果报告。%s。A/B/C最佳JF分别为%s，PPO已评价mean最佳JF为%s。初版固定时长certificate拒绝与逐关节终点缺锁已定位并修复；粗名义代理的实签参考映射是关键缺口；另定位原clearance包络差分跨分支触发jerk冲击，原guard保持，时序干预按实际结果报告。事后重建不能冒充前瞻预测。补充参考响应模型与同数据传统成本模型的实测状态为%s。保留JF/JM/原生motion取舍及失败partial，未建立少次患者适应或一般Learning优势。下一步先在独立协议检验非光滑clearance反馈处理且不放宽原阈值，再考察因果历史对实际参考与可部署motion余量预测的额外价值。独立raw/scorer重算、历史保护审计与STOP封包见REPORT；无Git、硬件或自动下一轮。\n'%(utc(),P,(time.time()-A['t0_unix'])/3600,len(starts),result,main_best,ppo_mean,response.get('status','NOT_RUN'))
  with journal.open('a') as s:s.write(text);s.flush();os.fsync(s.fileno())
  put('audit/JOURNAL_END_RECORDING.json',dict(utc=utc(),before_sha256=before,after_sha256=sha(journal),append_only=True,text=text))
 # Rerender after journal append so STOP report states the completed lifecycle truth.
 report.main('STOP')
 verification=dict(status='PASS' if not changes and git==read('audit/GIT_START.json') and not any(x['status'] in ['FAIL','INDEPENDENT_AUDIT_ERROR','NOT_AUDITED_DEADLINE'] for x in audits) and original_scorer['status']=='PASS' and ppo_replay['status'] in ['PASS','NOT_RUN'] and evidence_integrity['status']=='PASS' and gp_decision_replay['status']=='PASS' and not read('audit/OWNED_PROCESS_CLOSURE.json')['remaining_non_closer_watchdog'] else 'REVIEW_REQUIRED',utc=utc(),original_T0=A['T0_utc'],historical_changes=changes,Git_unchanged=git==read('audit/GIT_START.json'),all_started_attempts_accounted=len(starts)==len(audits),independent_raw_status=read('audit/INDEPENDENT_RAW_AUDIT.json')['status'],original_scorer_replay=original_scorer['status'],PPO_on_policy_replay=ppo_replay['status'],evidence_input_hash_integrity=evidence_integrity['status'],GP_saved_decision_replay=gp_decision_replay['status'],owned_process_closure_sha256=sha(P/'audit/OWNED_PROCESS_CLOSURE.json'),owned_pids_before_END=owned(),source_files={str(f.relative_to(P)):sha(f) for f in (P/'source').glob('*.py')},raw_partial_are_not_ranked=True,no_automatic_next_round=True)
 put('PACKAGE_VERIFICATION.json',verification)
 put('STATUS.json',dict(status='STOP',utc=utc(),physical_START=len(starts),actual_new_native_steps=native_used(),original_T0=A['T0_utc']))
 manifest={}
 for f in P.rglob('*'):
  if not f.is_file() or f.name in ['OUTPUT_MANIFEST.json','OUTPUT_MANIFEST_VERIFY.json','END.json','WATCHDOG_END.json'] or any(x in ['logs','owned','__pycache__'] for x in f.relative_to(P).parts) or f.suffix=='.log':continue
  manifest[str(f.relative_to(P))]=dict(size=f.stat().st_size,sha256=sha(f))
 put('OUTPUT_MANIFEST.json',dict(utc=utc(),files=manifest,scope='all scientific source/config/raw/partial/report artifacts; mutable daemon logs and final END excluded to avoid self-reference'))
 mismatches=[name for name,meta in manifest.items() if not (P/name).exists() or (P/name).stat().st_size!=meta['size'] or sha(P/name)!=meta['sha256']]
 put('OUTPUT_MANIFEST_VERIFY.json',dict(utc=utc(),status='PASS' if not mismatches else 'FAIL',files_checked=len(manifest),mismatches=mismatches,scope='Frozen scientific artifacts checked after final reports and STATUS; self-reference/lifecycle exclusions explicit.'))
 put('END.json',dict(status='STOP',utc=utc(),T0_utc=A['T0_utc'],hard_stop_utc=A['hard_stop_utc'],elapsed_h=(time.time()-A['t0_unix'])/3600,physical_START=len(starts),actual_new_native_steps=native_used(),package_verification_sha256=sha(P/'PACKAGE_VERIFICATION.json'),output_manifest_sha256=sha(P/'OUTPUT_MANIFEST.json'),output_manifest_verification=read('OUTPUT_MANIFEST_VERIFY.json')['status'],physics_owned_pids_remaining=[x for x in owned() if x not in [pid,watchdog]],no_new_round=True))
def main():
 put('owned/FINALIZER_START.json',dict(pid=pid,utc=utc(),source_sha256=sha(__file__),original_T0=A['T0_utc'],close_at_unix=A['t0_unix']+9.333333*3600,hard_deadline_unix=deadline))
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('FINALIZER_HARD_DEADLINE')));signal.alarm(max(1,int(deadline-time.time()-5)))
 for _ in range(20000):
  if (P/'END.json').exists():return
  sealed=P/'VALIDATION_QUEUE_SEALED.json';scientific_done=False
  if sealed.exists():
   q=read('VALIDATION_QUEUE_SEALED.json');scientific_done=bool(q['validation_job_ids']) and all((P/'jobs'/j/'END.json').exists() for j in q['validation_job_ids']+[q['extension_job_id']])
  if scientific_done:
   put('CLOSURE_COMPLETION_REASON.json',dict(utc=utc(),reason='Finite evidence-driven pipeline complete; original and time-only extended registered validation jobs closed; no further native extension or tuning.',sealed_validation_queue_sha256=sha(sealed),no_new_round=True));break
  if time.time()>=A['t0_unix']+9.333333*3600 or (P/'CLOSE_REQUEST').exists():break
  time.sleep(2)
 try:close()
 except BaseException as e:put('CLOSURE_ERROR.json',dict(utc=utc(),error=str(e),traceback=traceback.format_exc()));raise
if __name__=='__main__':main()
