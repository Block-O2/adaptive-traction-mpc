from pathlib import Path
import os,json,hashlib,time,subprocess,ast,shutil,collections
P=Path(__file__).resolve().parents[1];D=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/adaptive_continuous_coordination_interface_v1')
def load(n):return json.loads((P/n).read_text())
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False))
required=['REPORT.md','INTERFACE_FAILURE_ROOT_CAUSE.md','SELECTED_INTERFACE_DESIGN.md','MULTISEGMENT_REFERENCE_CONTRACT.md','PATH_CERTIFICATION_REPORT.md','CERTIFICATION_TEST_RESULTS.json','MATH_VALIDATION.json','PHYSICAL_INTERFACE_GATE.json','PHYSICAL_VALIDATION.json','CODE_MANIFEST.json','ATTEMPTS.jsonl','REPRODUCTION.md','NEXT_RESEARCH_DECISION.md']
assert all((P/n).is_file() and (P/n).stat().st_size>0 for n in required);assert len(list((P/'figures').glob('0*.png')))==5
for f in list((P/'control').glob('*.py'))+list((P/'tests').glob('*.py')):ast.parse(f.read_text())
ledger=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()];counter=collections.Counter(x['event'] for x in ledger);assert counter['START']==counter['END']==counter['AUDIT']==counter['IDENTITY_AUDIT']==10
assert load('STATE.json')['phase']=='STOP' and load('PHYSICAL_VALIDATION.json')['status']=='PASS' and load('audit/FINAL_PROTECTION_AND_EXIT.json')['status']=='PASS'
# Verify both historical execution manifests against their preserved versions.
checks=[]
for group in ['interface1','interface2']:
 manifest=P/'versions'/group/'EXECUTION_CODE_MANIFEST.json';m=json.loads(manifest.read_text());bad=[]
 for row in m['files']:
  f=P/'versions'/group/row['path']
  if not f.is_file():f=P/row['path']
  if sha(f)!=row['sha256']:bad.append(row['path'])
 assert not bad,(group,bad)
 checks.append(dict(group=group,status='PASS',files=len(m['files']),manifest_sha256=sha(manifest)))
# Source changes remain the exact two allowed files plus one new module.
cm=load('CODE_MANIFEST.json');changed=[r['path'] for r in cm['copied_files'] if sha(P/r['path'])!=r['sha256']];assert sorted(changed)==sorted(r['path'] for r in cm['changed_after_copy'])
# Every key trace link resolves to this package.
for f in (P/'key_traces').rglob('*'):
 if f.is_symlink():assert f.resolve().is_relative_to(P) and f.exists()
# No owned physical process can be live after joined owners.
live=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit() or proc.name==str(os.getpid()):continue
 try:cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
 except OSError:continue
 if str(P) in cmd and any(x in cmd for x in ['physical_runner.py','own_physics.py']):live.append(dict(pid=proc.name,cmd=cmd))
assert not live
put('audit/FINAL_DELIVERY_CHECK.json',dict(status='PASS',unix=time.time(),required_files=required,ledger_counts=dict(counter),owned_physical_processes_live=live,execution_manifest_verification=checks,copied_source_files=len(cm['copied_files']),only_two_original_source_files_changed=changed,new_reference_module_sha256=cm['new_reference_module_sha256'],all_five_figures_exist=True,all_key_trace_links_local=True,no_new_physics_after_completion=True))
# Freeze the all-file closure; cache/runtime scratch explicitly excluded.
rows=[]
for f in sorted(P.rglob('*')):
 rel=str(f.relative_to(P))
 if rel in ['PACKAGE_MANIFEST.json','STORAGE.json'] or rel.startswith('tmp/') or '__pycache__' in rel or f.suffix=='.pyc':continue
 if f.is_symlink():rows.append(dict(path=rel,kind='symlink',target=os.readlink(f),sha256=hashlib.sha256(os.readlink(f).encode()).hexdigest()))
 elif f.is_file():rows.append(dict(path=rel,kind='file',bytes=f.stat().st_size,sha256=sha(f)))
put('PACKAGE_MANIFEST.json',dict(frozen_unix=time.time(),status='FROZEN_STOP',files=rows,exclusions=['PACKAGE_MANIFEST.json (self)','STORAGE.json (post-freeze size measurement)','tmp/','__pycache__/','*.pyc'],no_production_changes=True))
for r in rows:
 f=P/r['path'];actual=hashlib.sha256(os.readlink(f).encode()).hexdigest() if r['kind']=='symlink' else sha(f);assert actual==r['sha256']
apparent=int(subprocess.check_output(['du','-sb',str(P)]).split()[0]);disk=int(subprocess.check_output(['du','-s','-B1',str(P)]).split()[0]);put('STORAGE.json',dict(measured_unix=time.time(),apparent_bytes_before_writing_this_measurement=apparent,allocated_disk_bytes_before_writing_this_measurement=disk,manifest_files=len(rows),scope='entire authoritative WSL package, no dereference of internal key_trace symlinks; final manifest verified',cache_in_size=True))
# Refresh only our known review copy after final changes.
for f in P.iterdir():
 if f.is_file() and f.suffix in ['.md','.json','.jsonl']:shutil.copy2(f,D/f.name)
for folder in ['figures','control']:
 for f in (P/folder).iterdir():
  if f.is_file():shutil.copy2(f,D/folder/f.name)
for n in ['FINAL_DELIVERY_CHECK.json','ALL_ATTEMPT_PLAN_IDENTITIES.json','UTILITY_DIAGNOSTICS.json']:shutil.copy2(P/'audit'/n,D/'audit'/n)
review=sum(f.stat().st_size for f in D.rglob('*') if f.is_file())
print(json.dumps(dict(status='FINAL_FROZEN_STOP',START=10,END=10,owned_live=0,package=str(P),apparent_bytes=int(subprocess.check_output(['du','-sb',str(P)]).split()[0]),disk_bytes=int(subprocess.check_output(['du','-s','-B1',str(P)]).split()[0]),manifest_entries=len(rows),package_manifest_sha256=sha(P/'PACKAGE_MANIFEST.json'),review_bytes=review,execution_manifests=checks)),flush=True)
