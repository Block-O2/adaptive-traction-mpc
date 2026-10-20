"""Every saved native step joined to the command actually held, no replay.

Integrity is separate from realtime qualification: old-command holds and grid
lag remain negative evidence. Uses existing tolerances and original quadrature.
"""
from task_bootstrap import *
from stream_runtime_evidence import array_items
import math,numpy as np,gzip,re
from collections import Counter

def original_wall_physics_elapsed(path):
 with gzip.open(path,'rt') as f:
  buf=''
  while True:
   part=f.read(65536)
   if not part:return None
   buf=buf[-512:]+part;match=re.search(r'"physics_elapsed_s"\s*:\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)',buf)
   if match:return float(match.group(1))

def audit_one(id,result,account,sample):
 folder=STUDY/'source/results'/id;artifact=folder/'runtime_artifacts.json.gz';trace=folder/'trace.npz';issues=[]
 if not artifact.exists():return dict(id=id,status='NO_SAVED_ARTIFACT',worker_status=result.get('status'),recorded_physics_steps=account.get('actual_new_native_steps'),physics_not_replayed=True)
 held=[r for r in array_items(artifact,'command_receipts') if r.get('applied') and r.get('native_steps',0)>0];held.sort(key=lambda r:r['start_physics_s']);counts=Counter();n=0;previous=None;first=None;maximum_dt_error=0.;maximum_torque_error=0.;host_before_write=0;grid_before_write=0;max_grid_lead=0.;max_host_step_ms=0.;total_host_step_ms=0.;first_host=None;last_host=None;nonfinite=0;receipt_source_future=0
 for r in held:
  if r.get('source_capture_ns') is not None and r.get('conservative_activation_ns') is not None and r['source_capture_ns']>r['conservative_activation_ns']:receipt_source_future+=1
 k=0
 for row in array_items(artifact,'native_states_evaluation_only'):
  if n%10000==0:sample()
  t=float(row['time_s']);n+=1
  if first is None:first=t
  if previous is not None:maximum_dt_error=max(maximum_dt_error,abs(t-previous-.00025))
  previous=t
  values=[*row['qpos_evaluation_only'],*row['qvel_evaluation_only'],*row['command_torque_nm']]
  if not all(math.isfinite(v) for v in values):nonfinite+=1
  while k<len(held) and t>held[k]['end_physics_s']+1e-10:k+=1
  if k>=len(held) or t-.00025<held[k]['start_physics_s']-1e-10:
   if 'NATIVE_STEP_WITHOUT_HELD_RECEIPT' not in issues:issues.append('NATIVE_STEP_WITHOUT_HELD_RECEIPT')
   continue
  r=held[k];counts[r['receipt_index']]+=1
  if row['command_torque_nm']!=r['command_torque_nm']:maximum_torque_error=max(maximum_torque_error,max(abs(a-b) for a,b in zip(row['command_torque_nm'],r['command_torque_nm'])))
  hs=row.get('host_step_start_ns');hf=row.get('host_step_finish_ns')
  if hs is not None and hf is not None:
   elapsed=(hf-hs)/1e6;max_host_step_ms=max(max_host_step_ms,elapsed);total_host_step_ms+=elapsed
   if first_host is None:first_host=hs
   last_host=hf
   if r.get('apply_ns') is not None and hs<r['apply_ns']:host_before_write+=1
  if result.get('inputs',{}).get('execution_mode')=='REALTIME_CHARACTERIZATION' and r.get('apply_ns') is not None and r.get('effective_activation_ns') is not None:
   fixed_grid_start=r['effective_activation_ns']+round((t-.00025-r['start_physics_s'])*1e9);lead=r['apply_ns']-fixed_grid_start
   if lead>0:grid_before_write+=1;max_grid_lead=max(max_grid_lead,lead/1e6)
 if maximum_dt_error>1e-10:issues.append('NATIVE_DT_DIFFERENCE')
 if maximum_torque_error>1e-10:issues.append('HELD_TORQUE_DIFFERENCE')
 if nonfinite:issues.append('NONFINITE_PHYSICAL_STATE')
 if host_before_write:issues.append('PHYSICS_STEP_COMPUTED_BEFORE_ITS_ACTUAL_COMMAND_WRITE')
 if receipt_source_future:issues.append('RECEIPT_SOURCE_AFTER_ACTIVATION')
 receipt_count_errors=[dict(receipt_index=r['receipt_index'],declared=r['native_steps'],observed=counts[r['receipt_index']]) for r in held if r['native_steps']!=counts[r['receipt_index']]]
 if receipt_count_errors:issues.append('RECEIPT_NATIVE_STEP_COUNT_DIFFERENCE')
 expected=account.get('actual_new_native_steps')
 wall_elapsed=original_wall_physics_elapsed(artifact);tail=None if expected is None else n-expected
 if expected is not None and n<expected:issues.append('RAW_HAS_FEWER_STEPS_THAN_RECORDED_DIFFERENTIAL_COUNT')
 if wall_elapsed is not None and round(wall_elapsed/.00025)!=n:issues.append('ORIGINAL_WALL_RECORD_STEP_COUNT_DIFFERENCE')
 metric=result.get('metric',{});recomputed={};metric_errors={}
 if trace.exists() and metric.get('J_F') is not None:
  with np.load(trace) as z:
   mask=z['stage']=='TASK';times=z['time_s'][mask];force=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);moment=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1)
   if len(times)>1:
    recomputed=dict(J_F=float(force[:-1]@np.diff(times)),moment_integral=float(moment[:-1]@np.diff(times)),force_peak=float(np.max(force)),moment_peak=float(np.max(moment)),duration_s=float(times[-1]-times[0]));metric_errors={key:abs(value-metric[key]) for key,value in recomputed.items()}
    if any(error>1e-10 for error in metric_errors.values()):issues.append('ORIGINAL_TASK_QUADRATURE_OR_PEAK_DIFFERENCE')
 return dict(id=id,status='PASS' if not issues else 'FAIL',issues=issues,worker_status=result['status'],execution_mode=result.get('inputs',{}).get('execution_mode'),full_task_valid=metric.get('valid',False),artifact_sha256=sha(artifact),native_step_count=n,expected_differential_native_steps=expected,original_wall_record_physics_elapsed_s=wall_elapsed,additional_native_tail_beyond_control_or_partial_snapshot=tail,accounting_note='Last control trace can precede terminal native freeze. Extra native tail is verified by all step states, held-receipt counts and original wall physics_elapsed; original lower-bound ledger is retained.',held_receipt_count=len(held),sum_held_receipt_native_steps=sum(r['native_steps'] for r in held),receipt_count_errors=receipt_count_errors,first_step_end_physics_s=first,last_step_end_physics_s=previous,max_native_dt_abs_error_s=maximum_dt_error,max_held_torque_abs_error_nm=maximum_torque_error,nonfinite_native_steps=nonfinite,computed_steps_before_actual_write=host_before_write,source_future_receipts=receipt_source_future,actual_wall_new_command_steps_on_grid_before_host_write=grid_before_write,actual_wall_max_grid_start_lead_ms=max_grid_lead,host_step_elapsed_ms=dict(n=n,mean=total_host_step_ms/n if n else None,max=max_host_step_ms,first_start_ns=first_host,last_finish_ns=last_host),recomputed_task_metrics=recomputed,task_metric_abs_errors=metric_errors,failed_cost_stays_unranked=not metric.get('valid',False))

