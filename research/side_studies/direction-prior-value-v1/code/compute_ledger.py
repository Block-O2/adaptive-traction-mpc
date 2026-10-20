"""Separate corrected accounting; scientific result files remain immutable."""
from freeze import *
import numpy as np,collections
def main():
 events=[json.loads(line) for line in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];ends={r['id']:r for r in events if r['event']=='END'};rows=[]
 data_by_trace={}
 for p in (STUDY/'output').glob('*_DATA.json'):
  r=json.loads(p.read_text());trace=r.get('metric',{}).get('trace')
  if trace:data_by_trace[Path(trace).parts[-2]]=(r,str(p))
 for start in (r for r in events if r['event']=='START'):
  name=start['id'];end=ends.get(name);result_path=STUDY/'output'/(name+'_RESULT.json');data_path=STUDY/'output'/(name+'_DATA.json');result=json.loads(result_path.read_text()) if result_path.exists() else json.loads(data_path.read_text()) if data_path.exists() else {}
  alias=None
  if not result and name in data_by_trace:result,alias=data_by_trace[name]
  # A pre-repair retry used the original DATA stem while writing its unique
  # retry trace folder. Never assign that trace to both original and retry IDs.
  if 'child' in result and result.get('metric',{}).get('trace') and Path(result['metric']['trace']).parts[-2]!=name:result={}
  metric=result.get('metric',{});trace=STUDY/'source/results'/name/'trace.npz';row=dict(id=name,completed=end is not None,start_unix=start.get('original_started_unix',start['unix']),end_unix=None if end is None else end['unix'],valid=bool(metric.get('valid') and metric.get('matched_eligible') and metric.get('status')=='COMPLETE'),worker_status=result.get('status'),code_manifest_sha256=start.get('code_manifest_sha256',start.get('config',{}).get('code_manifest_sha256')),child_branch='child' in result,main_model_calls=metric.get('actual_new_main_model_inverse_dynamics_api_calls'),native_worker_model_calls=metric.get('actual_new_native_worker_model_inverse_dynamics_api_calls'))
  if alias:row['preserved_retry_DATA_alias']=alias;row['original_END_mapping_mismatch']=end
  row['true_loaded_code_manifest_sha256']=result.get('loaded_code_manifest_sha256',result.get('child',{}).get('loaded_code_manifest_sha256'))
  if not row['true_loaded_code_manifest_sha256'] and 'child' in result:
   group=result['group'];parents=[r for r in events if r['event']=='START' and r.get('config',{}).get('mode') in ('branches','audit') and r.get('config',{}).get('group')==group and r['unix']<=start['unix']]
   if parents:row['true_loaded_code_manifest_sha256']=parents[-1].get('code_manifest_sha256');row['loaded_code_basis']='cold parent dispatch manifest; per-branch current on-disk manifest can differ during logging-only patches'
  if trace.exists():
   with np.load(trace) as z:
    final_steps=int(z['physics_steps'][-1]);final_time=float(z['time_s'][-1]);start_time=0.;basis='native logged physics_steps; full initial run includes commissioning'
    if 'child' in result:
     child=result['child'];start_time=child.get('physical_time_at_fork')
     if start_time is None:
      snapshot=STUDY/'output'/(child['label']+'_SNAPSHOT.json')
      if snapshot.exists():start_time=float(json.loads(snapshot.read_text())['manifest']['task_start_time'])+child['start_task_s'];basis='native logged terminal steps minus fork time reconstructed from saved task origin and causal task time'
     if start_time is None:row['accounting_incomplete']='missing physical fork time';start_time=final_time
    dt=final_time/final_steps if final_steps else .00025;assert abs(dt-.00025)<1e-8,'NATIVE_STEP_CONTRACT_CHANGED'
    row.update(physics_dt_s=.00025,actual_new_simulation_seconds=final_time-start_time,actual_new_native_physics_steps=final_steps-round(start_time/.00025),actual_new_native_control_intervals=round((final_time-start_time)/.005),accounting_basis=basis)
   if 'actual_new_main_model_inverse_dynamics_api_calls' not in metric:
    row['model_count_limitation']='early logging did not separate inherited prefix/counter coverage; unknown is not zero'
   row['wall_seconds_inclusive']=result.get('wall_seconds',None if end is None else end['unix']-start['unix'])
  else:
   row['trace_missing']=True
   error_path=STUDY/'output'/(name+'_BRANCH_ERROR.json')
   partial=json.loads(error_path.read_text()) if error_path.exists() else result
   terminal=partial.get('partial_physical_time_s');fork_time=0.;basis='failure handler recorded physical time; unfinished attempt'
   snapshot_label=start.get('config',{}).get('snapshot')
   if snapshot_label:
    anchors=[r for r,_ in data_by_trace.values() if r.get('child',{}).get('label')==snapshot_label and r['child'].get('physical_time_at_fork') is not None]
    if anchors:fork_time=anchors[0]['child']['physical_time_at_fork'];basis+=' minus exact common saved fork time'
    else:
     saved=STUDY/'output'/(snapshot_label+'_SNAPSHOT.json')
     fork_time=json.loads(saved.read_text())['manifest'].get('task_last_physics_time') if saved.exists() else None
     basis+=' minus causal snapshot task_last_physics_time; reconstructed'
   if terminal is not None and fork_time is not None:
    duration=max(0.,terminal-fork_time);steps=round(duration/.00025)
    assert abs(steps*.00025-duration)<1e-7,'PARTIAL_NATIVE_CLOCK_NOT_GRID_ALIGNED'
    row.update(actual_new_simulation_seconds=steps*.00025,actual_new_native_physics_steps=steps,physics_dt_s=.00025,accounting_basis=basis,partial_work_recovered=True)
   else:row['physics_work_unknown']=True
  rows.append(row)
 resources=[json.loads(line) for line in (STUDY/'output/RESOURCES.jsonl').read_text().splitlines()]
 all_tree_path=STUDY/'output/RESOURCES_ALL_PROCESS_TREES.jsonl'
 if all_tree_path.exists():resources.extend(json.loads(line) for line in all_tree_path.read_text().splitlines())
 resources.sort(key=lambda r:r['unix'])
 summary=dict(physics_attempts=len(rows),ended=sum(r['completed'] for r in rows),actual_new_simulation_seconds=sum(r.get('actual_new_simulation_seconds',0) for r in rows),actual_new_native_physics_steps=sum(r.get('actual_new_native_physics_steps',0) for r in rows),known_main_model_calls=sum(r.get('main_model_calls') or 0 for r in rows),known_native_worker_model_calls=sum(r.get('native_worker_model_calls') or 0 for r in rows),missing_model_count_runs=sum(r.get('main_model_calls') is None for r in rows),elapsed_wall_s=time.time()-1791222386,resource_samples=len(resources),swap_in_delta=resources[-1]['swap_in']-resources[0]['swap_in'],swap_out_delta=resources[-1]['swap_out']-resources[0]['swap_out'],oom_kill_delta=resources[-1]['oom_kill']-resources[0]['oom_kill'],min_windows_available_bytes=min(r['windows'].get('available',float('inf')) for r in resources),peak_owned_PSS_bytes=max(r['PSS'] for r in resources),resource_coverage='Early original runner samples cover physics runner descendants; supplemental observer covers both runner/controller trees from its startup. Brief v1 fit lacks a sampled peak; later fits separately record peak host RSS and CUDA allocations.')
 summary.update(partial_physics_recovered_runs=sum(r.get('partial_work_recovered',False) for r in rows),physics_work_unknown_runs=sum(r.get('physics_work_unknown',False) for r in rows))
 save(STUDY/'COMPUTE_LEDGER.json',dict(summary=summary,rows=rows,correction='Early harness incorrectly divided duration by 0.0005. Frozen native dynamics uses 0.00025; this ledger reads recorded physics_steps and excludes inherited branch prefixes. Original results are preserved.',double_counting='Search predictor counters are subsets of main model API calls; do not add them again. Parent wall includes branch wall; do not sum those inclusive walls.',new_bytes=sum(p.stat().st_size for p in STUDY.rglob('*') if p.is_file())));print(json.dumps(summary))
if __name__=='__main__':main()
