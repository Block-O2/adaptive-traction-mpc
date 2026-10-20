from pathlib import Path
import sys,json,time,types,socket
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
sys.path.insert(0,str(S/'code'));sys.path.insert(0,str(Path(__file__).resolve().parent))
import readiness_service as c,fast_task_ipc,completed_result_service
T=types.SimpleNamespace
class Clock:
 def __init__(self):self.n=1_000_000
 def __call__(self):return self.n
def case():
 k=Clock();r=T(stage='TASK',asynchronous=True,request_id=12,sensor_capture_ns=0,source_sample_time_s=0.)
 f=object.__new__(fast_task_ipc.ReadyFuture);f.warm=False;f.finished=False;f.identity=1;f.value={};f.executor=T(sock='fake')
 l=T(closed=False,_outstanding=r,_future=f,_future_requests={f:r},maximum_age_ns=100_000_000)
 calls=[]
 w=T(runtime={'plan_lifecycle':l},clock=k,phase_records=[{'phase':'TASK'}],epoch_ns=0,_last_poll_grid=0,sensor_steps=20,dt_ns=250_000,plant=T(data=T(time=.001)),active_receipt_index=1,catch_up=lambda why:calls.append(why))
 return w,l,r,f,k,calls
def main():
 rows=[];ordinary=[];c.ORIGINAL_NEXT=lambda w:ordinary.append(w.clock())
 saved_select=c.select.select;saved_ready=completed_result_service.completed_task
 try:
  for label,mutation in [('valid',lambda w,l,r,f,k:None),('closed',lambda w,l,r,f,k:setattr(l,'closed',True)),('commission',lambda w,l,r,f,k:setattr(r,'stage','COMMISSIONING')),('sync',lambda w,l,r,f,k:setattr(r,'asynchronous',False)),('warm',lambda w,l,r,f,k:setattr(f,'warm',True)),('finished',lambda w,l,r,f,k:setattr(f,'finished',True)),('badbinding',lambda w,l,r,f,k:l._future_requests.clear()),('recovery',lambda w,l,r,f,k:w.phase_records[-1].update(phase='ACTIVE_RECOVERY')),('expired',lambda w,l,r,f,k:setattr(k,'n',100_000_000))]:
   w,l,r,f,k,calls=case();mutation(w,l,r,f,k);assert (c.eligible(w) is not None)==(label=='valid'),label;rows.append(label)
  for label,readable,observed,complete in [('ready',True,2_000_000,True),('timeout',False,5_000_000,False),('at_deadline',True,5_000_000,True),('stale_readiness',True,2_000_000,False)]:
   w,l,r,f,k,calls=case();prior=len(ordinary);waits=[]
   def select_fake(read,write,error,timeout):
    assert read==['fake'] and not write and not error and 0<timeout<=.004;waits.append(timeout);k.n=observed;return (read if readable else [],[],[])
   c.select.select=select_fake;completed_result_service.completed_task=lambda wall:(r,f) if complete else None
   c.next_control_tick(w);assert len(waits)==1
   assert (len(ordinary)==prior)==(label=='ready');assert len(calls)==(2 if label=='ready' else 1);rows.append(label)
  w,l,r,f,k,calls=case();w.catch_up=lambda why:setattr(k,'n',5_100_000)
  c.select.select=lambda *a:(_ for _ in ()).throw(AssertionError('No timer past deadline'))
  c.next_control_tick(w);assert ordinary[-1]==5_100_000;rows.append('catchup_crosses_deadline')
  w,l,r,f,k,calls=case();k.n=5_000_000;c.next_control_tick(w);rows.append('already_overrun')
 finally:c.select.select=saved_select;completed_result_service.completed_task=saved_ready
 # Real bounded socket timeout, no worker or physical model.
 a,b=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
 try:
  begin=time.monotonic_ns();assert not saved_select([a],[],[],.002)[0];elapsed=time.monotonic_ns()-begin
  b.send(b'complete');assert saved_select([a],[],[],.002)[0]==[a];assert a.recv(64)==b'complete'
 finally:a.close();b.close()
 rows.extend(['real_socket_timer_timeout','real_atomic_socket_readable'])
 out=dict(status='PASS',cases=len(rows),rows=rows,actual_timeout_ns=elapsed,physics_steps=0,model_calls=0,unix=time.time(),limits='Scheduler unit tests only; real closed-loop qualification pending')
 (S/'output/C4_READINESS_SERVICE_LOCAL_REGRESSION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
if __name__=='__main__':main()
