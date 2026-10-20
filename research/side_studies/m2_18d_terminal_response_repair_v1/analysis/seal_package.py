"""Final read-only history/Git audit and new-package sealing. No physics."""
from pathlib import Path
import os,json,time,hashlib,subprocess,shutil
L=Path(__file__).resolve().parents[1];S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');P=S/L.name;MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
def read(n):return json.loads((L/n).read_text())
def put(n,x):(L/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with Path(f).open('rb') as z:
  for b in iter(lambda:z.read(2**20),b''):h.update(b)
 return h.hexdigest()
def git():return {k:subprocess.check_output(['git','-C',str(MAIN),*v]).decode() for k,v in dict(head=['rev-parse','HEAD'],branch=['branch','--show-current'],status=['status','--porcelain=v1','--untracked-files=all'],staged=['diff','--cached','--binary'],unstaged=['diff','--binary']).items()}
required=['REPORT.md','N2_TERMINAL_DIAGNOSIS.md','MECHANISM_FINDINGS.md','INTERVENTION_PROTOCOL.md','EXPERIMENT_RESULTS.json','ATTEMPT_ACCOUNTING.json','VALIDATION_RESULTS.json','NEXT_RESEARCH_DECISION.md','figures/N2_terminal_timeline.png']
assert all((L/n).is_file() for n in required)
assert read('audit/FIGURE_QA.json')['status']=='PASS'
account=read('ATTEMPT_ACCOUNTING.json');assert account['physical_START']==account['physical_END']<=20
for attempt in account['attempts']:
 ident=attempt['id'];data=json.loads((P/'output'/(ident+'_DATA.json')).read_text());check=json.loads((P/'derived'/(ident+'_INDEPENDENT.json')).read_text());child=data.get('child');inherited=0 if child is None else child['physics_step_at_fork']
 if child is not None:assert inherited==round(data['branch_start']['physical_time_s']/.00025)
 assert attempt['actual_new_native_steps']==check['native_rows']-inherited==check['actual_new_native_steps']
for g in ['N2','U1']:
 for n in [g+'_OWNER.json',g+'_WORKER_EXIT.json',g+'_DONE.json',g+'_PAIR_GATE.json',g+'_PARENT_GATE.json']:
  x=json.loads((P/n).read_text())
  if n.endswith('OWNER.json'):assert x['returncode']==0 and x['joined']
  if n.endswith('WORKER_EXIT.json'):assert x.get('active_child') is None
 assert json.loads((P/'audit'/('INDEPENDENT_'+g+'.json')).read_text())['status']=='PASS'
(P/'PHYSICS_STOP.json').write_text(json.dumps(dict(unix=time.time(),reason='Finite preregistered N2 and one U1 prefix branches complete; no further START allowed'),indent=2)+'\n')
put('PHYSICS_STOP.json',json.loads((P/'PHYSICS_STOP.json').read_text()))
ps=subprocess.check_output(['ps','-eo','pid,ppid,pgid,args']).decode();active=[line for line in ps.splitlines() if str(P) in line and ('/control/campaign.py' in line or '/control/own_campaign.py' in line)]
assert not active,active
assert all(r['execution']['original_executor_closed'] for g in read('EXPERIMENT_RESULTS.json')['groups'] for r in g['rows'])
put('audit/OWNED_PROCESS_FINAL.json',dict(status='PASS',active_physics_owners=active,ps=ps,all_groups_joined=True,closed_native_executors=[dict(id=r['id'],closed=r['execution']['original_executor_closed']) for g in read('EXPERIMENT_RESULTS.json')['groups'] for r in g['rows']]))
original=read('audit/GIT_BEFORE.json');current=git();assert original==current,'GIT_LOGICAL_STATE_CHANGED'
put('audit/GIT_FINAL.json',dict(status='PASS',branch=current['branch'],head=current['head'],logical_state_equal=True,fields={k:dict(bytes=len(v.encode()),sha256=hashlib.sha256(v.encode()).hexdigest()) for k,v in current.items()},preexisting_status_entries=len(current['status'].splitlines())))
print('GIT_AND_OWNERS PASS',flush=True)
metadata=read('audit/HISTORY_METADATA_BEFORE.json');protected=read('audit/PROTECTED_SHA_BEFORE.json');errors=[]
for name,expected in metadata.items():
 f=Path(name)
 if not f.is_file():errors.append(dict(path=name,reason='MISSING'));continue
 st=f.stat()
 if [st.st_size,st.st_mtime_ns]!=expected:errors.append(dict(path=name,reason='METADATA_CHANGED'))
print('HISTORY_METADATA',len(metadata),'errors',len(errors),flush=True)
for i,(name,expected) in enumerate(protected.items()):
 if not Path(name).is_file() or sha(name)!=expected:errors.append(dict(path=name,reason='SHA_CHANGED'))
 if (i+1)%5000==0:print('PROTECTED_SHA',i+1,flush=True)
existing=set()
for root in [MAIN,S]:
 for f in root.rglob('*'):
  if P in f.parents or '.git' in f.parts or '__pycache__' in f.parts or not f.is_file() or f.is_symlink():continue
  existing.add(str(f))
extras=sorted(existing-set(metadata));assert not errors and not extras,dict(errors=errors[:50],new_files_in_old_roots=extras[:50])
manifest=json.loads((P/'EXECUTION_CODE_MANIFEST.json').read_text());bad=[n for n,h in manifest['files'].items() if not (P/n).is_file() or sha(P/n)!=h];assert not bad,bad
assert sha(P/'FROZEN_18D.json')==sha(S/'m2_18d_autonomous_review_v1/FROZEN_18D.json')
assert sha(P/'MOTION_ACCEPTANCE_PROTOCOL.json')==sha(S/'m2_18d_autonomous_review_v1/MOTION_ACCEPTANCE_PROTOCOL.json')
put('audit/FINAL_PROTECTION.json',dict(status='PASS',historical_metadata_checked=len(metadata),historical_SHA_checked=len(protected),errors=errors,new_files_in_old_roots=extras,git_equal=True,frozen_execution_files_verified=len(manifest['files']),frozen_execution_manifest_unchanged=True))
# Copy the final reports/analysis into canonical; the pre-physics execution closure stays immutable.
for d in ['derived','figures','provenance']:
 shutil.copytree(L/d,P/d,dirs_exist_ok=True)
(P/'analysis').mkdir(exist_ok=True)
for f in (L/'control').glob('*.py'):shutil.copy2(f,P/'analysis'/f.name)
for f in (L/'audit').glob('*'):
 if f.is_file():shutil.copy2(f,P/'audit'/f.name)
for f in L.glob('*'):
 if f.is_file() and f.suffix in ['.md','.json'] and f.name not in ['RUN_PLAN.json','PACKAGE_VERIFICATION.json','EVIDENCE_MANIFEST.json']:shutil.copy2(f,P/f.name)
# Physics metadata and detailed numerical checks are also available in the Windows review mirror.
for f in P.glob('*'):
 if f.is_file() and f.suffix in ['.md','.json','.jsonl'] and f.name not in ['STATE.json','PACKAGE_VERIFICATION.json','EVIDENCE_MANIFEST.json']:shutil.copy2(f,L/f.name)
for d in ['reports','audit','derived','logs']:
 shutil.copytree(P/d,L/d,dirs_exist_ok=True)
now=time.time();plan=json.loads((P/'RUN_PLAN.json').read_text());assert now<plan['hard_stop_unix']
state=read('STATE.json');state.update(phase='STOPPED_COMPLETED',closed_unix=now,next_action='STOP; no automatic next campaign');put('STATE.json',state);shutil.copy2(L/'STATE.json',P/'STATE.json')
verification=dict(status='PASS',meaning='Delivery/integrity audit, scientific qualification separately in VALIDATION_RESULTS.json',closed_unix=now,elapsed_minutes=(now-plan['t0_unix'])/60,hard_limit_hours=4,hard_deadline_met=True,no_new_start_last45min_of_budget=all(a['START']['unix']<plan['no_new_physics_after_unix'] for a in account['attempts']),required_files=required+['PACKAGE_VERIFICATION.json'],required_files_present=True,physics_START=account['physical_START'],physics_END=account['physical_END'],actual_new_native_steps=account['actual_new_native_steps'],no_partials=True,all_owned_physical_processes_exited=True,active_owned_processes=active,git_logical_state_equal=True,historical_metadata_checked=len(metadata),historical_SHA_checked=len(protected),new_files_in_old_roots=extras,frozen_execution_manifest_verified=True,frozen_parameters_and_motion_protocol_unchanged=True,figure_visual_QA=read('audit/FIGURE_QA.json'),same_Human=True,new_prefix_pairs=1,new_prefix_qualified=read('VALIDATION_RESULTS.json')['new_prefix_T_qualified'],no_commit_push_merge=True,no_RL_Q_training=True,canonical=str(P),review=str(L),disk_free_bytes=shutil.disk_usage(P).free,scientific_status=read('VALIDATION_RESULTS.json')['scientific_status'])
put('PACKAGE_VERIFICATION.json',verification);shutil.copy2(L/'PACKAGE_VERIFICATION.json',P/'PACKAGE_VERIFICATION.json')
manifest_out={str(f.relative_to(P)):dict(size=f.stat().st_size,sha256=sha(f)) for f in P.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.name not in ['EVIDENCE_MANIFEST.json','REVIEW_MIRROR_MANIFEST.json']}
(P/'EVIDENCE_MANIFEST.json').write_text(json.dumps(dict(status='PASS',files=manifest_out,scope='Canonical full source/raw/report package; manifest excludes itself and mirror index'),indent=2)+'\n');shutil.copy2(P/'EVIDENCE_MANIFEST.json',L/'EVIDENCE_MANIFEST.json')
mirror={str(f.relative_to(L)):dict(size=f.stat().st_size,sha256=sha(f)) for f in L.rglob('*') if f.is_file() and f.name!='REVIEW_MIRROR_MANIFEST.json'}
put('REVIEW_MIRROR_MANIFEST.json',dict(status='PASS',files=mirror,full_raw_and_execution_closure_at=str(P),scope='Review reports/derived/receipt reports and analysis; control here includes latest offline analysis; immutable executed control/code/source are canonical and separately manifested'))
for n in required+['PACKAGE_VERIFICATION.json','STATE.json']:
 assert sha(L/n)==sha(P/n),(n,'MIRROR_REPORT_MISMATCH')
print('PACKAGE PASS',json.dumps({k:verification[k] for k in ['elapsed_minutes','physics_START','actual_new_native_steps','historical_SHA_checked','scientific_status']}),flush=True)
