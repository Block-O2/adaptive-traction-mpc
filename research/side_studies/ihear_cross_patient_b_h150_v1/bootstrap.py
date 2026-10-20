"""Isolate a frozen B/H150 cross-patient study. No physics or historical writes."""
from pathlib import Path
import os, sys, json, time, hashlib, subprocess, shutil, datetime
sys.dont_write_bytecode=True
REVIEW=Path(__file__).resolve().parent
SIDE=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
OLD=SIDE/'ihear_overnight_control_learning_transition_v1'
P=SIDE/REVIEW.name
T0=datetime.datetime.fromisoformat('2026-10-19T05:41:00+00:00').timestamp()
def sha(f):
    h=hashlib.sha256()
    with Path(f).open('rb') as stream:
        for block in iter(lambda:stream.read(4*2**20),b''):h.update(block)
    return h.hexdigest()
def put(n,x):
    p=P/n;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def git_snapshot():
    env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
    result={n:subprocess.check_output(['git','-C',str(MAIN),*args],env=env).decode() for n,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('cached',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]}
    result['index_sha256']=sha(MAIN/'.git/index')
    return result
assert not P.exists(),'Never overwrite an existing canonical package'
P.mkdir()
for d in ['audit','analysis','control','logs','reports','derived','figures','output','motion_series','tmp','provenance','patients','learning']:(P/d).mkdir()
put('RUN_PLAN.json',dict(t0_unix=T0,t0='2026-10-19T13:41:00+08:00',hard_stop_unix=T0+28800,dispatch_cutoff_unix=T0+26100,no_new_physics_after_unix=T0+26100,physics_hard_stop_unix=T0+26100,physical_timeout_s=900,physics_budget=80,all_physics_serial=True,no_training=True,no_parameter_search=True,no_auto_resume=True,early_finish_when_conclusive=True))
put('ENVIRONMENT.json',dict(canonical=str(P),review=str(REVIEW),python=sys.executable,historical_source=str(OLD),distribution=os.environ.get('WSL_DISTRO_NAME'),created_unix=time.time()))
put('audit/GIT_BEFORE.json',git_snapshot())
shutil.copy2(MAIN/'AGENTS.md',P/'provenance/AGENTS.md')
shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/4c926678-4a3f-4bee-ac5a-131d6191389f/已粘贴的文本.txt',P/'provenance/USER_REQUEST.txt')
print('HASHING_PROTECTED_HISTORY',flush=True)
protected={};started=time.time()
for root in [MAIN,SIDE]:
    for f in sorted(root.rglob('*')):
        if not f.is_file() or f.is_relative_to(P) or '.git' in f.parts:continue
        st=f.stat();protected[str(f)]=dict(size=st.st_size,mtime_ns=st.st_mtime_ns,sha256=sha(f))
put('audit/HISTORY_BEFORE.json',protected)
print('HISTORY',len(protected),'bytes',sum(x['size'] for x in protected.values()),'seconds',time.time()-started,flush=True)
checks=[]
for name in ['ihear_overnight_control_learning_transition_v1','ihear_model_terminal_compensation_v1','ihear_autonomous_multitrack_v1']:
    root=SIDE/name
    for mn in ['EXECUTION_CODE_MANIFEST.json','EVIDENCE_MANIFEST.json']:
        obj=json.loads((root/mn).read_text());errors=[]
        for rel,entry in obj['files'].items():
            f=Path(rel) if Path(rel).is_absolute() else root/rel
            expected=entry if isinstance(entry,str) else entry['sha256']
            if protected.get(str(f),{}).get('sha256')!=expected:errors.append(str(f))
        checks.append(dict(study=name,manifest=mn,files=len(obj['files']),errors=errors,sha256=sha(root/mn)))
put('audit/HISTORICAL_MANIFESTS_VERIFIED.json',checks)
# A later manifest can legitimately supersede an old one; report each rather than alter history.
for d in ['source','code','deps','control']:
    shutil.copytree(OLD/d,P/d,dirs_exist_ok=True,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
rebased=[]
for d in ['source','code','deps','control']:
    for f in (P/d).rglob('*'):
        if f.is_file() and f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml']:
            try:s=f.read_text()
            except UnicodeError:continue
            if str(OLD) in s:
                before=sha(f);f.write_text(s.replace(str(OLD),str(P)))
                rebased.append(dict(path=str(f.relative_to(P)),before=before,after=sha(f)))
for n in ['FROZEN_18D.json','PARAMETER_MAP.json','MOTION_ACCEPTANCE_PROTOCOL.json','FROZEN_SELECTION.json','ACTION_SET.json']:
    shutil.copy2(OLD/n,P/n)
shutil.copy2(OLD/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
for n in ['D01R_PLAN.json','D01R_RESULTS.json','FROZEN_CONTROL_BASELINE.md','PACKAGE_VERIFICATION.json','EXECUTION_CODE_MANIFEST_v3.json']:
    if (OLD/n).exists():shutil.copy2(OLD/n,P/'provenance'/('HISTORICAL__'+n))
shutil.copy2(REVIEW/'bootstrap.py',P/'bootstrap.py')
put('audit/PATH_REBASE.json',dict(path_only=rebased,source=str(OLD)))
put('BOOTSTRAP_DONE.json',dict(status='PASS',unix=time.time(),protected_files=len(protected),protected_bytes=sum(x['size'] for x in protected.values())))
put('STATE.json',dict(phase='MODEL_AUDIT_AND_PREREGISTRATION',physics_starts=0,next='Freeze cohort and validate patient-only generation; no physics before gates'))
for n in ['ENVIRONMENT.json','RUN_PLAN.json','STATE.json','BOOTSTRAP_DONE.json']:shutil.copy2(P/n,REVIEW/n)
print('BOOTSTRAP_PASS',flush=True)
