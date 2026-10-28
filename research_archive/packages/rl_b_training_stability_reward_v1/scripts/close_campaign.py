"""Deadline/final close with PID-identity checks and independent saved-data audits."""
from pathlib import Path
import os,sys,json,time,signal,subprocess,fcntl
from research_common import ROOT,RUNTIME,HARD_STOP,read,atomic,sha,now,same_pid,pid_identity,ledger

def kill_owned(record):
 if not same_pid(record.get('worker')):return
 assert os.getpgid(record['worker']['pid'])==record['pgid'],'OWNED_PGID_IDENTITY_MISMATCH'
 try:os.killpg(record['pgid'],signal.SIGTERM)
 except ProcessLookupError:return
 for _ in range(10):
  if not same_pid(record['worker']):return
  time.sleep(.2)
 if same_pid(record['worker']):os.killpg(record['pgid'],signal.SIGKILL)

def main():
 with (ROOT/'.close.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  if (ROOT/'END.json').exists():return
  atomic(ROOT/'CLOSURE_IDENTITY.json',dict(time_utc=now(),identity=pid_identity(os.getpid())))
  (ROOT/'STOP_REQUESTED').write_text(now())
  records=[read(p) for p in (ROOT/'owned').glob('*.json') if not p.name.endswith('_WATCHDOG_STOP.json')]
  for r in records:kill_owned(r)
  for _ in range(20):
   if not any(same_pid(r.get('worker')) for r in records):break
   time.sleep(.2)
  assert not any(same_pid(r.get('worker')) for r in records),'UNCLOSED_OWNER'
  with ledger() as value:
   for a in value['attempts']:
    if not a['settled']:
     a.update(settled=True,native_steps=a['reserved_native_steps'],native_counting='CONSERVATIVE_FULL_RESERVATION_AFTER_CRASH',outcome='DEADLINE_OR_OWNER_CLOSE',end_utc=now());value['native_steps']+=a['reserved_native_steps']
  # Fresh separate process recomputes saved evidence, never invokes environment reset/update.
  review_deadline=min(time.time()+480,HARD_STOP-30)
  with (ROOT/'review.stdout.log').open('w') as stdout,(ROOT/'review.stderr.log').open('w') as stderr:
   review=subprocess.Popen([sys.executable,str(ROOT/'scripts/verify_saved.py')],cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=stdout,stderr=stderr,start_new_session=True)
   owned=dict(time_utc=now(),job='FINAL_INDEPENDENT_SAVED_REVIEW',kind='bounded_saved_review',worker=pid_identity(review.pid),supervisor=pid_identity(os.getpid()),pgid=review.pid,deadline_unix=review_deadline)
   atomic(ROOT/'owned/FINAL_INDEPENDENT_SAVED_REVIEW.json',owned)
   error=None
   try:review.wait(timeout=max(1,review_deadline-time.time()))
   except subprocess.TimeoutExpired:
    error='FINAL_REVIEW_WALL_LIMIT';kill_owned(owned);review.wait(timeout=5)
   finally:
    if review.poll() is None:kill_owned(owned);review.wait(timeout=5)
    try:os.killpg(review.pid,signal.SIGKILL)
    except ProcessLookupError:pass
   result=type('ReviewResult',(),{'returncode':review.returncode})()
  owned['ended']=dict(time_utc=now(),returncode=review.returncode,error=error);atomic(ROOT/'owned/FINAL_INDEPENDENT_SAVED_REVIEW.json',owned)
  atomic(ROOT/'INDEPENDENT_REVIEW_PROCESS.json',dict(returncode=review.returncode,error=error,joined=review.poll() is not None))
  atomic(ROOT/'END.json',dict(time_utc=now(),owned_workers_exited=True,independent_review_pass=result.returncode==0,training_complete=False if (ROOT/'RESEARCH_STATE.json').exists() and read(ROOT/'RESEARCH_STATE.json')['status']=='GLOBAL_STOP' else None,formal_campaign_started=False,manual_scientific_review_required=True))
  finalizer=ROOT/'analysis_tools/finalize.py'
  if finalizer.exists():
   with (ROOT/'finalize.stdout.log').open('w') as stdout,(ROOT/'finalize.stderr.log').open('w') as stderr:
    child=subprocess.Popen([sys.executable,str(finalizer)],cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=stdout,stderr=stderr,start_new_session=True)
    atomic(ROOT/'FINALIZER_PROCESS.json',dict(time_utc=now(),worker=pid_identity(child.pid),supervisor=pid_identity(os.getpid()),pgid=child.pid,kind='bounded_readonly_finalization',deadline_unix=min(time.time()+1200,HARD_STOP-5)))

if __name__=='__main__':main()
