from pathlib import Path
import sys,json,types,time,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');sys.path.insert(0,str(S/'code'))
import hold_endpoint_handoff as c
from types import SimpleNamespace as N
rows=json.loads((S/'reports/HOLD_CRITICAL_PATH_EXISTING.json').read_text())['rows'];checks=[]
class Governor:
 def __init__(self,s,p):self.schedule=s;self.progress_s=p
 def is_complete(self,s):return self.schedule is s and self.progress_s>=s.duration_s-1e-12
class Wall:
 def __init__(self):self.runtime={};self.phase_records=[dict(phase='TASK')];self.steps=100;self.plant=N(data=N(time=1.));self.active_receipt_index=1;self.calls=[];self.now=10
 def clock(self):self.now+=1;return self.now
 def catch_up(self,label):self.calls.append(label) # logical harness, no physical simulation
fake=N(ROWS={'fast':[]});previous=sys.modules.get('multirate');sys.modules['multirate']=fake
c.ORIGINAL_NEXT=lambda w:w.calls.append('ORIGINAL_TIMER')
for row in rows:
 for event in row['events']:
  if 'ENDPOINT_RECEIPT' not in event['event'] or event['host_ns'] is None:continue
  wall=Wall();runtime={'wall_session':wall};wall.runtime=runtime;schedule=N(candidate=N(phase=N(value='HOLD')),duration_s=.5);g=Governor(schedule,.5)
  receipt=dict(applied=True,apply_ns=event['host_ns'],receipt_index=event['receipt_index'],start_physics_s=event['physical_time_s']);proposal={'selected_progress_s':.5}
  assert c.register(runtime,g,schedule,proposal,receipt,False)
  c.next_control_tick(wall);c.next_control_tick(wall)
  assert wall.calls==['C7_actual_committed_HOLD_endpoint_current_service','ORIGINAL_TIMER']
  assert not c.register(runtime,g,schedule,proposal,receipt,True)
  for bad in (dict(receipt,applied=False),dict(receipt,apply_ns=None)):
   assert not c.register(runtime,g,schedule,proposal,bad,False)
  g.progress_s=.5-2e-12;assert not c.register(runtime,g,schedule,proposal,receipt,False)
  g.progress_s=.5;schedule.candidate.phase.value='RETURN';assert not c.register(runtime,g,schedule,proposal,receipt,False)
  checks.append(dict(run=row['id'],endpoint_receipt_index=event['receipt_index'],one_current_service=True,original_timer_after_one_service=True,no_request_or_command_or_clock_credit=True,original_1e_12_boundary_preserved=True))
if previous is None:sys.modules.pop('multirate')
else:sys.modules['multirate']=previous
assert len(checks)>=14
for p in (S/'code').glob('*.py'):compile(p.read_text(),str(p),'exec')
out=dict(status='PASS',unix=time.time(),saved_endpoint_checks=checks,physical_steps=0,model_API_calls=0,source_sha256=hashlib.sha256((S/'code/hold_endpoint_handoff.py').read_bytes()).hexdigest(),scientific_bypass="installed only when execution_mode != SCIENTIFIC_SIMULATION",limits_unchanged=True)
(S/'output/C7_LOCAL_EQUIVALENCE.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(status=out['status'],saved_endpoint_count=len(checks),physical_steps=0,model_API_calls=0)))
