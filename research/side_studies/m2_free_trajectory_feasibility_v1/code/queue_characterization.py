"""Saved-state native worker transport/competition characterization.

No plant/environment/physics, no command activation and no qualification claim.
All calls use the unmodified native snapshot execution entry point.
"""
from task_bootstrap import *
import pickle,numpy as np,concurrent.futures as cf,multiprocessing as mp
from dataclasses import replace
def warm():
 import study_common
 from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import _warm_planner_process
 return _warm_planner_process()
def execute(payload,version):
 started=time.monotonic_ns();import study_common as sc
 if version=='C2':
  import batched_mechanics
  batched_mechanics.install(dict(public_version='C2',execution_mode='OFFLINE_NO_PHYSICS'))
 from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import execute_task_snapshot
 d=execute_task_snapshot(payload);finished=time.monotonic_ns()
 return dict(started_ns=started,finished_ns=finished,decision_sha256=sc.digest(replace(d,runtime_ms=0.)),decision_record=sc.clean(replace(d,runtime_ms=0.)))
def equivalent(a,b):
 if isinstance(a,dict):return set(a)==set(b) and all(equivalent(a[k],b[k]) for k in a)
 if isinstance(a,list):return isinstance(b,list) and len(a)==len(b) and all(equivalent(x,y) for x,y in zip(a,b))
 if isinstance(a,(int,float)) and not isinstance(a,bool):return isinstance(b,(int,float)) and abs(a-b)<=1e-10
 return a==b
def main():
 import study_common as sc,runner
 from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import execute_task_snapshot
 from causal_timing_report import quantile
 paths=sorted((STUDY/'output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))+sorted((STUDY/'output/STATE_SNAPSHOTS/062_E3T_science_deviation').glob('*.pkl'));assert len(paths)==22
 items=[]
 for p in paths:
  raw=pickle.loads(p.read_bytes());planner,args=pickle.loads(raw['payload']);planner.planner.residual_spec={}
  from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import snapshot_task_call
  t=time.monotonic_ns();payload=snapshot_task_call(planner,args);snapshot_ms=(time.monotonic_ns()-t)/1e6;t=time.monotonic_ns();pair=pickle.loads(payload);decode_ms=(time.monotonic_ns()-t)/1e6
  baseline=execute(payload,'T0');items.append(dict(path=str(p),sha256=sha(p),payload=payload,bytes=len(payload),snapshot_ms=snapshot_ms,decode_ms=decode_ms,decision_sha256=baseline['decision_sha256'],decision_record=baseline['decision_record']))
 selected=[items[k] for k in (0,4,7,11,15,21)];rows=[];sessions=[];start=time.time();next_sample=start
 conditions=[('process','T0',False),('process','C2',False),('process','C2',True),('thread','C2',True)]
 contract=dict(conditions=conditions,cold_sessions_per_condition=4,causal_states_per_session=6,state_selection_indices=[0,4,7,11,15,21],physics_attempts_added=0,contention='Parent re-executes the same current-state original B context while a submitted finite native worker executes. This is bounded duplicated research planner CPU competition, not a MuJoCo wall-clock surrogate.',no_unknown_processes=True,maximum_job_s=600)
 save(STUDY/'versions/O16_QUEUE_CHARACTERIZATION_CONTRACT.json',contract)
 for surface,version,duplicate in conditions:
  for cold in range(4):
   assert time.time()-start<600 and time.time()<START+8.25*3600,'QUEUE_DIAGNOSIS_BOUND'
   created=time.monotonic_ns();executor=cf.ProcessPoolExecutor(max_workers=1,mp_context=mp.get_context('spawn')) if surface=='process' else cf.ThreadPoolExecutor(max_workers=1)
   try:
    ready=executor.submit(warm).result(timeout=90);warm_end=time.monotonic_ns();sessions.append(dict(surface=surface,version=version,duplicate=duplicate,cold=cold+1,prewarm_ms=(warm_end-created)/1e6,worker_ready_ns=ready,prewarm_outside_request_age=True))
    for n,item in enumerate(selected):
     if time.time()>=next_sample:runner.sample(filename='OFFLINE_RESOURCE_LOG.jsonl');next_sample=time.time()+45
     enqueue=time.monotonic_ns();future=executor.submit(execute,item['payload'],version)
     duplicate_ms=0.
     if duplicate:
      t=time.monotonic_ns();execute_task_snapshot(item['payload']);duplicate_ms=(time.monotonic_ns()-t)/1e6
     value=future.result(timeout=60);collected=time.monotonic_ns();same=equivalent(value['decision_record'],item['decision_record']);assert same,'NATIVE_QUEUE_DECISION_CHANGED'
     rows.append(dict(surface=surface,version=version,duplicate_parent_context=duplicate,cold_session=cold+1,snapshot=item['path'],snapshot_sha256=item['sha256'],payload_bytes=item['bytes'],first_request_after_prewarm=n==0,enqueue_ns=enqueue,worker_start_ns=value['started_ns'],worker_finish_ns=value['finished_ns'],collected_ns=collected,queue_ms=(value['started_ns']-enqueue)/1e6,worker_ms=(value['finished_ns']-value['started_ns'])/1e6,finish_to_collect_ms=(collected-value['finished_ns'])/1e6,enqueue_to_collect_ms=(collected-enqueue)/1e6,parent_duplicate_ms=duplicate_ms,decision_exact=same))
   finally:executor.shutdown(wait=True,cancel_futures=True)
   print(json.dumps(dict(condition=[surface,version,duplicate],session=cold+1,completed_requests=len(rows))),flush=True)
 groups={}
 for surface,version,duplicate in conditions:
  for first in (True,False):
   rs=[r for r in rows if (r['surface'],r['version'],r['duplicate_parent_context'],r['first_request_after_prewarm'])==(surface,version,duplicate,first)];key=str((surface,version,duplicate,first));groups[key]={k:quantile([r[k] for r in rs]) for k in ('queue_ms','worker_ms','finish_to_collect_ms','enqueue_to_collect_ms','parent_duplicate_ms')}
 out=dict(status='PASS',contract=contract,rows=rows,sessions=sessions,groups=groups,payload_stats={k:quantile([r[k] for r in items]) for k in ('bytes','snapshot_ms','decode_ms')},wall_seconds=time.time()-start,physics_attempts_added=0,all_original_complete_decisions_within_existing_1e_10=True,interpretation='Offline saved-state timing only. Four independent prewarmed workers per condition. No physical epoch/activation/55ms qualification. Main duplicate work deliberately exposes request collection delay; it is retained as competition evidence, not subtracted from actual observations.')
 save(STUDY/'reports/QUEUE_CHARACTERIZATION.json',out);print(json.dumps({k:out[k] for k in ('status','groups','payload_stats','wall_seconds','physics_attempts_added')}))
if __name__=='__main__':main()
