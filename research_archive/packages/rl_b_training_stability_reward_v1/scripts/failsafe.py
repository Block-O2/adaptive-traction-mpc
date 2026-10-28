"""Independent deadline close; no new experiment generation."""
import time,os,sys,subprocess
from research_common import ROOT,HARD_STOP,atomic,pid_identity,now
atomic(ROOT/'FAILSAFE_START.json',dict(time_utc=now(),identity=pid_identity(os.getpid()),trigger_unix=HARD_STOP-600))
while not (ROOT/'END.json').exists() and time.time()<HARD_STOP-600:time.sleep(2)
if not (ROOT/'END.json').exists():
 subprocess.run([sys.executable,str(ROOT/'scripts/close_campaign.py')],cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},timeout=540)
atomic(ROOT/'FAILSAFE_END.json',dict(time_utc=now(),identity=pid_identity(os.getpid())))
