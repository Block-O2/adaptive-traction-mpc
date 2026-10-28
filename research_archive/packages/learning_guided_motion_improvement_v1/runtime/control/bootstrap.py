"""Create a new isolated campaign; historical evidence is never an output."""
from pathlib import Path
import os, sys, json, time, hashlib, subprocess, shutil, datetime
sys.dont_write_bytecode = True
R = Path(__file__).resolve().parents[1]
SIDE = Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
MAIN = Path('/home/hank/ihear-lab/learning_guided_motion_improvement_v1/runtime/source')
A = SIDE/'ihear_model_terminal_compensation_v1'
P = SIDE/R.name
assert not P.exists(), 'Never overwrite an existing study'
P.mkdir()
for d in ['audit','analysis','control','logs','reports','derived','figures','output','motion_series','tmp','provenance','models','learning']:
    (P/d).mkdir()
def put(n,x): (P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(f):
    h=hashlib.sha256()
    with f.open('rb') as src:
        for b in iter(lambda:src.read(4*2**20),b''): h.update(b)
    return h.hexdigest()
def git():
    env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
    return {n:subprocess.check_output(['git','-C',str(MAIN),*args],env=env).decode() for n,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('cached',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]}
t0=datetime.datetime.fromisoformat('2026-10-19T01:57:00+08:00').timestamp()
put('RUN_PLAN.json',dict(t0='2026-10-19T01:57:00+08:00',t0_unix=t0,hard_stop_unix=t0+36000,no_new_physics_after_unix=t0+32400,dispatch_cutoff_unix=t0+32400,physics_hard_stop_unix=t0+32400,physical_timeout_s=900,physics_budget=100,development_cap=76,all_physics_serial=True,p2_episode_cap=24,p2_native_step_cap=2400000,p2_wall_cap_s=3600,training_cpu_threads=1,early_finish_when_conclusive=True))
put('ENVIRONMENT.json',dict(canonical=str(P),review=str(R),python=sys.executable,historical_source=str(A),created_unix=time.time(),distribution=os.environ.get('WSL_DISTRO_NAME')))
put('STATE.json',dict(phase='PROVENANCE_AND_HISTORY_PROTECTION',physics_starts=0,next='Freeze small legal action set and grouped parent-state experiment; Stage C before T0+4h'))
put('audit/GIT_BEFORE.json',git())
shutil.copy2(MAIN/'AGENTS.md',P/'provenance/AGENTS.md')
shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/a8cbc450-f2d5-433b-8dd8-35dc2323de96/已粘贴的文本.txt',P/'provenance/USER_REQUEST.txt')
shutil.copy2(R/'control/bootstrap.py',P/'control/bootstrap.py')
print('HASHING_ALL_PROTECTED_HISTORY',flush=True)
protected={};beg=time.time()
for root in [MAIN,SIDE]:
    for f in sorted(root.rglob('*')):
        if not f.is_file() or f.is_relative_to(P) or '.git' in f.parts: continue
        st=f.stat();protected[str(f)]=dict(size=st.st_size,mtime_ns=st.st_mtime_ns,sha256=sha(f))
put('audit/HISTORY_BEFORE.json',protected)
print('PROTECTED',len(protected),'SECONDS',time.time()-beg,flush=True)
checks=[]
for name in ['ihear_model_terminal_compensation_v1','ihear_autonomous_multitrack_v1','m2_18d_w1_d_qualification_v1','m2_18d_t_second_round_coordination_v1','m2_18d_terminal_expanded_prefix_validation_v1']:
    root=SIDE/name
    for mn in ['EXECUTION_CODE_MANIFEST.json','EVIDENCE_MANIFEST.json']:
        obj=json.loads((root/mn).read_text());errors=[]
        for rel,entry in obj['files'].items():
            f=Path(rel) if Path(rel).is_absolute() else root/rel
            expected=entry if isinstance(entry,str) else entry['sha256']
            actual=protected.get(str(f),{}).get('sha256')
            if actual!=expected: errors.append(str(f))
        checks.append(dict(study=name,manifest=mn,count=len(obj['files']),errors=errors,sha256=sha(root/mn)))
put('audit/HISTORICAL_MANIFESTS_VERIFIED.json',checks)
assert not any(x['errors'] for x in checks), 'Historical manifest mismatch'
for d in ['source','code','deps','weights']:
    shutil.copytree(A/d,P/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
for n in ['base_campaign.py','round_planner.py','interface_base.py','independent_recompute.py','early_return_planner.py','terminal_planner.py','terminal_control_v2.py']:
    shutil.copy2(A/'control'/n,P/'control'/n)
rebased=[]
for d in ['source','code','deps','weights','control']:
    for f in (P/d).rglob('*'):
        if f.is_file() and f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml'] and f.name!='bootstrap.py':
            try: s=f.read_text()
            except UnicodeError: continue
            if str(A) in s: f.write_text(s.replace(str(A),str(P)));rebased.append(str(f.relative_to(P)))
for n in ['FROZEN_18D.json','PARAMETER_MAP.json','MOTION_ACCEPTANCE_PROTOCOL.json','FROZEN_SELECTION.json','SELECTION_RULE.json']:
    shutil.copy2(A/n,P/n)
shutil.copy2(A/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
for n in ['Ctrl_PLAN.json','W2_PLAN.json','NEW_FROZEN_SELECTION.json','REPEAT_VERIFICATION.json','VALIDATION_RESULTS.json','REPORT.md','PACKAGE_VERIFICATION.json']:
    shutil.copy2(A/n,P/'provenance'/('H150__'+n))
put('audit/PATH_REBASE.json',dict(path_only=rebased,source=str(A)))
put('BOOTSTRAP_DONE.json',dict(status='PASS',unix=time.time(),protected_files=len(protected),protected_bytes=sum(x['size'] for x in protected.values())))
for n in ['ENVIRONMENT.json','RUN_PLAN.json','STATE.json','BOOTSTRAP_DONE.json']:
    shutil.copy2(P/n,R/n)
print('BOOTSTRAP_PASS',flush=True)
