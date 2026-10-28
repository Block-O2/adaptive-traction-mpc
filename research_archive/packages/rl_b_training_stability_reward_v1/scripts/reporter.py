"""Progress telemetry and 2/4/6h reports; no experiment generation."""
import os,time,json
from datetime import datetime
from research_common import ROOT,read,atomic,append,now,pid_identity,HARD_STOP,resources
atomic(ROOT/'REPORTER_START.json',dict(time_utc=now(),identity=pid_identity(os.getpid())))
t0=datetime.fromisoformat(read(ROOT/'ACTIVATION.json')['activation_utc']).timestamp()
while time.time()<HARD_STOP-5 and not (ROOT/'END.json').exists() and not (ROOT/'CLOSURE_IDENTITY.json').exists():
 l=read(ROOT/'LEDGER.json',{});s=read(ROOT/'RESEARCH_STATE.json',{});r=resources();elapsed=time.time()-t0
 report=dict(time_utc=now(),elapsed_hours=elapsed/3600,state=s,attempts=len(l.get('attempts',[])),training_attempts=l.get('training_attempts',0),evaluation_attempts=l.get('evaluation_attempts',0),native_steps=l.get('native_steps',0),optimizer_steps=l.get('optimizer_steps',0),resources=r,remaining=dict(wall_s=max(0,HARD_STOP-time.time()),training=160-l.get('training_attempts',0),evaluation=36-l.get('evaluation_attempts',0),native=33000000-l.get('native_steps',0)),scope='Bounded development only; formal gates remain closed')
 atomic(ROOT/'PROGRESS_REPORT.json',report);append(ROOT/'RESOURCE_TELEMETRY.jsonl',r)
 for hour in [2,4,6]:
  p=ROOT/f'STAGE_REPORT_{hour}H.json'
  if elapsed>=hour*3600 and not p.exists():
   report['next_decision']='Continue finite preregistered queue unless safety/identity guard fails; failures preserved'
   atomic(p,report)
 for _ in range(30):
  if (ROOT/'END.json').exists() or (ROOT/'CLOSURE_IDENTITY.json').exists():break
  time.sleep(2)
atomic(ROOT/'REPORTER_END.json',dict(time_utc=now(),identity=pid_identity(os.getpid())))
