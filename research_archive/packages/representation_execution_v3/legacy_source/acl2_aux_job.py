"""One bounded zero-native auxiliary job; physical queue remains serial."""
from pathlib import Path
import os,sys,json,time,subprocess,signal,fcntl
from acl2_shared import P,R,read,put,sha,utc

def main():
    jid=sys.argv[1];j=read('queue/'+jid+'.json');assert j['script']=='acl2_response_model.py','ONLY_PREREGISTERED_ZERO_NATIVE_BUILDER';A=read('ACTIVATION.json');out=P/'jobs'/jid;out.mkdir(parents=True,exist_ok=True)
    lease=(out/'AUX_CLAIM.lock').open('a');fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert not (out/'START.json').exists() and not (out/'END.json').exists(),'NO_DUPLICATE_JOB'
    assert (P/'jobs/CORE/CHECKPOINT_016.json').exists(),'COMMON17_DATA_REQUIRED'
    deadline=min(time.time()+j['timeout_s'],A['hard_stop_unix']-600);command=[sys.executable,str(P/'source'/j['script'])]+j.get('args',[]);env=os.environ.copy();env.update(ACL2_PACKAGE=str(P),ACL2_OWNER=A['identity'],PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLCONFIGDIR=str(R/'tmp/mpl'))
    with (out/'stdout.log').open('ab') as stdout,(out/'stderr.log').open('ab') as stderr:proc=subprocess.Popen(command,env=env,stdout=stdout,stderr=stderr,start_new_session=True,cwd=P)
    start=time.time();put('jobs/'+jid+'/START.json',dict(id=jid,pid=proc.pid,owner_pid=os.getpid(),utc=utc(),start_unix=start,command=command,source_sha256=sha(P/'source'/j['script']),absolute_deadline_unix=deadline,execution='EARLY_BOUNDED_ZERO_NATIVE_AUXILIARY',schedule_addendum='EARLY_REFERENCE_BUILD_SCHEDULE_ADDENDUM.json'))
    code=None;reason=None
    while proc.poll() is None:
        if time.time()>=deadline or (P/'STOP_REQUESTED').exists():
            reason='AUX_TIMEOUT_OR_STOP';proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            break
        time.sleep(.5)
    code=proc.wait();put('jobs/'+jid+'/END.json',dict(status='COMPLETED' if code==0 else 'FAILED_PRESERVED',returncode=code,utc=utc(),wall_s=time.time()-start,reason=reason,new_native_steps=0,aux_owner_pid=os.getpid(),physical_queue_not_restarted=True))

if __name__=='__main__':main()
