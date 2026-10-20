"""Final integrity/ownership audit and readable mirror, no physics."""
from pathlib import Path
import os,json,time,hashlib,subprocess,shutil,gzip
L=Path(__file__).resolve().parents[1];S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');P=S/L.name;M=Path('/home/hank/coding/adaptive-traction-mpc-learning');A=S/'m2_18d_terminal_response_repair_v1'
os.environ['GIT_OPTIONAL_LOCKS']='0'
def read(n):return json.loads((P/n).read_text())
def sha(f):
 h=hashlib.sha256()
 with Path(f).open('rb') as z:
  for b in iter(lambda:z.read(2**20),b''):h.update(b)
 return h.hexdigest()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
req=['REPORT.md','T_EXECUTION_CONTRACT_AUDIT.md','VALIDATION_RESULTS.json','ATTEMPT_ACCOUNTING.json','MOTION_FAILURE_DIAGNOSIS.md','NEXT_RESEARCH_DECISION.md','EXPERIMENT_RESULTS.json','INTERVENTION_PROTOCOL.md']
assert all((P/n).is_file() for n in req)
figure_qa=read('audit/FIGURE_QA.json');assert figure_qa['status']=='PASS' and figure_qa['image_sha256']==sha(P/'figures/expanded_native_motion.png')
acct=read('ATTEMPT_ACCOUNTING.json');plan=read('RUN_PLAN.json');results=read('EXPERIMENT_RESULTS.json');assert acct['physical_START']==acct['physical_END']<=30
for a in acct['attempts']:
 assert a['returncode']==0 and not a['partial'];ident=a['id'];data=read('output/'+ident+'_DATA.json');ind=read('derived/'+ident+'_INDEPENDENT.json');inherited=0 if data.get('child') is None else data['child']['physics_step_at_fork'];assert ind['native_rows']-inherited==ind['actual_new_native_steps']==a['actual_new_native_steps'];assert ind['status']=='PASS'
 assert a['START']['unix']<plan['no_new_physics_after_unix']
 assert a['START']['code_manifest_sha256']==sha(P/'EXECUTION_CODE_MANIFEST.json') and a['START']['plan_sha256']==sha(P/'RUN_PLAN.json')
for g in results['groups']:
 name=g['group'];owner=read(name+'_OWNER.json');assert owner['returncode']==0 and owner['joined'];assert read(name+'_WORKER_EXIT.json')['active_child'] is None;assert read(name+'_DONE.json')['all_children_joined']
 assert read(name+'_PAIR_GATE.json')['status']=='PASS' and read(name+'_PARENT_GATE.json')['status']=='PASS'
 assert all(r['execution']['original_executor_closed'] for r in g['rows'])
 with gzip.open(P/'source/results'/(name+'_parent')/'runtime_artifacts.json.gz','rt') as f:raw=json.load(f)
 assert raw['executor_closed'];del raw
put('PHYSICS_STOP.json',dict(unix=time.time(),reason='Two preregistered new prefixes complete; finite evidence sufficient for this round; no further physics START'))
active=[];snapshot=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:args=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
 except OSError:continue
 if str(P) in args and ('/control/campaign.py' in args or '/control/own_campaign.py' in args):active.append(dict(pid=int(proc.name),args=args))
 if str(P) in args:snapshot.append(dict(pid=int(proc.name),args=args))
assert not active,active
put('audit/OWNED_PROCESS_FINAL.json',dict(status='PASS',active_physics_owners=active,all_children_joined=True,all_original_native_executors_closed=True,process_snapshot=snapshot))
git={k:subprocess.check_output(['git','-C',str(M),*v]).decode() for k,v in dict(head=['rev-parse','HEAD'],branch=['branch','--show-current'],status=['status','--porcelain=v1','--untracked-files=all'],staged=['diff','--cached','--binary'],unstaged=['diff','--binary']).items()};assert git==read('audit/GIT_BEFORE.json'),'GIT_CHANGED'
put('audit/GIT_FINAL.json',dict(status='PASS',branch=git['branch'],head=git['head'],logical_state_equal=True,preexisting_status_entries=len(git['status'].splitlines()),fields={k:dict(bytes=len(v.encode()),sha256=hashlib.sha256(v.encode()).hexdigest()) for k,v in git.items()}))
print('GIT_OWNERS_ACCOUNT PASS',flush=True)
meta=read('audit/HISTORY_METADATA_BEFORE.json');protected=read('audit/PROTECTED_SHA_BEFORE.json');errors=[]
for f,expected in meta.items():
 p=Path(f)
 if not p.is_file():errors.append(dict(path=f,reason='MISSING'));continue
 st=p.stat()
 if [st.st_size,st.st_mtime_ns]!=expected:errors.append(dict(path=f,reason='METADATA_CHANGED'))
print('METADATA_CHECKED',len(meta),'errors',len(errors),flush=True)
for i,(f,expected) in enumerate(protected.items()):
 if not Path(f).is_file() or sha(f)!=expected:errors.append(dict(path=f,reason='SHA_CHANGED'))
 if (i+1)%25000==0:print('SHA_CHECKED',i+1,flush=True)
nowfiles=set()
for root in [M,S]:
 for f in root.rglob('*'):
  if P in f.parents or '.git' in f.parts or '__pycache__' in f.parts or not f.is_file() or f.is_symlink():continue
  nowfiles.add(str(f))
