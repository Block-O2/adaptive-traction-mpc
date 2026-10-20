"""One physics owner; fresh native episodes in the same interpreter, all counted."""
from task_bootstrap import *
def run_many(outer):
 import worker,study_common as sc,call_audit,profiling_instrumentation as profile,batched_mechanics,public_worker
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime_coordination_residual_v2 as rt,runtime_sac_expert_v1 as original_rt
 import capture_states,shared_nominal,certified_snapshot,certified_snapshot_v2,mode_metadata
 from accounting import attempts,record
 persists={rt:rt.persist_runtime_artifacts,original_rt:original_rt.persist_runtime_artifacts}
 original_audit=call_audit.install;original_public=public_worker.install;original_metadata=mode_metadata.install;installed=[False,False,False]
 def once_audit():
  if not installed[0]:original_audit();installed[0]=True
 def once_public(r):
  if not installed[1]:original_public(r);installed[1]=True
 def once_metadata():
  if not installed[2]:original_metadata();installed[2]=True
 call_audit.install=once_audit;public_worker.install=once_public
 mode_metadata.install=once_metadata
 rows=[];first_pub=None;first_mode=None
 for j,req in enumerate(outer['consecutive_requests']):
  assert req['id']==outer['id'] if j==0 else req['id']!=outer['id'];assert req['mode']=='select'
  pub=req.get('public_version')
  if first_pub is None:first_pub=pub
  assert pub==first_pub,'CONSECUTIVE_PUBLIC_VERSION_MUST_BE_IDENTICAL'
  if first_mode is None:first_mode=req.get('execution_mode')
  assert req.get('execution_mode')==first_mode,'CONSECUTIVE_EXECUTION_MODE_MUST_BE_IDENTICAL'
  if time.time()>=START+8.25*3600:break
  if j and attempts()>=160:break
  p=STUDY/'inputs'/(req['id']+'.json');save(p,req)
  if j:record('START',req['id'],config=req,input_sha256=sha(p),input_path=str(p),same_process_parent=outer['id'])
  for mod,f in persists.items():mod.persist_runtime_artifacts=f
  profile.EVENTS.clear();call_audit.COUNTS.clear();call_audit.STACKS.clear();batched_mechanics.EVENTS.clear();capture_states.ROWS.clear();shared_nominal.EVENTS.clear();certified_snapshot.EVENTS.clear();certified_snapshot_v2.EVENTS.clear()
  import certified_apply
  certified_apply.EVENTS.clear()
  oldargs=sys.argv;sys.argv=['worker.py',str(p)];started=time.time()
  try:worker.main()
  finally:sys.argv=oldargs
  result=Path(req['result_path']);r=json.loads(result.read_text()) if result.exists() else dict(status='FAILED_NO_RESULT');rows.append(dict(id=req['id'],result=r.get('status'),valid=r.get('metric',{}).get('valid',False),wall_seconds=time.time()-started,pid=__import__('os').getpid(),repetition_index=j,full_native_episode_reinitialized=True,model_or_physical_state_carryover=False))
  if j:record('END',req['id'],status='COMPLETE' if result.exists() else 'FAILED_NO_RESULT',worker_status=r.get('status'),same_process_parent=outer['id'])
  print(json.dumps(dict(consecutive=req['id'],status=r.get('status'),pid=__import__('os').getpid())),flush=True)
 save(STUDY/'output'/(outer['id']+'_CONSECUTIVE_SESSION.json'),dict(rows=rows,same_interpreter=True,native_worker_closed_each_episode=True,single_high_fidelity_owner=True,interpretation='same-process timing robustness; fresh commissioning/reset each episode, not personalized-session adaptation'))
