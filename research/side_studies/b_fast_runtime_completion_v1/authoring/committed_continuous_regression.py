from pathlib import Path
import sys,json,time,types
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(Path(__file__).resolve().parent))
import committed_endpoint_service as c
T=types.SimpleNamespace
c.CONTINUOUS_PRECATCH=True;c.PRECATCH=False
original=[];c.ORIGINAL_NEXT=lambda w:original.append(w.clock());rows=[]
for name,deadline,advance,consumed,phase,expect in [('steady_before_endpoint',21500000000,1000000,False,'TASK',1),('endpoint_this_tick',21004000000,1000000,False,'TASK',2),('real_overrun',21004000000,6000000,False,'TASK',1),('consumed',21004000000,1000000,True,'TASK',0),('commissioning',21004000000,1000000,False,'COMMISSIONING',0)]:
 k=T(n=21001000000);calls=[];sleeps=[];item=dict(request_id=12,deadline_ns=deadline,target_step=82000,consumed=consumed)
 w=T(runtime={'_c5_committed_endpoint':item},epoch_ns=21000000000,_last_poll_grid=0,sensor_steps=20,dt_ns=250000,clock=lambda:k.n,phase_records=[dict(phase=phase)],steps=80000,plant=T(data=T(time=20.)))
 def catch(why):
  calls.append(why)
  if why.startswith('C5c_'):k.n+=advance
 def sleep(delay):assert 0<delay<=.005;sleeps.append(delay);k.n+=round(delay*1e9)
 w.catch_up=catch;w.sleeper=sleep;before=len(original);c.next_control_tick(w)
 assert len(calls)==expect,name
 assert (len(original)==before)==(name=='endpoint_this_tick'),name
 if name=='steady_before_endpoint':assert not item['consumed'] and not sleeps
 if name=='endpoint_this_tick':assert item['consumed'] and len(sleeps)==1
 rows.append(dict(name=name,calls=calls,sleep_seconds=sleeps,regular_service=len(original)>before,consumed=item['consumed']))
out=dict(status='PASS',cases=len(rows),rows=rows,physics_steps=0,model_API_calls=0,unix=time.time(),no_dwell_or_endpoint_test_change=True,no_new_requests=True)
(S/'output/C5c_CONTINUOUS_COMMITTED_HOLD_REGRESSION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
