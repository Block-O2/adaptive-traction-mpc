from pathlib import Path
import json,sys,time,socket,types,copy,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');sys.path.insert(0,str(S/'code'));sys.dont_write_bytecode=True
import hold_request_collection as c,fast_task_ipc
N=types.SimpleNamespace
class Wall:
 def __init__(self):
  self.epoch_ns=time.monotonic_ns();self.clock=time.monotonic_ns;self.steps=0;self._last_poll_grid=0;self.sensor_steps=20;self.dt_ns=250000;self.phase_records=[dict(phase='TASK')];self.active=True;self.active_receipt_index=0;self.applied_commands=[dict(receipt_index=0,applied=True,supervisor_mode='TRACK',command='unchanged original command')];self.events=[]
 def catch_up(self,reason):self.steps=max(self.steps,(self.clock()-self.epoch_ns)//self.dt_ns);self.events.append((reason,self.steps))
def case(ready,change=None):
 wall=Wall();request=N(stage='TASK',asynchronous=True,request_id=12,sensor_capture_ns=wall.epoch_ns)
 parent,child=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET);parent.setblocking(False)
 future=fast_task_ipc.ReadyFuture.__new__(fast_task_ipc.ReadyFuture);future.warm=False;future.identity=1;future.executor=N(sock=parent);future.done=lambda:ready
 life=N(closed=False,_outstanding=request,_future_requests={future:request},maximum_age_ns=100000000)
 pending=dict(request=request,future=future,phase=N(value='HOLD'),pass_through_prefetch=False);runtime=dict(wall_session=wall,plan_lifecycle=life)
 if change:change(runtime,pending)
 before=copy.deepcopy(wall.applied_commands)
 if ready:child.send(b'actual complete packet readiness')
 try:out=c.observe(runtime,pending)
 finally:parent.close();child.close()
 assert before==wall.applied_commands,'helper must not change or write a command'
 assert life._outstanding is request,'no original lifecycle disposition is changed'
 return out,wall
rows=[]
for ready in (True,False):
 out,wall=case(ready);assert out and wall.events
 event=c.ROWS[-1];assert event['authority'] is False and event['phase_advanced'] is False
 assert event['deadline_ns']-wall.epoch_ns==5000000
 rows.append(dict(ready=ready,result=out,deadline_original_5ms=True,actual_elapsed_old_command_steps=int(wall.steps),fake_clock_logic_only=True))
for name,change in [
 ('wrong phase',lambda r,p:setattr(p['phase'],'value','RETURN')),
 ('prefetch',lambda r,p:p.update(pass_through_prefetch=True)),
 ('wrong stage',lambda r,p:setattr(p['request'],'stage','COMMISSIONING')),
 ('closed',lambda r,p:setattr(r['plan_lifecycle'],'closed',True)),
 ('brake receipt',lambda r,p:r['wall_session'].applied_commands[0].update(supervisor_mode='BRAKE')),
 ('unapplied receipt',lambda r,p:r['wall_session'].applied_commands[0].update(applied=False)),
 ('expired request',lambda r,p:setattr(p['request'],'sensor_capture_ns',p['request'].sensor_capture_ns-100000001)),
 ('inactive epoch',lambda r,p:setattr(r['wall_session'],'active',False))]:
 out,wall=case(False,change);assert not out and not wall.events;rows.append(dict(case=name,original_path_preserved=True))
out=dict(status='PASS',rows=rows,physics_steps=0,model_API_calls=0,scope='service orchestration logic using real bounded socket readiness and stub physics; no controller/native-plant qualification',source_sha256=hashlib.sha256((S/'code/hold_request_collection.py').read_bytes()).hexdigest())
p=S/'output/C11_LOCAL_EQUIVALENCE.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
