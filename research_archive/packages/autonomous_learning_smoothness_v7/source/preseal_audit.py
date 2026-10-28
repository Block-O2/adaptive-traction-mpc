"""Read-only protection and frozen-job audit. No qualification relaxation."""
from pathlib import Path
import os,json,hashlib,subprocess,time
P=Path(__file__).resolve().parents[1];start=time.time()
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as z:
  for b in iter(lambda:z.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def put(n,d):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(d,indent=2)+'\n')
before=json.loads((P/'audit/PROTECTED_METADATA_BEFORE.json').read_text());changes=[]
for name,expected in before.items():
 f=Path(name)
 if not f.exists():changes.append(dict(path=name,reason='MISSING'));continue
 s=f.stat()
 if [s.st_size,s.st_mtime_ns]!=expected:changes.append(dict(path=name,reason='SIZE_OR_MTIME',before=expected,after=[s.st_size,s.st_mtime_ns]))
new=[]
for root in P.parent.iterdir():
 if root.is_dir() and root!=P:
  for f in root.rglob('*'):
   if f.is_file() and str(f) not in before:new.append(str(f))
put('audit/PROTECTED_METADATA_AFTER.json',dict(status='PASS' if not changes and not new else 'FAIL',files=len(before),changes=changes,new_historical_files=new))
initial=json.loads((P/'audit/INITIAL_SOURCE_SHA256.json').read_text());sourcechanges=[]
for rel,expected in initial.items():
 f=P/rel
 if not f.exists() or sha(f)!=expected:sourcechanges.append(rel)
allowed=['source/write_main_report.py'];unexpected=[f for f in sourcechanges if f not in allowed];put('audit/ISOLATED_COPY_CHANGE_AUDIT.json',dict(status='PASS' if not unexpected else 'FAIL',initial_files=len(initial),changes=sourcechanges,allowed_isolated_report_generator_changes=allowed,unexpected=unexpected,original_runtime_controller_and_scorer_files_unchanged=not any(f.startswith('runtime/') for f in sourcechanges)))
jobs=[]
for m in sorted((P/'jobs').glob('*/SOURCE_MANIFEST.json')):
 d=json.loads(m.read_text());bad=[r for r,h in d['files'].items() if not (P/r).is_file() or sha(P/r)!=h];group=m.parent.name;config=P/'experiments'/(group+'.json');cfgpass=sha(config)==d['config_sha256'];done=json.loads((m.parent/'WORKER_DONE.json').read_text());jobs.append(dict(group=group,files=len(d['files']),changed=bad,config_sha_matches=cfgpass,all_children_joined=done.get('all_children_joined'),all_parent_checks_unchanged=all(x['unchanged'] for x in done.get('parent_checks',[])),status='PASS' if not bad and cfgpass and done.get('all_children_joined') and all(x['unchanged'] for x in done.get('parent_checks',[])) else 'FAIL'))
put('audit/ALL_JOB_SOURCE_AND_PARENT_AUDIT.json',dict(status='PASS' if len(jobs)==5 and all(j['status']=='PASS' for j in jobs) else 'FAIL',jobs=jobs))
git=P.parent/'rl_b_matched_recovery_stability_v1/github';env=dict(os.environ,GIT_OPTIONAL_LOCKS='0');head=subprocess.check_output(['git','-C',str(git),'rev-parse','HEAD'],text=True,env=env).strip();status=subprocess.check_output(['git','-C',str(git),'status','--porcelain=v1','--untracked-files=no'],text=True,env=env);old=json.loads((P/'audit/GIT_BEFORE.json').read_text());put('audit/GIT_AFTER.json',dict(status='PASS' if head==old['HEAD']=='1adb1de177d6f5f32de6d01c4e629cbfae9ce121' and not status else 'FAIL',HEAD=head,tracked_status=status))
# Runtime implementation versions are byte-frozen against the actual cloud copy.
guardrel=Path('runtime/source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/clearance_feedback.py');origin=P.parent/'representation_execution_v3'/guardrel;put('audit/GUARD_IDENTITY.json',dict(status='PASS' if sha(P/guardrel)==sha(origin) else 'FAIL',new_copy_sha256=sha(P/guardrel),protected_origin_sha256=sha(origin),replacement_applied=False))
journal=(P.parent/'RESEARCH_DECISION_JOURNAL.md').read_bytes();oldj=json.loads((P/'audit/JOURNAL_BEFORE.json').read_text());jp=hashlib.sha256(journal[:oldj['size']]).hexdigest()==oldj['sha256'];put('audit/JOURNAL_PREFIX_AUDIT.json',dict(status='PASS' if jp else 'FAIL',original_prefix_size=oldj['size'],original_prefix_sha256=oldj['sha256'],current_size=len(journal)))
# Workers, supervisors and finite scientific queues must already have exited.
needles=['/source/v4_worker.py','/source/v4_factor_worker.py','/source/v4_validation_worker.py','/source/supervise.py','/source/supervise_v2.py','/source/finite_followups.py','/source/finite_factor_followup.py','/legacy_source/acl2_scorer_replay.py'];live=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace');stat=(proc/'stat').read_text();state=stat[stat.rindex(')')+2:].split()[0]
  if state!='Z' and str(P) in cmd and any(str(P)+n in cmd for n in needles):live.append(dict(pid=int(proc.name),cmd=cmd))
 except (FileNotFoundError,ProcessLookupError,PermissionError):pass
put('audit/OWNED_RESEARCH_PROCESS_FINAL.json',dict(status='PASS' if not live else 'FAIL',live_owned_research_processes=live,packaging_process_not_a_scientific_job=True))
checks=['audit/PROTECTED_METADATA_AFTER.json','audit/ISOLATED_COPY_CHANGE_AUDIT.json','audit/ALL_JOB_SOURCE_AND_PARENT_AUDIT.json','audit/GIT_AFTER.json','audit/GUARD_IDENTITY.json','audit/JOURNAL_PREFIX_AUDIT.json','audit/OWNED_RESEARCH_PROCESS_FINAL.json','audit/PROTECTED_MANIFEST_REVERIFICATION.json'];bad=[n for n in checks if json.loads((P/n).read_text())['status']!='PASS'];put('audit/PRESEAL_AUDIT.json',dict(status='PASS' if not bad else 'FAIL',failed_checks=bad,wall_s=time.time()-start));print('PRESEAL',bad,'metadata_changes',len(changes),'new_historical',len(new),'source_changes',sourcechanges);assert not bad,'PRESEAL_AUDIT_FAILED'
