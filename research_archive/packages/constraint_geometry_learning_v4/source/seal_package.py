"""Finite closeout: verify evidence, append one authorized end note, seal and STOP."""
from pathlib import Path
import os,sys,json,hashlib,time,datetime,subprocess
P=Path(__file__).resolve().parents[1];ROOT=P.parent
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
def read(n):return json.loads((P/n).read_text())
def put(n,d):(P/n).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def utc():return datetime.datetime.now(datetime.timezone.utc)
a=read('START.json');now=utc();assert now.timestamp()<a['hard_stop_unix'],'HARD_DEADLINE'
account=read('analysis/RESOURCE_ACCOUNTING.json');assert account['status']=='PASS' and account['physical_START']==20 and account['physical_END']==20 and not account['incomplete_ids']
scorer=read('audit/UNCHANGED_SCORER_REPLAY.json');assert scorer['status']=='PASS' and scorer['audited']==20
receipt=read('audit/ALL_RECEIPT_NATIVE_IDENTITY.json');assert receipt['status']=='PASS' and len(receipt['rows'])==20
for n in ['audit/PRIOR_MANIFEST_REVERIFIED.json','audit/JOB_SOURCE_MANIFEST_VERIFY.json','audit/COPY_CHANGE_ALLOWLIST_VERIFY.json','audit/FULL18D_ADAPTER_RAW_GATE.json','analysis/SCHEDULER_DIRECT_REPLAY.json']:assert read(n)['status']=='PASS',n
for g in ['P1','MATCH','P2']:
 d=read('jobs/'+g+'/WORKER_DONE.json');assert d['all_children_joined'] and all(c['unchanged'] and c['child_exitcode']==0 for c in d['parent_checks'])
 e=read('owned/'+g+'_EXIT.json');assert e['active_child'] is None
pairs=read('analysis/P2_PAIRED_RESULTS.json');assert len(pairs['pairs'])==6
for x in pairs['pairs']:
 assert x['same_parent'] and x['identical_native_before_RETURN'] and not x['duration_changed_decisions'] and x['request_shift_max_s']==0 and not x['activation_changed_decisions']
 assert not any(z['modal_status_changed'] for z in x['reference_changes'])
# Historical trees are never a write destination. Check the preserved initial metadata snapshot.
before=read('audit/HISTORY_BEFORE.json');changes=[]
for path,m in before.items():
 f=Path(path)
 if not f.exists():changes.append({'file':path,'reason':'MISSING'});continue
 s=f.stat()
 if s.st_size!=m['size'] or s.st_mtime_ns!=m['mtime_ns']:changes.append({'file':path,'reason':'METADATA_CHANGED'})
assert not changes,changes[:5]
put('audit/HISTORY_AFTER.json',{'status':'PASS','files_checked':len(before),'changes':changes,'scope':'Previous v2 and learning-guided package metadata; v2 full scientific manifest9215 content hashes independently checked earlier. Other historical directories were never write destinations.'})
git=ROOT/'rl_b_matched_recovery_stability_v1/github';env=dict(os.environ,GIT_OPTIONAL_LOCKS='0');head=subprocess.check_output(['git','-C',str(git),'rev-parse','HEAD'],env=env,text=True).strip();status=subprocess.check_output(['git','-C',str(git),'status','--porcelain=v1','--untracked-files=no'],env=env,text=True);assert head=='1adb1de177d6f5f32de6d01c4e629cbfae9ce121' and not status
put('audit/GIT_FINAL_READONLY.json',{'HEAD':head,'tracked_status':status,'no_git_mutations_performed':True})
# Inspect process command lines and package environment without exposing unrelated variables.
anc=set();pid=os.getpid()
while pid>0 and pid not in anc:
 anc.add(pid)
 try:pid=int(Path('/proc',str(pid),'stat').read_text().split(') ',1)[1].split()[1])
 except (FileNotFoundError,ProcessLookupError,PermissionError):break
