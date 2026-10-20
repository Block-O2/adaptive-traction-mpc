"""Read-only validation/review, or dispatch a prospectively registered unused ID.

Never resets the original clock or repeats an already started physical run.
"""
from pathlib import Path
import argparse, json, os, subprocess, sys, time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_runtime_qualification_decoupling_v1')
PY=Path('/home/hank/envs/adaptive-online-rl-v1/bin/python')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--review');ap.add_argument('--dispatch');a=ap.parse_args()
    assert sum((a.check,bool(a.review),bool(a.dispatch)))==1,'Choose exactly one operation'
    plan=json.loads((S/'RUN_PLAN.json').read_text());ledger=json.loads((S/'TASK_LEDGER.json').read_text())
    assert plan['t0_unix']==1791352438 and plan['hard_stop_unix']==1791388438
    assert plan['no_training'] and not plan['G'] and plan['physical_dt_s']==.00025
    active=[k for k,v in ledger.items() if v['status']=='RUNNING']
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    if a.check:
        required=['code/run_one.py','code/fast_dispatch.py','versions/RUNTIME_FUNCTIONAL_CHECKS.json','native/fast_native.cpp','preservation/HISTORICAL_KEY_BEFORE.json']
        assert all((S/n).is_file() for n in required)
        manifest=S/'FINAL_CODE_MANIFEST.json'
        if manifest.exists():
            import hashlib
            for n,h in json.loads(manifest.read_text())['files'].items():
                assert hashlib.sha256((S/n).read_bytes()).hexdigest()==h,n
        print(json.dumps(dict(status='PASS',entry=str(S/'code/run_one.py'),original_t0=plan['t0_unix'],started=len(ledger),active=active,heavy_dispatch_open=time.time()<plan['dispatch_cutoff_unix'] and not (S/'PACKAGE_CLOSED.json').exists(),Q='FROZEN_NOT_ENABLED',repetition='new plant per episode; never persistent physical session')))
    elif a.review:
        assert a.review in ledger and ledger[a.review]['status']!='RUNNING'
        cfg=json.loads((S/'queue'/(a.review+'.json')).read_text())
        entry='scientific_gate.py' if cfg['execution_mode']=='SCIENTIFIC_SIMULATION' else 'host_review.py'
        args=[str(PY),str(S/'code'/entry),a.review]
        if entry=='scientific_gate.py':args.append('deviation' if cfg.get('prefix') else 'nominal')
        subprocess.run(args,env=env,check=True)
    else:
        assert not (S/'PACKAGE_CLOSED.json').exists(),'PACKAGE_CLOSED: use read-only check/review; no implicit new t0'
        p=Path(a.dispatch).resolve();assert p.parent==(S/'queue').resolve() and p.is_file()
        cfg=json.loads(p.read_text());assert cfg['id'] not in ledger,'Already started: never replay a physical ID'
        assert not active and time.time()<plan['dispatch_cutoff_unix'],'Original dispatch window closed or owner active'
        assert len(ledger)<plan['physics_budget'] and cfg.get('method','B') not in ('M2','M2Q')
        subprocess.run([str(PY),str(S/'code/fast_dispatch.py'),str(p)],env=env,check=True)
if __name__=='__main__':main()
