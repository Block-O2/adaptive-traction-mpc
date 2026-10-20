"""Join one known extension child and monitor its actual descendant scope."""
from extension_common import *
import os,signal,fcntl

def main():
    job,script=sys.argv[1:3];guard(900)
    lock=(EXT/'owner.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);lock.write(str(os.getpid()));lock.flush()
    target=STUDY/'code'/script;source_sha=sha(target);begin=time.time();child=None;log=None;last_sample=0;history=[];signalled=None
    counted=script=='extension_single_capture.py'
    from accounting import attempts
    attempt_before=attempts()
    append('TASK_LEDGER.jsonl',dict(event='START',id=job,unix=begin,script=str(target),source_sha256=source_sha,kind='COUNTED_SINGLE_PHYSICS_DIAGNOSTIC' if counted else 'OFFLINE_NO_PHYSICS',physics_attempts_added=0,physics_attempts_planned=1 if counted else 0))
    try:
        import runner
        log=(EXT/(job+'_WORKER.log')).open('w')
        child=subprocess.Popen([sys.executable,'-u',str(target),*sys.argv[3:]],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        save(EXT/'ACTIVE.json',dict(id=job,owner_pid=os.getpid(),child_pid=child.pid,started_unix=begin,deadline_unix=DEADLINE))
        while child.poll() is None:
            now=time.time()
            if now-last_sample>=45:
                # runner.sample sees this monitor and verified descendants only;
                # original runner is closed, and no original ledger is edited.
                row=runner.sample(owner='NOON_EXTENSION_'+job,filename='NOON_EXTENSION_RESOURCE_LOG.jsonl');history.append(row);history=history[-5:];last_sample=time.time()
                append('RESOURCE_LOG.jsonl',row)
                low=row['mem_available']<.35*2**30 or row['windows'].get('commit_headroom',10*2**30)<.35*2**30
                oom=len(history)>1 and row['oom_kill']>history[-2]['oom_kill']
                pressure=len(history)>=4 and all(x['mem_available']<1.25*2**30 for x in history[-4:]) and row['swap_in']-history[-4]['swap_in']+row['swap_out']-history[-4]['swap_out']>4096
                if low or oom or pressure:
                    save(EXT/'RESOURCE_STOP.json',dict(unix=time.time(),row=row,reason='Observed actual resource pressure'))
                    if signalled is None:os.killpg(child.pid,signal.SIGINT);signalled=time.time()
            if time.time()>=DEADLINE-900 or time.time()-begin>1800:
                if signalled is None:os.killpg(child.pid,signal.SIGINT);signalled=time.time()
            if signalled is not None and time.time()-signalled>60:
                os.killpg(child.pid,signal.SIGTERM);break
            time.sleep(1)
        code=child.wait(timeout=30)
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGINT)
            try:child.wait(timeout=30)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=30)
        if log:log.close()
        row=dict(event='END',id=job,unix=time.time(),started_unix=begin,wall_seconds=time.time()-begin,returncode=None if child is None else child.returncode,source_sha256=source_sha,source_unchanged=sha(target)==source_sha,child_joined=child is None or child.poll() is not None,physics_attempts_added=attempts()-attempt_before)
        append('TASK_LEDGER.jsonl',row);save(EXT/'ACTIVE.json',dict(status='IDLE',last_job=job,unix=time.time(),owned_child=None))
    print(json.dumps(row));raise SystemExit(code)

if __name__=='__main__':main()
