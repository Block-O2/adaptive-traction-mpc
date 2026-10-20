from pathlib import Path
import sys,pickle,time,json,multiprocessing
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_overnight_v1');sys.path.insert(0,str(S/'code'))
def main():
 import lean_instrumentation;lean_instrumentation.prime()
 import study_common as sc,fast_task_ipc as ipc,fast_task_owner as owner
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 ident='019_N4_V2_C2_science_deviation';rows=pickle.loads((S/'inputs'/(ident+'_TASK_CAUSAL.pkl')).read_bytes());executor=ipc.DirectExecutor(mp_context=multiprocessing.get_context('spawn'));warm=executor.submit(owner.warm).result();checks=[]
 try:
  for row in rows:
   if 'expected' not in row:continue
   future=executor.submit(owner.task_with_certificates,row['payload']);immediate_done=future.done()
   while not future.done():time.sleep(.00025)
   raw=future.result();actual=sc.clean(raw['value']);expected=sc.clean(pickle.loads(row['expected']));actual.pop('runtime_ms');expected.pop('runtime_ms');assert actual==expected
   checks.append(dict(request_id=row['request_id'],phase=row['phase'],complete_packet_only=True,mathematics_bit_exact=True,research_model_invocations=raw['research_model_invocations'],immediate_done=immediate_done))
 finally:executor.shutdown()
 out=dict(status='PASS',no_native_physics=True,live_plant_allowed=False,warm=warm,checks=checks,IPC=ipc.ROWS,model_API_calls=sum(r['research_model_invocations'] for r in checks),source_sha256=sc.sha(S/'code/fast_task_ipc.py'),scope='Local TASK transport and fixed-input numerical equivalence only. Repeated 0.25ms polling is diagnostic, never a host control cadence.')
 sc.save('DIRECT_TASK_D1_LOCAL_REGRESSION.json',out);print(json.dumps({k:v for k,v in out.items() if k!='IPC'}))
if __name__=='__main__':main()
