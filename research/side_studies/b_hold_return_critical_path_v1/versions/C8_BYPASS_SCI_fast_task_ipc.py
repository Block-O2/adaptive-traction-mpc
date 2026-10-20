"""D1: one original TASK worker, atomic immutable packets, no manager thread.

SOCK_SEQPACKET provides complete-message readiness. Runtime polling never
waits for work, partial payloads or disk. Blocking warm/join occur outside the
physical epoch. No live plant or half-updated model is sent to this process.
"""
import socket,struct,pickle,time,hashlib,multiprocessing,select,os,gc
MAX_PACKET=1024*1024;HEADER=struct.Struct('!QQ');ROWS=[]
def packet(sock,identity,value):
 raw=pickle.dumps(value,protocol=5);ready=time.monotonic_ns();data=HEADER.pack(identity,ready)+raw
 if len(data)>MAX_PACKET:raise ValueError('TASK_PACKET_LIMIT_EXCEEDED')
 assert sock.send(data)==len(data),'ATOMIC_TASK_PACKET_INCOMPLETE'
def worker(sock,fast,fault_config=None):
 import lean_instrumentation;lean_instrumentation.prime()
 import slow_owner
 ready=slow_owner.warm()
 if fast:
  import fast_task_owner
  ready=fast_task_owner.warm()
 if os.environ.get('FAST_HOLD_STATIC_MECHANICS')=='C8':
  import hold_static_mechanics
  hold_static_mechanics.install()
 packet(sock,0,ready)
 while True:
  data=sock.recv(MAX_PACKET)
  if not data:break
  identity,kind,payload=pickle.loads(data)
  if kind=='STOP':break
  if kind=='WARM_TRANSPORT':
   assert identity==0 and isinstance(payload,bytes) and len(payload)==65536
   packet(sock,0,dict(transport_probe_sha256=hashlib.sha256(payload).hexdigest(),transport_echo=payload));continue
  assert kind=='TASK' and isinstance(payload,bytes)
  result=fast_task_owner.task_with_certificates(payload) if fast else slow_owner.task_with_certificates(payload)
  if fault_config is not None:
   import fault_injection
   result=fault_injection.task_result(result,identity,fault_config)
  if os.environ.get('FAST_HOLD_STATIC_MECHANICS')=='C8':result['hold_static_mechanics']=hold_static_mechanics.evidence()
  try:packet(sock,identity,result)
  except BaseException as error:
   now=time.monotonic_ns();packet(sock,identity,dict(worker_exception=f'TASK_TRANSPORT:{type(error).__name__}:{error}',worker_start_ns=now,compute_finish_ns=now))
  if os.environ.get('FAST_HOLD_STATIC_MECHANICS')=='C8' and 'value' in result:
   hold_static_mechanics.prepare(payload,result['value'])
 sock.close()
class ReadyFuture:
 def __init__(self,executor,identity,warm=False):
  self.executor=executor;self.identity=identity;self.warm=warm;self.value=None;self.finished=False;self.callbacks=[]
 def _receive(self,blocking=False):
  if self.finished:return True
  sock=self.executor.sock
  if blocking and not select.select([sock],[],[],120.)[0]:raise TimeoutError('FINITE_TASK_OWNER_WARM_JOIN_TIMEOUT')
  try:data=sock.recv(MAX_PACKET)
  except BlockingIOError:return False
  if not data:raise RuntimeError('TASK_OWNER_CLOSED_WITHOUT_RESULT')
  identity,ready=HEADER.unpack(data[:HEADER.size]);assert identity==self.identity,'TASK_RESULT_IDENTITY_MISMATCH'
  self.value=pickle.loads(data[HEADER.size:]);self.finished=True
  collected=time.monotonic_ns()
  ROWS.append(dict(event='COLLECT',identity=identity,worker_pid=self.executor.child.pid,packet_ready_ns=ready,collected_ns=collected,packet_bytes=len(data),model_API_calls=self.value.get('research_model_invocations'),no_partial_message_wait=True))
  if self.warm and self.executor.transport_warm:self.executor.warm_transport()
  if self.value.get('hold_static_mechanics'):ROWS[-1]['hold_static_mechanics']=self.value['hold_static_mechanics']
  if self.value.get('fault_injection'):ROWS[-1]['fault_injection']=self.value['fault_injection']
  for callback in self.callbacks:callback(self)
  return True
 def done(self):return self._receive()
 def result(self,timeout=None):
  if not self.finished:self._receive(blocking=self.warm or self.executor.scientific)
  if not self.finished:raise RuntimeError('TASK_RESULT_NOT_READY_NONBLOCKING')
  return self.value
 def add_done_callback(self,callback):
  if self.finished:callback(self)
  else:self.callbacks.append(callback)
 def cancel(self):return False # Atomic request was sent to the original worker.
 def cancelled(self):return False
