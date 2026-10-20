"""Read-only protection and owned-exit verification; writes only this package."""
from pathlib import Path
import os,sys,json,hashlib,subprocess,time,collections
P=Path(__file__).resolve().parents[1];M=Path('/home/hank/coding/adaptive-traction-mpc-learning');S=P.parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=M)
def load(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2))
before=load('audit/MAIN_BEFORE.json');errors=[]
now=dict(head=git('rev-parse','HEAD').decode().strip(),branch=git('branch','--show-current').decode().strip(),index_sha256=sha((M/'.git/index').read_bytes()),staged_diff_sha256=sha(git('diff','--cached','--binary')),unstaged_diff_sha256=sha(git('diff','--binary')))
for key in now:
 if now[key]!=before[key]:errors.append('MAIN:'+key)
paths=git('ls-files','-z','--cached','--others','--exclude-standard').decode().split('\0');paths=sorted(set(x for x in paths if x));assert set(paths)=={r['path'] for r in before['files']},'MAIN_FILE_SET_CHANGED'
for row in before['files']:
 f=M/row['path'];raw=os.readlink(f).encode() if row['kind']=='symlink' else f.read_bytes()
 if sha(raw)!=row['sha256']:errors.append('MAIN_FILE:'+row['path'])
status=git('status','--porcelain=v1','-uall');(P/'audit/git_status_after.txt').write_bytes(status)
if status!=(P/'audit/git_status_before.txt').read_bytes():errors.append('MAIN:STATUS')
prev=load('audit/PREVIOUS_PACKAGE_BEFORE.json')['files'];prev_root=S/'adaptive_continuous_coordination_overnight_v1'
if {str(f) for f in prev_root.rglob('*') if f.is_file()}!={r['path'] for r in prev}:errors.append('PREVIOUS:FILE_SET')
for row in prev:
 if sha(Path(row['path']).read_bytes())!=row['sha256']:errors.append('PREVIOUS:'+row['path'])
side=load('audit/SIDE_STUDIES_METADATA_BEFORE.json')['files'];current={}
for f in S.rglob('*'):
 if P in f.parents:continue
 if f.is_file():
  st=f.stat();current[str(f)]=(st.st_size,st.st_mtime_ns)
if set(current)!={r['path'] for r in side}:errors.append('SIDE:FILE_SET')
for r in side:
 if current.get(r['path'])!=(r['size'],r['mtime_ns']):errors.append('SIDE:'+r['path'])
owners=[load(str(f.relative_to(P))) for f in (P/'control').glob('OWNER_*.json')];live=[]
for proc in Path('/proc').iterdir():
 if proc.name.isdigit():
  try:cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  except (OSError,PermissionError):continue
  if str(P) in cmd and proc.name!=str(os.getpid()) and any(x in cmd for x in ['physical_runner.py','own_physics.py']):live.append(dict(pid=int(proc.name),command=cmd))
assert not live and all(x.get('joined') and x.get('returncode')==0 for x in owners),'OWNED_PHYSICAL_PROCESS_NOT_JOINED'
result=dict(status='PASS' if not errors else 'FAIL',unix=time.time(),main=now,main_files_sha256_verified=len(before['files']),main_status_exact=True,previous_package_sha256_verified=len(prev),all_existing_side_studies_metadata_verified=len(side),side_scope='all existing names/size/mtime; previous package additionally full SHA256',errors=errors,owned_processes_live=live,owners=owners)
put('audit/FINAL_PROTECTION_AND_EXIT.json',result);assert not errors,errors[:10]
print('PROTECTION_EXIT_PASS',len(before['files']),len(prev),len(side),flush=True)
