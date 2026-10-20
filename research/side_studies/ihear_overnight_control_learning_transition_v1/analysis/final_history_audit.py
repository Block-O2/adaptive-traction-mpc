"""Read every protected historical byte again; no Git mutation or physics."""
from pathlib import Path
import os,sys,json,time,hashlib,subprocess,traceback
R=Path(__file__).resolve().parents[1]
SIDE=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning');P=SIDE/R.name
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(f):
    h=hashlib.sha256()
    with f.open('rb') as stream:
        for block in iter(lambda:stream.read(4*2**20),b''):h.update(block)
    return h.hexdigest()
def git():
    env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
    return {n:subprocess.check_output(['git','-C',str(MAIN),*a],env=env).decode() for n,a in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('cached',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]}
started=time.time();put('audit/HISTORY_AUDIT_OWNER.json',dict(pid=os.getpid(),start=started))
try:
    assert (P/'PHYSICS_CLOSED.json').exists(),'MUST_CLOSE_PHYSICS_FIRST'
    before=json.loads((P/'audit/HISTORY_BEFORE.json').read_text());after={};changes=[]
    for root in [MAIN,SIDE]:
        for f in sorted(root.rglob('*')):
            if not f.is_file() or f.is_relative_to(P) or '.git' in f.parts:continue
            st=f.stat();row=dict(size=st.st_size,mtime_ns=st.st_mtime_ns,sha256=sha(f));after[str(f)]=row
            if before.get(str(f))!=row:changes.append(dict(path=str(f),before=before.get(str(f)),after=row))
            if len(after)%10000==0:print('HISTORY_REHASHED',len(after),flush=True)
    missing=sorted(set(before)-set(after));put('audit/HISTORY_AFTER.json',after)
    g0=json.loads((P/'audit/GIT_BEFORE.json').read_text());g1=git();put('audit/GIT_AFTER.json',g1)
    result=dict(status='PASS' if not changes and not missing and g0==g1 else 'FAIL',before_files=len(before),after_files=len(after),bytes_rehashed=sum(r['size'] for r in after.values()),changes=changes,missing=missing,git_logical_state_unchanged=g0==g1,git_changed_fields=[k for k in g0 if g0[k]!=g1[k]],started_unix=started,finished_unix=time.time(),wall_seconds=time.time()-started)
    put('audit/HISTORY_PROTECTION_FINAL.json',result)
    print('HISTORY_FINAL',result['status'],len(after),'FILES',flush=True)
    assert result['status']=='PASS'
except BaseException as e:
    put('audit/HISTORY_AUDIT_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),unix=time.time()));raise
finally:put('audit/HISTORY_AUDIT_EXIT.json',dict(pid=os.getpid(),unix=time.time()))
