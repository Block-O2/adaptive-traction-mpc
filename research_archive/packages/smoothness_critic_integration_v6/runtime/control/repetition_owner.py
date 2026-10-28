from pathlib import Path
import subprocess,os,sys,time,json,signal,fcntl
P=Path(__file__).resolve().parents[1]
lock=(P/'OWNER.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (P/'REPETITION_OWNER.json').exists()
plan=json.loads((P/'RUN_PLAN.json').read_text());cmd=[sys.executable,'-B',str(P/'control/repetition_runner.py')]
with (P/'logs/REPETITION.log').open('x') as out:
    child=subprocess.Popen(cmd,cwd=P,env=dict(os.environ,STUDY_GROUP='REP',STUDY_MODE='repetition',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'),stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
    rec=dict(pid=os.getpid(),child_pid=child.pid,command=cmd,start=time.time())
    (P/'REPETITION_OWNER_ACTIVE.json').write_text(json.dumps(rec)+'\n')
    try:rc=child.wait(timeout=max(1,min(1800,plan['physics_hard_stop_unix']-time.time())))
    except BaseException:
        os.kill(child.pid,signal.SIGALRM)
        try:child.wait(timeout=45)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=15)
        raise
    finally:
        rec.update(end=time.time(),returncode=child.returncode,joined=child.poll() is not None)
        (P/'REPETITION_OWNER.json').write_text(json.dumps(rec,indent=2)+'\n')
print(json.dumps(rec),flush=True)
raise SystemExit(rc)
