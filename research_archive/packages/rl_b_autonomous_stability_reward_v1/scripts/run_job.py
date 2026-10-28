"""Outer owned-process supervisor; survives IDE disconnect and enforces deadlines."""
from pathlib import Path
import json, os, signal, subprocess, sys, time
from research_common import ROOT,RUNTIME,HARD_STOP,NO_TRAIN,atomic,read,sha,resources,check_resources,pid_identity,same_pid,decision,ledger,now
PYTHON=ROOT.parent/'rl_b_matched_recovery_stability_v1/cpu-env/bin/python'

def stop_group(proc):
    if proc.poll() is None:
        try:os.killpg(proc.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            proc.wait(timeout=5)
    # Kill any remaining descendants in this exclusively owned session.
    try:os.killpg(proc.pid,signal.SIGKILL)
    except ProcessLookupError:pass

def run_job(config):
    config=Path(config);cfg=read(config);job=cfg['job_id'];out=ROOT/'jobs'/job
    if (out/'END.json').exists():return read(out/'END.json')
    if out.exists():raise RuntimeError('UNFINISHED_JOB_REQUIRES_EXPLICIT_RECOVERY')
    out.mkdir(parents=True);(ROOT/'owned').mkdir(exist_ok=True)
    started=time.time();wall=min(5400,cfg.get('episodes',1)*300+150)
    parent_id=pid_identity(os.getpid())
    record=dict(time_utc=now(),config=str(config),config_sha256=sha(config),
                 supervisor=parent_id,job=job,deadline_unix=min(started+wall,HARD_STOP-20))
    atomic(out/'START.json',record);proc=None;error=None;rc=None
    try:
        check_resources()
        if cfg['mode']=='training' and time.time()>=NO_TRAIN:raise RuntimeError('NO_NEW_TRAINING_WINDOW')
        names=['worker.py','rewards.py','research_common.py']
        source_hashes={name:sha(ROOT/'scripts'/name) for name in names}
        bundle_hash=__import__('hashlib').sha256(json.dumps(source_hashes,sort_keys=True).encode()).hexdigest()
        version=ROOT/'source_versions'/bundle_hash;version.mkdir(parents=True,exist_ok=True)
        for name in names:
            dest=version/name
            if dest.exists():assert sha(dest)==source_hashes[name]
            else:__import__('shutil').copyfile(ROOT/'scripts'/name,dest)
        atomic(out/'SOURCE_IDENTITY.json',dict(bundle_sha256=bundle_hash,files=source_hashes,path=str(version)))
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1',
            'OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1',
            'CUDA_VISIBLE_DEVICES':'','IHEAR_GUARDED':'1','IHEAR_RESEARCH_ROOT':str(ROOT)}
        with (out/'stdout.log').open('w') as stdout,(out/'stderr.log').open('w') as stderr:
            proc=subprocess.Popen([str(PYTHON),str(version/'worker.py'),'--config',str(config)],
                  cwd=RUNTIME,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
            record.update(worker=pid_identity(proc.pid),pgid=proc.pid)
            atomic(ROOT/'owned'/f'{job}.json',record)
            os.sched_setaffinity(proc.pid,{min(os.sched_getaffinity(0))})
            last_size=0;last_scan=0
            while proc.poll() is None:
                row=check_resources()
                if time.time()>=record['deadline_unix']:raise RuntimeError('OWNED_JOB_WALL_LIMIT')
                if time.time()-last_scan>30:
                    last_size=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())
                    last_scan=time.time()
                    if last_size>60*1024**3:raise RuntimeError('PACKAGE_OUTPUT_60GIB_LIMIT')
                atomic(out/'LIVE.json',dict(time_utc=now(),worker=record['worker'],
                       resources=row,package_bytes=last_size,wall_elapsed=time.time()-started))
                time.sleep(2)
            rc=proc.returncode
        if rc==0 and cfg['mode']=='evaluation':
            result=read(RUNTIME/'jobs'/job/'RESULT.json')
            motion=[]
            for row in result['rows']:
                calc=subprocess.run([str(PYTHON),str(ROOT/'scripts/motion_metrics.py'),row['run']],
                    cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
                motion.append(dict(run=row['run'],returncode=calc.returncode,stdout=calc.stdout,stderr=calc.stderr))
                if calc.returncode:raise RuntimeError('EVALUATION_MOTION_METRICS_FAILURE')
            atomic(out/'MOTION_METRICS_PROCESS.json',motion)
    except BaseException as exc:error=repr(exc)
    finally:
        if proc:stop_group(proc)
        worker_end=read(RUNTIME/'jobs'/job/'END.json')
        # Crash reservations remain charged conservatively; no native work vanishes.
        with ledger() as value:
            for a in value['attempts']:
                if a['job']==job and not a['settled']:
                    a.update(settled=True,native_steps=a['reserved_native_steps'],
                             native_counting='CONSERVATIVE_FULL_RESERVATION_AFTER_CRASH',
                             outcome='UNCONTROLLED_WORKER_EXIT',end_utc=now())
                    value['native_steps']+=a['reserved_native_steps']
        end=dict(time_utc=now(),job=job,returncode=rc,error=error,
                 success=rc==0 and error is None and bool(worker_end and worker_end['completed']),
                 worker_end=worker_end,child_joined=proc is None or proc.poll() is not None,
                 wall_s=time.time()-started)
        atomic(out/'END.json',end)
        if (ROOT/'owned'/f'{job}.json').exists():
            record['ended']=end;atomic(ROOT/'owned'/f'{job}.json',record)
    return end

if __name__=='__main__':
    result=run_job(sys.argv[1]);print(json.dumps(result),flush=True)
    raise SystemExit(0 if result['success'] else 1)
