"""Run one serial study worker with an exclusive, retained log and explicit ownership."""
from pathlib import Path
import os,sys,json,time,subprocess,signal
P=Path(__file__).resolve().parent
patient=sys.argv[1];mode=sys.argv[2] if len(sys.argv)>2 else 'development'
ident=patient+'_'+mode
log=P/'logs'/(ident+'.log');owner=P/'audit'/(ident+'_OWNER.json')
assert not log.exists() and not owner.exists(),'NO_OVERWRITE'
plan=json.loads((P/'RUN_PLAN.json').read_text());assert time.time()<plan['dispatch_cutoff_unix']-plan['physical_timeout_s']
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
with log.open('x') as out:
    cmd=[sys.executable,'-B',str(P/'continuous_runner.py'),patient,mode]
    worker=subprocess.Popen(cmd,cwd=P,env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
    owner.write_text(json.dumps(dict(pid=os.getpid(),worker_pid=worker.pid,command=cmd,log=str(log),start_unix=time.time()),indent=2)+'\n')
    (P/'OWNED_ACTIVE_PROCESS.json').write_text(json.dumps(dict(owner=os.getpid(),worker=worker.pid,patient=patient,mode=mode))+'\n')
    print('STARTED',patient,worker.pid,log,flush=True)
    try:rc=worker.wait(timeout=max(1,plan['physics_hard_stop_unix']-time.time()))
    except BaseException:
        os.killpg(worker.pid,signal.SIGINT)
        try:rc=worker.wait(timeout=45)
        except subprocess.TimeoutExpired:os.killpg(worker.pid,signal.SIGTERM);rc=worker.wait(timeout=30)
        raise
    finally:
        (P/'OWNED_ACTIVE_PROCESS.json').write_text(json.dumps(dict(active=False,worker_returncode=worker.poll(),closed_unix=time.time()))+'\n')
    (P/'audit'/(ident+'_OWNER_EXIT.json')).write_text(json.dumps(dict(returncode=rc,joined=True,unix=time.time()),indent=2)+'\n')
    print('FINISHED',patient,rc,flush=True)
    sys.exit(rc)
