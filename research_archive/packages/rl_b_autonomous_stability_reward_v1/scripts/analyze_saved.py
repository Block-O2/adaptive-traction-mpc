"""Finite analysis service: saved-data metrics and phase-level figures only."""
import os,sys,time,json,subprocess,traceback
from research_common import ROOT,HARD_STOP,atomic,read,append,now,pid_identity
PYTHON=ROOT.parent/'rl_b_matched_recovery_stability_v1/cpu-env/bin/python'

def run(script,args,timeout):
    proc=subprocess.run([str(PYTHON),str(ROOT/'scripts'/script),*args],cwd=ROOT,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1',
                 'OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'},capture_output=True,text=True,timeout=timeout)
    append(ROOT/'ANALYSIS_SERVICE_LOG.jsonl',dict(time_utc=now(),script=script,args=args,
           returncode=proc.returncode,stdout=proc.stdout[-2000:],stderr=proc.stderr[-4000:]))
    return proc.returncode==0

def main():
    cpus=sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0,{cpus[1] if len(cpus)>1 else cpus[0]})
    atomic(ROOT/'ANALYSIS_SERVICE_START.json',dict(time_utc=now(),identity=pid_identity(os.getpid()),physics_allowed=False))
    seen=set();last_plot=0;last_cp_count=0
    try:
        while not (ROOT/'END.json').exists() and time.time()<HARD_STOP-660:
            p=ROOT/'ALL_ATTEMPTS.jsonl'
            rows=[json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
            ev=[x for x in rows if x['mode']=='evaluation']
            for x in ev:
                if x['job_id'] in seen:continue
                dest=__import__('pathlib').Path(x['run'])/'COMMON_MOTION_METRICS.json'
                if dest.exists() or run('motion_metrics.py',[x['run']],90):seen.add(x['job_id'])
            cp_count=len({x['parent'] for x in ev})
            if cp_count>last_cp_count and time.time()-last_plot>120:
                run('checkpoint_diagnosis.py',[],120)
                run('plot_results.py',[],90)
                last_cp_count=cp_count;last_plot=time.time()
                # Non-scientific report builder uses system Python.
                proc=subprocess.run(['python3',str(ROOT/'scripts/build_reports.py')],cwd=ROOT,
                     env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=60)
                append(ROOT/'ANALYSIS_SERVICE_LOG.jsonl',dict(time_utc=now(),script='build_reports.py',returncode=proc.returncode,stderr=proc.stderr[-2000:]))
            time.sleep(15)
    except BaseException as exc:
        atomic(ROOT/'ANALYSIS_SERVICE_FAILURE.json',dict(time_utc=now(),error=repr(exc),traceback=traceback.format_exc()))
    finally:atomic(ROOT/'ANALYSIS_SERVICE_END.json',dict(time_utc=now(),pid=os.getpid()))
if __name__=='__main__':main()