extra=sorted(nowfiles-set(meta));assert not errors and not extra,dict(errors=errors[:30],extra=extra[:30])
manifest=read('EXECUTION_CODE_MANIFEST.json');bad=[n for n,h in manifest['files'].items() if not (P/n).is_file() or sha(P/n)!=h];assert not bad,bad
assert sha(P/'FROZEN_18D.json')==sha(A/'FROZEN_18D.json') and sha(P/'MOTION_ACCEPTANCE_PROTOCOL.json')==sha(A/'MOTION_ACCEPTANCE_PROTOCOL.json') and sha(P/'code/terminal_repair.py')==sha(A/'code/terminal_repair.py')
oldmirror=L.parent/'m2_18d_terminal_response_repair_v1';oldm=json.loads((oldmirror/'REVIEW_MIRROR_MANIFEST.json').read_text());oldbad=[n for n,h in oldm['files'].items() if not (oldmirror/n).is_file() or sha(oldmirror/n)!=h['sha256']];assert not oldbad,oldbad
put('audit/FINAL_PROTECTION.json',dict(status='PASS',historical_metadata_checked=len(meta),historical_SHA_checked=len(protected),historical_Windows_mirror_files_checked=len(oldm['files']),errors=errors,new_files_in_old_roots=extra,git_equal=True,frozen_execution_files_verified=len(manifest['files']),T_source_byte_identity=True,frozen_parameters_and_motion_protocol_byte_identity=True))
now=time.time();assert now<plan['hard_stop_unix'];state=read('STATE.json');state.update(phase='STOPPED_COMPLETED',closed_unix=now,owned_pids=[],next_action='STOP; no automatic next campaign');put('STATE.json',state)
report=(P/'REPORT.md').read_text();report+='\n最终保护核验：PASS。旧历史metadata '+str(len(meta))+' 项、SHA '+str(len(protected))+' 项及上一轮Windows镜像 '+str(len(oldm['files']))+' 项全部未变；主仓库Git逻辑状态完全一致，全部owned物理进程退出、native executors关闭，START/END闭合。最终耗时 '+f'{(now-plan["t0_unix"])/60:.2f}'+' 分钟。\n';(P/'REPORT.md').write_text(report)
verification=dict(status='PASS',meaning='Package/integrity verification; scientific qualifications separately in VALIDATION_RESULTS.json',scientific_status=read('VALIDATION_RESULTS.json')['scientific_status'],closed_unix=now,elapsed_minutes=(now-plan['t0_unix'])/60,hard_limit_hours=4,hard_deadline_met=True,no_new_start_last45min_of_budget=True,physics_START=acct['physical_START'],physics_END=acct['physical_END'],actual_new_native_steps=acct['actual_new_native_steps'],no_partials=True,all_owned_physical_processes_exited=True,all_native_executors_closed=True,active_owned_processes=active,git_logical_state_equal=True,starting_branch=git['branch'].strip(),starting_HEAD=git['head'].strip(),historical_metadata_checked=len(meta),historical_SHA_checked=len(protected),historical_Windows_mirror_files_checked=len(oldm['files']),new_files_in_old_roots=extra,frozen_execution_manifest_verified=True,T_source_byte_identity_previous=True,frozen_parameters_and_motion_protocol_unchanged=True,no_commit_push_merge_reset_stash_clean=True,no_branch_switch=True,no_RL_Q_training=True,required_files=req+['PACKAGE_VERIFICATION.json'],required_files_present=True,new_prefix_conditions=2,repeats_excluded=True,canonical=str(P),review=str(L),disk_free_bytes=shutil.disk_usage(P).free)
verification['figure_visual_QA']=figure_qa
put('PACKAGE_VERIFICATION.json',verification)
# Analysis scripts remain separate from frozen execution closure.
for f in (L/'control').glob('*.py'):shutil.copy2(f,P/'analysis'/('author_'+f.name))
# Mirror all readable scientific outputs, not bulk native raw/source.
for n in ['reports','audit','derived','logs','figures']:
 if (P/n).is_dir():shutil.copytree(P/n,L/n,dirs_exist_ok=True)
for f in P.iterdir():
 if f.is_file() and f.suffix in ['.md','.json','.jsonl']:shutil.copy2(f,L/f.name)
entries={str(f.relative_to(P)):dict(size=f.stat().st_size,sha256=sha(f)) for f in P.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.name not in ['EVIDENCE_MANIFEST.json','REVIEW_MIRROR_MANIFEST.json']}
put('EVIDENCE_MANIFEST.json',dict(status='PASS',files=entries,scope='Canonical full source/raw/report package; excludes manifest and mirror index'));shutil.copy2(P/'EVIDENCE_MANIFEST.json',L/'EVIDENCE_MANIFEST.json')
mirror={str(f.relative_to(L)):dict(size=f.stat().st_size,sha256=sha(f)) for f in L.rglob('*') if f.is_file() and f.name!='REVIEW_MIRROR_MANIFEST.json'}
(L/'REVIEW_MIRROR_MANIFEST.json').write_text(json.dumps(dict(status='PASS',files=mirror,full_raw_and_execution_closure_at=str(P),scope='Readable reports, independent calculations, receipts, audits and authoring scripts; full frozen execution closure/native raw at canonical path'),indent=2,ensure_ascii=False)+'\n')
assert all(sha(P/n)==sha(L/n) for n in req+['PACKAGE_VERIFICATION.json','STATE.json'])
print('SEALED',json.dumps({k:verification[k] for k in ['elapsed_minutes','physics_START','actual_new_native_steps','historical_SHA_checked','scientific_status']}),flush=True)
