from pathlib import Path
import sys,json,time,types
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(Path(__file__).resolve().parent))
import committed_endpoint_service as c
T=types.SimpleNamespace
def make(phase='HOLD',duration=.5,rolling=None,applied=True):
 decisions=[dict(phase=phase,rolling_composite=rolling)];active_decision_index=0;suffix_schedule=T(duration_s=duration);request=T(stage='TASK',request_id=12)
 def hook(receipt):return decisions[active_decision_index],suffix_schedule,request
 w=T(dt_ns=250_000,steps=80000,epoch_ns=1000000000,plant=T(data=T(time=20.)))
 return {'wall_session':w},hook,dict(applied=applied,apply_ns=21000000000,receipt_index=4)
def main():
 rows=[]
 for label,kw,expected in [('valid',{},True),('moving',{'phase':'OUTBOUND'},False),('nonoriginal_duration',{'duration':1.},False),('rolling',{'rolling':{}},False),('notapplied',{'applied':False},False)]:
  rt,h,r=make(**kw);h(r);c.register_after_original_hook(rt,h,r);assert ('_c5_committed_endpoint' in rt)==expected
  if expected:assert rt['_c5_committed_endpoint']['target_step']==82000 and rt['_c5_committed_endpoint']['deadline_ns']==21500000000
  rows.append(label)
 original=[];c.ORIGINAL_NEXT=lambda w:original.append(w.clock())
 c.PRECATCH=True
 for label,advance,expected_extra in [('precatch_then_endpoint',1000000,True),('precatch_overrun',6000000,False)]:
  clock=T(n=21001000000);calls=[];item=dict(request_id=12,consumed=False,deadline_ns=21004000000,target_step=84016)
  w=T(runtime={'_c5_committed_endpoint':item},epoch_ns=21000000000,_last_poll_grid=0,sensor_steps=20,dt_ns=250000,clock=lambda:clock.n,phase_records=[dict(phase='TASK')],steps=84000,plant=T(data=T(time=21.)))
  def catch(reason):
   calls.append(reason)
   if reason.startswith('C5b_'):clock.n+=advance
  w.catch_up=catch;w.sleeper=lambda delay:setattr(clock,'n',clock.n+round(delay*1e9))
  before=len(original);c.next_control_tick(w);assert item['consumed'];assert len(calls)==(2 if expected_extra else 1);assert (len(original)==before)==expected_extra
  rows.append(label)
 c.PRECATCH=False
 original=[];c.ORIGINAL_NEXT=lambda w:original.append(w.clock())
 for label,now,deadline,target,consumed,task,expected in [('future',21_001_000_000,21_002_000_000,21_005_000_000,False,True,True),('already_past',21_003_000_000,21_002_000_000,21_005_000_000,False,True,True),('regular_first',21_001_000_000,21_006_000_000,21_005_000_000,False,True,False),('already_regular',21_006_000_000,21_002_000_000,21_005_000_000,False,True,False),('consumed',21_001_000_000,21_002_000_000,21_005_000_000,True,True,False),('notTASK',21_001_000_000,21_002_000_000,21_005_000_000,False,False,False)]:
  clock=T(n=now);calls=[];slept=[];item=dict(request_id=12,consumed=consumed,deadline_ns=deadline,target_step=84008)
  w=T(runtime={'_c5_committed_endpoint':item},epoch_ns=target-5000000,_last_poll_grid=0,sensor_steps=20,dt_ns=250000,clock=lambda:clock.n,phase_records=[dict(phase='TASK' if task else 'COMMISSIONING')],steps=84000,plant=T(data=T(time=21.)))
  def sleep(delay):assert 0<delay<=.005;slept.append(delay);clock.n+=round(delay*1e9)
  w.sleeper=sleep;w.catch_up=lambda reason:calls.append(reason)
  before=len(original);c.next_control_tick(w);assert bool(calls)==expected;assert (len(original)==before)==expected
  if expected:assert item['consumed'];c.next_control_tick(w);assert len(calls)==1
  rows.append(label)
 # Completion checks remain entirely original; C5 only asks for real service.
 time_rows=[]
 for start in (0.,19.24525,20.,1000.,10000.):
  finish=start
  for _ in range(2000):finish+=.00025
  time_rows.append(dict(start=start,finish=finish,original_done=finish-start+1e-12>=.5,error_s=finish-start-.5))
 out=dict(status='PASS',cases=len(rows),rows=rows,grid_rounding_diagnostic=time_rows,original_completion_test_unchanged=True,physics_steps=0,model_API_calls=0,unix=time.time())
 (S/'output/C5b_COMMITTED_ENDPOINT_LOCAL_REGRESSION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
if __name__=='__main__':main()
