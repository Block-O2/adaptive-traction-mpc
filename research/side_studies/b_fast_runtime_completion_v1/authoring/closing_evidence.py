"""One lightweight final evidence reconciliation; no models/plant/native steps."""
from pathlib import Path
import collections, difflib, hashlib, json, os, shutil, subprocess, time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
OLD=S.parent/'b_multirate_realtime_v1';ROOT=Path('/home/hank/coding/adaptive-traction-mpc-learning')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def save(n,obj):
    p=S/n;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(obj,indent=2)+'\n');t.replace(p)
def main():
    ledger=json.loads((S/'TASK_LEDGER.json').read_text());assert not any(v['status']=='RUNNING' for v in ledger.values())
    events=[json.loads(l) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines() if l.strip()]
    starts=[x for x in events if x['event']=='START'];ends=[x for x in events if x['event']=='END']
    sc=collections.Counter(x['id'] for x in starts);ec=collections.Counter(x['id'] for x in ends)
    assert all(v==1 for v in sc.values()) and set(sc)==set(ledger), 'START/ledger mismatch'
    missing_ends=sorted(set(sc)-set(ec));assert not missing_ends
    totals={k:sum(v.get('compute',{}).get(k,0) for v in ledger.values() if isinstance(v.get('compute',{}).get(k), (int,float))) for k in ('native_physics_steps','simulation_seconds','main_model_inverse_dynamics_api_calls','native_worker_model_inverse_dynamics_api_calls')}
    offline=[json.loads(l) for l in (S/'OFFLINE_LEDGER.jsonl').read_text().splitlines() if l.strip()]
    incomplete={k:[n for n in totals if not isinstance((v.get('compute') or {}).get(n),(int,float))] for k,v in ledger.items()}
    incomplete={k:v for k,v in incomplete.items() if v}
    save('reports/FINAL_COMPUTE_ACCOUNT.json',dict(unix=time.time(),physics_attempts=len(starts),unique_START=len(sc),unique_END=len(ec),missing_END=missing_ends,totals_recorded_lower_bound=totals,offline_ledger=offline,offline_API_calls_recorded=sum(x.get('model_API_calls',0) for x in offline if x['event']=='END'),counter_fields_not_recorded=incomplete,unledgered_direct_controller_API_lower_bound=456,scope='Actual receipt steps when available; early commissioning, startup/import API counts incompletely measured. No claimed exact total model calls. Native formulas are not inverse-dynamics API calls.',worker_status= dict(collections.Counter(v.get('worker_status') for v in ledger.values()))))
    protected=json.loads((S/'preservation/HISTORICAL_KEY_BEFORE.json').read_text());checks={p:dict(before=h,after=sha(Path(p))) for p,h in protected.items()}
    assert all(v['before']==v['after'] for v in checks.values())
    before=json.loads((S/'GIT_BEFORE.json').read_text())
    def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'),text=True)
    after=dict(branch=git('branch','--show-current'),HEAD=git('rev-parse','HEAD'),status=git('status','--porcelain=v1'),index_sha256=sha(ROOT/'.git/index'),staged_diff=git('diff','--cached','--binary'))
    save('preservation/FINAL_PRESERVATION.json',dict(status='PASS' if before==after else 'FAIL',git_fields_equal={k:before[k]==after[k] for k in before},historical_key_hashes=checks,no_full_historical_raw_scan=True))
    assert before==after,'Protected Git changed'
    copied=[]
    for p in W.iterdir():
        if p.is_file() and p.suffix in ('.py','.cpp','.json','.ps1'):
            out=S/'authoring'/p.name;out.parent.mkdir(exist_ok=True);shutil.copy2(p,out);copied.append(str(out.relative_to(S)))
    shutil.copy2(W/'reproduce.py',S/'code/reproduce.py')
    shutil.copy2(W/'fast_dispatch.py',S/'code/fast_dispatch.py')
    shutil.copy2(W/'cohort_dispatch.py',S/'code/cohort_dispatch.py')
    diffs=[];stats=[]
    for top in ('code','source','deps'):
        for p in sorted((S/top).rglob('*')):
            if not p.is_file() or 'results' in p.parts or '__pycache__' in p.parts or p.suffix not in ('.py','.cpp','.json'):continue
            rel=p.relative_to(S);old=OLD/rel
            if old.is_file():
                a=old.read_text();b=p.read_text()
                if a==b:continue
                diffs.extend(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='R3/'+str(rel),tofile='FAST/'+str(rel)))
                stats.append(dict(path=str(rel),kind='modified',before_sha256=sha(old),after_sha256=sha(p)))
            else:stats.append(dict(path=str(rel),kind='added',after_sha256=sha(p)))
    (S/'reports/R3_TO_FAST.patch').write_text(''.join(diffs));save('reports/R3_TO_FAST_CHANGES.json',dict(modified_or_added=stats,added_implementation='Added files are retained in code/ and authoring/; patch covers changes to existing R3 files.',relocation='Study paths relocated; preserved source comparison includes these explicit path changes.'))
    files={}
    for top in ('code','native','build','authoring'):
        for p in sorted((S/top).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and 'temp' not in p.parts:files[str(p.relative_to(S))]=sha(p)
    save('FINAL_CODE_MANIFEST.json',dict(unix=time.time(),files=files,compiler='GCC -O3 -fno-fast-math -ffp-contract=off; one CPython/NumPy C API backend'))
    size=sum(p.stat().st_size for p in S.rglob('*') if p.is_file() and not p.is_symlink())
    save('reports/FINAL_DATA_ACCOUNT.json',dict(unix=time.time(),regular_file_bytes=size,GiB=size/2**30,target_bytes=10*2**30,old_raw_library_not_copied=True,all_owned_children_joined=True))
    print('CLOSING_EVIDENCE_PASS',len(starts),totals,'bytes',size,'code_files',len(files))
if __name__=='__main__':main()