live=[]
for d in Path('/proc').iterdir():
 if not d.name.isdigit() or int(d.name) in anc:continue
 try:
  cmd=(d/'cmdline').read_bytes();environ=(d/'environ').read_bytes();hit=str(P).encode() in cmd or ('ACL2_PACKAGE='+str(P)).encode()+b'\0' in environ
  if hit:live.append({'pid':int(d.name),'command':cmd.replace(b'\0',b' ').decode(errors='replace')})
 except (PermissionError,FileNotFoundError,ProcessLookupError):continue
assert not live,live
put('audit/FINAL_PROCESS_AUDIT.json',{'utc':now.isoformat(),'status':'PASS','live_research_processes':live,'all_physical_children_joined':True,'exclusions':'This finite verifier and its tool-shell ancestors only; package command lines and exact ACL2_PACKAGE environment scanned.','autonomous_services_started':False,'next_round_started':False})
# Append exactly one short end note; preserve the complete pre-round prefix.
journal=ROOT/'RESEARCH_DECISION_JOURNAL.md';old=read('audit/JOURNAL_BEFORE.json');jbytes=journal.read_bytes();assert hashlib.sha256(jbytes[:old['size']]).hexdigest()==old['sha256']
end_receipt=P/'audit/JOURNAL_END_RECEIPT.json'
if not end_receipt.exists():
 body='本轮完成完整旧18D恢复、零物理构造核验及20次有界物理任务。新表示在逐关节终点锁和时长编译上确有旧合同无法逐参考复现的能力，但旧18D加固定H150已得到JF1398.137075的合格近似，仅距新最佳0.102459N·s，JM较高，性能及搜索效率优势仍未建立。C19微参数配对在时长和请求不变时改变差分跨分支、实际扭矩与Human运动，三个motion失败完整保留；guard物理中介受支持但未做单独替换。原scorer和receipt全量重算通过，旧包与规则保持。下一步先对齐编译权限、推导端点分支保护，再决定Learning；本轮STOP，无自动下一轮。'
 entry='\n\n---\n\n## '+now.isoformat()+' UTC — Representation & Execution v3 结束\n\n'+body+'\n'
 with journal.open('a') as f:f.write(entry)
 put('audit/JOURNAL_END_RECEIPT.json',{'utc':now.isoformat(),'before_append_size':len(jbytes),'entry_sha256':hashlib.sha256(entry.encode()).hexdigest(),'entry_characters':len(body),'original_prefix_preserved':True})
else:
 e=read('audit/JOURNAL_END_RECEIPT.json');assert hashlib.sha256(journal.read_bytes()[e['before_append_size']:]).hexdigest()==e['entry_sha256']
