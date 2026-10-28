"""Independent deadline/orphan watchdog. Only kills identified campaign PGIDs."""
import os,signal,time,traceback
from research_common import ROOT,HARD_STOP,atomic,read,same_pid,now,pid_identity

def main():
    atomic(ROOT/'WATCHDOG_START.json',dict(time_utc=now(),identity=pid_identity(os.getpid()),hard_stop_unix=HARD_STOP))
    reason='NORMAL_FINALIZATION'
    try:
        while not (ROOT/'END.json').exists():
            expired=time.time()>=HARD_STOP-10
            for p in (ROOT/'owned').glob('*.json'):
                a=read(p)
                if a.get('ended') or not same_pid(a.get('worker')):continue
                orphan=not same_pid(a.get('supervisor'))
                timed=time.time()>=a['deadline_unix']
                if expired or orphan or timed or (ROOT/'STOP_REQUESTED').exists():
                    pgid=a['pgid'];os.killpg(pgid,signal.SIGTERM)
                    atomic(p.with_name(p.stem+'_WATCHDOG_STOP.json'),dict(time_utc=now(),pgid=pgid,expired=expired,orphan=orphan,timed=timed))
                    for _ in range(5):
                        if not same_pid(a['worker']):break
                        time.sleep(1)
                    if same_pid(a['worker']):os.killpg(pgid,signal.SIGKILL)
            if expired:reason='HARD_STOP';break
            time.sleep(2)
    except BaseException as exc:
        reason=repr(exc);atomic(ROOT/'WATCHDOG_FAILURE.json',dict(error=reason,traceback=traceback.format_exc()))
        # Workers carry their own deadlines and outer supervisors remain active.
    finally:atomic(ROOT/'WATCHDOG_END.json',dict(time_utc=now(),pid=os.getpid(),reason=reason))
if __name__=='__main__':main()
