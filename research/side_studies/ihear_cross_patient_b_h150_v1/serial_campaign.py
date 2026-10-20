"""Single serial subprocess owner; no detached continuation or automatic resume."""
from pathlib import Path
import os,sys,json,time,signal,subprocess,fcntl,traceback,shutil
P=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
def read(n):return json.loads((P/n).read_text())
def put(n,x):
    f=P/n;f.parent.mkdir(parents=True,exist_ok=True);tmp=f.with_suffix(f.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n');tmp.replace(f)
def sync_small():
    target=Path(read('ENVIRONMENT.json')['review'])
    for f in P.glob('*.json'):shutil.copy2(f,target/f.name)
    for d in ['reports','derived','audit','learning','patients']:
        for f in (P/d).rglob('*.json'):
            if f.stat().st_size>20*2**20:continue
            dest=target/f.relative_to(P);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
def main():
    lock=(P/'SERIAL_OWNER.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert not (P/'SERIAL_CAMPAIGN_DONE.json').exists(),'NO_AUTO_RESUME'
    assert read('PREPHYSICAL_CHECKS.json')['status']=='PASS'
    plan=read('RUN_PLAN.json');cohort=read('VIRTUAL_PATIENT_COHORT.json');static={r['patient_id']:r for r in read('STATIC_PATIENT_AUDIT.json')['records']}
    allowed=sys.argv[1:] or cohort['order']
    rows=[]
    for pid in allowed:
        assert pid in cohort['order']
        if not static[pid]['model_static_valid']:
            rows.append(dict(patient_id=pid,status='MODEL_NOT_ADMISSIBLE',subtype='STATIC_MODEL_OR_ASSEMBLY',evidence='patients/'+pid+'/static/MODEL_STATIC_AUDIT.json'));continue
        if time.time()>=plan['dispatch_cutoff_unix']-3*plan['physical_timeout_s']:
            rows.append(dict(patient_id=pid,status='NOT_RUN_BUDGET'));continue
        assert not (P/(pid+'_DONE.json')).exists(),'NO_REPEAT_IDENTITIES'
        command=[sys.executable,'-B',str(P/'cross_runner.py'),pid]
        rec=dict(patient_id=pid,command=command,start_unix=time.time())
        with (P/'logs'/(pid+'.log')).open('x') as out:
            child=subprocess.Popen(command,cwd=P,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
            rec.update(pid=child.pid,owner_pid=os.getpid());put('OWNED_ACTIVE_PROCESS.json',rec)
            print('PATIENT_START',pid,child.pid,flush=True)
            try:rc=child.wait(timeout=max(1,min(3600,plan['physics_hard_stop_unix']-time.time())))
            except BaseException:
                os.kill(child.pid,signal.SIGALRM)
                try:child.wait(timeout=45)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=15)
                raise
            finally:
                rec.update(end_unix=time.time(),returncode=child.returncode,joined=child.poll() is not None)
                put('audit/'+pid+'_OWNER.json',rec);put('OWNED_ACTIVE_PROCESS.json',dict(status='IDLE',pid=None,owner_pid=os.getpid(),unix=time.time()))
        rows.append(dict(patient_id=pid,returncode=rc,status=read(pid+'_DONE.json')['status'] if (P/(pid+'_DONE.json')).exists() else 'FAILED_BEFORE_RESULT'))
        put('CAMPAIGN_PROGRESS.json',dict(rows=rows,updated_unix=time.time()))
        print('PATIENT_END',pid,rc,flush=True)
        sync_small()
        if pid=='P00':
            # Reference is a deterministic package/runner regression, never a new patient.
            env=dict(os.environ,STUDY_GROUP='P00',STUDY_MODE='cross_patient')
            check=subprocess.run([sys.executable,'-B',str(P/'verify_reference.py')],cwd=P,env=env,capture_output=True,text=True)
            (P/'logs/verify_reference.log').write_text(check.stdout+check.stderr)
            if check.returncode:
                put('PHYSICS_STOP.json',dict(reason='REFERENCE_REPRODUCTION_GATE_FAILED',unix=time.time(),returncode=check.returncode));sync_small();raise RuntimeError('REFERENCE_REPRODUCTION_GATE_FAILED')
    put('SERIAL_CAMPAIGN_DONE.json',dict(status='COMPLETE_REGISTERED_DISPATCH',rows=rows,unix=time.time(),owned_children_joined=True))
    sync_small()
if __name__=='__main__':main()