with (P/'RESEARCH_DECISIONS.jsonl').open('a') as f:f.write(json.dumps({'utc':now.isoformat(),'decision':'FINAL_STOP','physical_starts':20,'native_steps':account['actual_new_native_steps'],'original_scorer_replays':'20/20 PASS','receipt_native_audits':'20/20 PASS','expected_motion_failures':account['expected_motion_failure_ids'],'P1B':'NOT_RUN','guard_replacement':'NOT_TESTED','future_actions_started':False},ensure_ascii=False)+'\n')
end=utc();elapsed=end.timestamp()-datetime.datetime.fromisoformat(a['T0_UTC']).timestamp();put('END.json',{'status':'STOP','T0_UTC':a['T0_UTC'],'end_UTC':end.isoformat(),'end_Asia_Shanghai':end.astimezone(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'deadline_UTC':a['deadline_UTC'],'elapsed_seconds':elapsed,'elapsed_hours':elapsed/3600,'physical_START':20,'physical_END':20,'actual_new_native_steps':account['actual_new_native_steps'],'new_physics_closed':True,'all_processes_stopped':True,'next_round_started':False})
put('STATUS.json',{'status':'STOP','utc':end.isoformat(),'next_action':'NONE'})
source={}
for base in [P/'source',P/'runtime']:
 for f in base.rglob('*'):
  if f.is_file() and f.suffix in ['.py','.xml','.so'] and 'results' not in f.parts and '__pycache__' not in f.parts:source[str(f.relative_to(P))]=sha(f)
put('audit/CURRENT_SOURCE_IDENTITY.json',{'status':'FROZEN','files':source})
required=['REPORT.md','OLD18D_EXPRESSIVITY.md','REPRESENTATION_EFFICIENCY.md','CLEARANCE_NONSMOOTHNESS.md','PHYSICAL_COMPARISON.md','RESEARCH_DECISIONS.jsonl','PACKAGE_VERIFICATION.json','NEXT_RESEARCH_DECISION.md']
assert all((P/n).exists() and (P/n).stat().st_size>0 for n in required if n!='PACKAGE_VERIFICATION.json')
# All raw/failures/source/logs are retained. Exclude only circular seals, caches and zero-content locks.
excluded={'OUTPUT_MANIFEST.json','OUTPUT_MANIFEST_VERIFY.json','PACKAGE_VERIFICATION.json'};files={}
for f in sorted(P.rglob('*')):
 if not f.is_file():continue
 rel=str(f.relative_to(P))
 if rel in excluded or '__pycache__' in f.parts or rel.startswith('runtime/tmp/') or f.suffix=='.lock':continue
 files[rel]={'size':f.stat().st_size,'sha256':sha(f)}
put('OUTPUT_MANIFEST.json',{'utc':end.isoformat(),'files':files,'scope':'All actual raw, complete/failed engineering logs, source versions, reports and evidence. Circular seals, runtime/tmp caches, __pycache__ and lock files excluded explicitly.'})
verify={'status':'PASS_WITH_EXPECTED_MOTION_FAILURES','verification_pass':True,'state':'STOP','elapsed_seconds':elapsed,'deadline_met':end.timestamp()<a['hard_stop_unix'],'required_deliverables':required,'physical_START':20,'physical_END':20,'actual_new_native_steps':account['actual_new_native_steps'],'all_started_accounted':True,'incomplete_physical_attempts':[],'expected_motion_failures':account['expected_motion_failure_ids'],'original_scorer_replay':'20/20 PASS','receipt_native_identity':'20/20 PASS','frozen_job_source_and_config':'3/3 PASS;1370 files per job','prior_manifest_hash_reverification':'9215 files;0 changes','prior_metadata_check':{'files':len(before),'changes':[]},'copy_changes_allowlist':'1424 checked;191 exact root relocations and budget RUN_PLAN only;0 unexpected','git_HEAD':head,'git_tracked_clean':True,'journal_start_and_end_appended':True,'journal_original_prefix_preserved':True,'process_audit':'PASS;no live research process','P1_expressivity':'CONFIRMED at matched-request target/signed-reference level; global physical performance not proven','old18d_near_performance':'SUPPORTED;full18D plus fixedH150 JF1398.137074559 JM108.434998743','P1_optimizer_efficiency':'NOT_RUN','P2_computation_and_total_intervention':'CONFIRMED','P2_unique_physical_mediation':'SUPPORTED, not guard-only physical intervention','guard_replacement':'NOT_TESTED; no qualification or promotion','engineering_errors_preserved':['initial offline internal-vs-registered endpoint basis','NumPy scalar/array JSON serialization in two analysis exports'],'next_round_started':False,'manifest_file_count':len(files),'manifest_sha256':sha(P/'OUTPUT_MANIFEST.json')};put('PACKAGE_VERIFICATION.json',verify)
print(json.dumps({'status':verify['status'],'state':'STOP','elapsed_hours':elapsed/3600,'end_Asia_Shanghai':read('END.json')['end_Asia_Shanghai'],'manifest_files':len(files),'history_changes':len(changes),'live_processes':len(live)},ensure_ascii=False))
