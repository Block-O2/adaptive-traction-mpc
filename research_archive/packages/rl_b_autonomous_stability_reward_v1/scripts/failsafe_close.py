"""Finite unattended fallback. The live agent may finalize sooner after review."""
import os,subprocess,time
from research_common import ROOT,HARD_STOP,atomic,pid_identity,now
atomic(ROOT/'FAILSAFE_START.json',dict(time_utc=now(),identity=pid_identity(os.getpid()),trigger_unix=HARD_STOP-600))
while not (ROOT/'STOP.json').exists() and time.time()<HARD_STOP-600:time.sleep(10)
if not (ROOT/'STOP.json').exists():
    with (ROOT/'failsafe_finalization.stdout.log').open('wb') as out,(ROOT/'failsafe_finalization.stderr.log').open('wb') as err:
        p=subprocess.Popen(['python3',str(ROOT/'scripts/finalize.py'),'UNATTENDED_DEADLINE_CLOSURE'],
             cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=out,stderr=err,start_new_session=True)
        atomic(ROOT/'FAILSAFE_FINALIZER.json',dict(time_utc=now(),identity=pid_identity(p.pid)))
atomic(ROOT/'FAILSAFE_END.json',dict(time_utc=now(),pid=os.getpid()))