class DirectExecutor:
 fast=True
 scientific=False
 fault_config=None
 transport_warm=False
 def __init__(self,max_workers=1,mp_context=None):
  assert max_workers==1
  parent,child=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
  for endpoint in (parent,child):
   endpoint.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,MAX_PACKET*2)
   endpoint.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,MAX_PACKET*2)
  self.sock=parent;self.sock.setblocking(False);self.child=(mp_context or multiprocessing.get_context('spawn')).Process(target=worker,args=(child,self.fast,self.fault_config),name='original-task-direct-ipc')
  self.child.start();child.close();self.current=None;self.sequence=0;self.closed=False;self.warmed=False
  self.transport_warmed=False
 def warm_transport(self):
  assert not self.transport_warmed and self.sequence==0 and self.current is not None and self.current.warm,'TRANSPORT_WARM_ONLY_BEFORE_FIRST_TASK'
  probe=bytes(65536);data=pickle.dumps((0,'WARM_TRANSPORT',probe),protocol=5)
  start=time.monotonic_ns();cpu=time.thread_time_ns()
  assert self.sock.send(data)==len(data),'ATOMIC_WARM_TRANSPORT_SEND'
  sent=time.monotonic_ns();sent_cpu=time.thread_time_ns()
  if not select.select([self.sock],[],[],120.)[0]:raise TimeoutError('FINITE_BIDIRECTIONAL_TRANSPORT_WARM_TIMEOUT')
  raw=self.sock.recv(MAX_PACKET);identity,ready=HEADER.unpack(raw[:HEADER.size]);value=pickle.loads(raw[HEADER.size:])
  assert identity==0 and value['transport_echo']==probe and value['transport_probe_sha256']==hashlib.sha256(probe).hexdigest()
  self.transport_warmed=True
  ROWS.append(dict(event='D2_BIDIRECTIONAL_TRANSPORT_WARM',worker_pid=self.child.pid,start_ns=start,send_finish_ns=sent,finish_ns=time.monotonic_ns(),send_wall_ns=sent-start,send_thread_cpu_ns=sent_cpu-cpu,request_bytes=len(data),response_bytes=len(raw),probe_identity=0,no_TASK_request=True,no_model_API_calls=True,no_live_plant_owner=True,outside_physical_epoch_required=True))
 def submit(self,function,*args):
  assert not self.closed
  if self.fault_config is not None:
   import fault_injection
   fault_injection.verify_task_submission(self,args)
  if self.current is not None and not self.current.done():raise RuntimeError('ONE_OUTSTANDING_ORIGINAL_TASK_REQUEST')
  if not args:
   assert not self.warmed,'TASK_OWNER_PREWARM_ONCE';self.warmed=True;self.current=ReadyFuture(self,0,warm=True);return self.current
  assert len(args)==1 and isinstance(args[0],bytes)
  assert function.__name__ in ('task_with_certificates','_process_task_snapshot')
  self.sequence+=1;begin=time.monotonic_ns();cpu_begin=time.thread_time_ns();gc_enabled=gc.isenabled();gc_counts=gc.get_count()
  data=pickle.dumps((self.sequence,'TASK',args[0]),protocol=5);serialized=time.monotonic_ns();cpu_serialized=time.thread_time_ns()
  if len(data)>MAX_PACKET:raise ValueError('TASK_INPUT_PACKET_LIMIT_EXCEEDED')
  assert self.sock.send(data)==len(data),'ATOMIC_TASK_INPUT_INCOMPLETE'
  sent=time.monotonic_ns();cpu_sent=time.thread_time_ns()
  ROWS.append(dict(event='SUBMIT',identity=self.sequence,start_ns=begin,serialized_ns=serialized,sent_ns=sent,serialize_wall_ns=serialized-begin,send_wall_ns=sent-serialized,serialize_thread_cpu_ns=cpu_serialized-cpu_begin,send_thread_cpu_ns=cpu_sent-cpu_serialized,gc_enabled=gc_enabled,gc_counts=gc_counts,input_bytes=len(args[0]),input_sha256=hashlib.sha256(args[0]).hexdigest(),worker_pid=self.child.pid))
  self.current=ReadyFuture(self,self.sequence);return self.current
 def shutdown(self,wait=True,cancel_futures=True):
  if self.closed:return
  try:
   if self.current is not None and not self.current.finished:self.current._receive(blocking=True)
   self.sock.send(pickle.dumps((0,'STOP',b''),protocol=5));self.child.join(timeout=30.)
   if self.child.is_alive():
    # Exact Process handle created here; no unrelated PID/process is touched.
    self.child.terminate();self.child.join(timeout=10.);raise RuntimeError('OWNED_TASK_OWNER_JOIN_TIMEOUT')
   ROWS.append(dict(event='JOIN',worker_pid=self.child.pid,exitcode=self.child.exitcode,joined=True,host_ns=time.monotonic_ns()))
  finally:self.closed=True;self.sock.close()
def install(fast=True,scientific=False,transport_warm=False):
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 DirectExecutor.fast=bool(fast);DirectExecutor.scientific=bool(scientific);DirectExecutor.transport_warm=bool(transport_warm);op.ProcessPoolExecutor=DirectExecutor
