from pathlib import Path
import sys,json,time,types,socket,multiprocessing,os
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(Path(__file__).resolve().parent))
import fast_task_ipc as ipc
def worker(sock):
 # Exercise the ACTUAL IPC worker's warm branch, without model/plant imports.
 sys.modules['slow_owner']=types.SimpleNamespace(warm=lambda:dict(pid=os.getpid(),ready_ns=time.monotonic_ns(),plant_owner=False))
 sys.modules['lean_instrumentation']=types.SimpleNamespace(prime=lambda:None)
 ipc.worker(sock,False)
def main():
 parent,child=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
 for endpoint in (parent,child):
  endpoint.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,ipc.MAX_PACKET*2);endpoint.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,ipc.MAX_PACKET*2)
 parent.setblocking(False);proc=multiprocessing.get_context('spawn').Process(target=worker,args=(child,));proc.start();child.close()
 owner=object.__new__(ipc.DirectExecutor);owner.sock=parent;owner.child=proc;owner.sequence=0;owner.closed=False;owner.transport_warm=True;owner.transport_warmed=False;owner.scientific=False
 future=ipc.ReadyFuture(owner,0,warm=True);owner.current=future
 try:
  result=future.result();assert result['plant_owner'] is False and future.finished and owner.transport_warmed and owner.sequence==0
  warm=next(r for r in ipc.ROWS if r['event']=='D2_BIDIRECTIONAL_TRANSPORT_WARM');assert warm['request_bytes']>65536 and warm['response_bytes']>65536
  try:owner.warm_transport();raise AssertionError('Repeated startup warm accepted')
  except AssertionError as e:assert 'TRANSPORT_WARM_ONLY_BEFORE_FIRST_TASK' in str(e)
 finally:owner.shutdown()
 assert not proc.is_alive() and proc.exitcode==0
 out=dict(status='PASS',actual_protocol_worker=True,no_mock_socket=True,cases=['actual_packet0_warm_before_TASK','64KiB_exact_bidirectional_echo_and_SHA','single_startup_only','owned_worker_join'],rows=ipc.ROWS,physics_steps=0,model_API_calls=0,no_model_module_imports='traction_mpc_stage4.estimator_v2' not in sys.modules,unix=time.time())
 (S/'output/D2_TRANSPORT_WARM_LOCAL_REGRESSION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='rows'}))
if __name__=='__main__':main()