def main():
 import runner
 reconciliation=json.loads((STUDY/'reports/AUDIT_COMPUTE_RECONCILIATION.json').read_text());pilot=bool(sys.argv[1:])
 if not pilot:assert not reconciliation['active_ids'],'JOIN_REGISTERED_PHYSICS_FIRST'
 accounts={r['id']:r for r in reconciliation['rows']};ids=sys.argv[1:] if pilot else list(accounts);assert all(id in accounts for id in ids);start=time.time();next_sample=start;rows=[]
 contract=dict(kind='READ_ONLY_COMPLETE_RAW_TRAJECTORY_PROVENANCE',ids=ids,reconciliation_sha256=sha(STUDY/'reports/AUDIT_COMPUTE_RECONCILIATION.json'),max_job_s=3600,native_dt_s=.00025,tolerance=1e-10,physics_added=0,new_model_predictions=0,original_quadrature='norm(force)[:-1] dot diff(TASK time), and same moment quadrature; original phase metric scope retained',inter_rep_scope='Between-repetition settle/hold physics is separately accounted in continuous-session metadata, not included in epoch raw arrays. No cumulative absolute step count is added.')
 save(STUDY/'versions'/('RAW_PHYSICS_PROVENANCE_PILOT_CONTRACT.json' if pilot else 'RAW_PHYSICS_PROVENANCE_CONTRACT.json'),contract)
 def sample():
  nonlocal next_sample
  assert time.time()-start<3600 and time.time()<START+8.25*3600,'READ_ONLY_AUDIT_WALL_BOUND'
  if time.time()>=next_sample:runner.sample(filename='OFFLINE_RESOURCE_LOG.jsonl');next_sample=time.time()+45
 def checkpoint(final=False):
  out=dict(status=('FAIL' if any(r['status']=='FAIL' for r in rows) else ('PASS' if final else 'RUNNING')),contract=contract,rows=rows,attempts_planned=len(ids),attempts_audited=len(rows),native_steps_audited=sum(r.get('native_step_count',0) for r in rows),issues=[r for r in rows if r['status']=='FAIL'],without_saved_artifact=[r['id'] for r in rows if r['status']=='NO_SAVED_ARTIFACT'],wall_seconds=time.time()-start,physics_added=0,actual_host_qualified=False,interpretation='Every recorded native step is checked against the contemporaneously held receipt and actual host write precedes integration; no existing physical state is rewritten. Fixed wall-grid time may lag host write in single-owner catch-up; its extent is reported, not counted as timely deployment. Therefore this provenance PASS is not realtime qualification, and conservative actual activation timestamps remain authoritative. Failed-prefix costs are never ranked.')
  save(STUDY/'reports'/('RAW_PHYSICS_PROVENANCE_PILOT.json' if pilot else 'RAW_PHYSICS_PROVENANCE_AUDIT.json'),out)
 for id in ids:
  sample();result=json.loads((STUDY/'output'/(id+'_RESULT.json')).read_text());row=audit_one(id,result,accounts[id],sample);rows.append(row);checkpoint();print(json.dumps(dict(id=id,status=row['status'],native_steps=row.get('native_step_count'),issues=row.get('issues',[]),audited=len(rows),total=len(ids),elapsed_s=time.time()-start)),flush=True)
 checkpoint(True)
 print(json.dumps(dict(completed=len(rows),native_steps=sum(r.get('native_step_count',0) for r in rows),failed_integrity=len([r for r in rows if r['status']=='FAIL']),without_artifacts=[r['id'] for r in rows if r['status']=='NO_SAVED_ARTIFACT'],physics_added=0)),flush=True)
if __name__=='__main__':main()
