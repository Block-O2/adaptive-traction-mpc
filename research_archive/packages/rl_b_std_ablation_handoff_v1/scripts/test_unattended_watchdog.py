"""Real disposable subprocess tests of the future watchdog; no simulator or learning."""
from pathlib import Path
import os,sys,json,time,subprocess,tempfile,datetime,signal
from research_common import ROOT,atomic,now,pid_identity,same_pid
T=ROOT/'unattended/template/scripts';checks={}
for scenario in ['timed_worker','orphan_worker','review_during_stop','reused_pid']:
 with tempfile.TemporaryDirectory(prefix='std_watchdog_',dir='/tmp') as tmp:
  r=Path(tmp);(r/'owned').mkdir();current=datetime.datetime.now(datetime.timezone.utc)
  atomic(r/'START.json',dict(hard_stop_utc=(current+datetime.timedelta(seconds=40)).isoformat(),no_new_training_utc=(current+datetime.timedelta(seconds=30)).isoformat(),limits=dict(training_attempts=160,evaluation_attempts=36,native_steps=33000000)))
  child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(25)'],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  ident=pid_identity(child.pid);parent=pid_identity(os.getpid());deadline=time.time()+1
  record=dict(job='DISPOSABLE_STD_CONTROL_FIXTURE',worker=ident,supervisor=parent,pgid=child.pid,deadline_unix=deadline)
  if scenario=='orphan_worker':record['supervisor']=dict(parent,start_ticks='0')
  if scenario=='reused_pid':record['worker']=dict(ident,start_ticks='0');record['deadline_unix']=time.time()-1
  if scenario=='review_during_stop':record.update(kind='bounded_saved_review',deadline_unix=time.time()+3);(r/'STOP_REQUESTED').write_text('fixture')
  atomic(r/'owned/fixture.json',record)
  env={**os.environ,'IHEAR_RESEARCH_ROOT':str(r),'PYTHONDONTWRITEBYTECODE':'1'}
  watch=subprocess.Popen([sys.executable,str(T/'watchdog.py')],cwd=r,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
  try:
   if scenario=='reused_pid':
    time.sleep(.5);checks['watchdog_does_not_kill_reused_PID_identity']=child.poll() is None
   else:
    if scenario=='review_during_stop':time.sleep(.7);checks['read_only_reviewer_survives_physics_STOP_until_its_deadline']=child.poll() is None
    child.wait(timeout=8);checks[scenario+'_killed_and_joined']=child.returncode is not None
   atomic(r/'END.json',dict(fixture_complete=True));watch.wait(timeout=4);checks[scenario+'_watchdog_exits']=watch.returncode==0 and (r/'WATCHDOG_END.json').exists()
  finally:
   if child.poll() is None:os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=3)
   if watch.poll() is None:watch.terminate();watch.wait(timeout=3)
   assert child.poll() is not None and watch.poll() is not None
result=dict(time_utc=now(),checks=checks,pass_=all(checks.values()),new_physics=0,Adam=0,scope='Actual watchdog tested with four disposable sleep subprocess groups only; all fixture processes joined')
atomic(ROOT/'audit/UNATTENDED_WATCHDOG_TESTS.json',result);print(json.dumps(result));assert result['pass_']
