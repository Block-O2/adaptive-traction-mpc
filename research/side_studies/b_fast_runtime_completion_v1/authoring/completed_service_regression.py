from pathlib import Path
import sys,json,time,types
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
sys.path.insert(0,str(S/'code'))
import completed_result_service as c,fast_task_ipc
T=types.SimpleNamespace
class Clock:
 def __init__(self,n):self.n=n
 def __call__(self):return self.n
def case(change=None):
 clock=Clock(3_000_000);request=T(stage='TASK',asynchronous=True,request_id=12,sensor_capture_ns=0,source_sample_time_s=0.)
 future=object.__new__(fast_task_ipc.ReadyFuture);future.warm=False;future.identity=7;future.finished=True;future.value={};future.executor=None
 life=T(closed=False,_outstanding=request,_future=future,_future_requests={future:request},maximum_age_ns=100_000_000)
 wall=T(runtime={'plan_lifecycle':life},clock=clock,phase_records=[{'phase':'TASK'}],epoch_ns=0,_last_poll_grid=0,sensor_steps=20,dt_ns=250_000,plant=T(data=T(time=.003)),active_receipt_index=8)
 calls=[];wall.catch_up=lambda reason:calls.append(reason)
 if change:change(wall,life,request,future,clock)
 return wall,life,request,future,clock,calls
def main():
 rows=[]
 for label,change in [('valid',None),('closed',lambda w,l,r,f,k:setattr(l,'closed',True)),('commission',lambda w,l,r,f,k:setattr(r,'stage','COMMISSIONING')),('sync',lambda w,l,r,f,k:setattr(r,'asynchronous',False)),('warm',lambda w,l,r,f,k:setattr(f,'warm',True)),('wrong_request',lambda w,l,r,f,k:l._future_requests.clear()),('recovery',lambda w,l,r,f,k:w.phase_records[-1].update(phase='ACTIVE_RECOVERY')),('expired_equal',lambda w,l,r,f,k:setattr(k,'n',100_000_000)),('missing',lambda w,l,r,f,k:setattr(l,'_outstanding',None))]:
  w,l,r,f,k,calls=case(change);value=c.completed_task(w)
  assert (value is not None)==(label=='valid'),label
  if value is not None:assert c.completed_task(w) is None
  rows.append(label)
 # An unfinished packet is observed nonblocking and produces no extra service.
 w,l,r,f,k,calls=case();f.finished=False
 class Empty:
  def recv(self,n):raise BlockingIOError
 f.executor=T(sock=Empty());assert c.completed_task(w) is None
 rows.append('unfinished_nonblocking')
 # Callback clearing the original lifecycle's outstanding request prevents wake.
 w,l,r,f,k,calls=case();f.done=lambda:(setattr(l,'_outstanding',None) or True)
 assert c.completed_task(w) is None;rows.append('failed_harvest')
 original_calls=[];c.ORIGINAL_NEXT=lambda w:original_calls.append(w.clock())
 w,l,r,f,k,calls=case();c.next_control_tick(w);assert len(calls)==1 and not original_calls
 assert c.ROWS[-1]['ready_observed_ns']<c.ROWS[-1]['scheduled_deadline_ns']
 c.next_control_tick(w);assert len(original_calls)==1
 w,l,r,f,k,calls=case();k.n=5_000_000;c.next_control_tick(w);assert not calls and len(original_calls)==2
 rows.extend(['one_extra_then_original','deadline_original'])
 c.PRECATCH=True
 w,l,r,f,k,calls=case();c.next_control_tick(w);assert len(calls)==2
 assert calls[0].startswith('C3b_existing_command') and calls[1].startswith('next_control_tick_C3')
 w,l,r,f,k,calls=case()
 def slowcatch(reason):calls.append(reason);k.n+=2_500_000
 w.catch_up=slowcatch;c.next_control_tick(w)
 assert len(calls)==1 and calls[0].startswith('C3b_existing_command') and original_calls[-1]==5_500_000
 w,l,r,f,k,calls=case();r.stage='COMMISSIONING';c.next_control_tick(w);assert not calls
 rows.extend(['precatch_existing_command_then_ready','precatch_cross_deadline_original','precatch_TASK_only'])
 out=dict(status='PASS',cases=len(rows),rows=rows,physics_steps=0,model_calls=0,unix=time.time(),limits='Scheduler decision unit regression; no host qualification claim.')
 (S/'output/C3b_COMPLETED_SERVICE_LOCAL_REGRESSION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
if __name__=='__main__':main()
