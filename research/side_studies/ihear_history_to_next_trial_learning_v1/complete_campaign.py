"""Serial continuation of the preregistered remaining campaign; no extra searches."""
from pathlib import Path
import json,time,subprocess,sys,os
P=Path(__file__).resolve().parent
def read(n):return json.loads((P/n).read_text())
def run(*args):
    print('OFFLINE_OR_OWNED_COMMAND',args,flush=True)
    subprocess.run([sys.executable,'-B',str(P/args[0]),*args[1:]],cwd=P,check=True)
def main():
    assert not (P/'P08_DONE.json').exists() and not (P/'models/METHOD_FREEZE.json').exists()
    print('WAITING_FOR_OWNED_P05_EXIT',flush=True)
    while not (P/'audit/P05_development_OWNER_EXIT.json').exists():
        assert time.time()<read('RUN_PLAN.json')['dispatch_cutoff_unix']-900
        time.sleep(5)
    assert read('audit/P05_development_OWNER_EXIT.json')['returncode']==0
    assert read('OWNED_ACTIVE_PROCESS.json')['active'] is False
    assert read('P05_DONE.json')['all_children_joined']
    run('analyze_study.py','--independent')
    run('owned_run.py','P08','development')
    assert read('P08_DONE.json')['all_children_joined']
    run('analyze_study.py','--independent')
    run('train_models.py')
    print('METHODS_FROZEN_BEFORE_VALIDATION',json.dumps(read('models/TRAINING_RESULTS.json')),flush=True)
    for group,mode in [('V12','validation'),('U14','heldout'),('U15','heldout'),('U16','heldout')]:
        assert read('OWNED_ACTIVE_PROCESS.json')['active'] is False
        run('owned_run.py',group,mode)
        assert read(group+'_DONE.json')['all_children_joined']
        run('analyze_study.py','--independent')
        rr=read(group+'_RESULTS.json')
        print('PATIENT_CLOSED',group,json.dumps([dict(method=r['method'],JF=r['J_F_N_s'],qualified=r['complete_qualified'],action=r['decision']['action']) for r in rr['rows']]),flush=True)
    (P/'PHYSICS_STOP.json').write_text(json.dumps(dict(status='STOP',unix=time.time(),reason='Preregistered campaign complete; no new physics authorized in this package'))+'\n')
    print('CAMPAIGN_PHYSICS_CLOSED',flush=True)
if __name__=='__main__':main()
